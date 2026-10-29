from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import IntEnum

from .i18n import t


class Severity(IntEnum):
    INFO = 0
    BAIXA = 1
    MEDIA = 2
    ALTA = 3
    CRITICA = 4

    @classmethod
    def parse(cls, value: str | None) -> "Severity":
        v = (value or "").strip().lower()
        mapping = {
            "critical": cls.CRITICA, "critica": cls.CRITICA, "error": cls.ALTA,
            "high": cls.ALTA, "alta": cls.ALTA, "warning": cls.MEDIA,
            "medium": cls.MEDIA, "media": cls.MEDIA, "moderate": cls.MEDIA,
            "low": cls.BAIXA, "baixa": cls.BAIXA, "note": cls.BAIXA,
            "info": cls.INFO, "none": cls.INFO,
        }
        return mapping.get(v, cls.MEDIA)

    @property
    def label(self) -> str:
        return t(f"sev.{self.name}")


@dataclass
class Finding:
    skill: str
    rule_id: str
    message: str
    severity: Severity
    file: str = ""
    line: int = 0
    suggestion: str = ""
    category: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.label
        return d


@dataclass
class SkillResult:
    skill: str
    title: str
    status: str  # "ok" | "skipped" | "error"
    findings: list[Finding] = field(default_factory=list)
    message: str = ""
    duration_s: float = 0.0


@dataclass
class Report:
    project_path: str
    languages: dict[str, int]
    results: list[SkillResult]
    started_at: str
    duration_s: float
    scope: str = ""  # descrição do escopo quando o CR não foi do projeto inteiro

    @property
    def findings(self) -> list[Finding]:
        return [f for r in self.results for f in r.findings]

    def counts(self) -> dict[Severity, int]:
        c = dict.fromkeys(Severity, 0)
        for f in self.findings:
            c[f.severity] += 1
        return c

    def score(self) -> int:
        """Nota 0-100 ponderada pela severidade e pelo tamanho do projeto."""
        weights = {Severity.CRITICA: 10, Severity.ALTA: 5, Severity.MEDIA: 2,
                   Severity.BAIXA: 0.5, Severity.INFO: 0}
        penalty = sum(weights[f.severity] for f in self.findings)
        files = sum(self.languages.values())
        return round(100 / (1 + penalty / (10 + files * 2)))
