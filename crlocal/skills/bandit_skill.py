from __future__ import annotations

import json

from ..detect import rel
from ..i18n import t
from ..models import Severity
from ..tools import find_tool, run
from .base import Skill, SkillSkipped
from .missing_tests import TEST_DIR, TEST_FILE


class BanditSkill(Skill):
    id = "seguranca-python"
    category = "Segurança"
    languages = {"Python"}

    def analyze(self, root, languages):
        exe = find_tool("bandit")
        if not exe:
            raise SkillSkipped(t("skip.tool_missing", tool="bandit"))
        targets = [p for p in self.cli_targets(root) if p.endswith(".py")] if self.targets is not None else []
        excludes = self.ignore.exclude_globs() if self.ignore else ["*/.git/*"]
        proc = run([*exe, "-r", *(targets or [str(root)]), "-f", "json", "-q",
                    "-x", ",".join(_fnmatch(g) for g in excludes)])
        data = json.loads(proc.stdout or "{}")
        results = [r for r in data.get("results", [])
                   # assert em teste é o jeito normal de testar em Python, não um problema de segurança
                   if not (r["test_id"] == "B101" and _is_test(rel(r["filename"], root)))]
        return [
            self.finding(
                rule_id=f"{r['test_id']} {r['test_name']}",
                message=r["issue_text"],
                severity=Severity.parse(r["issue_severity"]),
                file=rel(r["filename"], root),
                line=r["line_number"],
                suggestion=r.get("more_info", ""),
            )
            for r in results
        ]


def _is_test(path: str) -> bool:
    folder, _, name = path.rpartition("/")
    return bool(TEST_FILE.search(name) or TEST_DIR.search(folder) or name == "conftest.py")


def _fnmatch(glob: str) -> str:
    """O -x do Bandit usa fnmatch, onde * já atravessa pastas: '**/a/**/b/**' vira '*/a/*b/*'."""
    return glob.replace("/**/", "/*").replace("**/", "*/").replace("/**", "/*")
