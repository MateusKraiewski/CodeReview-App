from __future__ import annotations

import json
import os

from ..detect import rel
from ..i18n import get_language, t
from ..models import Severity
from ..tools import app_dir, find_tool, run
from .base import Skill, SkillSkipped

# linguagem detectada -> pasta das regras públicas (e nome do arquivo das nossas regras)
RULE_DIRS = {"Python": "python", "C#": "csharp", "JavaScript": "javascript", "TypeScript": "typescript",
             "Java": "java", "Go": "go"}


class SemgrepSkill(Skill):
    id = "seguranca-sast"
    category = "Segurança"

    def rules_paths(self, languages: dict[str, int]) -> list[str]:
        """Só as regras das linguagens que o projeto tem: carregar as de todas deixava a análise lenta demais."""
        wanted = {RULE_DIRS[lang] for lang in languages if lang in RULE_DIRS}
        if not wanted:
            raise SkillSkipped(t("skip.no_lang"))
        rules_dir = app_dir() / "rules" / "semgrep"
        custom = app_dir() / "crlocal" / "rules" / "semgrep"
        paths = [str(rules_dir / d) for d in sorted(wanted) if (rules_dir / d).is_dir()]
        # nossas regras: python.yaml, csharp.yaml... só da linguagem presente; outros nomes sempre carregam
        skip = set(RULE_DIRS.values()) - wanted
        paths += [str(f) for f in sorted(custom.glob("*.y*ml")) if f.stem not in skip] if custom.is_dir() else []
        if not paths:
            raise SkillSkipped(t("skip.semgrep_rules"))
        return paths

    def analyze(self, root, languages):
        exe = find_tool("semgrep")
        if not exe:
            raise SkillSkipped(t("skip.tool_missing", tool="semgrep"))
        cmd = [*exe, "scan", "--json", "--quiet", "--metrics=off", "--disable-version-check",
               # arquivo que demora demais numa regra é deixado de lado, em vez de travar a análise toda
               "--timeout", "10", "--timeout-threshold", "3", "--jobs", str(max(1, min(4, os.cpu_count() or 1)))]
        for p in self.rules_paths(languages):
            cmd += ["--config", p]
        for pattern in (self.ignore.exclude_names() if self.ignore else []):
            cmd += ["--exclude", pattern]
        files = sum(languages.get(lang, 0) for lang in RULE_DIRS)
        proc = run(cmd + self.cli_targets(root), cwd=str(root), timeout=min(1800, 300 + 2 * files))
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
