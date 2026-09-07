"""sgRNA Analyzer 主界面 — 单窗口，内置环境检测和进度"""

import os
import sys
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import wsl_bridge, presets
from .worker import AnalysisWorker
from .param_dialog import ParamDialog

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "sgrna_analyzer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load_config():
    defaults = {"r1": "", "r2": "", "ref": "", "name": "sample",
                "outdir": os.path.join(os.path.expanduser("~"), "sgRNA_output"), "threads": "4",
                "preset_name": "原始协议默认"}
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                defaults.update(json.load(f))
    except Exception:
        pass
    return defaults


def save_config(config: dict):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("sgRNA Analyzer v2.1 - 作者：许逸伦（AI 辅助编写）")
        self.root.geometry("780x720")
        self.root.minsize(700, 600)
        self.root.configure(bg="#f5f6fa")

        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 780) // 2
        y = (self.root.winfo_screenheight() - 720) // 2
        self.root.geometry(f"+{x}+{y}")

        self.worker = None
        self.report_path = None
        self.config = load_config()
        self.env_status = None
        self.env_checking = False
        self._analysis_running = False
        saved_preset = self.config.get("preset_name", "原始协议默认")
        self.current_params = presets.get_preset(saved_preset)
        self.current_preset_name = saved_preset

        self._build_ui()

        # WSL 预热（后台启动，不阻塞界面）
        threading.Thread(target=wsl_bridge.wsl_warm_up, daemon=True).start()

        self._check_env_background()

        # 启动时自动弹出声明窗口
        self.root.after(400, self._show_startup_notice)

    # ================================================================
    # UI
    # ================================================================

    def _build_ui(self):
        # ---- Header ----
        header = tk.Frame(self.root, bg="#2c3e50", height=55)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🧬 sgRNA Analysis Tool v2.1",
                 font=("Microsoft YaHei", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(expand=True)

        # 作者栏
        author_bar = tk.Frame(self.root, bg="#34495e", height=22)
        author_bar.pack(fill="x")
        author_bar.pack_propagate(False)
        tk.Label(author_bar,
                 text="软件作者：许逸伦 ｜ 本软件由 AI 辅助编写，代码经人工审核验证",
                 font=("Microsoft YaHei", 8),
                 bg="#34495e", fg="#bdc3c7").pack(expand=True)

        main = tk.Frame(self.root, bg="#f5f6fa", padx=20, pady=10)
        main.pack(fill="both", expand=True)

        # ---- Environment status bar ----
        self.env_frame = tk.Frame(main, bg="#ecf0f1", height=36)
        self.env_frame.pack(fill="x", pady=(0, 8))
        self.env_frame.pack_propagate(False)

        self.env_icon = tk.Label(self.env_frame, text="", font=("", 12), bg="#ecf0f1", width=2)
        self.env_icon.pack(side="left", padx=(10, 0))

        self.env_label = tk.Label(self.env_frame, text="Detecting environment...",
                                  font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#7f8c8d")
        self.env_label.pack(side="left", padx=(5, 0))

        self.env_btn = tk.Button(self.env_frame, text="Setup", font=("Microsoft YaHei", 8),
                                 bg="#3498db", fg="white", relief="flat", padx=10,
                                 cursor="hand2", state="disabled",
                                 command=self._run_auto_setup)
        self.env_btn.pack(side="right", padx=(0, 4))

        self.check_env_btn = tk.Button(self.env_frame, text="Check Env", font=("Microsoft YaHei", 8),
                                       bg="#7f8c8d", fg="white", relief="flat", padx=10,
                                       cursor="hand2",
                                       command=self._manual_env_check)
        self.check_env_btn.pack(side="right", padx=(0, 10))

        about_btn = tk.Button(self.env_frame, text="ℹ️ 关于", font=("Microsoft YaHei", 8),
                              bg="#7f8c8d", fg="white", relief="flat", padx=10,
                              cursor="hand2", command=self._show_about)
        about_btn.pack(side="right", padx=(0, 6))

        # ---- File selection ----
        file_frame = tk.LabelFrame(main, text="Input Files",
                                   font=("Microsoft YaHei", 10, "bold"),
                                   bg="white", fg="#2c3e50", padx=12, pady=8)
        file_frame.pack(fill="x", pady=(0, 8))

        self._file_row(file_frame, "Read 1 (R1):", "r1", 0)
        self._file_row(file_frame, "Read 2 (R2):", "r2", 1)
        self._file_row(file_frame, "Reference FASTA:", "ref", 2)

        # ---- Excel 文库录入（生成模板 / 转换 FASTA）----
        lib_frame = tk.LabelFrame(main, text="Excel Library (文库录入)",
                                  font=("Microsoft YaHei", 10, "bold"),
                                  bg="white", fg="#2c3e50", padx=12, pady=8)
        lib_frame.pack(fill="x", pady=(0, 8))

        lib_row = tk.Frame(lib_frame, bg="white")
        lib_row.pack(fill="x", pady=2)
        tk.Button(lib_row, text="① 生成 Excel 模板", font=("Microsoft YaHei", 10),
                  bg="#3498db", fg="white", activebackground="#2980b9",
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  command=self._library_make_template).pack(side="left")
        tk.Button(lib_row, text="② 读取 Excel → 转换 FASTA", font=("Microsoft YaHei", 10),
                  bg="#e67e22", fg="white", activebackground="#d35400",
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  command=self._library_convert).pack(side="left", padx=(8, 0))
        tk.Label(lib_frame,
                 text="提示：每行填一条 sgRNA；优先用「自定义ID」，否则自动用「基因名_sg序号」。"
                      "转换成功后 .fasta 会自动填入上方 Reference FASTA，可直接运行分析。",
                 font=("Microsoft YaHei", 8), bg="white", fg="#95a5a6",
                 anchor="w", justify="left", wraplength=700).pack(fill="x", pady=(4, 0))

        # ---- Parameters ----
        param_frame = tk.LabelFrame(main, text="Parameters",
                                    font=("Microsoft YaHei", 10, "bold"),
                                    bg="white", fg="#2c3e50", padx=12, pady=8)
        param_frame.pack(fill="x", pady=(0, 8))

        for label, key, width, is_spin in [
            ("Sample Name:", "name", 25, False),
            ("Output Dir:", "outdir", 40, False),
            ("Threads:", "threads", 5, True),
        ]:
            row = tk.Frame(param_frame, bg="white")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg="white", font=("Microsoft YaHei", 10),
                     width=12, anchor="e").pack(side="left", padx=(0, 6))
            var = tk.StringVar(value=str(self.config.get(key, "")))
            setattr(self, f"{key}_var", var)

            if is_spin:
                ttk.Spinbox(row, from_=1, to=32, textvariable=var, width=width).pack(side="left")
            elif key == "outdir":
                tk.Entry(row, textvariable=var, font=("Consolas", 9), width=width).pack(side="left", padx=(0, 4))
                tk.Button(row, text="Browse", font=("Microsoft YaHei", 8), bg="#bdc3c7",
                          relief="flat", padx=6, cursor="hand2",
                          command=lambda: self._browse_dir()).pack(side="left")
            else:
                tk.Entry(row, textvariable=var, font=("Consolas", 9), width=width).pack(side="left")

        # ---- Buttons ----
        btn_frame = tk.Frame(main, bg="#f5f6fa")
        btn_frame.pack(fill="x", pady=(4, 6))

        self.start_btn = tk.Button(btn_frame, text="Start Analysis",
                                   font=("Microsoft YaHei", 12, "bold"),
                                   bg="#27ae60", fg="white", activebackground="#219a52",
                                   relief="flat", padx=20, pady=8, cursor="hand2",
                                   command=self._start_analysis)
        self.start_btn.pack(side="left")

        self.stop_btn = tk.Button(btn_frame, text="Stop",
                                  font=("Microsoft YaHei", 11),
                                  bg="#e74c3c", fg="white", activebackground="#c0392b",
                                  relief="flat", padx=15, pady=8, cursor="hand2",
                                  state="disabled", command=self._stop_analysis)
        self.stop_btn.pack(side="left", padx=(8, 0))

        self.settings_btn = tk.Button(btn_frame, text="⚙️ Settings",
                                      font=("Microsoft YaHei", 10),
                                      bg="#8e44ad", fg="white", activebackground="#7d3c98",
                                      relief="flat", padx=12, pady=8, cursor="hand2",
                                      command=self._open_settings)
        self.settings_btn.pack(side="right")

        self.preset_label = tk.Label(btn_frame,
                                     text=f"预设: {self.current_preset_name}",
                                     font=("Microsoft YaHei", 9),
                                     bg="#f5f6fa", fg="#8e44ad")
        self.preset_label.pack(side="right", padx=(0, 10))

        # ---- Progress ----
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(main, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=(0, 2))

        self.progress_label = tk.Label(main, text="Ready.",
                                       font=("Microsoft YaHei", 8),
                                       bg="#f5f6fa", fg="#7f8c8d")
        self.progress_label.pack(anchor="w", pady=(0, 4))

        # ---- Log ----
        log_frame = tk.LabelFrame(main, text="Log",
                                  font=("Microsoft YaHei", 10, "bold"),
                                  bg="white", fg="#2c3e50", padx=8, pady=6)
        log_frame.pack(fill="both", expand=True, pady=(0, 4))

        self.log_text = tk.Text(log_frame, font=("Consolas", 9),
                                bg="#1e1e1e", fg="#d4d4d4", wrap="word", state="disabled")
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for tag, color in [("error", "#f44747"), ("warn", "#e5c07b"),
                           ("success", "#6a9955"), ("info", "#569cd6")]:
            self.log_text.tag_configure(tag, foreground=color)

        # ---- Bottom buttons ----
        bottom = tk.Frame(main, bg="#f5f6fa")
        bottom.pack(fill="x")

        self.report_btn = tk.Button(bottom, text="Open Report",
                                    font=("Microsoft YaHei", 10),
                                    bg="#27ae60", fg="white", relief="flat",
                                    padx=12, pady=5, cursor="hand2",
                                    state="disabled", command=self._open_report)
        self.report_btn.pack(side="left")

        self.folder_btn = tk.Button(bottom, text="Open Output Folder",
                                    font=("Microsoft YaHei", 10),
                                    bg="#8e44ad", fg="white", relief="flat",
                                    padx=12, pady=5, cursor="hand2",
                                    state="disabled", command=self._open_output_dir)
        self.folder_btn.pack(side="left", padx=(8, 0))

        # 底部版权栏
        bottom_bar = tk.Frame(main, bg="#f5f6fa")
        bottom_bar.pack(fill="x", pady=(8, 0))
        tk.Label(
            bottom_bar,
            text="作者：许逸伦 ｜ 本软件由 AI 辅助编写，代码经人工审核与验证，如有疑问请检查原始数据",
            font=("Microsoft YaHei", 8),
            bg="#f5f6fa", fg="#95a5a6",
        ).pack(anchor="e")

    def _file_row(self, parent, label, key, row):
        frame = tk.Frame(parent, bg="white")
        frame.pack(fill="x", pady=2)
        tk.Label(frame, text=label, bg="white", font=("Microsoft YaHei", 10),
                 width=14, anchor="e").pack(side="left", padx=(0, 6))
        var = tk.StringVar(value=self.config.get(key, ""))
        setattr(self, f"{key}_var", var)
        tk.Entry(frame, textvariable=var, font=("Consolas", 9)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(frame, text="Browse", font=("Microsoft YaHei", 8), bg="#bdc3c7",
                  relief="flat", padx=6, cursor="hand2",
                  command=lambda v=var: self._browse_file(v)).pack(side="right")

        # Trace file path changes to reset analysis state
        var.trace_add("write", lambda *_: self._on_file_changed())

    def _on_file_changed(self):
        """Reset progress/state when user selects new input files"""
        if not hasattr(self, '_analysis_running') or not self._analysis_running:
            if self.progress_var.get() > 0:
                self.progress_var.set(0)
                self.progress_label.config(text="新数据已导入，就绪。")
                self._log("📁 检测到新数据文件，状态已重置。")

    # ================================================================
    # Environment
    # ================================================================

    def _check_env_background(self, force=False):
        """Run environment detection in background thread.
        Only runs on first launch; subsequent launches use cached result.
        Set force=True to re-run regardless.
        """
        # Use cached result if available (skip on non-first runs)
        cache_file = os.path.join(CONFIG_DIR, "env_cache.json")
        if not force:
            try:
                if os.path.exists(cache_file):
                    with open(cache_file, "r") as f:
                        cache = json.load(f)
                    self.env_status = cache.get("data", None)
                    if self.env_status:
                        self._on_env_result()
                        return
            except Exception:
                pass

        # Full check (first run or manual re-check) — Windows 原生检测
        self.env_checking = True
        self._update_env_ui("checking")

        def do_check():
            # 调用 Windows 环境检测（检测 flash/blast + Python 依赖）
            self.env_status = wsl_bridge.check_environment()

            # Save cache (even if incomplete, to avoid repeated slow checks)
            try:
                os.makedirs(CONFIG_DIR, exist_ok=True)
                with open(cache_file, "w") as f:
                    json.dump({"timestamp": time.time(), "data": self.env_status}, f)
            except Exception:
                pass

            self.root.after(0, self._on_env_result)

        threading.Thread(target=do_check, daemon=True).start()

    def _manual_env_check(self):
        """Manual environment re-check (called by button)"""
        if self.env_checking:
            return
        # Clear cache to force re-check
        cache_file = os.path.join(CONFIG_DIR, "env_cache.json")
        try: os.remove(cache_file)
        except: pass
        self._check_env_background(force=True)

    def _on_env_result(self):
        self.env_checking = False
        ready = wsl_bridge.all_ready(self.env_status)

        if ready:
            self._update_env_ui("ready")
        else:
            self._update_env_ui("incomplete")

    def _update_env_ui(self, state):
        if state == "checking":
            self.env_icon.config(text="", fg="#7f8c8d")
            self.env_label.config(text="Detecting environment, please wait...", fg="#7f8c8d")
            self.env_btn.config(state="disabled", text="...")
            self.check_env_btn.config(state="disabled")
            self.start_btn.config(state="disabled", text="Please wait...")
            # Animated dots
            self._env_dots = 0
            self._animate_dots()
        elif state == "ready":
            self.env_icon.config(text="", fg="#27ae60")
            self.env_label.config(text="Environment ready", fg="#27ae60")
            self.env_btn.config(state="disabled", text="OK")
            self.check_env_btn.config(state="normal")
            self.start_btn.config(state="normal", text="Start Analysis")
        elif state == "incomplete":
            missing = [k for k in ["conda", "fastp", "flash", "blast", "python_deps", "sgrna_pkg"]
                       if self.env_status and self.env_status.get(k) != "yes"]
            msg = f"Missing: {', '.join(missing)}"
            self.env_icon.config(text="", fg="#e67e22")
            self.env_label.config(text=msg, fg="#e67e22")
            self.env_btn.config(state="normal", text="Install All", bg="#e67e22")
            self.check_env_btn.config(state="normal")
            self.start_btn.config(state="normal", text="Start Analysis")

    def _animate_dots(self):
        if not self.env_checking:
            return
        dots = "." * ((self._env_dots % 3) + 1)
        self.env_icon.config(text=dots)
        self._env_dots += 1
        self.root.after(500, self._animate_dots)

    def _run_auto_setup(self):
        """Windows 环境安装引导（2.0）"""
        msg = (
            "检测到缺少分析工具。Windows 版需要以下两个工具：\n\n"
            "1. FLASH (双端拼接)\n"
            "2. BLAST+ (序列比对)\n\n"
            "推荐使用 Miniconda for Windows 安装：\n"
            "  conda install -c conda-forge flash\n"
            "  conda install -c bioconda blast\n\n"
            "是否打开安装教程页面？"
        )
        if not messagebox.askyesno("环境安装引导", msg):
            return
        try:
            os.startfile("https://docs.conda.io/en/latest/miniconda.html")
        except Exception:
            pass
        messagebox.showinfo(
            "安装步骤",
            "1. 下载安装 Miniconda for Windows（勾选 Add to PATH）\n"
            "2. 打开 Anaconda Prompt，运行：\n"
            "     conda install -c conda-forge flash\n"
            "     conda install -c bioconda blast\n"
            "3. 安装完成后关闭本程序，重新打开即可。\n\n"
            "点击 [Check Env] 可重新检测。"
        )
        self._check_env_background()

    # ================================================================
    # File browse
    # ================================================================

    def _browse_file(self, var):
        path = filedialog.askopenfilename(
            title="Select file",
            filetypes=[("FASTQ/FASTA", "*.fq.gz;*.fastq.gz;*.fq;*.fastq;*.fa;*.fasta"), ("All", "*.*")],
            initialdir=os.path.dirname(var.get()) if var.get() else os.path.expanduser("~"),
        )
        if path:
            var.set(path)

    def _browse_dir(self):
        path = filedialog.askdirectory(
            title="Select output directory",
            initialdir=self.outdir_var.get() if self.outdir_var.get() else os.path.expanduser("~"),
        )
        if path:
            self.outdir_var.set(path)

    # ================================================================
    # Excel 文库录入（生成模板 / 转换 FASTA）
    # ================================================================

    def _library_make_template(self):
        """① 一键生成 sgRNA 文库录入 Excel 模板"""
        from sgrna_analyzer.modules import library_xlsx  # 懒加载：openpyxl 为可选依赖
        path = filedialog.asksaveasfilename(
            title="保存 Excel 模板",
            defaultextension=".xlsx",
            filetypes=[("Excel 工作簿", "*.xlsx")],
            initialfile="sgRNA文库录入模板.xlsx",
            initialdir=os.path.expanduser("~"),
        )
        if not path:
            return
        try:
            self.root.config(cursor="watch")
            self.root.update_idletasks()
            library_xlsx.write_template(path)
        except Exception as e:
            self._log(f"❌ 生成模板失败: {e}", "error")
            messagebox.showerror("生成模板失败", str(e))
            return
        finally:
            self.root.config(cursor="")
        self._log(f"✅ Excel 模板已生成：{path}", "success")
        if messagebox.askyesno("模板已生成", f"模板已保存到：\n{path}\n\n是否立即打开？"):
            try:
                os.startfile(path)
            except Exception:
                pass

    def _library_convert(self):
        """② 读取已填写的 xlsx → 校验并转换为参考库 FASTA，自动填入 Reference FASTA"""
        from sgrna_analyzer.modules import library_xlsx
        xlsx = filedialog.askopenfilename(
            title="选择已填写的 sgRNA 文库 Excel",
            filetypes=[("Excel 工作簿", "*.xlsx"), ("所有文件", "*.*")],
            initialdir=os.path.expanduser("~"),
        )
        if not xlsx:
            return
        out = os.path.splitext(xlsx)[0] + ".fasta"
        if os.path.exists(out):
            if not messagebox.askyesno("文件已存在",
                                       f"{out} 已存在。\n点“是”覆盖；点“否”自动另存为新文件。"):
                i = 1
                while os.path.exists(out):
                    out = f"{os.path.splitext(xlsx)[0]}_({i}).fasta"
                    i += 1
        try:
            self.root.config(cursor="watch")
            self.root.update_idletasks()
            res = library_xlsx.convert_xlsx_to_fasta(xlsx, out)
        except Exception as e:
            self._log(f"❌ Excel 转换失败: {e}", "error")
            messagebox.showerror("Excel 转换失败", str(e))
            return
        finally:
            self.root.config(cursor="")

        if not res["ok"]:
            errs = res["errors"]
            lines = [f"第 {r} 行：{m}" if isinstance(r, int) else m for r, m in errs[:15]]
            if len(errs) > 15:
                lines.append(f"…… 共 {len(errs)} 处错误，请修正后重新转换。")
            self._log(f"❌ 校验未通过（{len(errs)} 处错误），未生成 FASTA。", "error")
            messagebox.showerror("校验未通过", "未生成 FASTA，请修正：\n\n" + "\n".join(lines))
            return

        # 成功：持久化并自动回填 Reference FASTA（var.set 会触发 trace 重置分析状态）
        self.config["ref"] = res["fasta_path"]
        save_config(self.config)
        self.ref_var.set(res["fasta_path"])

        msg = (f"转换成功！\n\n已生成：{res['fasta_path']}\n"
               f"共 {res['entries']} 条序列（自动ID {res['auto_ids']} 条，自定义ID {res['custom_ids']} 条）\n\n"
               f"已自动填入 “Reference FASTA”，可直接开始分析。")
        if res["warnings"]:
            w = [f"第 {r} 行：{m}" if isinstance(r, int) else m for r, m in res["warnings"][:10]]
            if len(res["warnings"]) > 10:
                w.append(f"…… 共 {len(res['warnings'])} 条提示。")
            msg += "\n\n提示：\n" + "\n".join(w)
        self._log(f"✅ 已转换 {res['entries']} 条序列 → {res['fasta_path']}", "success")
        messagebox.showinfo("转换成功", msg)

    # ================================================================
    # Analysis
    # ================================================================

    def _open_settings(self):
        """打开参数设置对话框"""
        ParamDialog(self.root, self.current_params, self._on_params_changed)

    def _on_params_changed(self, new_params, preset_name):
        """参数设置变更回调"""
        self.current_params = new_params
        self.current_preset_name = preset_name
        # 同步线程数到 GUI 输入框
        self.threads_var.set(str(new_params.get("threads", 4)))
        self.preset_label.config(text=f"预设: {preset_name}")
        self._log(f"⚙️ 参数已应用: {preset_name}", "info")

    def _start_analysis(self):
        config = {
            "r1": self.r1_var.get().strip(),
            "r2": self.r2_var.get().strip(),
            "ref": self.ref_var.get().strip(),
            "name": self.name_var.get().strip() or "sample",
            "outdir": self.outdir_var.get().strip() or os.path.join(os.path.expanduser("~"), "sgRNA_output"),
            "threads": int(self.threads_var.get() or "4"),
            "extra_params": dict(self.current_params),  # 传递高级参数
        }

        for key, label in [("r1", "R1"), ("r2", "R2"), ("ref", "Reference")]:
            if not config[key]:
                messagebox.showerror("Error", f"Please select {label} file!")
                return
            if not os.path.exists(config[key]):
                messagebox.showerror("Error", f"{label} file not found:\n{config[key]}")
                return

        save_config(config)

        if not wsl_bridge.all_ready(self.env_status or {}):
            if messagebox.askyesno("Environment Not Ready",
                                   "Required tools are missing. Run auto-setup now?"):
                self._run_auto_setup()
            return

        self._set_running(True)
        self.report_path = None

        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        self.worker = AnalysisWorker(config)
        self.worker.on_log = lambda t: self.root.after(0, lambda: self._log(t))
        self.worker.on_progress = lambda p, s: self.root.after(0, lambda: self._update_progress(p, s))
        self.worker.on_complete = lambda ok, rp, err: self.root.after(0, lambda: self._on_done(ok, rp, err))
        self.worker.start()

    def _stop_analysis(self):
        if self.worker:
            self.worker.stop()
        self._set_running(False)
        self._log("Analysis stopped by user.", "warn")

    def _set_running(self, running):
        self._analysis_running = running
        if running:
            self.start_btn.config(state="disabled", text="Running...")
            self.stop_btn.config(state="normal")
            self.report_btn.config(state="disabled")
            self.folder_btn.config(state="disabled")
        else:
            self.start_btn.config(state="normal", text="Start Analysis")
            self.stop_btn.config(state="disabled")

    def _log(self, text, tag=""):
        self.log_text.config(state="normal")
        if tag:
            self.log_text.insert("end", text + "\n", tag)
        elif any(kw in text for kw in ["ERROR", "error", "fail", "X"]):
            self.log_text.insert("end", text + "\n", "error")
        elif any(kw in text for kw in ["WARNING", "warn"]):
            self.log_text.insert("end", text + "\n", "warn")
        elif any(kw in text for kw in ["OK", "success", "done", "complete"]):
            self.log_text.insert("end", text + "\n", "success")
        else:
            self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _update_progress(self, percent, step):
        self.progress_var.set(percent)
        self.progress_label.config(text=f"Step: {step} ({percent}%)")

    def _on_done(self, ok, report_path, error):
        self._set_running(False)
        if ok:
            self.report_path = report_path
            self.report_btn.config(state="normal")
            self.folder_btn.config(state="normal")
            self.progress_var.set(100)
            self.progress_label.config(text="Analysis complete!")
            self._log("Analysis completed successfully!", "success")
            if messagebox.askyesno("Done", "Analysis complete!\n\nOpen report now?"):
                self._open_report()
        else:
            # Check if the error looks like an environment issue
            env_keywords = [
                ("command not found", "未检测到分析工具"),
                ("127", "命令不存在（错误码127），可能是环境配置问题"),
                ("No such file", "文件或命令不存在"),
                ("conda", "conda 环境可能未正确配置"),
                ("sgrna-analyze", "sgrna-analyze 命令可能未安装"),
            ]
            is_env_issue = False
            for keyword, hint in env_keywords:
                if keyword.lower() in error.lower():
                    self._log(f"⚠️ {hint}：{keyword}", "warn")
                    is_env_issue = True
            if is_env_issue:
                self._log("", "warn")
                self._log("💡 建议：点击上方 [Check Env] 按钮重新检测环境，", "warn")
                self._log("   如检测到缺失组件，点击 [Install All] 自动安装。", "warn")

            self._log(f"❌ Analysis failed: {error}", "error")
            self.progress_label.config(text="Analysis failed")

    def _open_report(self):
        if self.report_path and os.path.exists(self.report_path):
            os.startfile(self.report_path)
        else:
            messagebox.showerror("Error", "Report file not found.")

    def _open_output_dir(self):
        d = self.outdir_var.get().strip()
        if d and os.path.exists(d):
            os.startfile(d)
        else:
            messagebox.showerror("Error", "Output directory not found.")

    def _show_startup_notice(self):
        """启动时自动弹出的声明窗口"""
        notice = tk.Toplevel(self.root)
        notice.title("软件声明")
        notice.geometry("560x520")
        notice.resizable(False, False)
        notice.configure(bg="#f5f6fa")
        notice.transient(self.root)
        notice.grab_set()

        # 居中
        notice.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 560) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 520) // 2
        notice.geometry(f"+{x}+{y}")

        # 标题栏
        header = tk.Frame(notice, bg="#2c3e50", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📜 软件声明与使用须知",
                 font=("Microsoft YaHei", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(expand=True)

        # 内容区（可滚动）
        text_frame = tk.Frame(notice, bg="#f5f6fa", padx=20, pady=12)
        text_frame.pack(fill="both", expand=True)

        text_widget = tk.Text(
            text_frame,
            font=("Microsoft YaHei", 10),
            bg="white", fg="#2c3e50",
            wrap="word", padx=16, pady=12,
            relief="solid", bd=1,
        )
        scroll = ttk.Scrollbar(text_frame, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scroll.set)
        text_widget.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        content = """尊敬的软件使用者：

欢迎使用 sgRNA Analyzer v2.1。在使用本软件前，请仔细阅读以下声明：

【作者信息】
软件作者：许逸伦

【AI 辅助编写声明】
本软件部分代码由 AI 大语言模型辅助生成，并经过人工审核、测试与修正。依据《生成式人工智能服务管理暂行办法》要求，特此标注。

【使用范围】
本软件仅供科研与教学目的使用。分析结果不构成医疗、临床诊断或治疗建议，不得用于任何临床决策。

【风险提示】
· 本软件按"原样"(AS-IS) 提供，不附带任何担保；
· 作者不对因使用本软件产生的数据丢失、实验失败或研究结论错误等任何直接或间接损失承担责任；
· 使用者应对分析结果自行验证，并对其发布的分析报告承担全部责任。

【数据合规】
涉及人类受试者或敏感数据的研究，使用者应自行确保符合伦理审批、知情同意及数据保护法律法规（如《个人信息保护法》《人类遗传资源管理条例》等）。

【许可信息】
本软件采用 MIT 许可证（Copyright © 2026 许逸伦）。依赖工具：fastp (MIT)、FLASH (GPLv2)、BLAST+ (公有领域)。

继续使用本软件即表示您已阅读并同意上述声明。"""

        text_widget.insert("1.0", content)
        text_widget.config(state="disabled")

        # 按钮区
        btn_frame = tk.Frame(notice, bg="#f5f6fa")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        agree_btn = tk.Button(
            btn_frame, text="✓ 我已知晓并同意",
            font=("Microsoft YaHei", 11, "bold"),
            bg="#27ae60", fg="white",
            activebackground="#219a52", activeforeground="white",
            relief="flat", padx=25, pady=8,
            cursor="hand2",
            command=notice.destroy,
        )
        agree_btn.pack(side="left")

        # 回车/空格键也能关闭
        notice.bind("<Return>", lambda e: notice.destroy())
        notice.bind("<Escape>", lambda e: notice.destroy())
        agree_btn.focus_set()

    def _show_about(self):
        """显示关于对话框（含作者、声明和免责条款）"""
        about_text = (
            "🧬 sgRNA Analyzer v2.1\n"
            "──────────────────────\n"
            "软件作者：许逸伦\n\n"
            "声明：\n"
            "· 本软件由 AI 辅助编写，代码经人工审核与验证；\n"
            "· 分析结果仅供科研与教学使用，不构成医疗、\n"
            "  临床诊断或治疗建议；\n"
            "· 使用者应对分析结果自行验证，并对其用途\n"
            "  承担全部责任。\n\n"
            "许可：\n"
            "· MIT License (Copyright © 2026 许逸伦)\n"
            "· 依赖工具：fastp (MIT) / FLASH (GPLv2)\n"
            "  / BLAST+ (Public Domain)\n\n"
            "本声明不构成法律意见。"
        )
        messagebox.showinfo("关于 sgRNA Analyzer", about_text)

    def run(self):
        def on_close():
            d = {k: getattr(self, f"{k}_var").get()
                 for k in ["r1", "r2", "ref", "name", "outdir", "threads"]}
            d["preset_name"] = self.current_preset_name
            save_config(d)
            self.root.destroy()
        self.root.protocol("WM_DELETE_WINDOW", on_close)
        self.root.mainloop()
