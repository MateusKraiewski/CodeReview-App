from __future__ import annotations

import json

from ..detect import rel
from ..i18n import get_language, t
from ..models import Severity
from ..tools import app_dir, find_tool, run
from .base import Skill, SkillSkipped


class SemgrepSkill(Skill):
    id = "seguranca-sast"
    category = "Segurança"

    def rules_paths(self) -> list[str]:
        rules_dir = app_dir() / "rules" / "semgrep"
        custom = app_dir() / "crlocal" / "rules" / "semgrep"
        paths = [str(p) for p in (rules_dir, custom) if p.is_dir() and any(p.rglob("*.y*ml"))]
        if not paths:
            raise SkillSkipped(t("skip.semgrep_rules"))
        return paths

    def analyze(self, root, languages):
        exe = find_tool("semgrep")
        if not exe:
            raise SkillSkipped(t("skip.tool_missing", tool="semgrep"))
        cmd = [*exe, "scan", "--json", "--quiet", "--metrics=off", "--disable-version-check", "--timeout", "30"]
        for p in self.rules_paths():
            cmd += ["--config", p]
        proc = run(cmd + [str(root)], cwd=str(root))
        if not proc.stdout.strip():
            raise RuntimeError(proc.stderr.strip()[-400:] or t("err.no_output", tool="semgrep"))
        data = json.loads(proc.stdout)
        findings = []
        for r in data.get("results", []):
            extra = r.get("extra", {})
            meta = extra.get("metadata", {})
            sev = meta.get("impact") if extra.get("severity") == "ERROR" and meta.get("impact") else extra.get("severity")
            refs = meta.get("references") or []
            findings.append(self.finding(
                rule_id=r.get("check_id", "").split(".")[-1],
                message=(meta.get(f"message_{get_language()}") or extra.get("message", "")).strip(),
                severity=Severity.parse(sev),
                file=rel(r.get("path", ""), root),
                line=r.get("start", {}).get("line", 0),
                suggestion=t("f.see", url=refs[0]) if refs else (", ".join(meta.get("cwe", [])[:1]) if isinstance(meta.get("cwe"), list) else ""),
            ))
        return findings
