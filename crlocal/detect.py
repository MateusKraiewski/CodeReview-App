from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

IGNORED_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "bin", "obj", "dist", "build", "out",
    ".venv", "venv", "env", "__pycache__", ".idea", ".vs", ".vscode", "packages",
    "target", ".gradle", "coverage", ".next", ".nuxt", "vendor", ".tox",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "TestResults",
}

EXTENSIONS = {
    ".py": "Python", ".cs": "C#", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin",
    ".go": "Go", ".rb": "Ruby", ".php": "PHP", ".c": "C", ".h": "C",
    ".cpp": "C++", ".hpp": "C++", ".cc": "C++", ".swift": "Swift",
    ".rs": "Rust", ".scala": "Scala", ".vb": "VB.NET", ".sql": "SQL",
}


def iter_source_files(root: str | Path):
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]
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
