from __future__ import annotations

import tempfile
from pathlib import Path

from ..i18n import t
from ..models import Severity
from ..tools import find_tool, run
from .base import Skill, SkillSkipped, parse_sarif


class GitleaksSkill(Skill):
    id = "segredos"
    category = "Segurança"

    def analyze(self, root, languages):
        exe = find_tool("gitleaks")
        if not exe:
            raise SkillSkipped(t("skip.tool_missing", tool="gitleaks"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "gitleaks.sarif"
            proc = run([*exe, "dir", str(root), "--report-format", "sarif",
                        "--report-path", str(out), "--no-banner", "--redact", "--exit-code", "0"])
            if not out.exists():
                raise RuntimeError(proc.stderr.strip()[-400:] or t("err.no_output", tool="gitleaks"))
            findings = parse_sarif(out.read_text(encoding="utf-8"), self, root)
        for f in findings:
            f.severity = Severity.CRITICA
            f.suggestion = t("f.secret.sug")
        return findings
