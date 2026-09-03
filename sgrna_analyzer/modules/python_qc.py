"""纯 Python 测序质控模块（替代 fastp）

实现 fastp 的核心质控功能：
1. 3' 端滑动窗口质量修剪（与 fastp -q 算法一致）
2. 最短长度过滤
3. N 碱基比例过滤
4. 生成与 fastp 相同结构的 JSON 输出（兼容下游 plotter/reporter）

优势：纯 Python + numpy，可在 Windows/Linux/macOS 原生运行，
无需安装 fastp，无 WSL 依赖。
"""

import os
import gzip
import json
import logging
import numpy as np

logger = logging.getLogger(__name__)

# 质量修剪滑动窗口大小（与 fastp 默认一致）
TRIM_WINDOW = 4
# N 碱基最大比例（超过则丢弃）
MAX_N_FRACTION = 0.10


# ============================================================
# 质量修剪
# ============================================================

def trim_quality(qual_bytes, threshold, window=TRIM_WINDOW):
    """从 3' 端修剪低质量碱基（fastp 滑动窗口算法）

    窗口内任一碱基质量 < threshold，则从该窗口位置剪到末尾。
    从 3' 端向 5' 端扫描，遇到第一个全高质量窗口即停止。

    Args:
        qual_bytes: 质量字符串（ASCII bytes，Phred+33）
        threshold: 质量阈值（Q 值）
        window: 滑动窗口大小

    Returns:
        int: 修剪后保留的长度
    """
    L = len(qual_bytes)
    if L <= window:
        return L

    q = np.frombuffer(qual_bytes, dtype=np.uint8).astype(np.int16) - 33
    low = (q < threshold).astype(np.uint8)

    # 构建窗口内"是否有低质量碱基"数组
    # win_bad[i] = 位置 i 起 window 个碱基内是否有低质量碱基
    win_len = L - window + 1
    win_bad = np.zeros(win_len, dtype=np.uint8)
    for w in range(window):
        win_bad |= low[w:w + win_len]

    # 从 3' 端找第一个全高质量窗口（win_bad == 0）
    good = (win_bad == 0)
    idx = win_len - 1
    # 从右向左扫描
    while idx >= 0 and not good[idx]:
        idx -= 1

    if idx < 0:
        return 0  # 全部低质量
    return idx + window


# ============================================================
# 统计辅助
# ============================================================

def _update_curves(curves, seq, qual_bytes, counts):
    """累加单条 read 的逐 cycle 质量和碱基含量

    Args:
        curves: {"mean": list, "A": list, "T": list, "C": list, "G": list,
                 "_cnt": list, "A_cnt": list, "T_cnt": list, "C_cnt": list, "G_cnt": list}
        seq: 修剪后的序列
        qual_bytes: 修剪后的质量
        counts: [总碱基计数, Q30 碱基计数]
    """
    L = len(seq)
    n_curves = len(curves["mean"])
    if L > n_curves:
        # 扩展数组
        extend = L - n_curves
        for k in curves:
            curves[k].extend([0] * extend)

    q = np.frombuffer(qual_bytes, dtype=np.uint8).astype(np.int16) - 33
    for i in range(L):
        b = seq[i]
        curves["mean"][i] += int(q[i])
        curves["_cnt"][i] += 1
        if b in ("A", "T", "C", "G"):
            curves[f"{b}_cnt"][i] += 1
        # 统计 Q30
        counts[1] += int(q[i] >= 30)

    counts[0] += L


def _finalize_curves(curves):
    """将累计值转换为平均质量（Q）和碱基占比（0-1）"""
    result = {"A": [], "T": [], "C": [], "G": [], "mean": []}
    n = len(curves["mean"])
    for i in range(n):
        cnt = curves["_cnt"][i]
        if cnt > 0:
            result["mean"].append(round(curves["mean"][i] / cnt, 4))
        else:
            result["mean"].append(0.0)
        for b in ("A", "T", "C", "G"):
            bcnt = curves[f"{b}_cnt"][i]
            result[b].append(round(bcnt / cnt, 6) if cnt > 0 else 0.0)
    return result


