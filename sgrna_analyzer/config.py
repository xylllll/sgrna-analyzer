"""配置管理模块"""

import os
import logging

logger = logging.getLogger(__name__)


class PipelineConfig:
    """sgRNA分析管线的配置类"""

    def __init__(
        self,
        r1: str,
        r2: str,
        ref_fasta: str,
        sample_name: str = "sample",
        outdir: str = "./output",
        threads: int = 4,
        flash_min_overlap: int = 10,
        flash_max_overlap: int = 150,
        blast_evalue: float = 1.0,
        blast_identity: float = 100.0,
        blast_align_length: int = 20,
        fastp_min_length: int = 15,
        fastp_quality_threshold: int = 20,
        skip_fastp: bool = False,
        skip_flash: bool = False,
        skip_blast: bool = False,
        skip_deps_check: bool = False,
    ):
        # 输入文件
        self.r1 = os.path.abspath(r1)
        self.r2 = os.path.abspath(r2)
        self.ref_fasta = os.path.abspath(ref_fasta)
        self.sample_name = sample_name

        # 输出目录
        self.outdir = os.path.abspath(outdir)
        self.data_dir = os.path.join(self.outdir, "data")
        self.results_dir = os.path.join(self.outdir, "results")
        self.figures_dir = os.path.join(self.outdir, "figures")

        # 计算参数
        self.threads = threads
        self.flash_min_overlap = flash_min_overlap
        self.flash_max_overlap = flash_max_overlap
        self.blast_evalue = blast_evalue
        self.blast_identity = blast_identity
        self.blast_align_length = blast_align_length
        self.fastp_min_length = fastp_min_length
        self.fastp_quality_threshold = fastp_quality_threshold

        # 跳过选项
        self.skip_fastp = skip_fastp
        self.skip_flash = skip_flash
        self.skip_blast = skip_blast
        self.skip_deps_check = skip_deps_check

        # 中间文件路径
        self.clean_r1 = os.path.join(self.results_dir, f"{sample_name}_clean_R1.fastq")
        self.clean_r2 = os.path.join(self.results_dir, f"{sample_name}_clean_R2.fastq")
        self.fastp_json = os.path.join(self.results_dir, f"{sample_name}_fastp.json")
        self.fastp_html = os.path.join(self.results_dir, f"{sample_name}_fastp.html")
        self.flash_prefix = os.path.join(self.results_dir, sample_name)
        self.extended_frags = os.path.join(
            self.results_dir, f"{sample_name}.extendedFrags.fastq"
        )
        self.flash_log = os.path.join(self.results_dir, "flash.log")
        self.merged_seqs_txt = os.path.join(self.results_dir, "merged_seqs.txt")
        self.merged_seqs_fasta = os.path.join(self.results_dir, "merged_seqs.fasta")
        self.seq_counts_txt = os.path.join(self.results_dir, "seq_counts.txt")
        self.blast_db = os.path.join(self.outdir, "ref", "sgRNA_db")
        self.blast_result = os.path.join(self.results_dir, "blast_result.txt")
        self.sgrna_ids_txt = os.path.join(self.results_dir, "sgRNA_ids.txt")
        self.sgrna_counts_txt = os.path.join(self.results_dir, "sgRNA_counts.txt")
        self.sgrna_counts_sorted = os.path.join(
            self.results_dir, "sgRNA_counts_sorted.txt"
        )

        # 图表路径
        self.insert_size_png = os.path.join(
            self.figures_dir, f"{sample_name}.insert_size.png"
        )
        self.cycleq_png = os.path.join(
            self.figures_dir, f"{sample_name}.cycleQ_after.png"
        )
        self.base_content_png = os.path.join(
            self.figures_dir, f"{sample_name}.base_content_after.png"
        )
        self.histogram_png = os.path.join(
            self.figures_dir, f"{sample_name}.histogram.png"
        )
        self.cumulative_png = os.path.join(
            self.figures_dir, f"{sample_name}.cumulative.png"
        )

        # 最终报告
        self.report_html = os.path.join(
            self.outdir, f"{sample_name}_sgRNA_report.html"
        )

    def setup_dirs(self):
        """创建所有必要的目录"""
        for d in [self.outdir, self.results_dir, self.figures_dir]:
            os.makedirs(d, exist_ok=True)

        # ref目录放在outdir下
        ref_dir = os.path.join(self.outdir, "ref")
        os.makedirs(ref_dir, exist_ok=True)

        logger.info(f"输出目录: {self.outdir}")
        logger.info(f"结果目录: {self.results_dir}")
        logger.info(f"图表目录: {self.figures_dir}")
