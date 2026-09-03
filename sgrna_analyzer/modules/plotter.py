"""绘图模块 - 使用 matplotlib 生成所有图表

替代原文档中的 R 脚本，生成:
1. Insert Size 分布图
2. 碱基质量分布图
3. 碱基含量分布图
4. sgRNA 核密度图
5. sgRNA 累积分布图

所有图表内嵌中文支持。
"""

import logging
import os
import numpy as np

logger = logging.getLogger(__name__)


def gaussian_kde_np(data, x):
    """一维高斯核密度估计（numpy 实现，替代 scipy.stats.gaussian_kde）

    使用 Scott's rule 带宽: h = n^(-1/5) * σ（与 scipy 默认一致）

    Args:
        data: 样本数据 (1D array)
        x: 需要计算密度值的位置 (1D array)

    Returns:
        array: 各 x 位置的核密度估计值
    """
    data = np.asarray(data, dtype=float).ravel()
    x = np.asarray(x, dtype=float).ravel()

    n = len(data)
    if n == 0:
        return np.zeros_like(x)

    std = np.std(data, ddof=1)
    if std == 0:
        std = 1e-6
    h = n ** (-1.0 / 5.0) * std

    # 高斯核: f(x) = (1/n) * Σ φ((x - xi) / h) / h
    x_col = x[:, None]
    data_row = data[None, :]
    diff = (x_col - data_row) / h
    density = np.exp(-0.5 * diff ** 2) / (h * np.sqrt(2 * np.pi))
    return density.mean(axis=1)

# 延迟导入 matplotlib，以便在没有 GUI 的环境中使用非交互式后端
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ========== 中文字体配置 ==========

def _setup_chinese_font():
    """配置 matplotlib 中文字体

    依次尝试以下字体:
    1. WenQuanYi Micro Hei (文泉驿微米黑)
    2. WenQuanYi Zen Hei (文泉驿正黑)
    3. SimHei (黑体, Windows)
    4. Microsoft YaHei (微软雅黑, Windows)
    5. Noto Sans CJK
    6. sans-serif (回退)
    """
    preferred_fonts = [
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
        "SimHei",
        "Microsoft YaHei",
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]

    available_fonts = {f.name for f in fm.fontManager.ttflist}
    selected = None

    for font_name in preferred_fonts:
        if font_name in available_fonts:
            selected = font_name
            break

    if selected:
        plt.rcParams["font.family"] = selected
        logger.info(f"使用字体: {selected}")
    else:
        plt.rcParams["font.family"] = "sans-serif"
        logger.warning("未找到中文字体，图表中的中文可能显示为方块。")
        logger.warning("Linux: sudo apt install fonts-wqy-microhei")
        logger.warning("macOS: 系统自带中文字体")
        logger.warning("Windows: 系统自带中文字体")

    plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题


# 模块导入时初始化字体
_setup_chinese_font()


# ========== 图表样式常量 ==========

FIG_DPI = 150
INSERT_SIZE_FIGSIZE = (12, 5)
QUALITY_FIGSIZE = (10, 5)
DIST_FIGSIZE = (8, 6)


def _save_figure(fig, path):
    """保存图表到文件"""
    fig.savefig(path, dpi=FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"图表已保存: {path}")


# ========== 1. Insert Size 分布图 ==========

