"""Interface desktop (CustomTkinter): escolher pasta, marcar skills, analisar e abrir o relatório."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from . import __version__
from . import report as report_mod
from . import updater
from .changes import MODES, ChangesError, resolve_scope
from .i18n import LANGUAGES, get_language, set_language, t
from .models import Finding, Report, Severity, SkillResult
from .runner import run_review
from .skills import all_skills

CONFIG_DIR = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "CodeReviewLocal"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_OUT = Path.home() / "Documents" / "CodeReviewLocal"
MAX_RECENT = 10
CATEGORIES = ["Segurança", "Qualidade", "Manutenibilidade", "Testes", "Padrões"]
THEMES = ("system", "light", "dark")

# cores (claro, escuro)
ACCENT = ("#4f46e5", "#6366f1")
ACCENT_HOVER = ("#4338ca", "#4f46e5")
BG = ("#f4f5f9", "#0f1117")
SURFACE = ("#ffffff", "#181b24")
SURFACE_2 = ("#eef0f6", "#222633")
BORDER = ("#e2e5ee", "#2a2f3d")
TEXT = ("#111827", "#e8eaf0")
MUTED = ("#6b7280", "#9aa1b2")
SEV_COLORS = {Severity.CRITICA: ("#991b1b", "#f87171"), Severity.ALTA: ("#dc2626", "#fb7185"),
              Severity.MEDIA: ("#d97706", "#fbbf24"), Severity.BAIXA: ("#2563eb", "#60a5fa"),
              Severity.INFO: ("#6b7280", "#9ca3af")}
OK_COLOR = ("#15803d", "#4ade80")
ERR_COLOR = ("#b91c1c", "#f87171")
CHIP_COLS = 4
GRADE_COLORS = {"A": "#16a34a", "B": "#65a30d", "C": "#d97706", "D": "#ea580c", "E": "#dc2626"}
FONT = "Segoe UI"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])  # noqa: S603


def pick(color: tuple[str, str]) -> str:
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]


class App(ctk.CTk):
    def __init__(self) -> None:
        self.cfg = load_config()
        ctk.set_appearance_mode(self.cfg.get("theme", "system"))
        super().__init__(fg_color=BG)
        set_language(self.cfg.get("lang", "pt"))
        self.title(f"CodeReview Local {__version__}")
        self.geometry("1280x800")
        self.minsize(1040, 640)

        self.skills = all_skills()
        enabled = set(self.cfg.get("skills", [s.id for s in self.skills]))
        self.skill_vars = {s.id: tk.BooleanVar(value=s.id in enabled) for s in self.skills}
        self.fmt_md = tk.BooleanVar(value=self.cfg.get("md", True))
        self.fmt_pdf = tk.BooleanVar(value=self.cfg.get("pdf", True))
        self.project = tk.StringVar(value=(self.cfg.get("recent") or [""])[0])
        self.out_dir = tk.StringVar(value=self.cfg.get("out_dir", str(DEFAULT_OUT)))
        self.scope_mode = self.cfg.get("scope", "tudo") if self.cfg.get("scope") in MODES else "tudo"
        self.sev_filter: Severity | None = None
        self.events: queue.Queue = queue.Queue()
        self.report: Report | None = None
        self.saved: list[Path] = []
        self._rows: dict[str, Finding] = {}
        # análise em andamento: sobrevive a trocas de idioma, que redesenham a tela
        self.running = False
        self.run_skills: list = []
        self.skill_state: dict[str, SkillResult | str] = {}  # "wait" | "run" | resultado
        self.live: list[Finding] = []
        self.run_started = 0.0
        self.container: ctk.CTkFrame | None = None

        self.update_info: updater.Update | None = None
        self.update_events: queue.Queue = queue.Queue()
        self.check_updates = tk.BooleanVar(value=self.cfg.get("check_updates", True))

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.check_updates.get():
            self.after(1500, self._check_updates)

    # ---------- layout ----------
    def _font(self, size=13, weight="normal") -> ctk.CTkFont:
        return ctk.CTkFont(family=FONT, size=size, weight=weight)

    def _build(self) -> None:
        if self.container:
            self.container.destroy()
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.container.grid_columnconfigure(1, weight=1)
        self.container.grid_rowconfigure(0, weight=1)
        self._build_sidebar(self.container).grid(row=0, column=0, sticky="nsw")
        self._build_main(self.container).grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self._style_tree()
        if self.run_skills:
            self._render_chips()
        if self.report:
            self._show_summary()
        elif self.running:
            self._show_live()
            self.btn_run.configure(state="disabled")

    def _build_sidebar(self, parent) -> ctk.CTkFrame:
        side = ctk.CTkFrame(parent, width=360, corner_radius=0, fg_color=SURFACE, border_width=0)
        side.grid_propagate(False)
        side.grid_rowconfigure(2, weight=1)
        side.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(side, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(22, 4))
        ctk.CTkLabel(head, text="◆  CodeReview Local", font=self._font(19, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(head, text=t("ui.subtitle"), font=self._font(12), text_color=MUTED,
                     wraplength=310, justify="left").pack(anchor="w", pady=(4, 0))

        bar = ctk.CTkFrame(side, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(14, 4))
        ctk.CTkLabel(bar, text=t("ui.skills").upper(), font=self._font(11, "bold"), text_color=MUTED).pack(side="left")
        ctk.CTkButton(bar, text=t("ui.none"), width=64, height=24, font=self._font(11), fg_color="transparent",
                      text_color=MUTED, hover_color=SURFACE_2, command=lambda: self._set_all(False)).pack(side="right")
        ctk.CTkButton(bar, text=t("ui.all"), width=56, height=24, font=self._font(11), fg_color="transparent",
                      text_color=ACCENT, hover_color=SURFACE_2, command=lambda: self._set_all(True)).pack(side="right")

        scroll = ctk.CTkScrollableFrame(side, fg_color="transparent")
        scroll.grid(row=2, column=0, sticky="nsew", padx=10)
        for cat in CATEGORIES:
            items = [s for s in self.skills if s.category == cat]
            if not items:
                continue
            ctk.CTkLabel(scroll, text=t(f"cat.{cat}"), font=self._font(12, "bold"),
                         text_color=TEXT).pack(anchor="w", padx=10, pady=(12, 4))
            for s in items:
                sw = ctk.CTkSwitch(scroll, text=s.title, variable=self.skill_vars[s.id], font=self._font(12),
                                   text_color=TEXT, progress_color=ACCENT, switch_width=34, switch_height=18)
                sw.pack(anchor="w", padx=10, pady=3)
                _Tooltip(sw, s.description)

        cfg = ctk.CTkFrame(side, fg_color=SURFACE_2, corner_radius=12)
        cfg.grid(row=3, column=0, sticky="ew", padx=16, pady=16)
        cfg.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cfg, text=t("ui.report").upper(), font=self._font(11, "bold"),
                     text_color=MUTED).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 4))
        fm = ctk.CTkFrame(cfg, fg_color="transparent")
        fm.grid(row=1, column=0, columnspan=2, sticky="w", padx=10)
        for label, var in (("PDF", self.fmt_pdf), ("Markdown", self.fmt_md)):
            ctk.CTkCheckBox(fm, text=label, variable=var, font=self._font(12), text_color=TEXT, fg_color=ACCENT,
                            hover_color=ACCENT_HOVER, checkbox_width=18, checkbox_height=18,
                            corner_radius=5).pack(side="left", padx=4)
        out = ctk.CTkFrame(cfg, fg_color="transparent")
        out.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(8, 4))
        out.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(out, textvariable=self.out_dir, height=30, font=self._font(11), fg_color=SURFACE,
                     border_color=BORDER, text_color=TEXT).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(out, text="…", width=32, height=30, fg_color=SURFACE, text_color=TEXT, border_width=1,
                      border_color=BORDER, hover_color=BORDER, command=self.browse_out).grid(row=0, column=1, padx=(6, 0))

        ctk.CTkLabel(cfg, text=t("ui.language"), font=self._font(12), text_color=MUTED).grid(
            row=3, column=0, sticky="w", padx=14, pady=(10, 4))
        lang = ctk.CTkOptionMenu(cfg, values=list(LANGUAGES.values()), command=self._change_language, height=28,
                                 font=self._font(12), fg_color=SURFACE, button_color=BORDER, text_color=TEXT,
                                 button_hover_color=ACCENT_HOVER)
        lang.set(LANGUAGES[get_language()])
        lang.grid(row=3, column=1, sticky="ew", padx=(0, 14), pady=(10, 4))
        ctk.CTkLabel(cfg, text=t("ui.appearance"), font=self._font(12), text_color=MUTED).grid(
            row=4, column=0, sticky="w", padx=14, pady=(4, 14))
        self._theme_labels = {t(f"ui.theme.{k}"): k for k in THEMES}
        theme = ctk.CTkSegmentedButton(cfg, values=list(self._theme_labels), command=self._change_theme,
                                       font=self._font(11), selected_color=ACCENT, selected_hover_color=ACCENT_HOVER)
        theme.set(t(f"ui.theme.{self.cfg.get('theme', 'system')}"))
        theme.grid(row=4, column=1, sticky="ew", padx=(0, 14), pady=(4, 6))
        ctk.CTkSwitch(cfg, text=t("upd.setting"), variable=self.check_updates, font=self._font(12), text_color=TEXT,
                      progress_color=ACCENT, switch_width=34, switch_height=18, command=self._persist).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=14, pady=(6, 14))
        ctk.CTkLabel(cfg, text=f"v{__version__}", font=self._font(11), text_color=MUTED).grid(
            row=5, column=1, sticky="e", padx=14, pady=(6, 14))
        return side

    def _build_main(self, parent) -> ctk.CTkFrame:
        main = ctk.CTkFrame(parent, fg_color="transparent")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        # aviso de atualização (aparece só quando há versão nova)
        self.banner = ctk.CTkFrame(main, fg_color=("#eef2ff", "#1e2140"), corner_radius=14, border_width=1,
                                   border_color=ACCENT)
        self.banner_lbl = ctk.CTkLabel(self.banner, text="", font=self._font(13, "bold"), text_color=TEXT)
        self.banner_lbl.pack(side="left", padx=16, pady=10)
        ctk.CTkButton(self.banner, text=t("upd.later"), width=80, height=30, font=self._font(12),
                      fg_color="transparent", text_color=MUTED, hover_color=SURFACE_2,
                      command=self.banner.grid_remove).pack(side="right", padx=(4, 12))
        ctk.CTkButton(self.banner, text=t("upd.notes"), width=100, height=30, font=self._font(12), fg_color=SURFACE_2,
                      text_color=TEXT, hover_color=BORDER,
                      command=lambda: self._open_url(self.update_info.page_url)).pack(side="right", padx=4)
        self.btn_update = ctk.CTkButton(self.banner, text="⬆  " + t("upd.install"), width=150, height=30,
                                        font=self._font(12, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                        command=self._install_update)
        self.btn_update.pack(side="right", padx=4)
        if self.update_info:
            self._show_update_banner()

        # busca da pasta
        search = ctk.CTkFrame(main, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        search.grid(row=1, column=0, sticky="ew")
        search.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(search, text=t("ui.folder"), font=self._font(12, "bold"), text_color=MUTED).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 2))
        # escopo: projeto inteiro, só as alterações não commitadas ou a branch comparada com a main
        scope_bar = ctk.CTkFrame(search, fg_color="transparent")
        scope_bar.grid(row=0, column=0, sticky="e", padx=(16, 8), pady=(10, 4))
        scope_lbl = ctk.CTkLabel(scope_bar, text=t("ui.scope") + " ⓘ", font=self._font(12), text_color=MUTED)
        scope_lbl.grid(row=0, column=0, padx=(0, 8))
        _Tooltip(scope_lbl, t("ui.scope.tip"))  # CTkSegmentedButton não aceita bind
        self._scope_labels = {t(f"scope.opt.{m}"): m for m in MODES}
        scope = ctk.CTkSegmentedButton(scope_bar, values=list(self._scope_labels), font=self._font(11),
                                       selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                                       command=self._change_scope)
        scope.set(t(f"scope.opt.{self.scope_mode}"))
        scope.grid(row=0, column=1)
        self.combo = ctk.CTkComboBox(search, variable=self.project, values=self.cfg.get("recent", []) or [""],
                                     height=40, font=self._font(13), fg_color=SURFACE_2, border_color=BORDER,
                                     button_color=BORDER, text_color=TEXT, dropdown_font=self._font(12))
        self.combo.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=(0, 14))
        if not self.project.get():
            self.combo.set("")
        self.combo.bind("<Return>", lambda _e: self.start())
        ctk.CTkButton(search, text=t("ui.browse"), height=40, width=120, font=self._font(13), fg_color=SURFACE_2,
                      text_color=TEXT, hover_color=BORDER, border_width=1, border_color=BORDER,
                      command=self.browse).grid(row=1, column=1, padx=4, pady=(0, 14))
        self.btn_run = ctk.CTkButton(search, text="▶  " + t("ui.analyze"), height=40, width=150,
                                     font=self._font(14, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                     command=self.start)
        self.btn_run.grid(row=1, column=2, padx=(4, 16), pady=(0, 14))

        # resumo
        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.grid(row=2, column=0, sticky="ew", pady=16)
        for i in range(6):
            cards.grid_columnconfigure(i, weight=2 if i == 0 else 1, uniform="cards" if i else None)
        score = ctk.CTkFrame(cards, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        score.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(score, text=t("ui.score").upper(), font=self._font(11, "bold"), text_color=MUTED).pack(
            anchor="w", padx=16, pady=(12, 0))
        row = ctk.CTkFrame(score, fg_color="transparent")
        row.pack(anchor="w", padx=16, pady=(0, 12))
        self.score_lbl = ctk.CTkLabel(row, text="–", font=self._font(36, "bold"), text_color=TEXT)
        self.score_lbl.pack(side="left")
        self.grade_lbl = ctk.CTkLabel(row, text="", font=self._font(12, "bold"), text_color="white",
                                      fg_color="transparent", corner_radius=8, height=26)
        self.grade_lbl.pack(side="left", padx=12)
        self.count_lbls: dict[Severity, ctk.CTkLabel] = {}
        self.sev_cards: dict[Severity, ctk.CTkFrame] = {}
        for i, sev in enumerate(sorted(Severity, reverse=True), 1):
            card = ctk.CTkFrame(cards, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER,
                                cursor="hand2")
            card.grid(row=0, column=i, sticky="nsew", padx=4)
            dot = ctk.CTkLabel(card, text=f"●  {sev.label}", font=self._font(12, "bold"), text_color=SEV_COLORS[sev])
            dot.pack(anchor="w", padx=14, pady=(12, 0))
            n = ctk.CTkLabel(card, text="0", font=self._font(26, "bold"), text_color=TEXT)
            n.pack(anchor="w", padx=14, pady=(0, 10))
            for w in (card, dot, n):
                w.bind("<Button-1>", lambda _e, s=sev: self._toggle_filter(s))
            self.count_lbls[sev] = n
            self.sev_cards[sev] = card

        # lista de achados
        panel = ctk.CTkFrame(main, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        panel.grid(row=3, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(panel, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        ctk.CTkLabel(top, text=t("ui.findings_title"), font=self._font(15, "bold"), text_color=TEXT).pack(side="left")
        self.filter_lbl = ctk.CTkLabel(top, text="", font=self._font(12), text_color=MUTED)
        self.filter_lbl.pack(side="left", padx=10)
        self.btn_dir = self._action(top, "📁  " + t("ui.open_dir"), lambda: open_path(Path(self.out_dir.get())))
        self.btn_md = self._action(top, "📝  " + t("ui.open_md"), lambda: self._open_saved(".md"))
        self.btn_pdf = self._action(top, "📄  " + t("ui.open_pdf"), lambda: self._open_saved(".pdf"), accent=True)

        holder = tk.Frame(panel, bd=0, highlightthickness=0, bg=pick(SURFACE))
        holder.grid(row=1, column=0, sticky="nsew", padx=12)
        self._tree_holder = holder
        cols = ("sev", "loc", "skill", "msg")
        self.tree = ttk.Treeview(holder, columns=cols, show="headings", style="CR.Treeview")
        for c, title, w in zip(cols, (t("r.severity"), t("r.location"), t("r.skill"), t("r.problem")),
                               (110, 280, 150, 540)):
            self.tree.heading(c, text=title, anchor="w")
            self.tree.column(c, width=w, stretch=(c == "msg"), anchor="w")
        sb = ctk.CTkScrollbar(holder, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._show_detail)
        self.empty_lbl = ctk.CTkLabel(holder, text=t("ui.empty"), font=self._font(13), text_color=MUTED,
                                      fg_color=SURFACE)
        self.empty_lbl.place(relx=0.5, rely=0.45, anchor="center")

        self.detail = ctk.CTkTextbox(panel, height=96, font=self._font(12), fg_color=SURFACE_2, text_color=TEXT,
                                     corner_radius=10, wrap="word")
        self.detail.grid(row=2, column=0, sticky="ew", padx=16, pady=12)
        self._set_detail(t("ui.select_finding"))

        # andamento: barra, contador e uma etiqueta por skill
        bottom = ctk.CTkFrame(main, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        bottom.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        bottom.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(bottom, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 4))
        self.status = ctk.CTkLabel(head, text=t("ui.ready"), font=self._font(13, "bold"), text_color=TEXT, anchor="w")
        self.status.pack(side="left")
        self.pct_lbl = ctk.CTkLabel(head, text="", font=self._font(13, "bold"), text_color=ACCENT)
        self.pct_lbl.pack(side="right")
        self.progress = ctk.CTkProgressBar(bottom, height=12, corner_radius=6, progress_color=ACCENT,
                                           fg_color=SURFACE_2)
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.chips = ctk.CTkFrame(bottom, fg_color="transparent")
        self.chips.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        for c in range(CHIP_COLS):
            self.chips.grid_columnconfigure(c, weight=1, uniform="chip")
        self._chip_lbls: dict[str, ctk.CTkLabel] = {}
        self._chip_tips: set[str] = set()
        return main

    def _action(self, parent, text, command, accent=False) -> ctk.CTkButton:
        b = ctk.CTkButton(parent, text=text, height=30, font=self._font(12), state="disabled", command=command,
                          fg_color=ACCENT if accent else SURFACE_2, hover_color=ACCENT_HOVER if accent else BORDER,
                          text_color=("white", "white") if accent else TEXT, text_color_disabled=MUTED)
        b.pack(side="right", padx=(6, 0))
        return b

    def _style_tree(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        bg, fg, head, sel = pick(SURFACE), pick(TEXT), pick(SURFACE_2), pick(("#e0e7ff", "#2e3350"))
        style.configure("CR.Treeview", background=bg, fieldbackground=bg, foreground=fg, rowheight=30,
                        borderwidth=0, font=(FONT, 10))
        style.configure("CR.Treeview.Heading", background=head, foreground=pick(MUTED), relief="flat",
                        font=(FONT, 10, "bold"), padding=(8, 6))
        style.map("CR.Treeview.Heading", background=[("active", head)])
        style.map("CR.Treeview", background=[("selected", sel)], foreground=[("selected", fg)])
        style.layout("CR.Treeview", [("CR.Treeview.treearea", {"sticky": "nswe"})])
        for sev, color in SEV_COLORS.items():
            self.tree.tag_configure(sev.name, foreground=pick(color))
        self.tree.tag_configure("odd", background=pick(("#fafbfd", "#1c1f2a")))
        self._tree_holder.configure(bg=bg)

    # ---------- ações ----------
    def browse(self) -> None:
        d = filedialog.askdirectory(title=t("ui.pick_project"), initialdir=self.project.get() or None)
        if d:
            self.project.set(d)
            self.combo.set(d)

    def browse_out(self) -> None:
        d = filedialog.askdirectory(title=t("ui.pick_output"), initialdir=self.out_dir.get() or None)
        if d:
            self.out_dir.set(d)

    def _set_all(self, value: bool) -> None:
        for v in self.skill_vars.values():
            v.set(value)

    def start(self) -> None:
        project = self.combo.get().strip().strip('"')
        if not project or not Path(project).is_dir():
            messagebox.showwarning("CodeReview Local", t("ui.invalid_folder"))
            return
        chosen = [s for s in self.skills if self.skill_vars[s.id].get()]
        if not chosen:
            messagebox.showwarning("CodeReview Local", t("ui.no_skill"))
            return
        self.project.set(project)
        self._remember(project)
        self.btn_run.configure(state="disabled")
        for b in (self.btn_pdf, self.btn_md, self.btn_dir):
            b.configure(state="disabled")
        self.report, self.saved, self.live = None, [], []
        self.running, self.run_started = True, time.monotonic()
        self.run_skills = chosen
        self.skill_state = {s.id: "wait" for s in chosen}
        self.score_lbl.configure(text="…")
        self.grade_lbl.configure(text="", fg_color="transparent")
        self._render_chips()
        self._show_live()
        self.after(250, self._tick)
        formats = [f for f, v in (("md", self.fmt_md), ("pdf", self.fmt_pdf)) if v.get()]
        threading.Thread(target=self._worker, args=(project, chosen, formats, self.out_dir.get(), self.scope_mode),
                         daemon=True).start()
        self.after(100, self._poll)

    def _worker(self, project, skills, formats, out_dir, mode) -> None:
        try:
            scope = resolve_scope(project, mode)
            rep = run_review(project, skills, scope=scope,
                             progress=lambda title, r: self.events.put(("progress", title, r)))
            try:
                saved, save_error = (report_mod.save(rep, out_dir, formats) if formats else []), None
            except Exception as e:  # falha no relatório não pode jogar fora a análise
                saved, save_error = [], e
            self.events.put(("done", rep, (saved, save_error)))
        except ChangesError as e:
            self.events.put(("info", e, None))
        except Exception as e:  # mostra qualquer falha na tela em vez de travar
            self.events.put(("error", e, None))

    def _poll(self) -> None:
        try:
            while True:
                kind, a, b = self.events.get_nowait()
                if kind == "progress":
                    skill = next((s for s in self.run_skills if s.title == a), None)
                    if skill:
                        self.skill_state[skill.id] = b if b is not None else "run"
                        self._update_chip(skill.id)
                    if b is not None:  # achados aparecem na lista assim que cada skill termina
                        self.live.extend(b.findings)
                        self._show_live()
                elif kind == "done":
                    self._finish(a, *b)
                    return
                elif kind in ("info", "error"):
                    self._stop_run()
                    self.status.configure(text=str(a) if kind == "info" else t("ui.error"))
                    (messagebox.showinfo if kind == "info" else messagebox.showerror)("CodeReview Local", str(a))
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _finish(self, rep: Report, saved: list[Path], save_error: Exception | None = None) -> None:
        self.report, self.saved = rep, saved
        self._stop_run()
        self.progress.set(1)
        self.pct_lbl.configure(text="100%")
        self._show_summary()
        if save_error:
            messagebox.showwarning("CodeReview Local", t("ui.save_failed", e=save_error))

    def _stop_run(self) -> None:
        self.running = False
        self.btn_run.configure(state="normal")

    # ---------- andamento ----------
    def _chip_look(self, sid: str):
        state = self.skill_state.get(sid, "wait")
        if state == "wait":
            return "○", MUTED, SURFACE_2
        if state == "run":
            return "◐◓◑◒"[int(time.monotonic() * 4) % 4], ACCENT, ("#e0e7ff", "#2e3350")
        if state.status == "ok":
            return f"✓ {len(state.findings)}", OK_COLOR, SURFACE_2
        if state.status == "skipped":
            return "–", MUTED, SURFACE_2
        return "✗", ERR_COLOR, SURFACE_2

    def _render_chips(self) -> None:
        for w in self.chips.winfo_children():
            w.destroy()
        self._chip_lbls, self._chip_tips = {}, set()
        for i, skill in enumerate(self.run_skills):
            lbl = ctk.CTkLabel(self.chips, text="", font=self._font(11), corner_radius=8, height=22, anchor="w")
            lbl.grid(row=i // CHIP_COLS, column=i % CHIP_COLS, sticky="ew", padx=3, pady=2)
            self._chip_lbls[skill.id] = lbl
            self._update_chip(skill.id)
        self._update_counter()

    def _update_chip(self, sid: str) -> None:
        lbl = self._chip_lbls.get(sid)
        if not lbl:
            return
        skill = next(s for s in self.run_skills if s.id == sid)
        icon, color, bg = self._chip_look(sid)
        state = self.skill_state.get(sid)
        title = skill.title if len(skill.title) <= 27 else skill.title[:26] + "…"
        lbl.configure(text=f"  {icon}  {title}", text_color=color, fg_color=bg)
        if isinstance(state, SkillResult) and state.status != "ok" and sid not in self._chip_tips:
            self._chip_tips.add(sid)
            _Tooltip(lbl, state.message)
        self._update_counter()

    def _update_counter(self) -> None:
        total = len(self.run_skills)
        done = sum(isinstance(v, SkillResult) for v in self.skill_state.values())
        if not total:
            return
        self.progress.set(done / total)
        self.pct_lbl.configure(text=f"{round(100 * done / total)}%")
        if self.running:
            elapsed = int(time.monotonic() - self.run_started)
            self.status.configure(text=t("ui.progress", done=done, total=total, s=elapsed, n=len(self.live)))

    def _tick(self) -> None:
        if not self.running:
            return
        for sid, state in self.skill_state.items():
            if state == "run":
                self._update_chip(sid)
        self._update_counter()
        self.after(250, self._tick)

    def _show_live(self) -> None:
        counts = {s: 0 for s in Severity}
        for f in self.live:
            counts[f.severity] += 1
        for sev, lbl in self.count_lbls.items():
            lbl.configure(text=str(counts[sev]))
        self._fill_tree()

    def _show_summary(self) -> None:
        rep, saved = self.report, self.saved
        score = rep.score()
        grade = report_mod.grade(score)
        self.score_lbl.configure(text=f"{score}")
        self.grade_lbl.configure(text=f"  {grade}  ", fg_color=GRADE_COLORS[grade[0]])
        counts = rep.counts()
        for sev, lbl in self.count_lbls.items():
            lbl.configure(text=str(counts[sev]))
        self._fill_tree()
        skipped = [r.title for r in rep.results if r.status != "ok"]
        self.status.configure(text=t("ui.done", s=rep.duration_s) + (f" · {t('ui.skipped', n=len(skipped))}" if skipped else "")
                              + (f" · {rep.scope}" if rep.scope else ""))
        self.btn_dir.configure(state="normal" if saved else "disabled")
        self.btn_pdf.configure(state="normal" if any(p.suffix == ".pdf" for p in saved) else "disabled")
        self.btn_md.configure(state="normal" if any(p.suffix == ".md" for p in saved) else "disabled")

    def _toggle_filter(self, sev: Severity) -> None:
        self.sev_filter = None if self.sev_filter == sev else sev
        for s, card in self.sev_cards.items():
            card.configure(border_color=SEV_COLORS[s] if s == self.sev_filter else BORDER,
                           border_width=2 if s == self.sev_filter else 1)
        self._fill_tree()

    def _fill_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows = {}
        source = self.report.findings if self.report else self.live
        if not source and not self.running and not self.report:
            return
        rows = [f for f in sorted(source, key=lambda x: (-x.severity, x.file, x.line))
                if self.sev_filter is None or f.severity == self.sev_filter]
        for i, f in enumerate(rows):
            loc = f"{f.file}:{f.line}" if f.file and f.line else (f.file or t("r.project_level"))
            tags = (f.severity.name, "odd") if i % 2 else (f.severity.name,)
            iid = self.tree.insert("", "end", values=(f"●  {f.severity.label}", loc, f.skill, f.message), tags=tags)
            self._rows[iid] = f
        self.filter_lbl.configure(text=f"{len(rows)}" + (f" · {self.sev_filter.label}" if self.sev_filter else ""))
        if rows:
            self.empty_lbl.place_forget()
        else:
            self.empty_lbl.configure(text=t("r.no_findings") if self.report else
                                     t("ui.analyzing") if self.running else t("ui.empty"))
            self.empty_lbl.place(relx=0.5, rely=0.45, anchor="center")

    def _show_detail(self, _e=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        f = self._rows[sel[0]]
        self._set_detail(f"[{f.severity.label}]  {f.rule_id}   ·   {f.skill}\n{f.message}\n\n"
                         f"💡 {t('ui.suggestion')}: {f.suggestion or '-'}")

    def _set_detail(self, text: str) -> None:
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def _open_saved(self, suffix: str) -> None:
        for p in self.saved:
            if p.suffix == suffix:
                open_path(p)

    # ---------- atualizações ----------
    def _check_updates(self) -> None:
        def worker():
            info = updater.check()
            if info:
                self.update_events.put(info)
        threading.Thread(target=worker, daemon=True).start()
        self.after(300, self._poll_updates)

    def _poll_updates(self, tries: int = 0) -> None:
        try:
            self.update_info = self.update_events.get_nowait()
        except queue.Empty:
            if tries < 40:  # a consulta tem timeout de 6s
                self.after(300, self._poll_updates, tries + 1)
            return
        self._show_update_banner()

    def _show_update_banner(self) -> None:
        self.banner_lbl.configure(text=f"✨  {t('upd.available', v=self.update_info.version)}   "
                                       f"·   {t('upd.current', v=__version__)}")
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 16))

    def _install_update(self) -> None:
        info = self.update_info
        if not updater.can_self_update() or not info.setup_url:
            self._open_url(info.page_url)
            return
        self.btn_update.configure(state="disabled")

        def worker():
            try:
                setup = updater.download(info.setup_url, lambda f: self.after(
                    0, lambda: self.status.configure(text=t("upd.downloading", p=int(f * 100)))))
                self.after(0, lambda: self._run_installer(setup))
            except OSError as e:
                self.after(0, lambda err=e: (self.btn_update.configure(state="normal"),
                                             messagebox.showerror("CodeReview Local", t("upd.failed", e=err))))
        threading.Thread(target=worker, daemon=True).start()

    def _run_installer(self, setup: Path) -> None:
        self.status.configure(text=t("upd.installing"))
        self._persist()
        updater.run_installer(setup)
        self.after(800, self.destroy)

    @staticmethod
    def _open_url(url: str) -> None:
        import webbrowser

        webbrowser.open(url)

    def _change_language(self, label: str) -> None:
        code = next(k for k, v in LANGUAGES.items() if v == label)
        if code == get_language():
            return
        set_language(code)
        self._persist()
        self._build()  # a tela e a lista de achados são redesenhadas no novo idioma

    def _change_theme(self, label: str) -> None:
        mode = self._theme_labels[label]
        self.cfg["theme"] = mode
        ctk.set_appearance_mode(mode)
        self._persist()
        self.after(50, self._style_tree)  # só a lista (ttk) precisa ser recolorida; a análise continua

    def _change_scope(self, label: str) -> None:
        self.scope_mode = self._scope_labels[label]
        self._persist()

    def _remember(self, project: str) -> None:
        recent = [project] + [p for p in self.cfg.get("recent", []) if p != project]
        self.cfg["recent"] = recent[:MAX_RECENT]
        self.combo.configure(values=self.cfg["recent"])
        self._persist()

    def _persist(self) -> None:
        self.cfg.update(lang=get_language(), check_updates=self.check_updates.get(), skills=[k for k, v in self.skill_vars.items() if v.get()],
                        md=self.fmt_md.get(), pdf=self.fmt_pdf.get(), out_dir=self.out_dir.get(),
                        scope=self.scope_mode)
        save_config(self.cfg)

    def _on_close(self) -> None:
        self._persist()
        self.destroy()


class _Tooltip:
    def __init__(self, widget, text: str) -> None:
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _e=None) -> None:
        if self.tip or not self.text:
            return
        x, y = self.widget.winfo_rootx() + 20, self.widget.winfo_rooty() + 26
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#111827", foreground="white", font=(FONT, 9),
                 padx=8, pady=5, wraplength=320, justify="left").pack()

    def hide(self, _e=None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
