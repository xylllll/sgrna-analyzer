"""参数设置对话框"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from . import presets


class ParamDialog(tk.Toplevel):
    def __init__(self, parent, current_params, on_apply):
        super().__init__(parent)
        self.on_apply = on_apply
        self.current_params = dict(current_params)
        self.title("参数设置 — sgRNA Analyzer")
        self.configure(bg="#f5f6fa")
        self.transient(parent)
        self.grab_set()
        self._param_entries = {}
        self._build_ui()

    def _build_ui(self):
        # ── 标题 ──
        h = tk.Frame(self, bg="#2c3e50", height=42)
        h.pack(fill="x"); h.pack_propagate(False)
        tk.Label(h, text="分析参数设置", font=("Microsoft YaHei", 12, "bold"),
                 bg="#2c3e50", fg="white").pack(expand=True)

        # ── 预设选择 ──
        pf = tk.Frame(self, bg="white", padx=12, pady=8)
        pf.pack(fill="x", padx=8, pady=(6, 0))

        r1 = tk.Frame(pf, bg="white"); r1.pack(fill="x")
        tk.Label(r1, text="预设方案:", font=("Microsoft YaHei", 10, "bold"), bg="white").pack(side="left")
        all_p = presets.list_presets()
        self._preset_var = tk.StringVar()
        self._preset_combo = ttk.Combobox(r1, textvariable=self._preset_var,
                                          values=[p["name"] for p in all_p],
                                          state="readonly", width=22,
                                          font=("Microsoft YaHei", 9))
        self._preset_combo.pack(side="left", padx=(6, 10))
        self._preset_combo.bind("<<ComboboxSelected>>", self._on_preset_select)
        tk.Button(r1, text="另存为", font=("Microsoft YaHei", 8), bg="#27ae60", fg="white",
                  relief="flat", padx=8, cursor="hand2", command=self._save_as).pack(side="right", padx=2)
        tk.Button(r1, text="删除", font=("Microsoft YaHei", 8), bg="#e74c3c", fg="white",
                  relief="flat", padx=8, cursor="hand2", command=self._delete_preset).pack(side="right", padx=2)

        # 预设说明
        self._desc_var = tk.StringVar()
        tk.Label(pf, textvariable=self._desc_var, font=("Microsoft YaHei", 8),
                 bg="white", fg="#555", anchor="w", justify="left",
                 wraplength=600).pack(fill="x", pady=(4, 0))

        # ── 参数卡片（直接用 Frame，去掉 canvas 滚动） ──
        pf2 = tk.Frame(self, bg="#f5f6fa", padx=8, pady=4)
        pf2.pack(fill="both", expand=True)

        keys = list(presets.PARAM_INFO.keys())
        for i, key in enumerate(keys):
            name, desc = presets.PARAM_INFO[key]
            val = self.current_params.get(key, "")

            card = tk.Frame(pf2, bg="white", padx=8, pady=4, relief="solid", bd=1)
            card.pack(fill="x", pady=2)

            top = tk.Frame(card, bg="white"); top.pack(fill="x")
            tk.Label(top, text=name, font=("Microsoft YaHei", 9, "bold"),
                     bg="white", fg="#2c3e50").pack(side="left")
            var = tk.StringVar(value=str(val))
            tk.Entry(top, textvariable=var, font=("Consolas", 10),
                     width=10, justify="center").pack(side="right")
            self._param_entries[key] = var

            tk.Label(card, text=desc, font=("Microsoft YaHei", 7),
                     bg="white", fg="#888", anchor="w", wraplength=580,
                     justify="left").pack(fill="x", pady=(1, 0))

        # ── 提示 ──
        tip = tk.Label(self, text="修改参数后需点击 [应用参数] 才能生效",
                       font=("Microsoft YaHei", 8), bg="#fef9e7", fg="#7d6608", pady=4)
        tip.pack(fill="x", padx=8, pady=(4, 0))

        # ── 按钮 ──
        bf = tk.Frame(self, bg="#ecf0f1", padx=12, pady=8)
        bf.pack(side="bottom", fill="x")
        tk.Button(bf, text="应用参数", font=("Microsoft YaHei", 11, "bold"),
                  bg="#27ae60", fg="white", relief="flat", padx=20, pady=6,
                  cursor="hand2", command=self._apply).pack(side="left")
        tk.Button(bf, text="恢复默认", font=("Microsoft YaHei", 9),
                  bg="#95a5a6", fg="white", relief="flat", padx=10, pady=6,
                  cursor="hand2", command=self._reset_default).pack(side="left", padx=6)
        tk.Button(bf, text="取消", font=("Microsoft YaHei", 9),
                  bg="#7f8c8d", fg="white", relief="flat", padx=10, pady=6,
                  cursor="hand2", command=self.destroy).pack(side="right")

        # 匹配当前预设
        self._select_current()

        # 最后设置窗口大小并居中
        self.update_idletasks()
        self.geometry("620x700")
        self.minsize(580, 600)
        x = self.master.winfo_x() + (self.master.winfo_width() - 620) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - 700) // 2
        self.geometry(f"+{x}+{y}")

    def _select_current(self):
        best, bn = 0, None
        for p in presets.list_presets():
            s = sum(1 for k, v in p["params"].items()
                    if str(v) == str(self.current_params.get(k)))
            if s > best: best, bn = s, p["name"]
        if bn:
            self._preset_var.set(bn)
            self._on_preset_select()

    def _on_preset_select(self, event=None):
        name = self._preset_var.get()
        params = presets.get_preset(name)
        for key, var in self._param_entries.items():
            var.set(str(params.get(key, "")))
        for p in presets.list_presets():
            if p["name"] == name:
                self._desc_var.set(p.get("description", ""))
                break

    def _save_as(self):
        name = simpledialog.askstring("保存预设", "预设名称:", parent=self)
        if not name: return
        params = {k: self._parse(k, v.get()) for k, v in self._param_entries.items()}
        presets.save_preset(name, f"用户自定义预设（{name}）", params)
        self._refresh_combo(name)

    def _delete_preset(self):
        name = self._preset_var.get()
        if not name: return
        if not messagebox.askyesno("删除", f"删除预设 '{name}'？\n内置预设不可删除。", parent=self):
            return
        if presets.delete_preset(name):
            self._refresh_combo(None)
        else:
            messagebox.showwarning("提示", "内置预设不可删除。", parent=self)

    def _refresh_combo(self, sel):
        all_p = presets.list_presets()
        self._preset_combo["values"] = [p["name"] for p in all_p]
        if sel: self._preset_var.set(sel)

    def _reset_default(self):
        d = presets.BUILTIN_PRESETS["原始协议默认"]["params"]
        for k, v in self._param_entries.items():
            v.set(str(d.get(k, "")))
        self._preset_var.set("原始协议默认")
        self._desc_var.set(presets.BUILTIN_PRESETS["原始协议默认"]["description"])

    def _parse(self, key, s):
        d = self.current_params.get(key, "")
        try:
            return float(s) if isinstance(d, float) else int(s)
        except ValueError:
            return d

    def _apply(self):
        params = {k: self._parse(k, v.get()) for k, v in self._param_entries.items()}
        name = self._preset_var.get() or "自定义"
        if self.on_apply: self.on_apply(params, name)
        self.destroy()
