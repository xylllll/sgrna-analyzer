"""报告生成模块

使用 Jinja2 模板引擎生成 HTML 报告，支持图片内嵌和统计表格。
"""

import logging
import os
import base64
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from sgrna_analyzer import __version__

logger = logging.getLogger(__name__)


def _img_to_base64(image_path):
    """将图片文件转换为 base64 data URI

    Args:
        image_path: 图片文件路径

    Returns:
        str: data:image/...;base64,... 格式的 URI，或空字符串
    """
    if not image_path or not os.path.exists(image_path):
        logger.warning(f"图片文件不存在: {image_path}")
        return ""

    # 确定 MIME 类型
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
    }
    mime = mime_map.get(ext, "image/png")

    try:
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{b64_data}"
    except Exception as e:
        logger.error(f"读取图片失败 {image_path}: {e}")
        return ""


def _theoretical_dominance(N):
    """无碱基偏好假设下，N 种 sgRNA 某位置主碱基占比的理论期望 E0(N)。

    数据来源：Multinomial(N; 1/4×4) 模拟（各 N 重复 5000-20000 次）：
    N=8:0.44, 20:0.37, 50:0.32, 100:0.30, 200:0.29, 500:0.27,
    1000:0.27, 5000:0.26, 10000:0.26
    按 N 分段线性插值，N 超大时趋于 0.25。

    Args:
        N: 参考库 sgRNA 数量

    Returns:
        float: 理论主碱基占比期望（0-1）
    """
    if N <= 0:
        return 0.30  # 未知时用保守默认
    table = [(8, 0.44), (20, 0.37), (50, 0.32), (100, 0.30), (200, 0.29),
             (500, 0.27), (1000, 0.27), (5000, 0.26), (10000, 0.26)]
    if N <= table[0][0]:
        return table[0][1]
    if N >= table[-1][0]:
        return 0.25
    for (n1, v1), (n2, v2) in zip(table, table[1:]):
        if n1 <= N <= n2:
            t = (N - n1) / (n2 - n1)
            return v1 + t * (v2 - v1)
    return 0.25