# ============================================================
# FASTQ 读取
# ============================================================

def _open_fastq(path):
    """打开 FASTQ 文件（自动识别 gzip）"""
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def _read_fastq_records(fh):
    """从 FASTQ 文件流式读取 (name, seq, qual)，跳过格式不完整记录"""
    while True:
        name = fh.readline()
        if not name:
            break
        seq = fh.readline().rstrip("\n")
        _plus = fh.readline()
        qual = fh.readline().rstrip("\n")
        if len(seq) == len(qual):
            yield name.rstrip("\n"), seq, qual


# ============================================================
# 主入口
# ============================================================

def run_qc(config):
    """执行纯 Python 质控

    Args:
        config: PipelineConfig 对象

    Returns:
        dict: fastp 兼容的质控统计（同 parse_fastp_json 返回结构）
    """
    logger.info("运行纯 Python 质控 (python_qc)...")

    q_threshold = config.fastp_quality_threshold
    min_length = config.fastp_min_length

    # 统计容器（reads 计数用双端 reads 数，即每对算 2 个 read，与 fastp 一致）
    stats = {
        "before_reads": 0, "before_bases": 0,
        "after_reads": 0, "after_bases": 0,
        "passed": 0, "low_quality": 0, "too_short": 0, "too_many_n": 0,
        "before_q30_bases": 0, "after_q30_bases": 0,
        "gc_bases": 0,
    }

    # 逐 cycle 曲线（read1，过滤后）
    curves1 = {"mean": [], "_cnt": [], "A_cnt": [], "T_cnt": [],
               "C_cnt": [], "G_cnt": []}
    curves2 = {"mean": [], "_cnt": [], "A_cnt": [], "T_cnt": [],
               "C_cnt": [], "G_cnt": []}
    after_counts = [0, 0]  # [总碱基, Q30碱基]

    # insert size 近似：保留 reads 的长度直方图
    max_len = 500
    insert_hist = [0] * (max_len + 1)

    try:
        with _open_fastq(config.r1) as f1, _open_fastq(config.r2) as f2:
            it1 = _read_fastq_records(f1)
            it2 = _read_fastq_records(f2)

            out1 = open(config.clean_r1, "w", encoding="utf-8")
            out2 = open(config.clean_r2, "w", encoding="utf-8")

            try:
                for (n1, s1, q1), (n2, s2, q2) in zip(it1, it2):
                    stats["before_reads"] += 2  # 双端 = 2 个 read
                    stats["before_bases"] += len(s1) + len(s2)
                    # 统计原始数据 Q30 碱基（质量字符 >= '?'，即 Q30）
                    stats["before_q30_bases"] += (
                        sum(1 for c in q1 if c >= "?")
                        + sum(1 for c in q2 if c >= "?")
                    )

                    # 质量修剪
                    len1 = trim_quality(q1.encode(), q_threshold)
                    len2 = trim_quality(q2.encode(), q_threshold)

                    # 长度过滤
                    if len1 < min_length or len2 < min_length:
                        stats["too_short"] += 1
                        continue

                    # N 比例过滤
                    s1_t = s1[:len1]
                    s2_t = s2[:len2]
                    n1_frac = s1_t.upper().count("N") / max(len1, 1)
                    n2_frac = s2_t.upper().count("N") / max(len2, 1)
                    if n1_frac > MAX_N_FRACTION or n2_frac > MAX_N_FRACTION:
                        stats["too_many_n"] += 1
                        continue

                    # 质量整体检查（修剪比例过大视为低质量）
                    if len1 < len(s1) * 0.5 or len2 < len(s2) * 0.5:
                        stats["low_quality"] += 1

                    # 写入 clean
                    out1.write(f"{n1}\n{s1_t}\n+\n{q1[:len1]}\n")
                    out2.write(f"{n2}\n{s2_t}\n+\n{q2[:len2]}\n")

                    # 统计
                    stats["after_reads"] += 2  # 双端 = 2 个 read
                    stats["after_bases"] += len1 + len2
                    _update_curves(curves1, s1_t, q1[:len1].encode(), after_counts)
                    _update_curves(curves2, s2_t, q2[:len2].encode(), after_counts)

                    # 统计 GC 碱基（R1 + R2）
                    stats["gc_bases"] += (
                        s1_t.upper().count("G") + s1_t.upper().count("C")
                        + s2_t.upper().count("G") + s2_t.upper().count("C")
                    )

                    # insert size 近似：取保留长度较小者
                    ins = min(len1, len2)
                    if ins <= max_len:
                        insert_hist[ins] += 1
            finally:
                out1.close()
                out2.close()

    except Exception as e:
        logger.error(f"质控失败: {e}")
        raise

    # 计算 summary
    before_q30_rate = stats["before_q30_bases"] / max(stats["before_bases"], 1)
    after_q30_rate = after_counts[1] / max(stats["after_bases"], 1)
    gc_content = stats["gc_bases"] / max(stats["after_bases"], 1)

    # 将曲线拆分为 quality_curves (mean) 和 content_curves (A/T/C/G 占比)
    c1 = _finalize_curves(curves1)
    c2 = _finalize_curves(curves2)
    n1 = len(c1["mean"])

    def _split_curves(c, n):
        return {
            "quality_curves": {"mean": c["mean"]},
            "content_curves": {
                "A": c["A"], "T": c["T"], "C": c["C"], "G": c["G"],
                "N": [0.0] * n, "GC": [round(c["G"][i] + c["C"][i], 6) for i in range(n)],
            },
        }

    # 组装 fastp 兼容 JSON
    fastp_json = {
        "summary": {
            "before_filtering": {
                "total_reads": stats["before_reads"],
                "total_bases": stats["before_bases"],
                "q30_rate": round(before_q30_rate, 4),
                "gc_content": 0.0,
            },
            "after_filtering": {
                "total_reads": stats["after_reads"],
                "total_bases": stats["after_bases"],
                "q30_rate": round(after_q30_rate, 4),
                "gc_content": round(gc_content, 4),
            },
            "filtering_result": {
                "passed_filter_reads": stats["after_reads"],
                "low_quality_reads": stats["low_quality"],
                "too_short_reads": stats["too_short"],
                "too_many_n_reads": stats["too_many_n"],
            },
        },
        "read1_before_filtering": {"total_reads": stats["before_reads"]},
        "read2_before_filtering": {"total_reads": stats["before_reads"]},
        "read1_after_filtering": {
            "total_reads": stats["after_reads"],
            "total_bases": stats["after_bases"],
            **_split_curves(c1, n1),
        },
        "read2_after_filtering": {
            "total_reads": stats["after_reads"],
            "total_bases": stats["after_bases"],
            **_split_curves(c2, n1),
        },
        "insert_size": {
            "peak": int(np.argmax(insert_hist)) if any(insert_hist) else 0,
            "histogram": insert_hist,
        },
        "adapter_cutting": {
            "adapter_trimmed_reads": 0,
            "adapter_trimmed_bases": 0,
        },
    }

    # 写入 JSON 文件
    with open(config.fastp_json, "w", encoding="utf-8") as f:
        json.dump(fastp_json, f)

    logger.info(f"质控完成: 过滤前 {stats['before_reads']:,} reads → 过滤后 {stats['after_reads']:,} reads")
    logger.info(f"  Q30: {after_q30_rate*100:.2f}%  GC: {gc_content*100:.2f}%")
    logger.info(f"  低质量 {stats['low_quality']}，过短 {stats['too_short']}，N过多 {stats['too_many_n']}")

    return fastp_json
