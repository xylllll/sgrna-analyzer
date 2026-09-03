"""BLAST 数据库构建与比对运行模块

负责:
1. makeblastdb - 构建 BLAST 核苷酸数据库
2. blastn - 短序列比对
3. 解析 BLAST 结果
"""

import subprocess
import logging
import os
import shutil
import tempfile

from .. import bundled_tools

logger = logging.getLogger(__name__)

# BLAST 可执行文件（优先捆绑版，其次 PATH）
MAKEBLASTDB_EXE = bundled_tools.find_tool("makeblastdb")
BLASTN_EXE = bundled_tools.find_tool("blastn")

# BDB v4 数据库文件扩展名（makeblastdb -blastdb_version 4 生成）
_BDB_EXTS = [".nhr", ".nin", ".nsq", ".nsi", ".nsd", ".nog"]


def check_blast():
    """检查 BLAST+ 工具是否可用"""
    for tool in [MAKEBLASTDB_EXE, BLASTN_EXE]:
        try:
            subprocess.run(
                [tool, "-version"],
                capture_output=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    return True


def build_blast_db(config):
    """构建 BLAST 核苷酸数据库

    Args:
        config: PipelineConfig 对象

    Returns:
        str: BLAST 数据库路径前缀
    """
    if config.skip_blast and os.path.exists(f"{config.blast_db}.nhr"):
        logger.info("跳过 BLAST 数据库构建（--skip-blast 且数据库文件已存在）")
        return config.blast_db

    logger.info("构建 BLAST 数据库...")

    # 确保 ref 目录存在
    ref_dir = os.path.join(config.outdir, "ref")
    os.makedirs(ref_dir, exist_ok=True)

    db_name = os.path.basename(config.blast_db)  # 如 "sgRNA_db"

    # BLAST 工具不支持含空格/中文的 cwd，改用临时目录（无空格）建库，
    # 完成后用 Python 把数据库文件复制回 ref 目录
    work_dir = tempfile.mkdtemp(prefix="sgrna_db_")
    try:
        # 复制参考文件到临时目录
        ref_copy = os.path.join(work_dir, "reference.fasta")
        shutil.copy2(config.ref_fasta, ref_copy)
        _ensure_unix_line_endings(ref_copy)
        _deduplicate_fasta(ref_copy)

        cmd = [
            MAKEBLASTDB_EXE,
            "-in", "reference.fasta",
            "-dbtype", "nucl",
            "-parse_seqids",
            "-out", "db",
            # 强制 BDB v4 格式，避免 BLAST 2.17 默认 LMDB 后端在 Windows
            # 含中文/空格路径下的 mdb_env_open "找不到路径" 错误
            "-blastdb_version", "4",
        ]

        logger.info(f"命令: {' '.join(cmd)} (cwd={work_dir})")

        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,  # 无空格临时目录，相对路径
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                logger.error(f"makeblastdb 运行失败:\n{result.stderr}")
                raise RuntimeError(f"makeblastdb 运行失败（返回码 {result.returncode}）")
        except FileNotFoundError:
            logger.error("未找到 BLAST，请安装: conda install -c bioconda blast（Windows 用官方安装包）")
            raise

        # 数据库文件复制回 ref 目录（Python 处理空格/中文路径）
        for ext in _BDB_EXTS:
            src = os.path.join(work_dir, "db" + ext)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(ref_dir, db_name + ext))

        logger.info("BLAST 数据库构建完成")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return config.blast_db


