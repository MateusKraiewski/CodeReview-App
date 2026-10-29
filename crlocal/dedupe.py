"""Une achados que várias skills reportam no mesmo ponto (ex.: SQL injection no Semgrep e no Bandit)."""
from __future__ import annotations

import re

from .i18n import t
from .models import Finding

TOPICS = {
    "sql": r"sql",
    "shell": r"subprocess|shell=|comando",
    "desserializacao": r"pickle|binaryformatter|deserializ|desserializ",
    "eval": r"\beval\b|exec\(",
    "segredo": r"password|senha|secret|segredo|token|api.?key|credential",
    "hash-fraco": r"md5|sha1|hash fraco|weak hash",  # DevSkim: ignore DS126858 (é o texto procurado, não um hash)
    "excecao": r"except|catch|exce[cç]",
    "tls": r"certific|verify=false|tls|ssl",
}
MERGEABLE = {"Segurança", "Padrões"}
_COMPILED = {k: re.compile(v, re.I) for k, v in TOPICS.items()}


def _topic(f: Finding) -> str | None:
    text = f"{f.rule_id} {f.message}"
    for name, rx in _COMPILED.items():
        if rx.search(text):
            return name
    return None


def merge_duplicates(findings: list[Finding]) -> list[Finding]:
    kept: dict[tuple, Finding] = {}
    out: list[Finding] = []
    seen: set[tuple] = set()
    for f in sorted(findings, key=lambda x: -x.severity):
        exact = (f.skill, f.rule_id, f.file, f.line, f.message)
        if exact in seen:  # a ferramenta achou o mesmo problema duas vezes na linha (ex.: MD5 e md5)
            continue
        seen.add(exact)
        topic = _topic(f)
        if not f.file or not topic or f.category not in MERGEABLE:
            out.append(f)
            continue
        key = (f.file, f.line, topic)
        if key in kept:
            first = kept[key]
            tag = t("f.also", skill=f.skill)
            if tag not in first.suggestion:
                first.suggestion = (first.suggestion + f" ({tag})").strip()
            continue
        kept[key] = f
        out.append(f)
    return out
