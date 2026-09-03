"""环境桥接模块 — Windows 原生版（2.0）

保留与 1.0 相同的函数签名，但内部实现改为纯 Windows：
- 不再依赖 WSL
- 环境检测改为检测 Windows PATH 中的工具
- 路径直接使用 Windows 路径
"""

import os
import shutil
import subprocess
import logging

logger = logging.getLogger(__name__)

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================
# 工具检测
# ============================================================

def _which(tool):
    """在 Windows PATH 中查找工具"""
    found = shutil.which(tool)
    if found:
        return found
    # 常见 conda 路径补充
    candidates = [
        os.path.expanduser(r"~\miniconda3\Library\bin"),
        os.path.expanduser(r"~\miniconda3\Scripts"),
        os.path.expanduser(r"~\anaconda3\Library\bin"),
        os.path.expanduser(r"~\anaconda3\Scripts"),
    ]
    for d in candidates:
        p = os.path.join(d, tool + ".exe")
        if os.path.exists(p):
            return p
    return None


def wsl_available():
    """Windows 原生运行，无需 WSL"""
    return True


def win_to_wsl(win_path: str) -> str:
    """Windows 路径无需转换，直接返回"""
    return win_path


def wsl_to_win(wsl_path: str) -> str:
    """已是 Windows 路径，直接返回"""
    return wsl_path


def wsl_run_sync(cmd: str, timeout: int = 3600):
    """在 Windows 上同步执行命令"""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def wsl_run_async(cmd: str):
    """在 Windows 上异步执行命令"""
    return subprocess.Popen(cmd, shell=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)


def wsl_warm_up():
    """Windows 原生无需预热"""
    pass


def _tool_available(name: str) -> bool:
    """检查工具是否可用（捆绑目录优先，其次系统 PATH）"""
    try:
        from sgrna_analyzer import bundled_tools
        p = bundled_tools.find_tool(name)
        if p != name:  # 找到捆绑版本
            return True
    except ImportError:
        pass
    return _which(name) is not None


def check_environment():
    """检测 Windows 环境中的分析工具和 Python 依赖（含捆绑工具）"""
    status = {
        "wsl": "yes",
        "conda": "yes",  # Windows 运行，默认可用
        "fastp": "yes",  # 2.0 用纯 Python 质控，始终可用
        "flash": "no",
        "blast": "no",
        "python_deps": "no",
        "sgrna_pkg": "no",
    }

    # 检测 FLASH（捆绑版或系统 PATH）
    if _tool_available("flash"):
        status["flash"] = "yes"

    # 检测 BLAST
    if _tool_available("makeblastdb") and _tool_available("blastn"):
        status["blast"] = "yes"

    # 检测 Python 依赖
    try:
        import matplotlib, numpy, jinja2  # noqa
        status["python_deps"] = "yes"
    except ImportError:
        pass

    # 检测 sgrna_analyzer 包（作为本程序的一部分）
    try:
        import sgrna_analyzer  # noqa
        status["sgrna_pkg"] = "yes"
    except ImportError:
        pass

    logger.info(f"环境检测: {status}")
    return status


def all_ready(env_status: dict) -> bool:
    """检查环境是否全部就绪（flash + blast 必需）"""
    required = ["flash", "blast", "python_deps"]
    return all(env_status.get(k) == "yes" for k in required)


def get_install_command(sgrna_pkg_path: str) -> str:
    """Windows 环境安装由 GUI 引导完成，返回空即可"""
    return ""