def _compute_assessments(fastp_stats, stats_results):
    """Generate automated assessments for each figure in the report."""

    def grade(condition, good, ok, bad):
        if condition:
            return {"level": "good", "text": good}
        elif bad:
            return {"level": "bad", "text": bad}
        else:
            return {"level": "ok", "text": ok}

    a = {}

    # --- Insert Size ---
    insert_data = fastp_stats.get("insert_size", {})
    peak = insert_data.get("peak", None) if isinstance(insert_data, dict) else None
    histogram = insert_data.get("histogram", []) if isinstance(insert_data, dict) else []

    if peak and 100 <= peak <= 350:
        a["insert_size"] = grade(True, f"主峰位于 {peak}bp，在预期范围 (100-350bp) 内。文库片段长度正常。", "", "")
    elif peak:
        a["insert_size"] = grade(False, "", f"主峰位于 {peak}bp，略偏离典型 sgRNA 文库范围 (100-350bp)。",
                                 f"主峰位于 {peak}bp，远偏离预期范围，文库可能存在非特异性扩增或降解。")
    elif histogram:
        nonzero = [i for i, v in enumerate(histogram) if v > 0]
        if nonzero:
            main_peak = max(range(len(histogram)), key=lambda i: histogram[i])
            a["insert_size"] = grade(100 <= main_peak <= 350,
                                     f"主峰约 {main_peak}bp，在预期范围内。",
                                     f"主峰约 {main_peak}bp，略偏离预期。",
                                     f"主峰约 {main_peak}bp，不符合预期。")
        else:
            a["insert_size"] = {"level": "ok", "text": "有 Insert Size 数据但分布较平坦，无法评估。"}
    else:
        a["insert_size"] = {"level": "ok", "text": "未获取到 Insert Size 峰值数据，无法自动评估。"}

    # --- Base Quality ---
    r1 = fastp_stats.get("read1_after", {})
    qc = r1.get("quality_curves", {}) if isinstance(r1, dict) else {}
    means = qc.get("mean", []) if isinstance(qc, dict) else []

    if means:
        front30 = means[:30]
        avg_q = sum(front30) / len(front30) if front30 else 0
        low_spots = sum(1 for q in means if q < 20)
        a["quality"] = grade(avg_q >= 30 and low_spots == 0,
                             f"前 30bp 平均质量值：{avg_q:.1f}（≥Q30）。所有位点均高于 Q20，测序质量优异。",
                             f"前 30bp 平均质量值：{avg_q:.1f}，质量可接受。",
                             f"前 30bp 平均质量值：{avg_q:.1f}，{low_spots} 个位点低于 Q20，存在质量隐患。")
    else:
        a["quality"] = {"level": "ok", "text": "无逐碱基质量数据，无法自动评估。"}

    # --- Base Content ---
    # 本库测序的是 sgRNA 表达盒：固定区（启动子/scaffold/接头）在所有 reads
    # 中一致，而 20bp sgRNA 区是可变的（文库多样性）。
    # 判定策略：
    #   · 固定区主碱基占比 fixed_dom：硬判定（有测序错误率依据）
    #   · 可变区主碱基占比 var_dom：软判定（风险提示，受碱基偏好/同源性影响）
    cc = r1.get("content_curves", {}) if isinstance(r1, dict) else {}

    if cc and isinstance(cc, dict):
        base_curves = [cc.get(b, []) for b in ("A", "T", "C", "G")]
        if base_curves and all(len(c) > 0 for c in base_curves):
            n = len(base_curves[0])
            # 每个 cycle 的主碱基占比 d_i = max(A_i, T_i, C_i, G_i)
            doms = []
            for i in range(n):
                probs = [curves[i] for curves in base_curves if i < len(curves)]
                if probs:
                    doms.append(max(probs))

            if doms:
                doms = [min(1.0, d) for d in doms]
                # 固定区：主碱基占比 >= 0.9 的位置
                fixed_vals = [d for d in doms if d >= 0.9]
                # 可变区：主碱基占比 < 0.9 的位置
                var_vals = [d for d in doms if d < 0.9]
                var_frac = len(var_vals) / len(doms) if doms else 0

                if fixed_vals:
                    fixed_dom = sum(fixed_vals) / len(fixed_vals) * 100
                else:
                    fixed_dom = 0.0
                var_dom = sum(var_vals) / len(var_vals) if var_vals else 0.0

                # 参考库 sgRNA 数量 N（用于可变区理论期望）
                N = stats_results.get("total_ref", 0)

                # ===== 固定区判定（硬判定）=====
                if fixed_dom > 95:
                    fixed_level, fixed_msg = "good", \
                        f"固定区（启动子/scaffold/接头）主碱基占比 {fixed_dom:.0f}%，高度一致。"
                elif fixed_dom >= 85:
                    fixed_level, fixed_msg = "warn", \
                        f"固定区主碱基占比 {fixed_dom:.0f}%，一致性略有不足，可能有轻微测序误差。"
                else:
                    fixed_level, fixed_msg = "bad", \
                        f"固定区主碱基占比仅 {fixed_dom:.0f}%，固定区碱基不一致，" \
                        f"可能存在文库构建错误或严重污染。"

                # ===== 可变区判定（软判定，仅风险提示）=====
                # 无偏好理论期望 E0(N)，Multinomial 模拟数据查表插值
                E0 = _theoretical_dominance(N)

                if var_dom < 0.20:
                    var_level, var_msg = "warn_strong", \
                        f"可变区主碱基占比仅 {var_dom*100:.0f}%，碱基过于混乱，" \
                        f"存在污染或测序严重错误的风险。"
                elif var_dom > max(0.80, 2.2 * E0):
                    var_level, var_msg = "warn_strong", \
                        f"可变区主碱基占比 {var_dom*100:.0f}%，显著高于随机文库期望" \
                        f"（{N} 种 sgRNA 约 {E0*100:.0f}%），多样性可能显著不足" \
                        f"（若文库无强碱基偏好）。"
                elif var_dom > max(0.70, 1.6 * E0):
                    var_level, var_msg = "warn", \
                        f"可变区主碱基占比 {var_dom*100:.0f}%，高于随机文库期望" \
                        f"（{N} 种 sgRNA 约 {E0*100:.0f}%），多样性可能不足，" \
                        f"或为碱基偏好/序列同源性所致。"
                else:
                    var_level, var_msg = "good", \
                        f"可变区主碱基占比 {var_dom*100:.0f}%，与 {N} 种 sgRNA 的" \
                        f"随机期望（约 {E0*100:.0f}%）相符。"

                # 固定区与可变区分别给出独立评估框
                a["base_content_fixed"] = {"level": fixed_level, "text": fixed_msg}
                a["base_content_var"] = {
                    "level": var_level,
                    "text": var_msg + "（可变区为风险提示，受文库碱基偏好和序列同源性影响，"
                             "非绝对异常判定；建议结合覆盖度与均一性综合评估。）"
                    if var_level in ("warn", "warn_strong") else var_msg,
                }
            else:
                a["base_content_fixed"] = {"level": "ok", "text": "无碱基含量数据，无法自动评估。"}
                a["base_content_var"] = {"level": "ok", "text": "无碱基含量数据，无法自动评估。"}
        else:
            a["base_content_fixed"] = {"level": "ok", "text": "无碱基含量数据，无法自动评估。"}
            a["base_content_var"] = {"level": "ok", "text": "无碱基含量数据，无法自动评估。"}
    else:
        a["base_content_fixed"] = {"level": "ok", "text": "无碱基含量数据，无法自动评估。"}
        a["base_content_var"] = {"level": "ok", "text": "无碱基含量数据，无法自动评估。"}

    # --- Kernel Density ---
    reads = stats_results.get("sgRNA_reads", [])
    if len(reads) > 1:
        import numpy as np
        arr = np.array(reads, dtype=float)
        cv = float(np.std(arr) / np.mean(arr) * 100) if np.mean(arr) > 0 else 100
        a["histogram"] = grade(cv < 100,
                               f"变异系数 CV = {cv:.0f}%。Reads 分布较为集中，均一性良好。",
                               f"变异系数 CV = {cv:.0f}%。Reads 分布中等分散。",
                               f"变异系数 CV = {cv:.0f}%。Reads 高度分散，文库可能存在较强偏好性。")
    else:
        a["histogram"] = {"level": "ok", "text": "数据不足，无法评估 reads 分布。"}

    # --- Cumulative Distribution ---
    uniformity = stats_results.get("uniformity", float("inf"))
    a["cumulative"] = grade(uniformity < 10,
                            f"均一性 (p90/p10) = {uniformity:.1f}。sgRNA 分布均匀，文库质量好。",
                            f"均一性 (p90/p10) = {uniformity:.1f}。存在中等程度偏斜。",
                            f"均一性 (p90/p10) = {uniformity:.1f}。偏斜严重，少数 sgRNA 占主导地位。")

    return a


