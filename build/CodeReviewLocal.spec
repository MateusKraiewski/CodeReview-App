# PyInstaller: pyinstaller build\CodeReviewLocal.spec --noconfirm
from PyInstaller.utils.hooks import collect_all

root = SPECPATH + "\\.."
datas, binaries, hidden = [], [], ["lizard_languages", "lizard_ext"]
for pkg in ("semgrep", "bandit", "lizard_ext", "lizard_languages", "reportlab"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h

import os
datas += [(root + "\\crlocal\\rules", "crlocal\\rules")]
for extra in ("rules", "tools"):  # regras Semgrep baixadas e binários .exe
    if os.path.isdir(root + "\\" + extra):
        datas += [(root + "\\" + extra, extra)]

a = Analysis([root + "\\build\\app_entry.py"], pathex=[root], datas=datas, binaries=binaries,
             hiddenimports=hidden, excludes=["matplotlib", "numpy", "pandas"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CodeReviewLocal",
          console=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="CodeReviewLocal")
