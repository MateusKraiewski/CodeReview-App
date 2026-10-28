"""Baixa (uma vez, com internet) os pacotes de regras públicos do Semgrep para rules/semgrep.
Depois disso a análise roda 100% offline. Licença das regras: Semgrep Rules License v1.0 (uso interno)."""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

import yaml

URL = "https://github.com/semgrep/semgrep-rules/archive/refs/heads/develop.zip"
LANGS = ["csharp", "python", "javascript", "typescript", "java", "go", "generic"]
DEST = Path(__file__).resolve().parent.parent / "rules" / "semgrep"


def main() -> None:
    print("Baixando", URL)
    data = urllib.request.urlopen(URL, timeout=120).read()
    DEST.mkdir(parents=True, exist_ok=True)
    kept = skipped = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) < 3 or parts[1] not in LANGS or not name.endswith((".yaml", ".yml")):
                continue
            if ".test." in name or "/fixtures/" in name:
                continue
            data = z.read(name)
            if not _is_rules_file(data):  # o repositório também tem YAMLs que são alvos de teste, não regras
                skipped += 1
                continue
            target = DEST.joinpath(*parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            kept += 1
    print(f"{kept} arquivos de regras salvos em {DEST} ({skipped} YAMLs que não são regras foram ignorados)")


def _is_rules_file(data: bytes) -> bool:
    try:
        doc = yaml.safe_load(data)
    except yaml.YAMLError:
        return False
    rules = doc.get("rules") if isinstance(doc, dict) else None
    return isinstance(rules, list) and bool(rules) and all(isinstance(r, dict) and "id" in r for r in rules)


if __name__ == "__main__":
    main()
