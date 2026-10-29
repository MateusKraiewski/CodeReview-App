from __future__ import annotations

from collections import Counter
from pathlib import Path

from .ignore import IGNORED_DIRS, IgnoreRules, walk

__all__ = ["EXTENSIONS", "IGNORED_DIRS", "detect_languages", "iter_source_files", "rel"]

EXTENSIONS = {
    ".py": "Python", ".cs": "C#", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin",
    ".go": "Go", ".rb": "Ruby", ".php": "PHP", ".c": "C", ".h": "C",
    ".cpp": "C++", ".hpp": "C++", ".cc": "C++", ".swift": "Swift",
    ".rs": "Rust", ".scala": "Scala", ".vb": "VB.NET", ".sql": "SQL",
}


def iter_source_files(root: str | Path, rules: IgnoreRules | None = None):
    """Arquivos de código do projeto, sem as pastas de build/dependências e o que o .crlocalignore tira."""
    root = Path(root)
    for dirpath, filenames in walk(root, rules):
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in EXTENSIONS:
                yield p


def detect_languages(root: str | Path) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for p in iter_source_files(root):
        counter[EXTENSIONS[p.suffix.lower()]] += 1
    return dict(counter.most_common())


def rel(path: str | Path, root: str | Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")