# ==============================================
# 分析工具信息（含官网链接）
# ==============================================
TOOLS = [
    ("sgRNA Analyzer", "本分析软件", "https://github.com/xylllll/sgrna-analyzer/", "管线编排、统计与报告生成"),
    ("FLASH", "拼接工具", "https://ccb.jhu.edu/software/FLASH/", "双端 Reads 拼接"),
    ("BLAST+ (blastn)", "比对工具", "https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/", "序列比对"),
    ("Python", "编程语言", "https://www.python.org/", "分析管线运行环境"),
    ("matplotlib", "绘图库", "https://matplotlib.org/", "图表生成"),
    ("NumPy", "数值计算库", "https://numpy.org/", "数值计算"),
    ("Jinja2", "模板引擎", "https://jinja.palletsprojects.com/", "HTML 报告渲染"),
]

# ==============================================
# 参考文献
# ==============================================
REFERENCES = [
    "Chen S, Zhou Y, Chen Y, Gu J. fastp: an ultra-fast all-in-one FASTQ preprocessor[J]. Bioinformatics, 2018, 34(17): i884-i890.",
    "Magoč T, Salzberg S L. FLASH: fast length adjustment of short reads to improve genome assemblies[J]. Bioinformatics, 2011, 27(21): 2957-2963.",
    "Camacho C, Coulouris G, Avagyan V, et al. BLAST+: architecture and applications[J]. BMC Bioinformatics, 2009, 10: 421.",
    "Sanjana N E, Shalem O, Zhang F. Refined high-throughput CRISPR screening[J]. Nature Methods, 2014, 11(8): 783-784.",
    "Shalem O, Sanjana N E, Hartenian E, et al. Genome-scale CRISPR-Cas9 knockout screening in human cells[J]. Science, 2014, 343(6166): 84-87.",
    "Hunter J D. Matplotlib: A 2D graphics environment[J]. Computing in Science & Engineering, 2007, 9(3): 90-95.",
    "Harris C R, Millman K J, van der Walt S J, et al. Array programming with NumPy[J]. Nature, 2020, 585(7825): 357-362.",
]

