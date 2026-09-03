"""质控运行模块 — 纯 Python 实现（替代 fastp）

2.0 版本使用 python_qc 模块完成质控，无需安装 fastp，
可在 Windows / Linux / macOS 原生运行。
"""

import os
import json
import logging

from . import python_qc

logger = logging.getLogger(__name__)


def check_fastp():
    """纯 Python 质控始终可用"""
    return True


def run_fastp(config):
    """运行质控

    Args:
        config: PipelineConfig 对象

    Returns:
        dict: 包含质控统计信息的字典（同 fastp 解析结构）
    """
    if config.skip_fastp and os.path.exists(config.fastp_json):
        logger.info("跳过质控（--skip-fastp 且 JSON 文件已存在）")
        return parse_fastp_json(config.fastp_json)

    # 调用纯 Python 质控
    python_qc.run_qc(config)

    # 解析生成的 JSON 获取统一统计结构
    return parse_fastp_json(config.fastp_json)


def parse_fastp_json(json_path):
    """解析质控 JSON 输出，提取关键统计信息"""
    with open(json_path, "r") as f:
        data = json.load(f)

    summary = data.get("summary", {})

    def _safe_get(d, key, default=0):
        return d.get(key, default)

    # 过滤前统计
    before = summary.get("before_filtering", {})
    before_reads = _safe_get(before, "total_reads")
    before_bases = _safe_get(before, "total_bases")
    before_q30 = _safe_get(before, "q30_rate", 0.0)
    before_gc = _safe_get(before, "gc_content", 0.0)

    # 过滤后统计
    after = summary.get("after_filtering", {})
    after_reads = _safe_get(after, "total_reads")
    after_bases = _safe_get(after, "total_bases")
    after_q30 = _safe_get(after, "q30_rate", 0.0)
    after_gc = _safe_get(after, "gc_content", 0.0)

    # 过滤统计
    filtering = summary.get("filtering_result", {})
    passed_reads = _safe_get(filtering, "passed_filter_reads")
    low_quality = _safe_get(filtering, "low_quality_reads")
    too_short = _safe_get(filtering, "too_short_reads")
    too_many_n = _safe_get(filtering, "too_many_n_reads")

    # Insert size 分布（用于绘图）
    insert_size = data.get("insert_size", {})

    # Read 质量分布（用于碱基质量图和碱基含量图）
    read1_before = data.get("read1_before", data.get("read1_before_filtering", {}))
    read1_after = data.get("read1_after", data.get("read1_after_filtering", {}))
    read2_before = data.get("read2_before", data.get("read2_before_filtering", {}))
    read2_after = data.get("read2_after", data.get("read2_after_filtering", {}))

    # 碱基质量曲线（每个cycle的质量值）
    quality_curves = data.get("quality_curves", {})
    content_curves = data.get("content_curves", {})

    stats = {
        "before_reads": before_reads,
        "before_bases": before_bases,
        "before_q30": before_q30 * 100 if before_q30 else 0.0,
        "before_gc": before_gc * 100 if before_gc else 0.0,
        "after_reads": after_reads,
        "after_bases": after_bases,
        "after_q30": after_q30 * 100 if after_q30 else 0.0,
        "after_gc": after_gc * 100 if after_gc else 0.0,
        "passed_reads": passed_reads,
        "low_quality_reads": low_quality,
        "too_short_reads": too_short,
        "too_many_n_reads": too_many_n,
        "insert_size": insert_size,
        "read1_before": read1_before,
        "read1_after": read1_after,
        "read2_before": read2_before,
        "read2_after": read2_after,
        "quality_curves": quality_curves,
        "content_curves": content_curves,
    }

    logger.info(f"质控统计: 过滤前 {before_reads:,} reads → 过滤后 {after_reads:,} reads")
    logger.info(f"  Q30: {stats['before_q30']:.2f}% → {stats['after_q30']:.2f}%")
    logger.info(f"  GC: {stats['before_gc']:.2f}% → {stats['after_gc']:.2f}%")

    return stats
