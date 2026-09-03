"""命令行入口

用法:
    sgrna-analyze --r1 sample_R1.fq.gz --r2 sample_R2.fq.gz \
                  --ref NC50.fasta --name NC48 --outdir ./output

或:
    python -m sgrna_analyzer --r1 ... --r2 ... --ref ... --name ...
"""

import argparse
import logging
import sys
import os

from .config import PipelineConfig
from .pipeline import SGRNAPipeline


def setup_logging(verbose: bool = False):
    """配置日志输出"""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        prog="sgrna-analyze",
        description="sgRNA 文库测序结果自动化分析工具 — 从测序文件一键生成完整报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    sgrna-analyze --r1 sample_R1.fq.gz --r2 sample_R2.fq.gz \\
                  --ref NC50.fasta --name NC48 --outdir ./output

    sgrna-analyze --r1 data/CME8-2_R1.fq.gz --r2 data/CME8-2_R2.fq.gz \\
                  --ref ref/library.fasta --name CME8-2 --threads 8

输入文件要求:
    --r1          Read 1 FASTQ 文件 (.fq.gz 或 .fastq.gz)
    --r2          Read 2 FASTQ 文件 (.fq.gz 或 .fastq.gz)
    --ref         参考 sgRNA 库 FASTA 文件 (.fasta 或 .fa)

外部工具依赖 (需预先安装):
    fastp         conda install -c bioconda fastp
    FLASH         conda install -c bioconda flash
    BLAST+        conda install -c bioconda blast
        """,
    )

    # 必选参数
    required = parser.add_argument_group("必选参数")
    required.add_argument("--r1", required=True, help="Read 1 FASTQ 文件路径")
    required.add_argument("--r2", required=True, help="Read 2 FASTQ 文件路径")
    required.add_argument("--ref", required=True, dest="ref_fasta",
                           help="参考 sgRNA 库 FASTA 文件路径")

    # 可选参数
    optional = parser.add_argument_group("可选参数")
    optional.add_argument("--name", default="sample",
                          help="样品名称 (用于输出文件命名, 默认: sample)")
    optional.add_argument("--outdir", default="./output",
                          help="输出目录 (默认: ./output)")
    optional.add_argument("--threads", type=int, default=4,
                          help="并行线程数 (默认: 4)")

    # 高级参数
    advanced = parser.add_argument_group("高级参数 (BLAST / FLASH 调优)")
    advanced.add_argument("--flash-min-overlap", type=int, default=10,
                          help="FLASH 最小 overlap (默认: 10)")
    advanced.add_argument("--flash-max-overlap", type=int, default=150,
                          help="FLASH 最大 overlap (默认: 150)")
    advanced.add_argument("--blast-evalue", type=float, default=1.0,
                          help="BLAST e-value 阈值 (默认: 1.0)")
    advanced.add_argument("--blast-identity", type=float, default=100.0,
                          help="BLAST 最小 identity%% (默认: 100.0)")
    advanced.add_argument("--blast-align-length", type=int, default=20,
                          help="BLAST 最小比对长度 (默认: 20)")
    advanced.add_argument("--fastp-min-length", type=int, default=15,
                          help="fastp 最小 read 长度 (默认: 15)")
    advanced.add_argument("--fastp-quality", type=int, default=20,
                          dest="fastp_quality_threshold",
                          help="fastp 质量阈值 (默认: 20)")

    # 跳过选项
    skip = parser.add_argument_group("跳过选项 (用于断点续跑)")
    skip.add_argument("--skip-fastp", action="store_true",
                      help="跳过 fastp (需要已有 clean reads)")
    skip.add_argument("--skip-flash", action="store_true",
                      help="跳过 FLASH (需要已有 extendedFrags)")
    skip.add_argument("--skip-blast", action="store_true",
                      help="跳过 BLAST (需要已有比对结果)")
    skip.add_argument("--skip-deps-check", action="store_true",
                      help="跳过启动时依赖检测（GUI已检测，省4s）")

    # 其他
    other = parser.add_argument_group("其他")
    other.add_argument("--verbose", "-v", action="store_true",
                       help="输出详细调试信息")
    other.add_argument("--version", action="version",
                       version="sgrna-analyzer v1.0.0")

    return parser.parse_args()


def main():
    """主入口"""
    args = parse_args()
    setup_logging(verbose=args.verbose)

    logger = logging.getLogger(__name__)

    # 检查输入文件
    for fpath, label in [(args.r1, "R1"), (args.r2, "R2"), (args.ref_fasta, "参考库")]:
        if not os.path.exists(fpath):
            logger.error(f"{label} 文件不存在: {fpath}")
            sys.exit(1)

    # 构建配置
    config = PipelineConfig(
        r1=args.r1,
        r2=args.r2,
        ref_fasta=args.ref_fasta,
        sample_name=args.name,
        outdir=args.outdir,
        threads=args.threads,
        flash_min_overlap=args.flash_min_overlap,
        flash_max_overlap=args.flash_max_overlap,
        blast_evalue=args.blast_evalue,
        blast_identity=args.blast_identity,
        blast_align_length=args.blast_align_length,
        fastp_min_length=args.fastp_min_length,
        fastp_quality_threshold=args.fastp_quality_threshold,
        skip_fastp=args.skip_fastp,
        skip_flash=args.skip_flash,
        skip_blast=args.skip_blast,
        skip_deps_check=args.skip_deps_check,
    )

    # 运行管线
    pipeline = SGRNAPipeline(config)
    report_path = pipeline.run()

    print(f"\n📄 报告已生成: {report_path}")
    print("   用浏览器打开即可查看。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