# ==============================================
# 软件信息（作者声明与免责声明）
# ==============================================
SOFTWARE_INFO = {
    "author": "许逸伦",
    "ai_disclaimer": "本软件由 AI 辅助编写，代码经人工审核与验证。",
    "disclaimer": "本报告由软件自动生成，仅供科研与教学目的使用，不构成医疗、临床诊断或治疗建议；"
                  "分析结果未经人工复核，使用者应自行验证并对其用途承担全部责任。",
    "license": "本软件采用 MIT 许可证（Copyright © 2026 许逸伦）。",
}


def get_tool_versions():
    """尝试获取各分析工具的安装版本号（失败时返回 '—'）"""
    import subprocess
    versions = {}

    def run_ver(cmd_list):
        try:
            r = subprocess.run(cmd_list, capture_output=True, text=True, timeout=15)
            first_line = (r.stdout or r.stderr).strip().split("\n")[0]
            return first_line.split()[-1] if first_line else "—"
        except Exception:
            return "—"

    versions["fastp"] = run_ver(["fastp", "--version"])
    versions["flash"] = run_ver(["flash", "--version"])
    versions["blast"] = run_ver(["blastn", "-version"])
    versions["python"] = run_ver(["python", "--version"])
    try:
        import matplotlib, numpy, jinja2
        versions["matplotlib"] = matplotlib.__version__
        versions["numpy"] = numpy.__version__
        versions["jinja2"] = jinja2.__version__
    except Exception:
        pass
    return versions