def run_blast(config):
    """运行 blastn 短序列比对

    Args:
        config: PipelineConfig 对象

    Returns:
        list: 比对结果列表，每项为 dict
    """
    if config.skip_blast and os.path.exists(config.blast_result):
        logger.info("跳过 BLAST 比对（--skip-blast 且结果文件已存在）")
        return parse_blast_result(config)

    logger.info("运行 BLAST 比对...")

    # BLAST 工具不支持含空格/中文的 cwd，改用临时目录（无空格）运行，
    # 把数据库和 query 复制过去，结果再复制回 results 目录
    ref_dir = os.path.join(config.outdir, "ref")
    db_name = os.path.basename(config.blast_db)

    work_dir = tempfile.mkdtemp(prefix="sgrna_blast_")
    try:
        # 复制数据库文件到临时目录
        for ext in _BDB_EXTS:
            src = os.path.join(ref_dir, db_name + ext)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(work_dir, "db" + ext))

        # 复制 query 到临时目录
        shutil.copy2(config.merged_seqs_fasta, os.path.join(work_dir, "merged_seqs.fasta"))

        cmd = [
            BLASTN_EXE,
            "-query", "merged_seqs.fasta",
            "-db", "db",
            "-out", "result.txt",
            "-outfmt", "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore",
            "-task", "blastn-short",
            "-evalue", str(config.blast_evalue),
            "-num_threads", str(config.threads),
        ]

        logger.info(f"命令: {' '.join(cmd)} (cwd={work_dir})")

        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,  # 无空格临时目录，相对路径
                capture_output=True,
                text=True,
                timeout=7200,
            )
            if result.returncode != 0:
                logger.error(f"blastn 运行失败:\n{result.stderr}")
                raise RuntimeError(f"blastn 运行失败（返回码 {result.returncode}）")
        except FileNotFoundError:
            logger.error("未找到 BLAST，请安装: conda install -c bioconda blast（Windows 用官方安装包）")
            raise

        # 结果复制回 results 目录
        tmp_out = os.path.join(work_dir, "result.txt")
        if os.path.exists(tmp_out):
            shutil.copy2(tmp_out, config.blast_result)

        logger.info("BLAST 比对完成")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return parse_blast_result(config)


def _ensure_unix_line_endings(filepath):
    """Convert file to Unix line endings (LF)"""
    try:
        with open(filepath, "rb") as f:
            content = f.read()
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        with open(filepath, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.warning(f"Line ending conversion failed: {e}")


def _deduplicate_fasta(filepath):
    """Remove duplicate sequences from FASTA file (keep first occurrence)"""
    try:
        with open(filepath, "r") as f:
            content = f.read()

        seen = set()
        unique_entries = []
        current_header = None
        current_seq_lines = []

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith(">"):
                # Save previous entry
                if current_header is not None:
                    seq_id = current_header[1:].split()[0]  # Get ID without '>'
                    if seq_id not in seen:
                        seen.add(seq_id)
                        unique_entries.append(current_header)
                        unique_entries.extend(current_seq_lines)
                current_header = line
                current_seq_lines = []
            elif current_header is not None and line:
                current_seq_lines.append(line)

        # Save last entry
        if current_header is not None:
            seq_id = current_header[1:].split()[0]
            if seq_id not in seen:
                seen.add(seq_id)
                unique_entries.append(current_header)
                unique_entries.extend(current_seq_lines)

        with open(filepath, "w") as f:
            f.write("\n".join(unique_entries) + "\n")

        removed = content.count(">") - len(seen)
        if removed > 0:
            logger.info(f"Removed {removed} duplicate sequences from reference")
    except Exception as e:
        logger.warning(f"Deduplication failed: {e}")


def parse_blast_result(config):
    """解析 BLAST 比对结果，提取满足条件的匹配

    默认筛选条件：identity=100% 且 alignment length=20

    Args:
        config: PipelineConfig 对象

    Returns:
        dict: 包含 subject_id -> count 的字典
    """
    if not os.path.exists(config.blast_result):
        logger.warning(f"BLAST 结果文件不存在: {config.blast_result}")
        return {}

    logger.info("解析 BLAST 比对结果...")

    subject_ids = []
    total_hits = 0

    with open(config.blast_result, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) < 12:
                continue

            total_hits += 1

            # outfmt 6 字段:
            # 0:qseqid 1:sseqid 2:pident 3:length 4:mismatch 5:gapopen
            # 6:qstart 7:qend 8:sstart 9:send 10:evalue 11:bitscore
            try:
                pident = float(fields[2])
                aln_length = int(fields[3])
                sseqid = fields[1]
            except (ValueError, IndexError):
                continue

            # 筛选：identity >= 阈值 且 长度 >= 阈值
            if pident >= config.blast_identity and aln_length >= config.blast_align_length:
                subject_ids.append(sseqid)

    # 保存筛选后的 subject_id 列表
    subject_ids_file = os.path.join(
        os.path.dirname(config.blast_result), "subject_ids_filtered.txt"
    )
    with open(subject_ids_file, "w") as f:
        for sid in subject_ids:
            f.write(sid + "\n")

    # 统计每个 subject_id 的出现次数
    subject_counts = {}
    for sid in subject_ids:
        subject_counts[sid] = subject_counts.get(sid, 0) + 1

    logger.info(f"BLAST 总匹配数: {total_hits:,}")
    logger.info(f"筛选后（identity≥{config.blast_identity}%, length≥{config.blast_align_length}）: "
                f"{len(subject_ids):,} 条匹配，{len(subject_counts):,} 个唯一 sgRNA")

    return subject_counts
