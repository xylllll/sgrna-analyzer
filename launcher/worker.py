"""后台分析工作线程 — Windows 原生版（2.0）

直接调用 sgrna_analyzer.pipeline 库在 GUI 进程内运行管线，
通过 logging 捕获日志更新进度条。无需 WSL / conda run / subprocess CLI。
"""

import os
import re
import logging
import threading

# 直接导入分析管线库
from sgrna_analyzer.config import PipelineConfig
from sgrna_analyzer.pipeline import SGRNAPipeline

# 确保日志转发到 GUI 的回调
_log_handlers = []


class _GuiLogHandler(logging.Handler):
    """将分析日志转发到 worker 的回调，并解析步骤更新进度"""
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.setLevel(logging.INFO)

    def emit(self, record):
        if not self.worker:
            return
        try:
            msg = self.format(record)
            if self.worker.on_log:
                self.worker.on_log(msg)
            # 解析步骤更新进度
            step = self.worker._parse_step(msg)
            if step and self.worker.on_progress:
                self.worker.on_progress(self.worker._step_percent(step), step)
        except Exception:
            pass


class AnalysisWorker:
    """sgRNA 分析后台工作线程"""

    # 管线步骤与进度权重
    STEPS = [
        ("检查依赖", 2),
        ("创建目录", 2),
        ("质控", 13),
        ("FLASH 双端拼接", 13),
        ("序列提取", 5),
        ("参考 sgRNA", 2),
        ("BLAST 数据库", 5),
        ("BLAST 比对", 28),
        ("统计覆盖度", 5),
        ("生成图表", 10),
        ("生成 HTML 报告", 10),
    ]

    def __init__(self, config: dict):
        """
        Args:
            config: {
                "r1": str,        # R1 文件路径 (Windows)
                "r2": str,        # R2 文件路径 (Windows)
                "ref": str,       # 参考库路径 (Windows)
                "name": str,      # 样品名
                "outdir": str,    # 输出目录 (Windows)
                "threads": int,   # 线程数
                "extra_params": dict,  # 高级参数
            }
        """
        self.config = config
        self._running = False
        self._thread = None

        # 回调
        self.on_log = None          # (text: str) -> None
        self.on_progress = None     # (percent: int, step_name: str) -> None
        self.on_complete = None     # (success: bool, report_path: str, error: str) -> None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """停止分析（设置标志，当前步骤完成后中断）"""
        self._running = False
        if self.on_log:
            self.on_log("⚠️ 用户请求停止分析，正在中断...")

    def _log(self, text: str):
        if self.on_log:
            self.on_log(text)

    def _build_config(self) -> PipelineConfig:
        """构建管线配置对象"""
        extra = self.config.get("extra_params", {})
        return PipelineConfig(
            r1=self.config["r1"],
            r2=self.config["r2"],
            ref_fasta=self.config["ref"],
            sample_name=self.config["name"],
            outdir=self.config["outdir"],
            threads=int(self.config.get("threads", extra.get("threads", 4))),
            fastp_min_length=int(extra.get("fastp_min_length", 15)),
            fastp_quality_threshold=int(extra.get("fastp_quality_threshold", 20)),
            flash_min_overlap=int(extra.get("flash_min_overlap", 10)),
            flash_max_overlap=int(extra.get("flash_max_overlap", 150)),
            blast_evalue=float(extra.get("blast_evalue", 1.0)),
            blast_identity=float(extra.get("blast_identity", 100.0)),
            blast_align_length=int(extra.get("blast_align_length", 20)),
            skip_deps_check=True,  # GUI 启动时已检测环境
        )

    def _run(self):
        """在后台线程中执行分析管线"""
        self._log(f"🚀 启动分析管线: {self.config['name']}")
        self._log(f"📂 输入 R1: {self.config['r1']}")
        self._log("")

        # 添加日志捕获器
        handler = _GuiLogHandler(self)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

        try:
            pcfg = self._build_config()
            pipeline = SGRNAPipeline(pcfg)
            pipeline.run()
            report_path = pcfg.report_html

            if self._running:
                self._log("")
                self._log("=" * 50)
                if self.on_progress:
                    self.on_progress(100, "完成")
                if self.on_complete:
                    self.on_complete(True, report_path, "")
            else:
                if self.on_complete:
                    self.on_complete(False, "", "分析已被用户停止")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._log(f"❌ 运行出错: {e}")
            if self.on_complete:
                self.on_complete(False, "", str(e))

        finally:
            root_logger.removeHandler(handler)
            self._running = False

    # ========== 进度解析 ==========

    def _parse_step(self, line: str) -> str:
        """从日志行解析当前步骤名称"""
        step_keywords = [
            (r"检查依赖", "检查依赖"),
            (r"创建目录", "创建目录"),
            (r"质控|fastp|FASTP", "质控"),
            (r"FLASH|拼接", "FLASH 双端拼接"),
            (r"序列提取|去冗余", "序列提取"),
            (r"参考.*sgRNA|参考库", "参考 sgRNA"),
            (r"BLAST.*数据库|数据库", "BLAST 数据库"),
            (r"BLAST.*比对", "BLAST 比对"),
            (r"统计|覆盖度", "统计覆盖度"),
            (r"图表", "生成图表"),
            (r"HTML|报告", "生成 HTML 报告"),
            (r"分析完成", "完成"),
        ]
        for pattern, step_name in step_keywords:
            if re.search(pattern, line, re.IGNORECASE):
                return step_name
        return ""

    def _step_percent(self, step_name: str) -> int:
        """返回某步骤对应的进度百分比"""
        cumulative = 0
        for name, weight in self.STEPS:
            cumulative += weight
            if name == step_name:
                return min(cumulative, 95)
        return 0
