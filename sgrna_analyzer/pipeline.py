"""主流程编排器

按顺序调度所有分析步骤:
1. 环境检测
2. 数据质控 (fastp)
3. 双端拼接 (FLASH)
4. 序列提取与去冗余
5. BLAST 数据库构建与比对
6. 覆盖度与均一性统计
7. 图表生成
8. HTML 报告生成
"""

import logging
import sys
import time
from .config import PipelineConfig
from .modules import fastp_runner
from .modules import flash_runner
from .modules import blast_runner
from .modules import sequence_tools
from .modules import stats as stats_module
from .modules import plotter
from .modules import reporter

logger = logging.getLogger(__name__)


class SGRNAPipeline:
    """sgRNA 文库测序分析管线"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.fastp_stats = {}
        self.flash_stats = {}
        self.blast_counts = {}
        self.ref_ids = []
        self.stats_results = {}
        self.plot_paths = {}

    def run(self):
        """执行全部分析流程"""
        steps = [
            ("检查依赖", self._step_check_deps),
            ("创建目录", self._step_setup_dirs),
            ("fastp 质控", self._step_fastp),
            ("FLASH 双端拼接", self._step_flash),
            ("序列提取与去冗余", self._step_extract_seqs),
            ("提取参考 sgRNA ID", self._step_ref_ids),
            ("构建 BLAST 数据库", self._step_blast_db),
            ("BLAST 比对", self._step_blast),
            ("统计覆盖度与均一性", self._step_stats),
            ("生成图表", self._step_plots),
            ("生成 HTML 报告", self._step_report),
        ]

        logger.info(f"{'='*60}")
        logger.info(f"sgRNA 分析管线启动 - 样品: {self.config.sample_name}")
        logger.info(f"{'='*60}")

        total_start = time.time()
        for step_name, step_func in steps:
            logger.info(f"\n{'─'*40}")
            logger.info(f"▶ {step_name}")
            logger.info(f"{'─'*40}")
            t0 = time.time()
            try:
                step_func()
                elapsed = time.time() - t0
                logger.info(f"✅ {step_name} 完成 (耗时 {elapsed:.1f}s)")
            except Exception as e:
                elapsed = time.time() - t0
                logger.error(f"❌ 步骤 [{step_name}] 失败: {e} (耗时 {elapsed:.1f}s)")
                logger.error("管线终止，请检查日志和中间文件。")
                sys.exit(1)

        total_elapsed = time.time() - total_start
        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 分析完成 (总耗时 {total_elapsed:.0f}s, {total_elapsed/60:.1f}min)")
        logger.info(f"报告路径: {self.config.report_html}")
        logger.info(f"{'='*60}")

        return self.config.report_html

    def _step_check_deps(self):
        """检查所有外部工具依赖"""
        if self.config.skip_deps_check:
            logger.info("  ⏭ 跳过依赖检测 (--skip-deps-check)")
            return

        tools = {
            "fastp": fastp_runner.check_fastp,
            "FLASH": flash_runner.check_flash,
            "BLAST+ (makeblastdb, blastn)": blast_runner.check_blast,
        }

        all_ok = True
        for name, check_fn in tools.items():
            if check_fn():
                logger.info(f"  ✅ {name}: 已安装")
            else:
                logger.error(f"  ❌ {name}: 未找到")
                all_ok = False

        if not all_ok:
            logger.error("\n请安装缺失的工具:")
            logger.error("  conda install -c conda-forge flash")
            logger.error("  conda install -c bioconda blast")
            logger.error("  （质控已内置，无需 fastp）")
            sys.exit(1)

    def _step_setup_dirs(self):
        """创建输出目录"""
        self.config.setup_dirs()

    def _step_fastp(self):
        """质控"""
        self.fastp_stats = fastp_runner.run_fastp(self.config)

    def _step_flash(self):
        """双端拼接"""
        self.flash_stats = flash_runner.run_flash(self.config)

    def _step_extract_seqs(self):
        """序列提取"""
        n = sequence_tools.extract_sequences(self.config)
        if n == 0:
            logger.error("序列提取结果为空，请检查 FLASH 输出")
            sys.exit(1)

    def _step_ref_ids(self):
        """获取参考 sgRNA ID"""
        self.ref_ids = sequence_tools.extract_reference_ids(self.config)
        if not self.ref_ids:
            logger.error("参考库文件为空或格式不正确")
            sys.exit(1)

    def _step_blast_db(self):
        """构建 BLAST 数据库"""
        blast_runner.build_blast_db(self.config)

    def _step_blast(self):
        """BLAST 比对"""
        self.blast_counts = blast_runner.run_blast(self.config)

        if not self.blast_counts:
            logger.warning("BLAST 比对无结果！请检查数据质量。")

    def _step_stats(self):
        """统计"""
        self.stats_results = stats_module.compute_stats(
            self.config, self.blast_counts, self.ref_ids
        )

    def _step_plots(self):
        """生成图表"""
        sgRNA_reads = self.stats_results.get("sgRNA_reads", [])
        self.plot_paths = plotter.generate_all_plots(
            self.config, self.fastp_stats, sgRNA_reads
        )

    def _step_report(self):
        """生成报告"""
        reporter.generate_report(
            self.config,
            self.fastp_stats,
            self.flash_stats,
            self.stats_results,
            self.plot_paths,
        )
