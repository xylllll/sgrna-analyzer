"""统计分析模块

负责计算 sgRNA 文库的覆盖度、均一性和各 sgRNA 丰度。
"""

import logging
import os

logger = logging.getLogger(__name__)


def compute_stats(config, blast_counts, ref_ids):
    """计算 sgRNA 文库覆盖度和均一性

    Args:
        config: PipelineConfig 对象
        blast_counts: dict, {sgRNA_ID: reads_count}
        ref_ids: list, 参考库中所有 sgRNA ID

    Returns:
        dict: 包含 coverage, uniformity, p10, p90, sgRNA列表等
    """
    logger.info("计算 sgRNA 统计信息...")

    total_ref = len(ref_ids)
    covered = len(blast_counts)

    if total_ref == 0:
        logger.error("参考库无 sgRNA 记录")
        return {
            "total_ref": 0,
            "covered": 0,
            "uncovered": 0,
            "coverage": 0.0,
            "uniformity": float("inf"),
            "p10": 0,
            "p90": 0,
            "total_reads": 0,
            "sgRNA_list": [],
        }

    # 覆盖度
    coverage = (covered / total_ref) * 100
    uncovered = total_ref - covered

    # 按 reads 数排序（从小到大）
    sorted_items = sorted(blast_counts.items(), key=lambda x: x[1])
    sgRNA_names = [item[0] for item in sorted_items]
    reads_list = [item[1] for item in sorted_items]

    total_reads = sum(reads_list)

    # 保存 sgRNA_counts.txt
    with open(config.sgrna_counts_txt, "w") as f:
        for name, cnt in zip(sgRNA_names, reads_list):
            f.write(f"{name}\t{cnt}\n")

    # 保存排序后的版本
    with open(config.sgrna_counts_sorted, "w") as f:
        for name, cnt in zip(sgRNA_names, reads_list):
            f.write(f"{name}\t{cnt}\n")

    # 计算 p10 和 p90 (累积 reads 达到 10% 和 90% 时的 sgRNA 排名)
    p10 = 0
    p90 = 0
    cumsum = 0
    for i, r in enumerate(reads_list, start=1):
        cumsum += r
        perc = cumsum / total_reads
        if perc >= 0.1 and p10 == 0:
            p10 = i
        if perc >= 0.9 and p90 == 0:
            p90 = i
            break

    # 均一性 = p90/p10
    uniformity = (p90 / p10) if (p10 and p90) else float("inf")

    logger.info(f"参考库 sgRNA 总数: {total_ref}")
    logger.info(f"检测到 sgRNA 数: {covered}")
    logger.info(f"覆盖度: {coverage:.2f}%")
    logger.info(f"均一性: {uniformity:.2f} (p10={p10}, p90={p90})")
    logger.info(f"总 reads 数: {total_reads:,}")

    return {
        "total_ref": total_ref,
        "covered": covered,
        "uncovered": uncovered,
        "coverage": coverage,
        "uniformity": uniformity,
        "p10": p10,
        "p90": p90,
        "total_reads": total_reads,
        "sgRNA_names": sgRNA_names,
        "sgRNA_reads": reads_list,
    }
