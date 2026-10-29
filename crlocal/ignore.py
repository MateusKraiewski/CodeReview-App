"""O que o code review deixa de fora: pastas de build/dependências e os padrões dos arquivos .crlocalignore.

O .crlocalignore segue o estilo do .gitignore (um padrão por linha, # para comentário) e vale para a pasta
onde está e as de baixo, então cada projeto dentro de uma pasta maior pode ter o seu.
  exemplos/        -> a pasta exemplos (em qualquer nível abaixo do arquivo)
  docs/antigo/     -> com barra no meio, o caminho a partir da pasta do .crlocalignore
  *.min.js         -> arquivos pelo nome
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

IGNORE_FILE = ".crlocalignore"

IGNORED_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "bin", "obj", "dist", "build", "out",
    ".venv", "venv", "env", "__pycache__", ".idea", ".vs", ".vscode", "packages",
    "target", ".gradle", "coverage", ".next", ".nuxt", "vendor", ".tox",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "TestResults",
}


@dataclass
class Pattern:
    base: str      # pasta do .crlocalignore, relativa à raiz analisada ("" = a própria raiz)
    glob: str
    anchored: bool  # tinha "/" no meio: vale a partir de base, não em qualquer nível
    dir_only: bool

    @classmethod
    def parse(cls, line: str, base: str) -> Pattern | None:
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        dir_only = line.endswith("/")
        line = line.strip("/")
        return cls(base, line, "/" in line, dir_only) if line else None

    def matches(self, rel_path: str, is_dir: bool) -> bool:
        if self.base:
            if not rel_path.startswith(self.base + "/"):
                return False
            rel_path = rel_path[len(self.base) + 1:]
        parts = rel_path.split("/")
        if self.anchored:
            # casa o caminho inteiro ou uma das pastas que contêm o arquivo
            whole_ok = is_dir or not self.dir_only
            return any(fnmatch.fnmatchcase("/".join(parts[:i]), self.glob)
                       for i in range(self.glob.count("/") + 1, len(parts) + 1) if i < len(parts) or whole_ok)
        # sem "/": casa o nome de qualquer pasta do caminho, ou o do arquivo se o padrão não for só de pasta
        names = parts if is_dir else parts[:-1] + ([] if self.dir_only else [parts[-1]])
        return any(fnmatch.fnmatchcase(n, self.glob) for n in names)


@dataclass
class IgnoreRules:
    patterns: list[Pattern] = field(default_factory=list)

    def add_file(self, path: Path, base: str) -> None:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return
        self.patterns += [p for p in (Pattern.parse(line, base) for line in lines) if p]

    def ignored(self, rel_path: str, is_dir: bool = False) -> bool:
        rel_path = rel_path.replace("\\", "/").strip("/")
        if not rel_path:
            return False
        parts = rel_path.split("/")
        if IGNORED_DIRS & set(parts if is_dir else parts[:-1]):
            return True
        return any(p.matches(rel_path, is_dir) for p in self.patterns)

    def exclude_globs(self) -> list[str]:
        """Padrões no formato '**/x/**' para passar às ferramentas externas que aceitam exclusões."""
        globs = [f"**/{d}/**" for d in sorted(IGNORED_DIRS)]
        for p in self.patterns:
            prefix = f"{p.base}/" if p.base else ""
            head = prefix + p.glob if p.anchored else f"{prefix}**/{p.glob}"
            head = head if head.startswith("**/") else f"**/{head}"  # as ferramentas comparam o caminho completo
            globs.append(f"{head}/**" if p.dir_only else head)
        return globs

    def exclude_names(self) -> list[str]:
        """Padrões no formato do --exclude do Semgrep (casam nomes ou caminhos relativos)."""
        names = sorted(IGNORED_DIRS)
        for p in self.patterns:
            if not p.base:
                names.append(p.glob)
            else:
                names.append(f"{p.base}/{p.glob}" if p.anchored else f"{p.base}/**/{p.glob}")
        return names


def walk(root: str | Path, rules: IgnoreRules | None = None):
    """os.walk que pula pastas ignoradas e vai lendo os .crlocalignore que encontra pelo caminho."""
    root = Path(root)
    rules = rules if rules is not None else IgnoreRules()
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath).relative_to(root).as_posix()
        base = "" if base == "." else base
        if IGNORE_FILE in filenames:
            rules.add_file(Path(dirpath) / IGNORE_FILE, base)
        prefix = f"{base}/" if base else ""
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not rules.ignored(prefix + d, is_dir=True)]
        yield dirpath, [f for f in filenames if not rules.ignored(prefix + f)]


def load(root: str | Path) -> IgnoreRules:
    rules = IgnoreRules()
    for _ in walk(root, rules):
        pass
    return rules
