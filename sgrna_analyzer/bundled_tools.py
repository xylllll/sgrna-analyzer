"""捆绑工具查找模块

PyInstaller 单文件模式下，捆绑的外部工具（FLASH/BLAST）会被解压到
临时目录 sys._MEIPASS/tools/。本模块负责在运行时定位这些工具。

开发模式（未打包）下回退到系统 PATH 查找。
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包环境中"""
    return getattr(sys, "frozen", False)


def tools_dir() -> str:
    """返回捆绑工具的目录路径

    - 打包模式: sys._MEIPASS/tools （PyInstaller 解压目录）
    - 开发模式: 项目根目录下的 tools/
    """
    if is_frozen():
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        # 项目根目录 = sgrna_analyzer 的上级
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "tools")


def find_tool(name: str) -> str:
    """查找工具可执行文件的完整路径

    Args:
        name: 工具名（如 "flash", "makeblastdb", "blastn"）

    Returns:
        str: 可执行文件绝对路径；若未找到捆绑版本则返回原始命令名（走 PATH）
    """
    exe_name = name + (".exe" if os.name == "nt" else "")
    bundled = os.path.join(tools_dir(), exe_name)
    if os.path.exists(bundled):
        return bundled
    return name  # 回退到 PATH


def list_bundled_tools() -> list:
    """列出 tools/ 目录中的所有捆绑工具文件"""
    d = tools_dir()
    if not os.path.isdir(d):
        return []
    return sorted(os.listdir(d))
