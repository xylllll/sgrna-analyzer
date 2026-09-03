"""FLASH 双端拼接运行模块

负责调用 FLASH 将质控后的双端 reads 拼接为 extendedFrags。
"""

import subprocess
import logging
import os
import re
import gzip

from .. import bundled_tools

logger = logging.getLogger(__name__)

# FLASH 可执行文件（优先捆绑版，其次 PATH）
FLASH_EXE = bundled_tools.find_tool("flash")


def check_flash():
    """检查 FLASH 是否可用"""
    try:
        result = subprocess.run(
            [FLASH_EXE, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def run_flash(config):
    """运行 FLASH 双端拼接

    Args:
        config: PipelineConfig 对象

    Returns:
        dict: 包含拼接统计信息的字典
    """
    if config.skip_flash and os.path.exists(config.extended_frags):
        logger.info("跳过 FLASH（--skip-flash 且 extendedFrags 文件已存在）")
        return parse_flash_log(config.flash_log) if os.path.exists(config.flash_log) else {}

    # FLASH 在 Windows 上对带盘符的 -d 路径解析有 bug（会把 C: 当目录），
    # 因此改用设置工作目录 cwd 的方式输出到 results 目录
    out_dir = os.path.dirname(config.flash_prefix)
    cmd = [
        FLASH_EXE,
        os.path.basename(config.clean_r1),
        os.path.basename(config.clean_r2),
        "-o", os.path.basename(config.flash_prefix),
        "-M", str(config.flash_max_overlap),
        "-m", str(config.flash_min_overlap),
        "-t", str(config.threads),
    ]

    # FLASH 将输出重命名; 使用 sample.extendedFrags.fastq 检测
    log_path = config.flash_log

    logger.info("运行 FLASH 双端拼接...")
    logger.info(f"命令: {' '.join(cmd)} (cwd={out_dir})")

    try:
        with open(log_path, "w") as log_f:
            result = subprocess.run(
                cmd,
                cwd=out_dir,  # 输出到 results 目录
                stdout=log_f,
                stderr=subprocess.STDOUT,
                timeout=7200,
            )
        if result.returncode != 0:
            with open(log_path, "r") as f:
                log_content = f.read()
            logger.error(f"FLASH 运行失败:\n{log_content[-1000:]}")
            raise RuntimeError(f"FLASH 运行失败（返回码 {result.returncode}）")

        # FLASH 默认输出名为 out.extendedFrags.fastq 等
        # 根据 prefix 重命名为我们需要的名称
        expected_output = os.path.join(
            os.path.dirname(config.flash_prefix),
            f"{os.path.basename(config.flash_prefix)}.extendedFrags.fastq"
        )
        if os.path.exists(expected_output) and expected_output != config.extended_frags:
            os.rename(expected_output, config.extended_frags)

        logger.info("FLASH 拼接完成")
        return parse_flash_log(log_path)

    except FileNotFoundError:
        logger.error(
            "未找到 FLASH，请安装: conda install -c conda-forge flash"
        )
        raise


def parse_flash_log(log_path):
    """解析 FLASH 日志文件，提取拼接统计

    Args:
        log_path: FLASH 日志文件路径

    Returns:
        dict: 包含 total_pairs, combined_pairs, percent_combined 等
    """
    if not os.path.exists(log_path):
        logger.warning(f"FLASH 日志不存在: {log_path}")
        return {}

    with open(log_path, "r") as f:
        content = f.read()

    stats = {}

    # 匹配模式示例:
    # Total pairs: 12345678
    # Combined pairs: 9876543
    patterns = {
        "total_pairs": r"Total pairs:\s+([\d,]+)",
        "combined_pairs": r"Combined pairs:\s+([\d,]+)",
        "uncombined_pairs": r"Uncombined pairs:\s+([\d,]+)",
        "percent_combined": r"Percent combined:\s+([\d.]+)%",
        "min_overlap": r"Min overlap:\s+(\d+)",
        "max_overlap": r"Max overlap:\s+(\d+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            val = match.group(1).replace(",", "")
            try:
                if "." in val:
                    stats[key] = float(val)
                else:
                    stats[key] = int(val)
            except ValueError:
                stats[key] = match.group(1)

    if stats:
        logger.info(
            f"FLASH 统计: {stats.get('combined_pairs', 'N/A'):,} / "
            f"{stats.get('total_pairs', 'N/A'):,} pairs combined "
            f"({stats.get('percent_combined', 'N/A')}%)"
        )

    return stats


def count_extended_reads(config):
    """统计 extendedFrags 文件中的 reads 数量

    支持 .fastq, .fastq.gz 格式

    Args:
        config: PipelineConfig 对象

    Returns:
        int: reads 数量
    """
    fpath = config.extended_frags
    if not os.path.exists(fpath):
        logger.error(f"extendedFrags 文件不存在: {fpath}")
        return 0

    # 处理 gzip 压缩
    open_func = gzip.open if fpath.endswith(".gz") else open

    try:
        count = 0
        with open_func(fpath, "rt") as f:
            for _ in f:
                count += 1
        reads = count // 4  # FASTQ 每4行一个read
        logger.info(f"extendedFrags 中共 {reads:,} reads")
        return reads
    except Exception as e:
        logger.error(f"读取 extendedFrags 失败: {e}")
        return 0
