"""Excel 文库录入 → 参考库 FASTA 转换模块。

用途：
    一键生成 sgRNA 文库录入 Excel 模板（write_template）；
    读取用户填好的 xlsx，逐行校验并写出参考库 FASTA（convert_xlsx_to_fasta），
    供下游 blast_runner / sequence_tools 直接使用。

设计要点（与下游 blast 约束对齐）：
    · 生成 FASTA 每条约 ``>ID\\n<SEQ>\\n``，LF 行尾；
    · FASTA 头只含 ``[A-Za-z0-9_]``（makeblastdb -parse_seqids 不接受空格/中文/连字符）；
    · 头在全文件内唯一（blast_runner._deduplicate_fasta 会静默丢弃重复头）；
    · 本模块不依赖 tkinter，只被 GUI 处理器函数内懒加载 import。

ID 规则（两种都支持）：
    每行若填「自定义ID」→ 原样作 FASTA 头（须合法且全文件唯一）；
    否则若填「基因名」→ 自动 ``<基因名>_sg<序号>``（各基因名从 1 各自计数）；
    两者皆空 → 报错。

返回约定：
    convert_xlsx_to_fasta 返回 dict；文件级错误（文件不存在/打不开/找不到表头/无数据行）
    以 FileNotFoundError / ValueError 抛出，由调用方（GUI）捕获提示。
"""

import os
import re

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
TEMPLATE_COLUMNS = ["基因名(可选)", "自定义ID(可选)", "sgRNA序列(必填)", "备注(可选)"]

SHEET_DATA = "sgRNA文库"       # 第一个 Sheet，数据区
SHEET_HELP = "填写说明"        # 第二个 Sheet，纯说明

SGRNA_LEN_MIN = 17            # 硬错误：短于此
SGRNA_LEN_MAX = 25            # 硬错误：长于此
SGRNA_LEN_TYPICAL = (18, 22)  # 此区间为典型 sgRNA spacer，之外仅警告
BASE_CHARS = set("ACGTN")      # 允许的碱基（自动转大写，不允许 U）

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")  # BLAST -parse_seqids 安全的头字符集

# 样式
_HEADER_FILL = PatternFill("solid", fgColor="4472C4")
_HEADER_FONT = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
_THIN = Side(style="thin", color="BFBFBF")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HELP_HEAD_FONT = Font(name="微软雅黑", size=13, bold=True, color="1F4E79")
_HELP_FONT = Font(name="微软雅黑", size=10)


# --------------------------------------------------------------------------- #
# 模板生成
# --------------------------------------------------------------------------- #
def write_template(path: str) -> None:
    """生成两 Sheet 的录入模板：数据 Sheet 只含表头行（无示例数据，杜绝误带）。

    数据 Sheet 首行即表头：基因名(可选) | 自定义ID(可选) | sgRNA序列(必填) | 备注(可选)。
    「填写说明」Sheet 用文字说明两套 ID 规则与序列要求。
    """
    wb = Workbook()

    # ---- 数据 Sheet ----
    ws = wb.active
    ws.title = SHEET_DATA
    widths = [26, 28, 34, 32]
    for c, (col, width) in enumerate(zip(TEMPLATE_COLUMNS, widths), start=1):
        cell = ws.cell(row=1, column=c, value=col)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _BORDER
        ws.column_dimensions[get_column_letter(c)].width = width
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(TEMPLATE_COLUMNS))}1"

    # ---- 填写说明 Sheet ----
    ws2 = wb.create_sheet(SHEET_HELP)
    ws2.column_dimensions["A"].width = 120
    lines = [
        ("📋 填写说明", _HELP_HEAD_FONT),
        ("", _HELP_FONT),
        ("1. 本表用于录入 sgRNA 文库：每行填写一条 sgRNA。转换成功后会自动生成参考库 FASTA，并填入主界面的「Reference FASTA」，可直接开始分析。", _HELP_FONT),
        ("", _HELP_FONT),
        ("2. 每列含义：", _HELP_FONT),
        ("    · 基因名(可选)：靶基因/靶点名称，如 GAPDH、TP53。仅用于自动生成 FASTA 头，可留空。", _HELP_FONT),
        ("    · 自定义ID(可选)：想完全自定义本条 FASTA 头时填写；只允许英文字母/数字/下划线，且全表不能重复。", _HELP_FONT),
        ("    · sgRNA序列(必填)：仅填 spacer 序列，不要包含 PAM/NGG。只允许 A/C/G/T/N（不区分大小写，自动转大写、去空格）。", _HELP_FONT),
        ("    · 备注(可选)：仅作记录，不写入 FASTA。", _HELP_FONT),
        ("", _HELP_FONT),
        ("3. FASTA 头（ID）怎么定？每行二选一：", _HELP_FONT),
        ("    · 填了「自定义ID」→ 用它。例：KD01_P53 → >KD01_P53", _HELP_FONT),
        ("    · 没填「自定义ID」但填了「基因名」→ 自动为 基因名_sg序号。例：GAPDH 的第 3 条 → >GAPDH_sg3", _HELP_FONT),
        ("    · 两列都空 → 该行报错。注意：FASTA 头就是分析报告中该 sgRNA 显示的名字，请让它有辨识度。", _HELP_FONT),
        ("", _HELP_FONT),
        ("4. 序列长度：典型 sgRNA spacer 为 18–22 nt，本工具接受 17–25 nt（超出会报错）。", _HELP_FONT),
        ("", _HELP_FONT),
        ("5. 特殊字符自动处理：基因名中的空格/连字符/中文等会被转成下划线（如 HLA-A → HLA_A_sg1）；若因此无法生成合法 ASCII 头（例如纯中文基因名），该行会报错，请在「自定义ID」列手动填写一个英文/数字 ID。", _HELP_FONT),
        ("", _HELP_FONT),
        ("6. 校验策略：只要有一行出错，本次就不会生成 FASTA；软件会逐行列出全部错误，修正后重新点「② 读取 Excel → 转换 FASTA」即可。", _HELP_FONT),
    ]
    for i, (text, font) in enumerate(lines, start=1):
        cell = ws2.cell(row=i, column=1, value=text)
        cell.font = font
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    wb.save(path)


