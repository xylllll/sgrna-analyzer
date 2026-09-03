"""下载并准备 FLASH + BLAST 的 Windows 二进制，供 PyInstaller 捆绑。

用法:
    python prepare_tools.py

输出:
    tools/ 目录，内含 flash.exe, makeblastdb.exe, blastn.exe 及依赖 DLL
"""

import os
import sys
import io
import json
import zipfile
import tarfile
import urllib.request
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(PROJECT_DIR, "tools")
TMP_DIR = os.path.join(PROJECT_DIR, "build", "tools_download")


def log(msg):
    print(f"[prepare_tools] {msg}")


def download(url, dest):
    """下载文件到 dest，带简单进度"""
    log(f"下载 {url}")
    log(f"  -> {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)
    return dest


def get_conda_package(channel, package, build=None):
    """查询 conda 包的下载 URL（通过 anaconda.org API）"""
    api = f"https://api.anaconda.org/package/{channel}/{package}"
    log(f"查询 conda 包信息: {api}")
    with urllib.request.urlopen(api, timeout=60) as resp:
        data = json.load(resp)
    files = data.get("files", [])
    # 找 win-64 平台的包
    for f in files:
        if f.get("basename", "").endswith(".conda") or f.get("basename", "").endswith(".tar.bz2"):
            if f.get("attrs", {}).get("subdir") == "win-64":
                return f"https://anaconda.org/{channel}/{package}/{f['version']}/download/{f['basename']}"
    return None


def extract_conda_flat(archive, out_dir):
    """解压 conda 包（.conda 是 zip 或 tar.bz2）到 out_dir"""
    os.makedirs(out_dir, exist_ok=True)

    # 检测实际格式：先看 magic bytes
    with open(archive, "rb") as f:
        magic = f.read(4)

    if magic[:2] == b"BZ":  # bzip2
        log("检测到 tar.bz2 格式")
        with tarfile.open(archive, "r:bz2") as tf:
            tf.extractall(out_dir)
    elif magic[:4] == b"\x28\xb5\x2f\xfd":  # zstd
        log("检测到 zstd 格式")
        try:
            import zstandard
        except ImportError:
            log("需要 pip install zstandard，正在安装...")
            os.system("pip install zstandard")
            import zstandard
        dctx = zstandard.ZstdDecompressor()
        with open(archive, "rb") as f:
            decompressed = dctx.decompressobj().decompress(f.read())
        import io as _io
        with tarfile.open(fileobj=_io.BytesIO(decompressed)) as tf:
            tf.extractall(out_dir)
    elif archive.endswith(".conda") or magic[:2] == b"PK":  # zip
        log("检测到 .conda/zip 格式")
        with zipfile.ZipFile(archive) as zf:
            for n in zf.namelist():
                if n.endswith(".tar.zst"):
                    data = zf.read(n)
                    import zstandard
                    dctx = zstandard.ZstdDecompressor()
                    decompressed = dctx.decompressobj().decompress(data)
                    import io as _io
                    with tarfile.open(fileobj=_io.BytesIO(decompressed)) as tf:
                        tf.extractall(out_dir)
    else:
        # 最后尝试 tar.bz2（conda 老格式）
        log("按 tar.bz2 尝试解压")
        with tarfile.open(archive, "r:bz2") as tf:
            tf.extractall(out_dir)


def prepare_flash():
    """获取 FLASH win-64 二进制"""
    log("=== 准备 FLASH ===")
    dest = os.path.join(TMP_DIR, "flash_win")
    if os.path.exists(os.path.join(TOOLS_DIR, "flash.exe")):
        log("flash.exe 已存在，跳过")
        return

    url = get_conda_package("conda-forge", "flash")
    if not url:
        log("❌ 未找到 FLASH 的 win-64 包")
        return

    archive = download(url, os.path.join(TMP_DIR, "flash_win.conda"))
    extract_conda_flat(archive, dest)

    # 从 Library/bin 复制 flash.exe 及依赖
    bin_dir = os.path.join(dest, "Library", "bin")
    if not os.path.isdir(bin_dir):
        # 有时结构不同，全目录搜索
        for root, dirs, files in os.walk(dest):
            if "flash.exe" in files:
                bin_dir = root
                break

    copied = 0
    if os.path.isdir(bin_dir):
        for fname in os.listdir(bin_dir):
            if fname.lower().endswith((".exe", ".dll")):
                if fname.lower().startswith("flash") or copied < 30:  # flash + 依赖 dll
                    src = os.path.join(bin_dir, fname)
                    if os.path.isfile(src):
                        shutil.copy2(src, os.path.join(TOOLS_DIR, fname))
                        copied += 1
    if os.path.exists(os.path.join(TOOLS_DIR, "flash.exe")):
        log(f"✅ flash.exe 就绪 (复制 {copied} 个文件)")
    else:
        log("❌ FLASH 提取失败，请手动从 conda-forge 获取")


def prepare_blast():
    """获取 BLAST+ win-64 二进制"""
    log("=== 准备 BLAST+ ===")
    if os.path.exists(os.path.join(TOOLS_DIR, "makeblastdb.exe")):
        log("makeblastdb.exe 已存在，跳过")
        return

    # BLAST 官方 win64 包（约 100MB）
    blast_ver = "2.17.0"
    url = (f"https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/{blast_ver}/"
           f"ncbi-blast-{blast_ver}+-x64-win64.tar.gz")
    archive = download(url, os.path.join(TMP_DIR, "blast_win.tar.gz"))

    dest = os.path.join(TMP_DIR, "blast_win")
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(dest)

    # 找到 bin 目录
    bin_dir = None
    for root, dirs, files in os.walk(dest):
        if "blastn.exe" in files and "makeblastdb.exe" in files:
            bin_dir = root
            break

    if bin_dir:
        # 复制需要的 exe + 依赖 dll
        needed = {"makeblastdb", "blastn"}
        copied = 0
        for fname in os.listdir(bin_dir):
            fl = fname.lower()
            if fl.endswith(".exe"):
                base = os.path.splitext(fname)[0].lower()
                if base in needed or base.startswith(("blast", "makeblastdb")):
                    shutil.copy2(os.path.join(bin_dir, fname), os.path.join(TOOLS_DIR, fname))
                    copied += 1
            elif fl.endswith(".dll"):
                shutil.copy2(os.path.join(bin_dir, fname), os.path.join(TOOLS_DIR, fname))
                copied += 1
        log(f"✅ BLAST 就绪 (复制 {copied} 个文件)")
    else:
        log("❌ BLAST 提取失败，请检查下载")


def main():
    os.makedirs(TOOLS_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    prepare_flash()
    prepare_blast()
    log("\n=== 完成 ===")
    if os.path.isdir(TOOLS_DIR):
        for f in sorted(os.listdir(TOOLS_DIR)):
            sz = os.path.getsize(os.path.join(TOOLS_DIR, f))
            log(f"  {f} ({sz/1024:.0f} KB)")


if __name__ == "__main__":
    main()
