from __future__ import annotations

import json
import time
from pathlib import Path

from ..detect import rel
from ..i18n import t
from ..models import Finding, Severity, SkillResult


class SkillSkipped(Exception):
    """A skill não se aplica ou a ferramenta não está disponível."""


class Skill:
    id: str = ""
    category: str = ""
    languages: set[str] | None = None  # None = qualquer linguagem

    @property
    def title(self) -> str:
        return t(f"skill.{self.id}.title")

    @property
    def description(self) -> str:
        return t(f"skill.{self.id}.desc")

    def applies_to(self, languages: dict[str, int]) -> bool:
        return self.languages is None or bool(self.languages & languages.keys())

    def analyze(self, root: Path, languages: dict[str, int]) -> list[Finding]:
        raise NotImplementedError

    def execute(self, root: Path, languages: dict[str, int]) -> SkillResult:
        start = time.perf_counter()
        result = SkillResult(self.id, self.title, "ok")
        try:
            if not self.applies_to(languages):
                raise SkillSkipped(t("skip.no_lang"))
            result.findings = self.analyze(root, languages)
        except SkillSkipped as e:
            result.status, result.message = "skipped", str(e)
        except Exception as e:  # uma skill com erro não derruba as outras
            result.status, result.message = "error", f"{type(e).__name__}: {e}"
        result.duration_s = round(time.perf_counter() - start, 2)
        return result

    def finding(self, **kw) -> Finding:
        kw.setdefault("category", self.category)
        return Finding(skill=self.id, **kw)


def parse_sarif(text: str, skill: Skill, root: Path, default_level: str = "warning") -> list[Finding]:
    data = json.loads(text) if text.strip() else {}
    findings: list[Finding] = []
    for run in data.get("runs", []):
        rules = {}
        driver = run.get("tool", {}).get("driver", {})
        for r in driver.get("rules", []) or []:
            rules[r.get("id")] = r
        for res in run.get("results", []) or []:
            rule_id = res.get("ruleId", "")
            rule = rules.get(rule_id, {})
            level = res.get("level") or rule.get("defaultConfiguration", {}).get("level") or default_level
            sev = res.get("properties", {}).get("severity") or rule.get("properties", {}).get("severity")
            loc = (res.get("locations") or [{}])[0].get("physicalLocation", {})
            uri = loc.get("artifactLocation", {}).get("uri", "")
            if uri.startswith("file://"):
                uri = uri[7:].lstrip("/") if ":" in uri[7:10] else uri[7:]
            path = (root / uri) if uri and not Path(uri).is_absolute() else Path(uri or ".")
            help_text = (rule.get("help") or {}).get("text") or (rule.get("shortDescription") or {}).get("text", "")
            findings.append(skill.finding(
                rule_id=rule_id,
                message=(res.get("message") or {}).get("text", "").strip(),
                severity=Severity.parse(sev or level),
                file=rel(path, root) if uri else "",
                line=int(loc.get("region", {}).get("startLine", 0) or 0),
                suggestion=help_text.strip()[:500],
            ))
    return findings
