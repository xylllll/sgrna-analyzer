"""序列提取、去冗余与 FASTA 格式化工具模块

负责:
1. 从 extendedFrags.fastq 提取序列（每4行第2行）
2. 添加 FASTA 格式头
3. 去冗余排序
"""

import logging
import os
import gzip

logger = logging.getLogger(__name__)


def extract_sequences(config):
    """从 FLASH 输出提取序列，并生成 FASTA 和计数文件

    Args:
        config: PipelineConfig 对象

    Returns:
        int: 提取到的序列总数
    """
    logger.info("提取序列并生成 FASTA 文件...")

    fpath = config.extended_frags
    if not os.path.exists(fpath):
        logger.error(f"extendedFrags 文件不存在: {fpath}")
        return 0

    # 检测是否为 gzip 压缩
    is_gzip = fpath.endswith(".gz")
    open_func = gzip.open if is_gzip else open
    read_mode = "rt" if is_gzip else "r"

    # Step 1: 提取每4行中的第2行（序列行）
    seqs = []
    with open_func(fpath, read_mode) as f:
        for i, line in enumerate(f):
            line_num = i + 1  # 1-based
            if line_num % 4 == 2:
                seqs.append(line.strip())

    if not seqs:
        logger.warning("未提取到任何序列")
        return 0

    logger.info(f"提取到 {len(seqs):,} 条序列")

    # Step 2: 写入纯序列文件 merged_seqs.txt
    with open(config.merged_seqs_txt, "w") as f:
        for seq in seqs:
            f.write(seq + "\n")

    # Step 3: 添加 FASTA 头 → merged_seqs.fasta
    with open(config.merged_seqs_fasta, "w") as f:
        for i, seq in enumerate(seqs, start=1):
            f.write(f">read_{i}\n{seq}\n")

    # Step 4: 去冗余并排序 → seq_counts.txt
    seq_count = {}
    for seq in seqs:
        seq_count[seq] = seq_count.get(seq, 0) + 1

    sorted_counts = sorted(seq_count.items(), key=lambda x: x[1], reverse=True)
    with open(config.seq_counts_txt, "w") as f:
        for seq, count in sorted_counts:
            f.write(f"{count}\t{seq}\n")

    logger.info(f"去冗余后 {len(seq_count):,} 条唯一序列")

    return len(seqs)


def extract_reference_ids(config):
    """从参考 FASTA 文件提取所有 sgRNA ID

    Args:
        config: PipelineConfig 对象

    Returns:
        list: sgRNA ID 列表
    """
    logger.info(f"读取参考文件: {config.ref_fasta}")

    if not os.path.exists(config.ref_fasta):
        logger.error(f"参考文件不存在: {config.ref_fasta}")
        return []

    ids = []
    with open(config.ref_fasta, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                # 提取 > 后的 ID（第一个空格前的部分）
                seq_id = line[1:].split()[0]
                ids.append(seq_id)

    # 保存 ID 列表
    with open(config.sgrna_ids_txt, "w") as f:
        for sid in ids:
            f.write(sid + "\n")

    logger.info(f"参考库共 {len(ids):,} 个 sgRNA")
    return ids
