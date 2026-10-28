"""Exporta os achados em SARIF 2.1.0 (VS Code, Visual Studio, GitHub Code Scanning) e no formato de
"problemas" (arquivo:linha:coluna: nível: mensagem) que o VS Code lê com um problemMatcher."""
from __future__ import annotations

import json
from pathlib import Path

from . import __version__
from .models import Finding, Report, Severity

LEVEL = {Severity.CRITICA: "error", Severity.ALTA: "error", Severity.MEDIA: "warning",
         Severity.BAIXA: "note", Severity.INFO: "note"}
PROBLEM_LEVEL = {"error": "error", "warning": "warning", "note": "info"}


def _rule_key(f: Finding) -> str:
    return f"{f.skill}/{f.rule_id}" if f.rule_id else f.skill


def to_sarif(report: Report) -> dict:
    rules: dict[str, dict] = {}
    results = []
    for f in report.findings:
        key = _rule_key(f)
        if key not in rules:
            rules[key] = {"id": key, "name": f.rule_id or f.skill,
                          "shortDescription": {"text": (f.message or key)[:200]},
                          "properties": {"skill": f.skill, "category": f.category}}
            if f.suggestion:
                rules[key]["help"] = {"text": f.suggestion}
        result = {
            "ruleId": key,
            "level": LEVEL[f.severity],
            "message": {"text": f.message + (f"\n{f.suggestion}" if f.suggestion else "")},
            "properties": {"severity": f.severity.name.lower(), "skill": f.skill},
        }
        if f.file:
            loc = {"artifactLocation": {"uri": f.file, "uriBaseId": "SRCROOT"}}
            if f.line:
                loc["region"] = {"startLine": f.line}
            result["locations"] = [{"physicalLocation": loc}]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "CodeReview Local", "version": __version__,
                                "informationUri": "https://github.com/MateusKraiewski/CodeReview-App",
                                "rules": list(rules.values())}},
            "originalUriBaseIds": {"SRCROOT": {"uri": Path(report.project_path).resolve().as_uri() + "/"}},
            "results": results,
            "properties": {"score": report.score()},
        }],
    }


def save_sarif(report: Report, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_sarif(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def problem_lines(report: Report) -> list[str]:
    """Uma linha por achado, com caminho absoluto, para o painel Problemas do VS Code."""
    root = Path(report.project_path)
    lines = []
    for f in report.findings:
        file = str(root / f.file) if f.file else str(root)
        lines.append(f"{file}:{f.line or 1}:1: {PROBLEM_LEVEL[LEVEL[f.severity]]}: "
                     f"[{f.severity.label}] {f.message} ({_rule_key(f)})")
    return lines