# ==============================================
# 专业名词术语表（用于报告末尾的名词解释）
# ==============================================
GLOSSARY = [
    ("sgRNA", "小向导RNA (single guide RNA)，由 CRISPR/Cas9 系统中的 crRNA 与 tracrRNA 融合而成，长度约 20nt，负责引导 Cas9 蛋白靶向切割特定 DNA 序列。sgRNA 文库即包含大量不同靶向序列的 sgRNA 集合。"),
    ("FASTQ", "测序数据标准文件格式，每条序列由4行组成：第1行为序列标识符（@开头），第2行为碱基序列，第3行为分隔符（+），第4行为每个碱基对应的质量值字符。"),
    ("Read", "测序读段，指测序仪在一次测序反应中读出的单条 DNA 片段序列。双端测序中，一条 DNA 片段的两端分别产生 Read1 和 Read2。"),
    ("双端测序 (Paired-end)", "从 DNA 片段两端同时测序的技术，产生一对相互配对的 Reads（R1 和 R2），通过两端序列的相互印证可以提高碱基判读准确性，并支持片段长度推断。"),
    ("fastp", "一款快速、全功能的 FASTQ 数据质控工具，可自动完成接头（adapter）去除、低质量碱基修剪、PolyG 去除、质量统计等功能，并输出 HTML/JSON 质控报告。"),
    ("质控 (QC)", "质量控制，指对测序原始数据进行质量评估和过滤处理，去除低质量碱基、接头序列和过短读段，保证下游分析数据质量。"),
    ("质量值 (Q-score)", "用于衡量单个碱基测序准确度的指标，公式为 Q = -10×log10(P)，其中 P 为该碱基判读错误的概率。Q30 表示错误率 1/1000（准确度 99.9%），Q20 表示错误率 1/100（准确度 99%）。"),
    ("Q20 / Q30", "质量值阈值，Q20 对应碱基准确度 99%，Q30 对应 99.9%。Q30 占比是衡量测序质量的核心指标，通常要求 ≥80-85% 以上视为合格。"),
    ("GC 含量", "DNA 序列中鸟嘌呤（G）和胞嘧啶（C）碱基所占的比例。sgRNA 文库测序的是固定表达盒序列，各位置碱基组成确定且不均匀，整体 GC 含量取决于表达盒序列组成，不能套用随机打断 DNA 的\"40-60% 平稳\"标准。"),
    ("Insert Size", "插入片段长度，指文库中真正被测序的 DNA 片段（如 sgRNA 序列加上接头）的总长度。对于 sgRNA 文库，Insert Size 分布应集中在一个较窄范围，峰值应接近预期值。"),
    ("接头 (Adapter)", "连接在 DNA 片段两端的人工合成序列，用于测序仪识别和序列扩增。测序数据中常包含接头序列污染，需要在质控步骤中去除。"),
    ("FLASH", "双端 reads 拼接工具（Fast Length Adjustment of SHort reads），利用双端序列的重叠区域（overlap）将 R1 和 R2 拼接为完整的单条序列，适用于 insert 长度较短的文库。"),
    ("拼接率 (Percent combined)", "双端 reads 成功拼接的比例，FLASH 拼接后得到 extendedFrags（延伸片段）。拼接率越高说明文库片段长度与读长匹配越好，通常应 ≥90%。"),
    ("去冗余 (Deduplication)", "将完全相同的序列合并为一条并统计其出现次数（reads 数）的过程。由于 PCR 扩增会产生大量相同序列，去冗余后可以得到每个唯一序列的实际丰度。"),
    ("BLAST", "基本局部比对搜索工具（Basic Local Alignment Search Tool），用于将查询序列与参考数据库进行序列比对，找到相似的序列。本流程使用 blastn 将测序序列比对到参考 sgRNA 库。"),
    ("makeblastdb", "BLAST+ 软件包中的数据库构建工具，将 FASTA 格式的参考序列文件转换为 BLAST 可检索的数据库格式。"),
    ("blastn", "BLAST+ 中用于核苷酸序列比对的程序，blastn-short 任务模式针对短序列（如 sgRNA 20bp）进行了优化。"),
    ("比对一致性 (Identity)", "比对中完全匹配碱基数占总比对长度的百分比。本流程要求 identity=100%（完全匹配）且比对长度=20bp（完整 sgRNA 长度），以确保 reads 准确比对到参考 sgRNA。"),
    ("参考库 (Reference Library)", "包含所有已知 sgRNA 序列及其 ID 的 FASTA 文件，是判断测序序列归属的标准数据库。"),
    ("覆盖度 (Coverage)", "文库中被检测到的 sgRNA 种类数占参考库全部 sgRNA 种类的百分比。覆盖度 ≥95% 说明文库完整，接近 100% 为理想状态。"),
    ("未覆盖数", "参考库中未被检测到的 sgRNA 数量，即测序深度不足或文库缺失的部分。"),
    ("均一性 (Uniformity)", "衡量文库中各 sgRNA 丰度分布均匀程度的指标，定义为 p90/p10 的比值。比值越小表示分布越均匀，通常 <10 为合格。"),
    ("p10 / p90", "将 sgRNA 按 reads 数从小到大排序后，累计 reads 达到总 reads 的 10% 和 90% 时对应的 sgRNA 排名序号。p90/p10 比值越小，文库均一性越好。"),
    ("核密度图 (Kernel Density Plot)", "一种估计连续概率密度分布的统计图表，通过核函数平滑每个数据点来估计分布形状。用于直观展示 sgRNA 丰度（reads 数）的整体分布特征。"),
    ("累积分布图 (ECDF)", "经验累积分布函数图，展示数据中小于等于某个值的观测所占的比例。横轴为 reads 数（对数刻度），纵轴为累积比例，曲线越陡峭说明丰度分布越集中。"),
    ("变异系数 (CV)", "标准差与平均值的比值（CV = σ/μ × 100%），用于衡量数据的离散程度。CV 越小说明各 sgRNA 丰度越接近，文库越均匀。"),
    ("Clean Data", "经过质控过滤后的有效测序数据，即去除低质量碱基、接头和短序列后的数据，是下游分析（拼接、比对）的输入。"),
    ("文库 (Library)", "通过建库流程制备的、包含大量不同 DNA 片段的混合样本，sgRNA 文库即包含成千上万种不同 sgRNA 序列的集合。"),
    ("丰度 (Abundance)", "某个 sgRNA 在测序结果中的相对含量，以其 reads 数或占总 reads 的百分比表示。"),
    ("PCR 扩增偏差", "PCR 扩增过程中由于片段 GC 含量、长度等差异导致的扩增效率不均一现象，会造成文库中部分 sgRNA 的 reads 数被人为放大或减少。"),
]


