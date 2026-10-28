from __future__ import annotations

import json
import os
from pathlib import Path

from ..detect import rel
from ..i18n import t
from ..models import Severity
from ..tools import find_tool, run
from .base import Skill, SkillSkipped


def db_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache")
    d = base / "CodeReviewLocal" / "osv-db"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cvss_to_severity(vuln: dict) -> Severity:
    sev = (vuln.get("database_specific") or {}).get("severity")
    if sev:
        return Severity.parse(sev)
    return Severity.ALTA


class OsvSkill(Skill):
    id = "dependencias"
    category = "Segurança"

    def __init__(self, update_db: bool = False):
        self.update_db = update_db

    def analyze(self, root, languages):
        exe = find_tool("osv-scanner")
        if not exe:
            raise SkillSkipped(t("skip.tool_missing", tool="osv-scanner"))
        os.environ["OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY"] = str(db_dir())
        cmd = [*exe, "scan", "source", "-r", str(root), "--format", "json", "--offline-vulnerabilities"]
        if self.update_db or not any(db_dir().rglob("*.zip")):
            cmd.append("--download-offline-databases")
        proc = run(cmd)
        if "no package sources found" in (proc.stderr + proc.stdout).lower():
            raise SkillSkipped(t("skip.no_deps"))
        if not proc.stdout.strip().startswith("{"):
            raise RuntimeError(proc.stderr.strip()[-400:] or t("err.no_output", tool="osv-scanner"))
        data = json.loads(proc.stdout)
        findings = []
        for res in data.get("results", []):
            source = rel((res.get("source") or {}).get("path", ""), root)
            for pkg in res.get("packages", []):
                p = pkg.get("package", {})
                for v in pkg.get("vulnerabilities", []):
                    fixed = [e.get("fixed") for a in v.get("affected", []) for r in a.get("ranges", [])
                             for e in r.get("events", []) if e.get("fixed")]
                    aliases = ", ".join(v.get("aliases", [])[:2])
                    findings.append(self.finding(
                        rule_id=v.get("id", ""),
                        message=t("f.vuln", pkg=f"{p.get('name')} {p.get('version')} ({p.get('ecosystem')})",
                                  summary=v.get("summary") or t("f.vuln.default")) + (f" [{aliases}]" if aliases else ""),
                        severity=_cvss_to_severity(v),
                        file=source,
                        suggestion=t("f.vuln.fix", v=fixed[-1]) if fixed else t("f.vuln.nofix"),
                    ))
        return findings
