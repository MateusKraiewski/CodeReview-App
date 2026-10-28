from __future__ import annotations

from .bandit_skill import BanditSkill
from .base import Skill
from .devskim import DevSkimSkill
from .gitleaks import GitleaksSkill
from .lizard_skill import ComplexitySkill, DuplicationSkill
from .missing_tests import MissingTestsSkill
from .osv import OsvSkill
from .patterns import PatternsSkill
from .roslyn import RoslynSkill
from .ruff_skill import RuffSkill
from .semgrep import SemgrepSkill


def all_skills() -> list[Skill]:
    return [
        GitleaksSkill(), SemgrepSkill(), DevSkimSkill(), BanditSkill(), OsvSkill(),
        RoslynSkill(), RuffSkill(), ComplexitySkill(), DuplicationSkill(),
        MissingTestsSkill(), PatternsSkill(),
    ]