def generate_report(config, fastp_stats, flash_stats, stats_results, plot_paths):
    """生成最终的 HTML 报告

    Args:
        config: PipelineConfig 对象
        fastp_stats: fastp 质控统计字典
        flash_stats: FLASH 拼接统计字典
        stats_results: 覆盖度/均一性统计字典（来自 stats.compute_stats）
        plot_paths: 图表路径字典（来自 plotter.generate_all_plots）

    Returns:
        str: 生成的 HTML 报告路径
    """
    logger.info("生成 HTML 报告...")

    # 加载 Jinja2 模板
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("report.html")

    # 转换所有图片为 base64
    images_b64 = {}
    for key, path in plot_paths.items():
        images_b64[key] = _img_to_base64(path)

    # 构建 sgRNA 表格数据（所有sgRNA）
    sgrna_names = stats_results.get("sgRNA_names", [])
    sgrna_reads = stats_results.get("sgRNA_reads", [])
    total_reads = stats_results.get("total_reads", 1)

    sgrna_table = []
    for i, (name, reads) in enumerate(zip(sgrna_names, sgrna_reads), start=1):
        pct = reads / total_reads * 100 if total_reads else 0
        sgrna_table.append({
            "rank": i,
            "name": name,
            "reads": reads,
            "pct": pct,
        })

    # 按 reads 降序排列
    sgrna_table.sort(key=lambda x: x["reads"], reverse=True)
    for i, item in enumerate(sgrna_table, start=1):
        item["rank"] = i

    # ---- Generate assessments for each figure ----
    assessments = _compute_assessments(fastp_stats, stats_results)

    # ---- Tool versions ----
    tool_versions = get_tool_versions()

    # 将版本号合并到工具列表中: (name, version, url, desc)
    _version_map = {
        "fastp": tool_versions.get("fastp", "—"),
        "FLASH": tool_versions.get("flash", "—"),
        "blast": tool_versions.get("blast", "—"),
        "python": tool_versions.get("python", "—"),
        "matplotlib": tool_versions.get("matplotlib", "—"),
        "numpy": tool_versions.get("numpy", "—"),
        "jinja2": tool_versions.get("jinja2", "—"),
        "sgrna": "v" + __version__,
    }
    tools_with_versions = [
        (name, _version_map.get(name.lower().split(" ")[0].split("(")[0].split("+")[0], "—"),
         url, desc)
        for name, _, url, desc in TOOLS
    ]

    # 构建渲染上下文
    ctx = {
        "sample_name": config.sample_name,
        "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fastp": {
            "before_reads": fastp_stats.get("before_reads", 0),
            "before_bases": fastp_stats.get("before_bases", 0),
            "before_q30": fastp_stats.get("before_q30", 0),
            "before_gc": fastp_stats.get("before_gc", 0),
            "after_reads": fastp_stats.get("after_reads", 0),
            "after_bases": fastp_stats.get("after_bases", 0),
            "after_q30": fastp_stats.get("after_q30", 0),
            "after_gc": fastp_stats.get("after_gc", 0),
        },
        "flash_stats": flash_stats or {},
        "stats": {
            "total_ref": stats_results.get("total_ref", 0),
            "covered": stats_results.get("covered", 0),
            "uncovered": stats_results.get("uncovered", 0),
            "coverage": stats_results.get("coverage", 0),
            "uniformity": stats_results.get("uniformity", float("inf")),
            "p10": stats_results.get("p10", 0),
            "p90": stats_results.get("p90", 0),
            "total_reads": total_reads,
        },
        "images": {
            "insert_size": images_b64.get("insert_size", ""),
            "quality": images_b64.get("quality", ""),
            "base_content": images_b64.get("base_content", ""),
            "histogram": images_b64.get("histogram", ""),
            "cumulative": images_b64.get("cumulative", ""),
        },
        "sgrna_table": sgrna_table,
        "assessments": assessments,
        "glossary": GLOSSARY,
        "tools": tools_with_versions,
        "references": REFERENCES,
        "software": SOFTWARE_INFO,
    }

    # 渲染
    html_output = template.render(**ctx)

    # 写入文件
    with open(config.report_html, "w", encoding="utf-8") as f:
        f.write(html_output)

    logger.info(f"✅ 报告已生成: {config.report_html}")

    return config.report_html
