"""
PyInstaller 打包脚本 — 将 sgRNA Analyzer GUI 封装为单个 .exe

用法:
    pip install pyinstaller
    python build_exe.py

输出:
    dist/sgRNA_Analyzer.exe
"""

import PyInstaller.__main__
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Windows 路径分隔符
SEP = ";" if sys.platform == "win32" else ":"

# 数据文件映射 (源路径 -> 打包后相对路径)
datas = [
    (os.path.join(PROJECT_DIR, "sgrna_analyzer", "templates"),
     "sgrna_analyzer" + os.sep + "templates"),
    # LICENSE and DISCLAIMER at root
    (os.path.join(PROJECT_DIR, "LICENSE"), "."),
    (os.path.join(PROJECT_DIR, "DISCLAIMER.md"), "."),
]

add_data_args = []
for src, dst in datas:
    if os.path.exists(src):
        add_data_args.append("--add-data")
        add_data_args.append(src + SEP + dst)

# 收集 matplotlib 的 mpl-data（字体/样式资源，运行必需）
try:
    import matplotlib
    _mpl_data = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data")
    if os.path.isdir(_mpl_data):
        add_data_args.append("--add-data")
        add_data_args.append(_mpl_data + SEP + "matplotlib" + os.sep + "mpl-data")
        print(f"[build] 收集 matplotlib mpl-data: {_mpl_data}")
except ImportError:
    pass

# 捆绑外部工具二进制 (FLASH + BLAST) 到 tools/
add_binary_args = []
_tools_dir = os.path.join(PROJECT_DIR, "tools")
if os.path.isdir(_tools_dir):
    for fname in sorted(os.listdir(_tools_dir)):
        fpath = os.path.join(_tools_dir, fname)
        if os.path.isfile(fpath) and fname.lower().endswith((".exe", ".dll")):
            add_binary_args.append("--add-binary")
            add_binary_args.append(fpath + SEP + "tools")

PyInstaller.__main__.run([
    # 入口
    os.path.join(PROJECT_DIR, "sgRNA_Analyzer.pyw"),
    "--name=sgRNA_Analyzer",
    "--onedir",
    "--noconsole",
    # 程序图标
    "--icon=" + os.path.join(PROJECT_DIR, "assets", "app_icon.ico"),

    # 隐藏导入
    "--hidden-import=tkinter",
    "--hidden-import=launcher",
    "--hidden-import=launcher.main_window",
    "--hidden-import=launcher.setup_wizard",
    "--hidden-import=launcher.wsl_bridge",
    "--hidden-import=launcher.worker",
    "--hidden-import=launcher.presets",
    "--hidden-import=launcher.param_dialog",
    "--hidden-import=sgrna_analyzer",
    "--hidden-import=sgrna_analyzer.pipeline",
    "--hidden-import=sgrna_analyzer.config",
    "--hidden-import=sgrna_analyzer.cli",
    "--hidden-import=sgrna_analyzer.bundled_tools",
    "--hidden-import=sgrna_analyzer.modules",
    "--hidden-import=sgrna_analyzer.modules.python_qc",
    "--hidden-import=sgrna_analyzer.modules.fastp_runner",
    "--hidden-import=sgrna_analyzer.modules.flash_runner",
    "--hidden-import=sgrna_analyzer.modules.blast_runner",
    "--hidden-import=sgrna_analyzer.modules.sequence_tools",
    "--hidden-import=sgrna_analyzer.modules.stats",
    "--hidden-import=sgrna_analyzer.modules.plotter",
    "--hidden-import=sgrna_analyzer.modules.reporter",
    "--hidden-import=jinja2",
    "--hidden-import=matplotlib",
    "--hidden-import=numpy",

    # 数据文件
    *add_data_args,

    # 捆绑外部二进制（FLASH/BLAST）
    *add_binary_args,

    # 收集 tkinter 资源（保留）
    "--collect-all=tkinter",

    "--clean",
    "--noconfirm",
    "--distpath=" + os.path.join(PROJECT_DIR, "dist"),
    "--workpath=" + os.path.join(PROJECT_DIR, "build", "pyinstaller"),
])

print()
print("=" * 50)
print(" 打包完成！")
print(" 可执行文件: " + os.path.join(PROJECT_DIR, "dist", "sgRNA_Analyzer.exe"))
print("=" * 50)
