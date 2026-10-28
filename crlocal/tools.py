"""Localiza executáveis: primeiro a pasta tools/ embutida no app, depois o PATH."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import control

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
        # o crlocal.exe (console) escreve erros no stderr; o exe da interface abriria uma janela de erro
        # invisível e o processo ficaria parado esperando alguém fechar
        console = Path(sys.executable).with_name("crlocal.exe" if IS_WINDOWS else "crlocal")
        return [str(console if console.is_file() else sys.executable), "--run-tool", name]
    found = shutil.which(name)
    if found:
        return [found]
    candidate = Path(sys.executable).parent / ("Scripts" if IS_WINDOWS else "") / exe
    return [str(candidate)] if candidate.is_file() else None


def ensure_std_streams() -> None:
    """No .exe sem console, stdout/stderr vêm como None: reabre os pipes herdados do processo pai."""
    for fd, attr, mode in ((0, "stdin", "r"), (1, "stdout", "w"), (2, "stderr", "w")):
        if getattr(sys, attr) is None:
            try:
                setattr(sys, attr, open(fd, mode, encoding="utf-8", closefd=False))  # noqa: SIM115
            except OSError:
                setattr(sys, attr, open(os.devnull, mode, encoding="utf-8"))  # noqa: SIM115


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
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", SEMGREP_SEND_METRICS="off", **{CHILD_ENV: "1"})
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True,
        encoding="utf-8", errors="replace", env=env, creationflags=CREATE_NO_WINDOW,
    )
    ctl, skill = control.active(), control.current_skill()
    if ctl:
        ctl.register(skill, proc)
    try:
        waited = 0.0
        while True:
            try:
                out, err = proc.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                if not (ctl and ctl.paused):  # o tempo pausado não conta para o limite
                    waited += 1
                if waited >= timeout:
                    proc.kill()
                    proc.communicate()
                    raise subprocess.TimeoutExpired(cmd, timeout) from None
    finally:
        if ctl:
            ctl.unregister(skill, proc)
    if ctl:
        ctl.checkpoint(skill)  # pulada/concluída enquanto rodava: o processo foi encerrado, descarta a saída
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
