"""
sgRNA Analyzer v2.0 - Windows Desktop Launcher
Double-click this file or use Start.bat to start.

命令行自检:  sgRNA_Analyzer.exe --selftest <输出文件>
"""

import sys, os

# 强制 UTF-8 输出，避免 Windows GBK 控制台下 emoji/中文崩溃
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---- 自检模式：验证捆绑工具定位 ----
if "--selftest" in sys.argv:
    try:
        idx = sys.argv.index("--selftest")
        outfile = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "selftest.txt"
        from sgrna_analyzer import bundled_tools
        from launcher import wsl_bridge

        lines = []
        lines.append(f"frozen: {bundled_tools.is_frozen()}")
        lines.append(f"meipass: {getattr(sys, '_MEIPASS', 'N/A')}")
        lines.append(f"tools_dir: {bundled_tools.tools_dir()}")
        for t in ["flash", "makeblastdb", "blastn"]:
            lines.append(f"{t}: {bundled_tools.find_tool(t)}")
        lines.append(f"bundled_files: {bundled_tools.list_bundled_tools()}")
        env = wsl_bridge.check_environment()
        lines.append(f"env_flash: {env['flash']}, env_blast: {env['blast']}, ready: {wsl_bridge.all_ready(env)}")
        with open(outfile, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        sys.exit(0)
    except Exception as e:
        import traceback
        try:
            with open(outfile, "w", encoding="utf-8") as f:
                f.write("SELFTEST ERROR:\n" + traceback.format_exc())
        except Exception:
            pass
        sys.exit(1)

from launcher.main_window import MainWindow

if __name__ == "__main__":
    print("Starting sgRNA Analyzer v2.0 GUI...")
    app = MainWindow()
    app.run()
