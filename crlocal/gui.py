"""Interface desktop (Tkinter): escolher pasta, marcar skills, analisar e abrir o relatório."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from . import report as report_mod
from .i18n import LANGUAGES, get_language, set_language, t
from .models import Report, Severity
from .runner import run_review
from .skills import all_skills

CONFIG_DIR = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "CodeReviewLocal"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_OUT = Path.home() / "Documents" / "CodeReviewLocal"
MAX_RECENT = 10
SEV_TAGS = {Severity.CRITICA: "#7f1d1d", Severity.ALTA: "#dc2626", Severity.MEDIA: "#b45309",
            Severity.BAIXA: "#1d4ed8", Severity.INFO: "#6b7280"}


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


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"CodeReview Local {__version__}")
        self.geometry("1200x780")
        self.minsize(900, 600)
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Score.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        self.cfg = load_config()
        set_language(self.cfg.get("lang", "pt"))
        self.lang = tk.StringVar(value=LANGUAGES[get_language()])
        self.skills = all_skills()
        enabled = set(self.cfg.get("skills", [s.id for s in self.skills]))
        self.skill_vars = {s.id: tk.BooleanVar(value=s.id in enabled) for s in self.skills}
        self.fmt_md = tk.BooleanVar(value=self.cfg.get("md", True))
        self.fmt_pdf = tk.BooleanVar(value=self.cfg.get("pdf", True))
        self.project = tk.StringVar(value=(self.cfg.get("recent") or [""])[0])
        self.out_dir = tk.StringVar(value=self.cfg.get("out_dir", str(DEFAULT_OUT)))
        self.sev_filter = tk.StringVar(value=t("ui.filter_all"))
        self.events: queue.Queue = queue.Queue()
        self.report: Report | None = None
        self.saved: list[Path] = []

        self.container: ttk.Frame | None = None
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- layout ----------
    def _build(self) -> None:
        if self.container:
            self.container.destroy()
        root = self.container = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        top = ttk.Frame(root)
        top.pack(fill="x")
        ttk.Label(top, text="CodeReview Local", style="Title.TLabel").pack(side="left")
        lang = ttk.Combobox(top, textvariable=self.lang, values=list(LANGUAGES.values()), state="readonly", width=11)
        lang.pack(side="right")
        lang.bind("<<ComboboxSelected>>", self._change_language)
        ttk.Label(top, text="🌐 " + t("ui.language")).pack(side="right", padx=4)
        ttk.Label(root, text=t("ui.subtitle"), foreground="#6b7280").pack(anchor="w", pady=(0, 8))

        search = ttk.Frame(root)
        search.pack(fill="x")
        ttk.Label(search, text=t("ui.folder")).pack(side="left")
        self.combo = ttk.Combobox(search, textvariable=self.project, values=self.cfg.get("recent", []))
        self.combo.pack(side="left", fill="x", expand=True, padx=6)
        self.combo.bind("<Return>", lambda _e: self.start())
        ttk.Button(search, text=t("ui.browse"), command=self.browse).pack(side="left")
        self.btn_run = ttk.Button(search, text=t("ui.analyze"), style="Accent.TButton", command=self.start)
        self.btn_run.pack(side="left", padx=(6, 0))

        body = ttk.PanedWindow(root, orient="horizontal")
        body.pack(fill="both", expand=True, pady=10)
        body.add(self._build_left(body), weight=0)
        body.add(self._build_right(body), weight=3)

        bottom = ttk.Frame(root)
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=len(self.skills))
        self.progress.pack(side="left", fill="x", expand=True)
        self.status = ttk.Label(bottom, text=t("ui.ready"), width=60)
        self.status.pack(side="left", padx=8)

    def _build_left(self, parent) -> ttk.Frame:
        left = ttk.Frame(parent, padding=(0, 0, 8, 0), width=330)
        box = ttk.LabelFrame(left, text=t("ui.skills"), padding=8)
        box.pack(fill="both", expand=True)
        for s in self.skills:
            cb = ttk.Checkbutton(box, text=s.title, variable=self.skill_vars[s.id])
            cb.pack(anchor="w", pady=1)
            _Tooltip(cb, s.description)
        row = ttk.Frame(box)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Button(row, text=t("ui.all"), width=8, command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(row, text=t("ui.none"), width=8, command=lambda: self._set_all(False)).pack(side="left", padx=4)

        out = ttk.LabelFrame(left, text=t("ui.report"), padding=8)
        out.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(out, text="Markdown (.md)", variable=self.fmt_md).pack(anchor="w")
        ttk.Checkbutton(out, text="PDF", variable=self.fmt_pdf).pack(anchor="w")
        ttk.Label(out, text=t("ui.save_to")).pack(anchor="w", pady=(6, 0))
        row = ttk.Frame(out)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.out_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="…", width=3, command=self.browse_out).pack(side="left", padx=(4, 0))
        return left

    def _build_right(self, parent) -> ttk.Frame:
        right = ttk.Frame(parent)
        head = ttk.Frame(right)
        head.pack(fill="x")
        self.score_lbl = ttk.Label(head, text="–", style="Score.TLabel")
        self.score_lbl.pack(side="left")
        self.summary_lbl = ttk.Label(head, text=t("ui.no_analysis"), foreground="#374151")
        self.summary_lbl.pack(side="left", padx=12)
        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=(6, 0))
        self.btn_pdf = ttk.Button(actions, text=t("ui.open_pdf"), state="disabled", command=lambda: self._open_saved(".pdf"))
        self.btn_md = ttk.Button(actions, text=t("ui.open_md"), state="disabled", command=lambda: self._open_saved(".md"))
        self.btn_dir = ttk.Button(actions, text=t("ui.open_dir"), state="disabled",
                                  command=lambda: open_path(Path(self.out_dir.get())))
        for b in (self.btn_pdf, self.btn_md, self.btn_dir):
            b.pack(side="left", padx=(0, 4))

        filt = ttk.Frame(right)
        filt.pack(fill="x", pady=(8, 4))
        ttk.Label(filt, text=t("r.severity") + ":").pack(side="left")
        cb = ttk.Combobox(filt, textvariable=self.sev_filter, state="readonly", width=12,
                          values=[t("ui.filter_all")] + [s.label for s in sorted(Severity, reverse=True)])
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._fill_tree())

        cols = ("sev", "loc", "skill", "msg")
        frame = ttk.Frame(right)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, title, w in zip(cols, (t("r.severity"), t("r.location"), t("r.skill"), t("r.problem")), (80, 260, 140, 520)):
            self.tree.heading(c, text=title)
            self.tree.column(c, width=w, stretch=(c == "msg"))
        for sev, color in SEV_TAGS.items():
            self.tree.tag_configure(sev.label, foreground=color)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._show_detail)

        self.detail = tk.Text(right, height=5, wrap="word", relief="flat", background="#f3f4f6")
        self.detail.pack(fill="x", pady=(6, 0))
        self.detail.configure(state="disabled")
        if self.report:
            self._show_summary()
        return right

    # ---------- ações ----------
    def browse(self) -> None:
        d = filedialog.askdirectory(title=t("ui.pick_project"), initialdir=self.project.get() or None)
        if d:
            self.project.set(d)

    def browse_out(self) -> None:
        d = filedialog.askdirectory(title=t("ui.pick_output"), initialdir=self.out_dir.get() or None)
        if d:
            self.out_dir.set(d)

    def _set_all(self, value: bool) -> None:
        for v in self.skill_vars.values():
            v.set(value)

    def start(self) -> None:
        project = self.project.get().strip().strip('"')
        if not project or not Path(project).is_dir():
            messagebox.showwarning("CodeReview Local", t("ui.invalid_folder"))
            return
        chosen = [s for s in self.skills if self.skill_vars[s.id].get()]
        if not chosen:
            messagebox.showwarning("CodeReview Local", t("ui.no_skill"))
            return
        self._remember(project)
        self.btn_run.configure(state="disabled")
        for b in (self.btn_pdf, self.btn_md, self.btn_dir):
            b.configure(state="disabled")
        self.progress.configure(value=0, maximum=len(chosen))
        self.status.configure(text=t("ui.analyzing"))
        self.tree.delete(*self.tree.get_children())
        formats = [f for f, v in (("md", self.fmt_md), ("pdf", self.fmt_pdf)) if v.get()]
        threading.Thread(target=self._worker, args=(project, chosen, formats, self.out_dir.get()),
                         daemon=True).start()
        self.after(100, self._poll)

    def _worker(self, project, skills, formats, out_dir) -> None:
        try:
            rep = run_review(project, skills, progress=lambda t, r: self.events.put(("progress", t, r)))
            saved = report_mod.save(rep, out_dir, formats) if formats else []
            self.events.put(("done", rep, saved))
        except Exception as e:  # mostra qualquer falha na tela em vez de travar
            self.events.put(("error", e, None))

    def _poll(self) -> None:
        try:
            while True:
                kind, a, b = self.events.get_nowait()
                if kind == "progress":
                    if b is None:
                        self.status.configure(text=t("ui.running", name=a))
                    else:
                        self.progress.configure(value=min(self.progress["value"] + 1, self.progress["maximum"]))
                elif kind == "done":
                    self._finish(a, b)
                    return
                elif kind == "error":
                    self.btn_run.configure(state="normal")
                    self.status.configure(text=t("ui.error"))
                    messagebox.showerror("CodeReview Local", str(a))
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _finish(self, rep: Report, saved: list[Path]) -> None:
        self.report, self.saved = rep, saved
        self.progress.configure(value=self.progress.cget("maximum"))
        self._show_summary()
        self.btn_run.configure(state="normal")

    def _show_summary(self) -> None:
        rep, saved = self.report, self.saved
        score = rep.score()
        self.score_lbl.configure(text=f"{score}/100")
        counts = rep.counts()
        self.summary_lbl.configure(text=f"{t('r.grade').capitalize()} {report_mod.grade(score)}   ·   " + "   ".join(
            f"{s.label}: {counts[s]}" for s in sorted(Severity, reverse=True)))
        self._fill_tree()
        skipped = [r.title for r in rep.results if r.status != "ok"]
        self.status.configure(text=t("ui.done", s=rep.duration_s) + (f" · {t('ui.skipped', n=len(skipped))}" if skipped else ""))
        if saved:
            self.btn_dir.configure(state="normal")
            if any(p.suffix == ".pdf" for p in saved):
                self.btn_pdf.configure(state="normal")
            if any(p.suffix == ".md" for p in saved):
                self.btn_md.configure(state="normal")

    def _fill_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if not self.report:
            return
        want = self.sev_filter.get()
        self._rows = {}
        for f in sorted(self.report.findings, key=lambda x: (-x.severity, x.file, x.line)):
            if want != t("ui.filter_all") and f.severity.label != want:
                continue
            loc = f"{f.file}:{f.line}" if f.file and f.line else (f.file or t("r.project_level"))
            iid = self.tree.insert("", "end", values=(f.severity.label, loc, f.skill, f.message), tags=(f.severity.label,))
            self._rows[iid] = f

    def _show_detail(self, _e=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        f = self._rows[sel[0]]
        text = f"[{f.severity.label}] {f.rule_id}  ({f.skill})\n{f.message}\n\n{t('ui.suggestion')}: {f.suggestion or '-'}"
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def _open_saved(self, suffix: str) -> None:
        for p in self.saved:
            if p.suffix == suffix:
                open_path(p)

    def _change_language(self, _e=None) -> None:
        code = next(k for k, v in LANGUAGES.items() if v == self.lang.get())
        if code == get_language():
            return
        set_language(code)
        self.cfg["lang"] = code
        self.sev_filter.set(t("ui.filter_all"))
        self._persist()
        self._build()  # a tela e a lista de achados são redesenhadas no novo idioma

    def _remember(self, project: str) -> None:
        recent = [project] + [p for p in self.cfg.get("recent", []) if p != project]
        self.cfg["recent"] = recent[:MAX_RECENT]
        self.combo.configure(values=self.cfg["recent"])
        self._persist()

    def _persist(self) -> None:
        self.cfg.update(lang=get_language(), skills=[k for k, v in self.skill_vars.items() if v.get()],
                        md=self.fmt_md.get(), pdf=self.fmt_pdf.get(), out_dir=self.out_dir.get())
        save_config(self.cfg)

    def _on_close(self) -> None:
        self._persist()
        self.destroy()


class _Tooltip:
    def __init__(self, widget, text: str) -> None:
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _e=None) -> None:
        if self.tip or not self.text:
            return
        x, y = self.widget.winfo_rootx() + 20, self.widget.winfo_rooty() + 22
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#111827", foreground="white",
                 padx=6, pady=3, wraplength=320, justify="left").pack()

    def hide(self, _e=None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
