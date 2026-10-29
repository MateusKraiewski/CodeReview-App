from __future__ import annotations

import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from . import control as control_mod
from .changes import ChangesError, Scope
from .dedupe import merge_duplicates
from .detect import EXTENSIONS, detect_languages
from .i18n import t
from .ignore import load as load_ignore
from .models import Report, SkillResult
from .skills import Skill, all_skills

ProgressFn = Callable[[str, SkillResult | None], None]


def run_review(project: str | Path, skills: Iterable[Skill] | None = None,
               progress: ProgressFn | None = None, workers: int = 4, scope: Scope | None = None,
               control: control_mod.RunControl | None = None) -> Report:
    """Roda as skills. Com um `scope` ativo, só os arquivos alterados entram no resultado."""
    root = Path(project).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"{t('ui.invalid_folder')} {root}")
    skills = list(skills or all_skills())
    started, t0 = datetime.now(), time.perf_counter()
    targets = None
    ignore = load_ignore(root)
    if scope and scope.active:
        if not scope.files:
            raise ChangesError(t("chg.none"))
        targets = sorted(root / f for f in scope.files
                         if Path(f).suffix.lower() in EXTENSIONS and not ignore.ignored(f))
        languages = dict(Counter(EXTENSIONS[p.suffix.lower()] for p in targets).most_common())
    else:
        languages = detect_languages(root)

    def job(skill: Skill) -> SkillResult:
        if progress:
            progress(skill.title, None)
        result = skill.execute(root, languages, targets, ignore)
        if scope and scope.active:  # ferramentas que analisam a pasta toda: fica só o que é das alterações
            result.findings = [f for f in result.findings if f.file in scope.files]
        if progress:
            progress(skill.title, result)
        return result

    control_mod.activate(control)  # pular / pausar / concluir pela tela
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(job, skills))
    finally:
        control_mod.activate(None)
    _dedupe_across_skills(results)
    for r in results:
        r.findings.sort(key=lambda f: (-f.severity, f.file, f.line))
    return Report(str(root), languages, results, started.strftime("%d/%m/%Y %H:%M"),
                  round(time.perf_counter() - t0, 1), scope.describe() if scope and scope.active else "")


def _dedupe_across_skills(results: list[SkillResult]) -> None:
    all_findings = [f for r in results for f in r.findings]
    survivors = {id(f) for f in merge_duplicates(all_findings)}
    for r in results:
        r.findings = [f for f in r.findings if id(f) in survivors]
