from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from .dedupe import merge_duplicates
from .detect import detect_languages
from .i18n import t
from .models import Report, SkillResult
from .skills import Skill, all_skills

ProgressFn = Callable[[str, SkillResult | None], None]


def run_review(project: str | Path, skills: Iterable[Skill] | None = None,
               progress: ProgressFn | None = None, workers: int = 4) -> Report:
    root = Path(project).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{t('ui.invalid_folder')} {root}")
    skills = list(skills or all_skills())
    started, t0 = datetime.now(), time.perf_counter()
    languages = detect_languages(root)

    def job(skill: Skill) -> SkillResult:
        if progress:
            progress(skill.title, None)
        result = skill.execute(root, languages)
        if progress:
            progress(skill.title, result)
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(job, skills))
    _dedupe_across_skills(results)
    for r in results:
        r.findings.sort(key=lambda f: (-f.severity, f.file, f.line))
    return Report(str(root), languages, results, started.strftime("%d/%m/%Y %H:%M"),
                  round(time.perf_counter() - t0, 1))


def _dedupe_across_skills(results: list[SkillResult]) -> None:
    all_findings = [f for r in results for f in r.findings]
    survivors = {id(f) for f in merge_duplicates(all_findings)}
    for r in results:
        r.findings = [f for f in r.findings if id(f) in survivors]
