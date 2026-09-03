"""环境检测与安装引导 — Windows 原生版（2.0）

引导用户完成:
1. FLASH 工具安装
2. BLAST+ 工具安装
3. Python 依赖检查
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from . import wsl_bridge

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SetupWizard(tk.Toplevel):
    """环境检测与安装引导窗口"""

    def __init__(self, parent=None, on_complete=None):
        super().__init__(parent)
        self.on_complete = on_complete
        self.env_status = {}
        self.installing = False

        self.title("sgRNA Analyzer - 环境检测")
        self.geometry("560x420")
        self.resizable(False, False)
        self.configure(bg="#f5f6fa")
        self.transient(parent)

        self._build_ui()
        self._start_detection()

    def _build_ui(self):
        header = tk.Frame(self, bg="#2c3e50", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🔍 环境检测向导",
                 font=("Microsoft YaHei", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(expand=True)

        main = tk.Frame(self, bg="#f5f6fa", padx=25, pady=15)
        main.pack(fill="both", expand=True)

        # 组件检测列表
        self.components = {
            "flash": ("FLASH (双端拼接工具)", "conda install -c conda-forge flash"),
            "blast": ("BLAST+ (序列比对工具)", "conda install -c bioconda blast"),
            "python_deps": ("Python 依赖 (matplotlib/numpy等)", "pip install matplotlib numpy jinja2"),
            "sgrna_pkg": ("sgRNA Analyzer 核心包", "随程序内置"),
        }

        self.status_labels = {}
        for key, (title, hint) in self.components.items():
            frame = tk.Frame(main, bg="white", bd=1, relief="solid")
            frame.pack(fill="x", pady=4)
            st = tk.Label(frame, text="⏳", font=("", 14), bg="white", width=3)
            st.pack(side="left", padx=(10, 5), pady=8)
            tk.Label(frame, text=title, font=("Microsoft YaHei", 10),
                     bg="white", anchor="w").pack(side="left", fill="x", expand=True, pady=8)
            self.status_labels[key] = st

        # 说明
        tk.Label(main, text="💡 本程序质控功能已内置（纯 Python 实现，无需安装 fastp）。\n"
                            "分析前需安装 FLASH 和 BLAST+ 工具。",
                 font=("Microsoft YaHei", 9), bg="#f5f6fa", fg="#7f8c8d",
                 justify="left", anchor="w").pack(fill="x", pady=(8, 0))

        # 按钮
        bf = tk.Frame(main, bg="#f5f6fa")
        bf.pack(fill="x", pady=(12, 0))

        tk.Button(bf, text="📖 查看安装教程", font=("Microsoft YaHei", 10),
                  bg="#3498db", fg="white", relief="flat", padx=15, pady=6,
                  cursor="hand2", command=self._show_guide).pack(side="left")
        tk.Button(bf, text="重新检测", font=("Microsoft YaHei", 10),
                  bg="#95a5a6", fg="white", relief="flat", padx=15, pady=6,
                  cursor="hand2", command=self._start_detection).pack(side="left", padx=(8, 0))
        tk.Button(bf, text="关闭", font=("Microsoft YaHei", 10),
                  bg="#7f8c8d", fg="white", relief="flat", padx=15, pady=6,
                  cursor="hand2", command=self.destroy).pack(side="right")

    def _start_detection(self):
        for lbl in self.status_labels.values():
            lbl.config(text="⏳", fg="#7f8c8d")

        def detect():
            self.env_status = wsl_bridge.check_environment()
            self.after(0, self._update)

        threading.Thread(target=detect, daemon=True).start()

    def _update(self):
        for key, lbl in self.status_labels.items():
            if self.env_status.get(key) == "yes":
                lbl.config(text="✅", fg="green")
            else:
                lbl.config(text="❌", fg="red")

    def _show_guide(self):
        guide = (
            "安装步骤：\n\n"
            "1. 下载安装 Miniconda for Windows\n"
            "   https://docs.conda.io/en/latest/miniconda.html\n"
            "   （安装时勾选 Add to PATH）\n\n"
            "2. 打开 Anaconda Prompt，运行：\n"
            "   conda install -c conda-forge flash\n"
            "   conda install -c bioconda blast\n\n"
            "3. 若缺 Python 依赖：\n"
            "   pip install matplotlib numpy jinja2\n\n"
            "4. 安装完成后重启本程序，点 [Check Env] 重新检测"
        )
        messagebox.showinfo("安装教程", guide, parent=self)


def should_run_setup():
    """判断是否需要运行环境检测"""
    try:
        env = wsl_bridge.check_environment()
        return not wsl_bridge.all_ready(env)
    except Exception:
        return True


def run_setup_if_needed(parent=None):
    """如果需要则运行安装向导"""
    if should_run_setup():
        SetupWizard(parent)
        return False
    return True
