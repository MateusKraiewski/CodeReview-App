from __future__ import annotations

import json

from ..detect import rel
from ..i18n import t
from ..models import Severity
from ..tools import find_tool, run
from .base import Skill, SkillSkipped


class BanditSkill(Skill):
    id = "seguranca-python"
    category = "Segurança"
    languages = {"Python"}

    def analyze(self, root, languages):
        exe = find_tool("bandit")
        if not exe:
            raise SkillSkipped(t("skip.tool_missing", tool="bandit"))
        proc = run([*exe, "-r", str(root), "-f", "json", "-q",
                    "-x", ",".join(f"*/{d}/*" for d in (".venv", "venv", "node_modules", ".git"))])
        data = json.loads(proc.stdout or "{}")
        return [
            self.finding(
                rule_id=f"{r['test_id']} {r['test_name']}",
                message=r["issue_text"],
                severity=Severity.parse(r["issue_severity"]),
                file=rel(r["filename"], root),
                line=r["line_number"],
                suggestion=r.get("more_info", ""),
            )
            for r in data.get("results", [])
        ]