# --------------------------------------------------------------------------- #
# Excel → FASTA 转换
# --------------------------------------------------------------------------- #
def _find_header_row(ws, max_scan=10):
    """定位表头行（容忍用户自加标题行），返回 1-based 行号；找不到返回 None。"""
    last = min(ws.max_row, max_scan)
    for r in range(1, last + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(row=r, column=c).value
            if v is not None and "sgRNA" in str(v) and "序列" in str(v):
                return r
    return None


def _locate_columns(ws, header_row):
    """按子串匹配表头各列，返回 {gene, custom, seq, remark}（1-based 列号，缺为 None）。"""
    cols = {"gene": None, "custom": None, "seq": None, "remark": None}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=header_row, column=c).value
        if v is None:
            continue
        t = str(v).strip()
        if cols["seq"] is None and "sgRNA" in t and "序列" in t:
            cols["seq"] = c
        elif cols["custom"] is None and ("自定义ID" in t or t.upper() == "ID"):
            cols["custom"] = c
        elif cols["gene"] is None and "基因名" in t:
            cols["gene"] = c
        elif cols["remark"] is None and "备注" in t:
            cols["remark"] = c
    return cols


def _sanitize_gene(gene: str) -> str:
    """把基因名清洗为 BLAST 安全的 ASCII token；清洗后为空表示无法生成合法头。"""
    return re.sub(r"[^A-Za-z0-9_]+", "_", gene).strip("_")


