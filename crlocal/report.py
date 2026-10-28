"""Gera o relatório do CR em Markdown e PDF."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

from . import __version__
from .i18n import t
from .models import Finding, Report, Severity

SEV_COLORS = {Severity.CRITICA: "#7f1d1d", Severity.ALTA: "#dc2626", Severity.MEDIA: "#d97706",
              Severity.BAIXA: "#2563eb", Severity.INFO: "#6b7280"}
TOP_N = 10


def grade(score: int) -> str:
    letter = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "E"
    return t(f"grade.{letter}")


def by_file(findings: list[Finding]) -> dict[str, list[Finding]]:
    groups: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        groups[f.file or t("r.project_level")].append(f)
    for items in groups.values():
        items.sort(key=lambda f: (f.line, -f.severity))
    return dict(sorted(groups.items(), key=lambda kv: (-max(f.severity for f in kv[1]), kv[0])))


def top_findings(report: Report) -> list[Finding]:
    return sorted(report.findings, key=lambda f: (-f.severity, f.file, f.line))[:TOP_N]


def _md(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def _loc(f: Finding) -> str:
    return f"{f.file}:{f.line}" if f.file and f.line else (f.file or "-")


def to_markdown(report: Report) -> str:
    score = report.score()
    counts = report.counts()
    lines = [
        f"# {t('r.title')}",
        "",
        f"- **{t('r.project')}:** `{report.project_path}`",
        f"- **{t('r.date')}:** {report.started_at}  ·  **{t('r.duration')}:** {report.duration_s}s",
        f"- **{t('r.languages')}:** " + (", ".join(f"{k} ({v})" for k, v in report.languages.items()) or t("r.none_detected")),
        f"- **{t('r.score')}:** **{score}/100**, {t('r.grade')} {grade(score)}",
        "",
        f"## {t('r.by_severity')}",
        "",
        f"| {t('r.severity')} | {t('r.findings')} |",
        "|---|---:|",
        *[f"| {s.label} | {counts[s]} |" for s in sorted(Severity, reverse=True)],
        f"| **{t('r.total')}** | **{len(report.findings)}** |",
        "",
        f"## {t('r.skills')}",
        "",
        f"| {t('r.skill')} | {t('r.status')} | {t('r.findings')} | {t('r.time')} | {t('r.note')} |",
        "|---|---|---:|---:|---|",
        *[f"| {r.title} | {t('status.' + r.status)} | {len(r.findings)} | {r.duration_s}s | {_md(r.message)} |"
          for r in report.results],
        "",
    ]
    top = top_findings(report)
    if top:
        lines += [f"## {t('r.priorities')}", "", t("r.priorities_intro"), ""]
        lines += [f"{i}. **[{f.severity.label}]** `{_loc(f)}`: {_md(f.message)}" for i, f in enumerate(top, 1)]
        lines.append("")
    lines += [f"## {t('r.by_file')}", "", f"_{t('r.tool_lang_note')}_", ""]
    if not report.findings:
        lines.append(t("r.no_findings") + " 🎉")
    for file, items in by_file(report.findings).items():
        lines += [f"### `{file}` ({len(items)})", "",
                  f"| {t('r.line')} | {t('r.severity')} | {t('r.skill')} | {t('r.rule')} | {t('r.problem')} | {t('r.suggestion')} |",
                  "|---:|---|---|---|---|---|"]
        lines += [f"| {f.line or '-'} | {f.severity.label} | {f.skill} | `{_md(f.rule_id)}` | {_md(f.message)} | {_md(f.suggestion)} |"
                  for f in items]
        lines.append("")
    lines.append(f"---\n_{t('r.footer', v=__version__)}_")
    return "\n".join(lines) + "\n"


def to_pdf(report: Report, path: str | Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    ss = getSampleStyleSheet()
    h1, h2 = ss["Title"], ss["Heading2"]
    h3 = ParagraphStyle("h3", parent=ss["Heading3"], keepWithNext=1)
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9, leading=11)
    cell = ParagraphStyle("cell", parent=body, fontSize=7.5, leading=9)
    mono = ParagraphStyle("mono", parent=cell, fontName="Courier")
    p = lambda t, s=cell: Paragraph(escape(str(t or "")), s)  # noqa: E731

    page = landscape(A4)
    doc = SimpleDocTemplate(str(path), pagesize=page, leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title=t("r.title"), author="CodeReview Local")
    width = page[0] - 24 * mm
    grid = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
    ])

    score, counts = report.score(), report.counts()
    story = [
        Paragraph(t("r.title"), h1),
        Paragraph(f"<b>{t('r.project')}:</b> {escape(report.project_path)}", body),
        Paragraph(f"<b>{t('r.date')}:</b> {report.started_at} · <b>{t('r.duration')}:</b> {report.duration_s}s", body),
        Paragraph(f"<b>{t('r.languages')}:</b> " + escape(", ".join(f"{k} ({v})" for k, v in report.languages.items()) or "-"), body),
        Spacer(1, 4 * mm),
        Paragraph(f"<font size=22><b>{score}/100</b></font>  {t('r.grade')} {grade(score)}", body),
        Spacer(1, 6 * mm),
    ]

    sev_rows = [[t("r.severity"), t("r.findings")]] + [[s.label, counts[s]] for s in sorted(Severity, reverse=True)]
    sev_rows.append([t("r.total"), len(report.findings)])
    t1 = Table(sev_rows, colWidths=[40 * mm, 25 * mm])
    t1.setStyle(grid)
    for i, s in enumerate(sorted(Severity, reverse=True), 1):
        t1.setStyle([("TEXTCOLOR", (0, i), (0, i), colors.HexColor(SEV_COLORS[s]))])
    skill_rows = [[t("r.skill"), t("r.status"), t("r.findings"), t("r.time"), t("r.note")]] + [
        [p(r.title), t("status." + r.status), len(r.findings), f"{r.duration_s}s", p(r.message)] for r in report.results]
    t2 = Table(skill_rows, colWidths=[75 * mm, 22 * mm, 18 * mm, 16 * mm, width - 131 * mm], repeatRows=1)
    t2.setStyle(grid)
    story += [Paragraph(t("r.by_severity"), h2), t1, Spacer(1, 4 * mm),
              Paragraph(t("r.skills"), h2), t2]

    top = top_findings(report)
    if top:
        rows = [["#", t("r.severity"), t("r.location"), t("r.problem")]] + [
            [i, f.severity.label, p(_loc(f), mono), p(f.message)] for i, f in enumerate(top, 1)]
        tt = Table(rows, colWidths=[8 * mm, 22 * mm, 70 * mm, width - 100 * mm], repeatRows=1)
        tt.setStyle(grid)
        story += [Spacer(1, 4 * mm), KeepTogether([Paragraph(t("r.priorities"), h2), tt])]

    story += [PageBreak(), Paragraph(t("r.by_file"), h2), Paragraph(f"<i>{escape(t('r.tool_lang_note'))}</i>", body),
              Spacer(1, 2 * mm)]
    if not report.findings:
        story.append(Paragraph(t("r.no_findings"), body))
    cols = [12 * mm, 18 * mm, 28 * mm, 34 * mm, (width - 92 * mm) * 0.55, (width - 92 * mm) * 0.45]
    for file, items in by_file(report.findings).items():
        rows = [[t("r.line"), t("r.severity")[:4] + ".", t("r.skill"), t("r.rule"), t("r.problem"), t("r.suggestion")]] + [
            [f.line or "-", f.severity.label, p(f.skill), p(f.rule_id, mono), p(f.message), p(f.suggestion)]
            for f in items]
        tf = Table(rows, colWidths=cols, repeatRows=1)
        tf.setStyle(grid)
        for i, f in enumerate(items, 1):
            tf.setStyle([("TEXTCOLOR", (1, i), (1, i), colors.HexColor(SEV_COLORS[f.severity]))])
        story += [Paragraph(f"{escape(file)} ({len(items)})", h3), tf, Spacer(1, 3 * mm)]

    def footer(canvas, _doc):
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(12 * mm, 6 * mm, f"CodeReview Local {__version__} · 100% offline")
        canvas.drawRightString(page[0] - 12 * mm, 6 * mm, t("r.page", n=_doc.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def save(report: Report, out_dir: str | Path, formats=("md", "pdf")) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"CR_{Path(report.project_path).name}_{report.started_at.replace('/', '-').replace(' ', '_').replace(':', '')}"
    saved = []
    if "md" in formats:
        md = out_dir / f"{name}.md"
        md.write_text(to_markdown(report), encoding="utf-8")
        saved.append(md)
    if "pdf" in formats:
        pdf = out_dir / f"{name}.pdf"
        to_pdf(report, pdf)
        saved.append(pdf)
    return saved
