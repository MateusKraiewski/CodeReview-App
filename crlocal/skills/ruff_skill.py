from __future__ import annotations

import json

from ..detect import rel
from ..i18n import t
from ..models import Severity
from ..tools import find_tool, run
from .base import Skill, SkillSkipped

# Regras com mais sinal e menos ruído para CR
# Segurança (S) fica com o Bandit para não duplicar achados
SELECT = "E9,F,B,C4,SIM,UP,PL,RET,ARG,ERA,N,PERF,RUF,ASYNC"
HIGH = ("F8", "E9", "B0")
MEDIUM = ("F", "B", "PL", "ASYNC")
# Regras que geram muito ruído em CR
IGNORE = "ARG002,PLR2004,PLR0913,RUF012,UP035,UP037,N818"


class RuffSkill(Skill):
    id = "qualidade-python"
    category = "Qualidade"
    languages = {"Python"}

    def analyze(self, root, languages):
        exe = find_tool("ruff")
        if not exe:
            raise SkillSkipped(t("skip.tool_missing", tool="ruff"))
        proc = run([*exe, "check", str(root), "--output-format", "json", "--exit-zero",
                    "--no-cache", "--isolated", "--select", SELECT, "--ignore", IGNORE])
        data = json.loads(proc.stdout or "[]")
        findings = []
        for r in data:
            code = r.get("code") or ""
            sev = Severity.ALTA if code.startswith(HIGH) else (
                Severity.MEDIA if code.startswith(MEDIUM) else Severity.BAIXA)
            fix = (r.get("fix") or {}).get("message") or ""
            findings.append(self.finding(
                rule_id=code, message=r.get("message", ""), severity=sev,
                file=rel(r.get("filename", ""), root),
                line=(r.get("location") or {}).get("row", 0),
                suggestion=fix or (r.get("url") or ""),
            ))
        return findings
