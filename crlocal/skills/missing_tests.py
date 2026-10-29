from __future__ import annotations

import re
from pathlib import Path

from ..detect import iter_source_files, rel
from ..i18n import t
from ..models import Severity
from .base import Skill

TEST_FILE = re.compile(r"(^test_.*\.py$|_test\.(py|go)$|tests?\.cs$|\.(spec|test)\.[jt]sx?$|Tests?\.(java|kt)$)", re.I)
TEST_DIR = re.compile(r"(^|/)(tests?|__tests__|spec|[^/]*\.(unit|integration)?tests?)(/|$)", re.I)
TRIVIAL = re.compile(r"(^__init__\.py$|^Program\.cs$|^Startup\.cs$|AssemblyInfo\.cs$|\.Designer\.cs$|"
                     r"\.g\.cs$|^setup\.py$|^conftest\.py$|^manage\.py$|\.d\.ts$|^index\.[jt]s$|"
                     r"(Migration|Snapshot|Dto|Model|Config|Options|Constants?)\.cs$)", re.I)
MIN_LINES = 30
MAX_LISTED = 25


def _stem(name: str) -> str:
    s = Path(name).stem.lower()
    s = re.sub(r"\.(spec|test)$", "", s)
    return re.sub(r"(^test_|_test$|tests?$)", "", s)


class MissingTestsSkill(Skill):
    id = "testes"
    category = "Testes"

    def analyze(self, root, languages):
        tests, sources = [], []
        for p in self.checked(iter_source_files(root)):
            r = rel(p, root)
            (tests if TEST_FILE.search(p.name) or TEST_DIR.search(r.rsplit("/", 1)[0] if "/" in r else "") else sources).append(p)
        if not sources:
            return []
        if not tests:
            return [self.finding(
                rule_id="sem-testes", severity=Severity.ALTA,
                message=t("f.notests", n=len(sources)),
                suggestion=t("f.notests.sug"),
            )]
        tested = {_stem(t.name) for t in tests}
        findings = []
        untested = []
        for p in sources:
            if TRIVIAL.search(p.name):
                continue
            try:
                lines = sum(1 for line in p.open(encoding="utf-8", errors="ignore") if line.strip())
            except OSError:
                continue
            if lines >= MIN_LINES and _stem(p.name) not in tested:
                untested.append((lines, p))
        ratio = len(tests) / max(len(sources), 1)
        if ratio < 0.2:
            findings.append(self.finding(
                rule_id="poucos-testes", severity=Severity.MEDIA,
                message=t("f.fewtests", t=len(tests), s=len(sources), ratio=f"{ratio:.0%}"),
                suggestion=t("f.fewtests.sug"),
            ))
        for lines, p in sorted(untested, reverse=True)[:MAX_LISTED]:
            findings.append(self.finding(
                rule_id="arquivo-sem-teste", severity=Severity.BAIXA,
                message=t("f.untested", lines=lines, stem=p.stem),
                file=rel(p, root), suggestion=t("f.untested.sug"),
            ))
        if len(untested) > MAX_LISTED:
            findings.append(self.finding(
                rule_id="arquivo-sem-teste", severity=Severity.INFO,
                message=t("f.untested.more", n=len(untested) - MAX_LISTED),
            ))
        return findings
