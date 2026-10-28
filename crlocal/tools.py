"""Localiza executáveis: primeiro a pasta tools/ embutida no app, depois o PATH."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = os.name == "nt"
CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


def app_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


FROZEN = getattr(sys, "frozen", False)

# Ferramentas Python embutidas no .exe: o app chama a si mesmo com --run-tool <nome>
PY_TOOLS = {
    "bandit": ("bandit.cli.main", "main"),
    # pysemgrep: o entrypoint padrão usa os.execvp, que no Windows perde a saída capturada
    "semgrep": ("semgrep.main", "main"),
}


def find_tool(name: str) -> list[str] | None:
    """Comando para executar a ferramenta, ou None se ela não estiver disponível."""
    exe = name + (".exe" if IS_WINDOWS else "")
    for base in (app_dir() / "tools", app_dir() / "tools" / name):
        candidate = base / exe
        if candidate.is_file():
            return [str(candidate)]
    if FROZEN and name in PY_TOOLS:
        return [sys.executable, "--run-tool", name]
    found = shutil.which(name)
    if found:
        return [found]
    candidate = Path(sys.executable).parent / ("Scripts" if IS_WINDOWS else "") / exe
    return [str(candidate)] if candidate.is_file() else None


def ensure_std_streams() -> None:
    """No .exe sem console, stdout/stderr vêm como None: reabre os pipes herdados do processo pai."""
    for fd, attr in ((1, "stdout"), (2, "stderr")):
        if getattr(sys, attr) is None:
            try:
                setattr(sys, attr, open(fd, "w", encoding="utf-8", closefd=False))  # noqa: SIM115
            except OSError:
                setattr(sys, attr, open(os.devnull, "w", encoding="utf-8"))  # noqa: SIM115


def dispatch_tool(argv: list[str]) -> int | None:
    """Se o processo foi iniciado com --run-tool, executa a ferramenta e devolve o código de saída."""
    if len(argv) < 3 or argv[1] != "--run-tool" or argv[2] not in PY_TOOLS:
        return None
    import importlib

    module, func = PY_TOOLS[argv[2]]
    ensure_std_streams()
    sys.argv = [argv[2], *argv[3:]]
    try:
        result = getattr(importlib.import_module(module), func)()
    except SystemExit as e:
        result = e.code
    return result if isinstance(result, int) else 0


CHILD_ENV = "CRLOCAL_CHILD"


def run(cmd: list[str], cwd: str | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    # CHILD_ENV avisa o .exe chamado como ferramenta para nunca abrir a interface gráfica
    env = dict(os.environ, PYTHONIOENCODING="utf-8", SEMGREP_SEND_METRICS="off", **{CHILD_ENV: "1"})
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, env=env, creationflags=CREATE_NO_WINDOW,
    )
