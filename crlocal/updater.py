"""Verifica novas versões na página de Releases do GitHub e instala a atualização.

É a única conexão de rede do app: consulta só a versão publicada e nunca envia código
ou dados do projeto analisado. Pode ser desligada nas configurações.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__

REPO = "MateusKraiewski/CodeReview-App"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
SETUP_ASSET = re.compile(r"^CodeReviewLocal-Setup-.*\.exe$", re.I)


@dataclass
class Update:
    version: str
    setup_url: str | None
    page_url: str
    notes: str


def parse_version(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", (text or "").lstrip("vV").split("-")[0])
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def parse_release(data: dict) -> Update:
    asset = next((a for a in data.get("assets", []) if SETUP_ASSET.match(a.get("name", ""))), None)
    return Update(
        version=(data.get("tag_name") or "").lstrip("vV"),
        setup_url=asset.get("browser_download_url") if asset else None,
        page_url=data.get("html_url") or RELEASES_PAGE,
        notes=(data.get("body") or "").strip(),
    )


def check(timeout: float = 6.0) -> Update | None:
    """Devolve a atualização disponível, ou None se já está na última versão ou sem internet."""
    req = urllib.request.Request(API_LATEST, headers={"User-Agent": f"CodeReviewLocal/{__version__}",
                                                      "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (URL fixa https)
            update = parse_release(json.load(resp))
    except (OSError, ValueError):
        return None
    return update if update.version and is_newer(update.version) else None


def can_self_update() -> bool:
    """Só o app instalado (.exe) se atualiza sozinho; rodando do código-fonte, abre a página."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def download(url: str, progress: Callable[[float], None] | None = None) -> Path:
    dest = Path(tempfile.gettempdir()) / url.rsplit("/", 1)[-1]
    req = urllib.request.Request(url, headers={"User-Agent": f"CodeReviewLocal/{__version__}"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as fh:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(256 * 1024):
            fh.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)
    return dest


def run_installer(setup: Path) -> None:
    """Executa o instalador em modo silencioso; ele fecha o app, atualiza e abre de novo."""
    subprocess.Popen([str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/NORESTART"],  # noqa: S603
                     close_fds=True)
