"""Escopo do code review: projeto inteiro, alterações não commitadas ou a branch atual comparada com a base.

Usa o git da máquina. No modo de alterações, só os arquivos alterados entram no relatório, e as skills
de linguagens que não foram tocadas são puladas.
"""
from __future__ import annotations

import shutil
import subprocess  # nosec B404 (roda as ferramentas de análise e o git)
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import t

MODES = ("tudo", "local", "branch")
BASE_CANDIDATES = ("origin/HEAD", "origin/main", "origin/master", "main", "master", "origin/develop", "develop")


class ChangesError(Exception):
    """Não foi possível descobrir os arquivos alterados (sem git, fora de um repositório...)."""


@dataclass
class Scope:
    mode: str = "tudo"
    base: str = ""
    files: set[str] = field(default_factory=set)  # caminhos relativos à pasta analisada, com "/"

    @property
    def active(self) -> bool:
        return self.mode != "tudo"

    def describe(self) -> str:
        if self.mode == "local":
            return t("scope.local", n=len(self.files))
        if self.mode == "branch":
            return t("scope.branch", base=self.base, n=len(self.files))
        return t("scope.all")


def _git(root: Path, *args: str) -> str:
    git = shutil.which("git")
    if not git:
        raise ChangesError(t("chg.no_git"))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    proc = subprocess.run([git, "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",  # nosec B603
                          errors="replace", stdin=subprocess.DEVNULL, creationflags=flags, timeout=60, check=False)
    if proc.returncode != 0:
        raise ChangesError(proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else f"git {args[0]}")
    return proc.stdout


def _names(out: str) -> set[str]:
    return {line.strip().strip('"') for line in out.splitlines() if line.strip()}


def default_base(root: Path) -> str:
    for ref in BASE_CANDIDATES:
        try:
            _git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
            return ref
        except ChangesError:
            continue
    raise ChangesError(t("chg.no_base"))


def resolve_scope(root: str | Path, mode: str = "tudo", base: str | None = None) -> Scope:
    """Descobre os arquivos do escopo. `base` só vale no modo branch (padrão: main/master do repositório)."""
    if mode not in MODES:
        raise ValueError(mode)
    if mode == "tudo":
        return Scope()
    root = Path(root).resolve()
    try:
        _git(root, "rev-parse", "--is-inside-work-tree")
    except ChangesError:
        raise ChangesError(t("chg.not_repo", path=root)) from None
    if mode == "local":
        try:
            changed = _names(_git(root, "diff", "--name-only", "--relative", "HEAD"))
        except ChangesError:  # repositório sem nenhum commit ainda
            changed = _names(_git(root, "diff", "--name-only", "--relative", "--cached"))
        base = ""
    else:
        base = base or default_base(root)
        merge_base = _git(root, "merge-base", base, "HEAD").strip()
        # commits da branch + o que ainda não foi commitado, comparados com o ponto onde ela saiu da base
        changed = _names(_git(root, "diff", "--name-only", "--relative", merge_base))
    changed |= _names(_git(root, "ls-files", "--others", "--exclude-standard"))
    existing = {f.replace("\\", "/") for f in changed if (root / f).is_file()}
    return Scope(mode, base, existing)
