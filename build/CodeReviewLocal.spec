# PyInstaller: pyinstaller build\CodeReviewLocal.spec --noconfirm
import os

from PyInstaller.utils.hooks import collect_all

root = os.path.abspath(os.path.join(SPECPATH, ".."))
datas, binaries, hidden = [], [], ["lizard_languages", "lizard_ext"]
for pkg in ("semgrep", "bandit", "stevedore", "lizard_ext", "lizard_languages", "reportlab", "yaml", "customtkinter"):
    try:
        d, b, h = collect_all(pkg)
    except Exception as e:  # semgrep é opcional: se não instalou no Windows, o app pula a skill
        print(f"AVISO: pacote {pkg} não incluído: {e}")
        continue
    datas += d
    binaries += b
    hidden += h

datas += [(os.path.join(root, "crlocal", "rules"), os.path.join("crlocal", "rules"))]
for extra in ("rules", "tools"):  # regras Semgrep baixadas e binários .exe
    if os.path.isdir(os.path.join(root, extra)):
        datas += [(os.path.join(root, extra), extra)]

a = Analysis([os.path.join(root, "build", "app_entry.py")], pathex=[root], datas=datas, binaries=binaries,
             hiddenimports=hidden, excludes=["matplotlib", "numpy", "pandas", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CodeReviewLocal", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="CodeReviewLocal")