def convert_xlsx_to_fasta(xlsx_path: str, out_fasta: str | None = None) -> dict:
    """读取填好的 xlsx，校验并写出参考库 FASTA。

    返回 dict：
        ok / fasta_path / entries / auto_ids / custom_ids
        errors: list[(row 或 "文件", msg)]    —— 非空则 ok=False 且不写盘
        warnings: list[(row 或 "文件", msg)]   —— 不阻塞

    文件级问题（文件不存在/打不开/找不到表头/无数据行）抛 FileNotFoundError / ValueError。
    """
    out_fasta = out_fasta or (os.path.splitext(xlsx_path)[0] + ".fasta")

    if not os.path.exists(xlsx_path):
        raise FileNotFoundError(f"文件不存在：{xlsx_path}")

    try:
        wb = load_workbook(xlsx_path, data_only=True, read_only=False)
    except Exception as exc:  # PermissionError（文件被占用）/ 格式损坏等
        raise ValueError(
            f"无法打开 Excel 文件（{exc}）。\n如果文件正在被 Excel/WPS 打开，请先关闭后再试。"
        ) from exc

    ws = wb[SHEET_DATA] if SHEET_DATA in wb.sheetnames else wb[wb.sheetnames[0]]

    header_row = _find_header_row(ws)
    if header_row is None:
        raise ValueError("未找到表头行（需包含「sgRNA序列(必填)」列），请使用本软件生成的模板。")

    cols = _locate_columns(ws, header_row)
    if cols["seq"] is None:
        raise ValueError("模板缺少「sgRNA序列」列，请使用本软件生成的模板。")

    errors: list = []            # [(row, msg)]
    warnings: list = []          # [(row, msg)]
    entries: list = []           # [(header, seq)]，仅收集校验通过的行
    auto_ids = 0
    custom_ids = 0
    token_counter: dict = {}     # 基因 token -> 已生成条数（用于 _sgN 计数）
    header_first_row: dict = {}  # header -> 首次出现的 Excel 行号（重复提示用）

    def cell_str(r, c):
        v = ws.cell(row=r, column=c).value if c is not None else None
        return str(v).strip() if v is not None else ""

    for r in range(header_row + 1, ws.max_row + 1):
        gene = cell_str(r, cols["gene"])
        custom = cell_str(r, cols["custom"])
        seq = re.sub(r"\s+", "", cell_str(r, cols["seq"])).upper()

        if gene == "" and custom == "" and seq == "":
            continue  # 全空行跳过

        row_errors = []
        row_warnings = []

        # ---- 序列校验 ----
        if seq == "":
            row_errors.append("sgRNA序列为空")
        else:
            bad = sorted({ch for ch in seq if ch not in BASE_CHARS})
            if bad:
                row_errors.append(f"sgRNA序列含非法字符：{''.join(bad)}（只允许 A/C/G/T/N）")
            else:
                n = len(seq)
                if n < SGRNA_LEN_MIN or n > SGRNA_LEN_MAX:
                    row_errors.append(
                        f"sgRNA序列长度 {n} nt，超出允许范围 {SGRNA_LEN_MIN}–{SGRNA_LEN_MAX}"
                    )
                elif not (SGRNA_LEN_TYPICAL[0] <= n <= SGRNA_LEN_TYPICAL[1]):
                    row_warnings.append(
                        f"sgRNA序列长度 {n} nt 不典型（常见 {SGRNA_LEN_TYPICAL[0]}–{SGRNA_LEN_TYPICAL[1]} nt），"
                        f"如比对结果为空请检查 BLAST 比对长度参数"
                    )

        # ---- ID 确定（序列已合法时）----
        header = None
        if not row_errors:
            if custom:
                if not SAFE_ID_RE.match(custom):
                    row_errors.append(
                        "自定义ID含非法字符，仅允许英文字母/数字/下划线，不能含空格/中文/连字符"
                    )
                else:
                    header = custom
                    custom_ids += 1
            elif gene:
                token = _sanitize_gene(gene)
                if token == "":
                    row_errors.append(
                        "基因名无法生成合法的 ASCII ID（需至少含一个英文字母或数字）；"
                        "请在「自定义ID」列手动填写"
                    )
                else:
                    if token != gene:
                        row_warnings.append(f"基因名「{gene}」已转成 ASCII ID 前缀「{token}」")
                    token_counter[token] = token_counter.get(token, 0) + 1
                    header = f"{token}_sg{token_counter[token]}"
                    auto_ids += 1
            else:
                row_errors.append("「基因名」与「自定义ID」均为空")

        errors.extend((r, m) for m in row_errors)
        warnings.extend((r, m) for m in row_warnings)

        # ---- 校验通过则收录（含全文件唯一网）----
        if header is not None and not row_errors:
            if header in header_first_row:
                errors.append((r, f"FASTA 头重复：{header}（与第 {header_first_row[header]} 行重复）"))
            else:
                header_first_row[header] = r
                entries.append((header, seq))

    # 全空数据 → 不允许写出 0 条记录的参考库
    if not entries and not errors:
        errors.append(("文件", "Excel 中没有找到任何数据行"))

    if errors:
        return {
            "ok": False,
            "fasta_path": out_fasta,
            "entries": 0,
            "auto_ids": 0,
            "custom_ids": 0,
            "errors": errors,
            "warnings": warnings,
        }

    # 全部通过 → 写 FASTA（LF 行尾，ASCII 编码）
    with open(out_fasta, "w", newline="\n", encoding="ascii") as f:
        for header, seq in entries:
            f.write(f">{header}\n{seq}\n")

    return {
        "ok": True,
        "fasta_path": out_fasta,
        "entries": len(entries),
        "auto_ids": auto_ids,
        "custom_ids": custom_ids,
        "errors": [],
        "warnings": warnings,
    }
