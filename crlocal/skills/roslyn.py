from __future__ import annotations

import re
from pathlib import Path

from ..detect import IGNORED_DIRS, rel
from ..i18n import t
from ..models import Severity
from ..tools import find_tool, run
from .base import Skill, SkillSkipped

# C:\src\Foo.cs(12,5): warning CA1822: Member 'X' does not access instance data ... [C:\src\Foo.csproj]
DIAG = re.compile(r"^\s*(?P<file>[^\r\n]+?\.cs)\((?P<line>\d+),\d+(?:,\d+,\d+)?\):\s*"
                  r"(?P<level>warning|error)\s+(?P<id>[A-Z]+\d+):\s*(?P<msg>.*?)(?:\s+\[[^\]]+\])?\s*$", re.M)

SECURITY_PREFIXES = ("CA2100", "CA21", "CA23", "CA30", "CA31", "CA35", "CA53", "CA54", "SYSLIB")


def _severity(rule_id: str, level: str) -> Severity:
    if level == "error":
        return Severity.ALTA
    if rule_id.startswith(SECURITY_PREFIXES) or rule_id.startswith("CA5"):
        return Severity.ALTA
    if rule_id.startswith(("CS", "CA2")):
        return Severity.MEDIA
    if rule_id.startswith("IDE"):
        return Severity.BAIXA
    return Severity.BAIXA if rule_id.startswith("CA1") else Severity.MEDIA


def _find_entrypoints(root: Path) -> list[Path]:
    def walk(pattern):
        return [p for p in root.rglob(pattern) if not IGNORED_DIRS & set(p.relative_to(root).parts[:-1])]
    slns = walk("*.sln") + walk("*.slnx")
    return slns[:1] if slns else walk("*.csproj")


class RoslynSkill(Skill):
    id = "qualidade-csharp"
    category = "Qualidade"
    languages = {"C#"}

    def analyze(self, root, languages):
        exe = find_tool("dotnet")
        if not exe:
            raise SkillSkipped(t("skip.dotnet"))
        targets = _find_entrypoints(root)
        if not targets:
            raise SkillSkipped(t("skip.no_sln"))
        seen, findings = set(), []
        for target in targets:
            proc = run([*exe, "build", str(target), "--no-incremental", "-nologo", "-v:q", "-clp:NoSummary",
                        "-p:RunAnalyzers=true", "-p:AnalysisMode=All", "-p:EnforceCodeStyleInBuild=true",
                        "-p:TreatWarningsAsErrors=false", "-p:GenerateDocumentationFile=false"],
                       cwd=str(target.parent), timeout=1800)
            for m in DIAG.finditer(proc.stdout + "\n" + proc.stderr):
                key = (m["file"], m["line"], m["id"])
                if key in seen:
                    continue
                seen.add(key)
                findings.append(self.finding(
                    rule_id=m["id"], message=m["msg"].strip(),
                    severity=_severity(m["id"], m["level"]),
                    file=rel(Path(m["file"]), root), line=int(m["line"]),
                    suggestion=f"https://learn.microsoft.com/dotnet/fundamentals/code-analysis/quality-rules/{m['id'].lower()}"
                    if m["id"].startswith("CA") else "",
                ))
            if proc.returncode != 0 and not findings:
                tail = (proc.stdout + proc.stderr).strip()[-400:]
                raise RuntimeError(t("err.build", name=target.name, tail=tail))
        return findings
