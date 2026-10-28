from __future__ import annotations

import tempfile
from pathlib import Path

from ..i18n import t
from ..tools import find_tool, run
from .base import Skill, SkillSkipped, parse_sarif


class DevSkimSkill(Skill):
    id = "seguranca-devskim"
    category = "Segurança"

    def analyze(self, root, languages):
        exe = find_tool("devskim")
        if not exe:
            raise SkillSkipped(t("skip.tool_missing", tool="devskim"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "devskim.sarif"
            proc = run([*exe, "analyze", "-I", str(root), "-O", str(out), "-f", "sarif",
                        "--ignore-globs", "**/bin/**,**/obj/**,**/node_modules/**,**/.git/**"])
            if not out.exists():
                raise RuntimeError(proc.stderr.strip()[-400:] or t("err.no_output", tool="devskim"))
            return parse_sarif(out.read_text(encoding="utf-8"), self, root)