def plot_insert_size(fastp_stats, output_path, sample_name="sample"):
    """Plot Insert Size distribution from fastp JSON data."""
    logger.info("Plotting Insert Size distribution...")

    insert_data = fastp_stats.get("insert_size", {})
    histogram = insert_data.get("histogram", []) if isinstance(insert_data, dict) else []
    peak = insert_data.get("peak", None) if isinstance(insert_data, dict) else None

    fig, ax = plt.subplots(figsize=INSERT_SIZE_FIGSIZE)

    if histogram and len(histogram) > 0:
        sizes = list(range(len(histogram)))
        total = sum(histogram)
        if total > 0:
            percentages = [c / total * 100 for c in histogram]
            ax.fill_between(sizes, percentages, alpha=0.3, color="#3498db")
            ax.plot(sizes, percentages, color="#3498db", linewidth=1.5)
        if peak:
            ax.axvline(x=peak, color="#e74c3c", linestyle="--",
                       linewidth=1.5, label=f"Peak: {peak}bp")
            ax.legend()
    else:
        ax.text(0.5, 0.5, "No insert size distribution data\nPlease check fastp JSON output",
                transform=ax.transAxes, ha="center", va="center", fontsize=14, color="#999")
        logger.warning("Insert size histogram is empty")

    ax.set_xlabel("Fragment Length (bp)", fontsize=12)
    ax.set_ylabel("Fraction (%)", fontsize=12)
    ax.set_title(f"{sample_name} - Insert Size Distribution", fontsize=14, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    _save_figure(fig, output_path)


# ========== 2. 碱基质量分布图 ==========

def plot_quality_curves(fastp_stats, output_path, sample_name="sample"):
    """Plot base quality distribution from fastp JSON."""
    logger.info("Plotting base quality distribution...")

    fig, ax = plt.subplots(figsize=QUALITY_FIGSIZE)
    plotted = False

    # Data is in read1_after.quality_curves
    for rkey, rlabel in [("read1_after", "Read 1 (forward)"),
                          ("read2_after", "Read 2 (reverse)")]:
        rdata = fastp_stats.get(rkey, {})
        if not isinstance(rdata, dict):
            continue
        qc = rdata.get("quality_curves", {})
        if not isinstance(qc, dict):
            continue
        means = qc.get("mean", [])
        if isinstance(means, list) and len(means) > 0:
            cycles = list(range(1, len(means) + 1))
            ax.plot(cycles, means, linewidth=1.2, label=rlabel, alpha=0.8)
            plotted = True

    if plotted:
        ax.axhline(y=30, color="#e74c3c", linestyle="--", linewidth=1,
                   alpha=0.6, label="Q30")
        ax.legend(loc="lower left")
    else:
        ax.text(0.5, 0.5, "No base quality data\nPlease check fastp JSON output",
                transform=ax.transAxes, ha="center", va="center", fontsize=14, color="#999")
        logger.warning("Quality curve data is empty")

    ax.set_xlabel("Position (bp)", fontsize=12)
    ax.set_ylabel("Quality Score", fontsize=12)
    ax.set_title(f"{sample_name} - Base Quality (after filtering)", fontsize=14, fontweight="bold")
    ax.grid(alpha=0.3)
    _save_figure(fig, output_path)


# ========== 3. 碱基含量分布图 ==========

def plot_base_content(fastp_stats, output_path, sample_name="sample"):
    """Plot base content distribution from fastp JSON."""
    logger.info("Plotting base content distribution...")

    fig, ax = plt.subplots(figsize=QUALITY_FIGSIZE)

    # Data is in read1_after.content_curves
    rdata = fastp_stats.get("read1_after", {})
    if not isinstance(rdata, dict):
        rdata = {}
    content_data = rdata.get("content_curves", {})

    bases = ["A", "T", "C", "G", "N"]
    colors = {"A": "#e74c3c", "T": "#3498db", "C": "#2ecc71",
              "G": "#f39c12", "N": "#95a5a6"}

    plotted = False
    for base in bases:
        base_data = content_data.get(base, [])
        if isinstance(base_data, list) and len(base_data) > 0:
            cycles = list(range(1, len(base_data) + 1))
            # Scale from fraction (0-1) to percentage (0-100)
            ax.plot(cycles, [v * 100 for v in base_data], linewidth=1,
                    color=colors[base], label=base, alpha=0.8)
            plotted = True

    if plotted:
        ax.legend(loc="center right", ncol=1)
    else:
        ax.text(0.5, 0.5, "No base content data\nPlease check fastp JSON output",
                transform=ax.transAxes, ha="center", va="center", fontsize=14, color="#999")
        logger.warning("Base content data is empty")

    ax.set_xlabel("Position (bp)", fontsize=12)
    ax.set_ylabel("Base Fraction (%)", fontsize=12)
    ax.set_title(f"{sample_name} - Base Content (after filtering)", fontsize=14, fontweight="bold")
    ax.grid(alpha=0.3)
    _save_figure(fig, output_path)


# ========== 4. sgRNA 核密度图 ==========

def plot_kernel_density(sgRNA_reads, output_path, sample_name="sample"):
    """绘制 sgRNA 丰度核密度图

    横轴: Reads 数
    纵轴: 概率密度

    Args:
        sgRNA_reads: reads 数列表
        output_path: 输出路径
        sample_name: 样品名
    """
    logger.info(f"绘制 sgRNA 核密度图 (n={len(sgRNA_reads)})...")

    if len(sgRNA_reads) < 2:
        logger.warning("sgRNA 数据不足（<2），跳过核密度图")
        return

    fig, ax = plt.subplots(figsize=DIST_FIGSIZE)

    reads_array = np.array(sgRNA_reads, dtype=float)

    # 使用 scipy 的 gaussian_kde
    try:
        # 对于有大量相同值的数据，添加微小噪声以避免带宽选择问题
        if len(np.unique(reads_array)) < 5:
            jitter = np.random.normal(0, 0.01, size=len(reads_array))
            kde_data = reads_array + jitter
        else:
            kde_data = reads_array

        # 生成 x 轴范围
        x_min = max(0, reads_array.min() * 0.8)
        x_max = reads_array.max() * 1.1
        if x_max <= x_min:
            x_max = x_min + 10

        x_range = np.linspace(x_min, x_max, 500)
        density = gaussian_kde_np(kde_data, x_range)

        ax.fill_between(x_range, density, alpha=0.3, color="#3498db")
        ax.plot(x_range, density, color="#3498db", linewidth=1.5)

        # 标记均值
        mean_reads = reads_array.mean()
        ax.axvline(x=mean_reads, color="#e74c3c", linestyle="--",
                   linewidth=1.2, alpha=0.8,
                   label=f"均值: {mean_reads:.1f}")
        ax.legend()

    except Exception as e:
        logger.warning(f"核密度估计失败: {e}，改用直方图")
        ax.hist(reads_array, bins=min(50, len(np.unique(reads_array))),
                density=True, alpha=0.6, color="#3498db", edgecolor="white")

    ax.set_xlabel("Reads 数", fontsize=12)
    ax.set_ylabel("概率密度", fontsize=12)
    ax.set_title(f"{sample_name} - sgRNA 核密度图", fontsize=14, fontweight="bold")
    ax.grid(alpha=0.3)

    _save_figure(fig, output_path)


# ========== 5. sgRNA 累积分布图 ==========

def plot_cumulative_distribution(sgRNA_reads, output_path, sample_name="sample"):
    """绘制 sgRNA 累积分布图

    横轴: Reads 数 (log10)
    纵轴: 累积比例

    Args:
        sgRNA_reads: 已排序的 reads 数列表（从小到大）
        output_path: 输出路径
        sample_name: 样品名
    """
    logger.info(f"绘制 sgRNA 累积分布图 (n={len(sgRNA_reads)})...")

    if len(sgRNA_reads) < 2:
        logger.warning("sgRNA 数据不足（<2），跳过累积分布图")
        return

    fig, ax = plt.subplots(figsize=DIST_FIGSIZE)

    sorted_reads = np.array(sorted(sgRNA_reads), dtype=float)

    # 过滤掉 0 值（log(0) 无意义）
    valid = sorted_reads[sorted_reads > 0]
    if len(valid) < 2:
        logger.warning("有效 reads 数据不足，跳过累积分布图")
        plt.close(fig)
        return

    # 计算 ECDF
    n = len(valid)
    y = np.arange(1, n + 1) / n

    ax.step(valid, y, where="post", color="#2ecc71", linewidth=1.5)
    ax.set_xscale("log")

    # 标记 p10 和 p90
    p10_idx = int(np.ceil(n * 0.1)) - 1
    p90_idx = int(np.ceil(n * 0.9)) - 1
    p10_idx = max(0, min(p10_idx, n - 1))
    p90_idx = max(0, min(p90_idx, n - 1))

    ax.axvline(x=valid[p10_idx], color="#3498db", linestyle="--",
               linewidth=1, alpha=0.7, label=f"p10={valid[p10_idx]:.0f}")
    ax.axvline(x=valid[p90_idx], color="#e74c3c", linestyle="--",
               linewidth=1, alpha=0.7, label=f"p90={valid[p90_idx]:.0f}")
    ax.axhline(y=0.1, color="#3498db", linestyle=":", linewidth=0.8, alpha=0.5)
    ax.axhline(y=0.9, color="#e74c3c", linestyle=":", linewidth=0.8, alpha=0.5)
    ax.legend()

    ax.set_xlabel("Reads 数 (log10)", fontsize=12)
    ax.set_ylabel("累积比例", fontsize=12)
    ax.set_title(f"{sample_name} - sgRNA 累积分布图", fontsize=14, fontweight="bold")
    ax.grid(alpha=0.3)

    _save_figure(fig, output_path)


# ========== 批量生成 ==========

def generate_all_plots(config, fastp_stats, sgRNA_reads):
    """生成所有图表

    Args:
        config: PipelineConfig 对象
        fastp_stats: fastp JSON 统计数据
        sgRNA_reads: sgRNA reads 数列表

    Returns:
        dict: 各图表文件路径
    """
    os.makedirs(config.figures_dir, exist_ok=True)

    sample = config.sample_name

    plot_insert_size(fastp_stats, config.insert_size_png, sample)
    plot_quality_curves(fastp_stats, config.cycleq_png, sample)
    plot_base_content(fastp_stats, config.base_content_png, sample)
    plot_kernel_density(sgRNA_reads, config.histogram_png, sample)
    plot_cumulative_distribution(sgRNA_reads, config.cumulative_png, sample)

    return {
        "insert_size": config.insert_size_png,
        "quality": config.cycleq_png,
        "base_content": config.base_content_png,
        "histogram": config.histogram_png,
        "cumulative": config.cumulative_png,
    }
