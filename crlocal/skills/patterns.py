from __future__ import annotations

import re
from pathlib import Path

import yaml

from ..detect import EXTENSIONS, iter_source_files, rel
from ..i18n import pick, t
from ..models import Severity
from ..tools import app_dir
from .base import Skill

MAX_PER_RULE = 50


def load_rules(path: Path | None = None) -> list[dict]:
    files = [path] if path else sorted((app_dir() / "crlocal" / "rules").glob("*.y*ml"))
    rules = []
    for f in files:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for r in data.get("rules", []):
            r["_regex"] = re.compile(r["pattern"], re.M if r.get("multiline") else 0)
            r["languages"] = set(r.get("languages") or [])
            rules.append(r)
    return rules


class PatternsSkill(Skill):
    id = "padroes"
    category = "Padrões"

    def __init__(self, rules_file: Path | None = None, max_file_lines: int = 500):
        self.rules_file = rules_file
        self.max_file_lines = max_file_lines

    def analyze(self, root, languages):
        rules = load_rules(self.rules_file)
        findings, per_rule = [], {}
        for p in iter_source_files(root):
            lang = EXTENSIONS[p.suffix.lower()]
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            path = rel(p, root)
            n_lines = text.count("\n") + 1
            if n_lines > self.max_file_lines:
                findings.append(self.finding(
                    rule_id="arquivo-grande", severity=Severity.BAIXA, file=path,
                    message=t("f.bigfile", n=n_lines, limit=self.max_file_lines),
                    suggestion=t("f.bigfile.sug")))
            for r in rules:
                if r["languages"] and lang not in r["languages"]:
                    continue
                if r.get("exclude_paths") and re.search(r["exclude_paths"], path, re.I):
                    continue
                for m in r["_regex"].finditer(text):
                    per_rule[r["id"]] = per_rule.get(r["id"], 0) + 1
                    if per_rule[r["id"]] > MAX_PER_RULE:
                        break
                    findings.append(self.finding(
                        rule_id=r["id"], message=pick(r["message"]).format(match=m.group(0).strip()[:80]),
                        severity=Severity.parse(r.get("severity")), file=path,
                        line=text.count("\n", 0, m.start()) + 1,
                        suggestion=pick(r.get("suggestion")),
                    ))
        for rid, count in per_rule.items():
            if count > MAX_PER_RULE:
                findings.append(self.finding(rule_id=rid, severity=Severity.INFO,
                                             message=t("f.capped", rule=rid, n=count, max=MAX_PER_RULE)))
        return findings
