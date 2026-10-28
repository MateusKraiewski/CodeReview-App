"""Controle de uma análise em andamento: pular skills, pausar/continuar e concluir antes do fim.

O runner registra o controle ativo; cada skill roda numa thread marcada com o próprio id, e os processos
externos que ela abre ficam registrados para poderem ser congelados (pausa) ou encerrados (pular/concluir).
"""
from __future__ import annotations

import subprocess
import threading

try:
    import psutil
except ImportError:  # sem psutil a pausa só segura as próximas skills; as que já rodam continuam
    psutil = None


class Cancelled(Exception):
    """A skill foi pulada ou a análise foi concluída pelo usuário."""


class RunControl:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._running.set()
        self._skipped: set[str] = set()
        self._finished = False
        self._procs: dict[str, list[subprocess.Popen]] = {}

    # ---------- comandos da tela ----------
    @property
    def paused(self) -> bool:
        return not self._running.is_set()

    @property
    def finished(self) -> bool:
        return self._finished

    def pause(self) -> None:
        self._running.clear()
        self._signal_procs("suspend")

    def resume(self) -> None:
        self._signal_procs("resume")
        self._running.set()

    def skip(self, skill_id: str) -> None:
        with self._lock:
            self._skipped.add(skill_id)
            procs = list(self._procs.get(skill_id, []))
        for p in procs:
            _kill(p)

    def finish(self) -> None:
        self._finished = True
        with self._lock:
            procs = [p for ps in self._procs.values() for p in ps]
        for p in procs:
            _kill(p)
        self._running.set()  # libera quem estava esperando a pausa, para encerrar

    # ---------- usado pelas skills ----------
    def cancelled(self, skill_id: str | None) -> bool:
        return self._finished or (skill_id is not None and skill_id in self._skipped)

    def checkpoint(self, skill_id: str | None) -> None:
        """Espera enquanto pausado; interrompe se a skill foi pulada ou a análise concluída."""
        self._running.wait()
        if self.cancelled(skill_id):
            raise Cancelled

    def register(self, skill_id: str | None, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs.setdefault(skill_id or "", []).append(proc)
        if self.paused:
            _signal(proc, "suspend")

    def unregister(self, skill_id: str | None, proc: subprocess.Popen) -> None:
        with self._lock:
            procs = self._procs.get(skill_id or "", [])
            if proc in procs:
                procs.remove(proc)

    def _signal_procs(self, action: str) -> None:
        with self._lock:
            procs = [p for ps in self._procs.values() for p in ps]
        for p in procs:
            _signal(p, action)


def _tree(proc: subprocess.Popen):
    if psutil is None:
        return []
    try:
        root = psutil.Process(proc.pid)
        return [root, *root.children(recursive=True)]
    except psutil.Error:
        return []


def _signal(proc: subprocess.Popen, action: str) -> None:
    for p in _tree(proc):
        try:
            getattr(p, action)()
        except psutil.Error:
            pass


def _kill(proc: subprocess.Popen) -> None:
    tree = _tree(proc)
    for p in reversed(tree):  # filhos primeiro (ex.: semgrep-core aberto pelo semgrep)
        try:
            p.kill()
        except psutil.Error:
            pass
    if not tree:
        try:
            proc.kill()
        except OSError:
            pass


# controle ativo e skill da thread atual (cada skill roda na sua thread do runner)
_active: RunControl | None = None
_local = threading.local()


def activate(control: RunControl | None) -> None:
    global _active
    _active = control


def active() -> RunControl | None:
    return _active


def current_skill() -> str | None:
    return getattr(_local, "skill", None)


def set_current_skill(skill_id: str | None) -> None:
    _local.skill = skill_id


def checkpoint() -> None:
    if _active is not None:
        _active.checkpoint(current_skill())
