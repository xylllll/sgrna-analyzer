"""参数预设管理"""

import os, json, copy

PRESET_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                          "sgrna_analyzer", "presets")

# ── 每个参数的中文名称与解释 ──
PARAM_INFO = {
    "threads":             ("并行线程数", "分析时使用的 CPU 核心数。数值越大处理越快，但不宜超过物理核心数。推荐 4~8。"),
    "fastp_min_length":    ("fastp 最短 read 长度", "质控时保留 reads 的最短长度（bp）。低于此长度的 reads 将被丢弃。sgRNA 文库建议 15。"),
    "fastp_quality_threshold": ("fastp 质量阈值", "碱基质量 Q 值门槛。低于此值的碱基会被从 read 末端修剪。Q15=准确度97%，Q20=99%，Q30=99.9%。"),
    "flash_min_overlap":   ("FLASH 最小 overlap", "双端 reads 拼接时，R1 和 R2 必须重叠的最小碱基数。通常 10。"),
    "flash_max_overlap":   ("FLASH 最大 overlap", "双端 reads 拼接时允许的最大重叠碱基数。通常 150（覆盖 sgRNA+接头长度）。"),
    "blast_evalue":        ("BLAST e-value 阈值", "BLAST 比对的期望值上限。值越小比对越严格。短序列比对建议 1.0（宽松）或更小。"),
    "blast_identity":      ("BLAST 最小 identity", "比对一致性的最低百分比（%）。100 表示只接受完全匹配的比对结果。"),
    "blast_align_length":  ("BLAST 最小比对长度", "有效比对所需的最短碱基数。sgRNA 通常设为 20（完整 sgRNA 长度）。"),
}

# ── 内置预设 ──
BUILTIN_PRESETS = {
    "原始协议默认": {
        "description": "基于 sgRNA 文库测序结果分析实验步骤的默认参数，适用于常规分析。",
        "params": {"threads": 4, "fastp_min_length": 15, "fastp_quality_threshold": 20,
                   "flash_min_overlap": 10, "flash_max_overlap": 150,
                   "blast_evalue": 1.0, "blast_identity": 100.0, "blast_align_length": 20},
    },
    "严格比对": {
        "description": "提高质控和比对精度，适合对准确性有严格要求的分析。",
        "params": {"threads": 4, "fastp_min_length": 20, "fastp_quality_threshold": 25,
                   "flash_min_overlap": 15, "flash_max_overlap": 150,
                   "blast_evalue": 0.1, "blast_identity": 100.0, "blast_align_length": 20},
    },
    "宽松比对": {
        "description": "降低比对阈值，适合低质量或部分降解样品的挽救分析。",
        "params": {"threads": 4, "fastp_min_length": 10, "fastp_quality_threshold": 15,
                   "flash_min_overlap": 8, "flash_max_overlap": 150,
                   "blast_evalue": 10.0, "blast_identity": 95.0, "blast_align_length": 18},
    },
    "快速模式": {
        "description": "最低质控门槛 + 最大并行，适合初步筛查或大批量快速分析。",
        "params": {"threads": 8, "fastp_min_length": 10, "fastp_quality_threshold": 15,
                   "flash_min_overlap": 10, "flash_max_overlap": 150,
                   "blast_evalue": 5.0, "blast_identity": 95.0, "blast_align_length": 18},
    },
}


def _safe_name(name):
    return "".join(c for c in name if c.isalnum() or c in "._- ").strip().replace(" ", "_")


def ensure_presets():
    os.makedirs(PRESET_DIR, exist_ok=True)
    for name, preset in BUILTIN_PRESETS.items():
        path = os.path.join(PRESET_DIR, _safe_name(name) + ".json")
        if not os.path.exists(path):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"name": name, **preset}, f, indent=2, ensure_ascii=False)
            except: pass


def list_presets():
    ensure_presets()
    presets = []
    builtin_names = set(BUILTIN_PRESETS.keys())
    for fname in sorted(os.listdir(PRESET_DIR)):
        if not fname.endswith(".json"): continue
        try:
            with open(os.path.join(PRESET_DIR, fname), "r", encoding="utf-8") as f:
                p = json.load(f)
            p["is_builtin"] = p.get("name", "") in builtin_names
            presets.append(p)
        except: pass
    return presets or [{"name": "原始协议默认", **BUILTIN_PRESETS["原始协议默认"]}]


def get_preset(name):
    for p in list_presets():
        if p.get("name") == name:
            return p["params"]
    return copy.deepcopy(BUILTIN_PRESETS["原始协议默认"]["params"])


def save_preset(name, description, params):
    ensure_presets()
    data = {"name": name, "description": description, "params": dict(params)}
    path = os.path.join(PRESET_DIR, _safe_name(name) + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def delete_preset(name):
    if name in BUILTIN_PRESETS: return False
    path = os.path.join(PRESET_DIR, _safe_name(name) + ".json")
    if os.path.exists(path): os.remove(path); return True
    return False
