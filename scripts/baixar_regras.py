"""Baixa (uma vez, com internet) os pacotes de regras públicos do Semgrep para rules/semgrep.
Depois disso a análise roda 100% offline. Licença das regras: Semgrep Rules License v1.0 (uso interno)."""
from __future__ import annotations

import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

URL = "https://github.com/semgrep/semgrep-rules/archive/refs/heads/develop.zip"
LANGS = ["csharp", "python", "javascript", "typescript", "java", "go", "generic"]
DEST = Path(__file__).resolve().parent.parent / "rules" / "semgrep"


def main() -> None:
    print("Baixando", URL)
    data = urllib.request.urlopen(URL, timeout=120).read()
    DEST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) < 3 or parts[1] not in LANGS or not name.endswith((".yaml", ".yml")):
                continue
            if ".test." in name or "/fixtures/" in name:
                continue
            target = DEST.joinpath(*parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
    print("Regras salvas em", DEST)


if __name__ == "__main__":
    main()
