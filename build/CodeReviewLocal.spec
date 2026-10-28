# PyInstaller: pyinstaller build\CodeReviewLocal.spec --noconfirm
import glob
import os
import site

from PyInstaller.utils.hooks import collect_all

root = os.path.abspath(os.path.join(SPECPATH, ".."))
datas, binaries, hidden = [], [], ["lizard_languages", "lizard_ext"]
for pkg in ("semgrep", "semdep", "bandit", "stevedore", "lizard_ext", "lizard_languages", "reportlab", "yaml", "customtkinter"):
    try:
        d, b, h = collect_all(pkg)
    except Exception as e:  # semgrep é opcional: se não instalou no Windows, o app pula a skill
        print(f"AVISO: pacote {pkg} não incluído: {e}")
        continue
    datas += d
    binaries += b
    hidden += h

# módulos compilados com mypyc (usados pelo semgrep/semdep) dependem de um módulo auxiliar de nome
# aleatório na raiz do site-packages, que a análise do PyInstaller não encontra sozinha
for sp in site.getsitepackages():
    for f in glob.glob(os.path.join(sp, "*__mypyc*")):
        hidden.append(os.path.basename(f).split(".")[0])

datas += [(os.path.join(root, "crlocal", "rules"), os.path.join("crlocal", "rules")),
          (os.path.join(root, "assets"), "assets")]
icon = os.path.join(root, "assets", "icone.ico")
for extra in ("rules", "tools"):  # regras Semgrep baixadas e binários .exe
    if os.path.isdir(os.path.join(root, extra)):
        datas += [(os.path.join(root, extra), extra)]

a = Analysis([os.path.join(root, "build", "app_entry.py")], pathex=[root], datas=datas, binaries=binaries,
             hiddenimports=hidden, excludes=["matplotlib", "numpy", "pandas", "pytest"])
pyz = PYZ(a.pure)
# UTF-8 como codificação padrão: sem isso o Semgrep lê as regras em cp1252 no Windows e falha
utf8 = [("X utf8", None, "OPTION")]
exe = EXE(pyz, a.scripts, utf8, exclude_binaries=True, name="CodeReviewLocal", console=False, icon=icon)
# crlocal.exe: mesma aplicação em modo console, para terminal, tarefas do VS Code e servidor MCP
cli = EXE(pyz, a.scripts, utf8, exclude_binaries=True, name="crlocal", console=True, icon=icon)
coll = COLLECT(exe, cli, a.binaries, a.datas, name="CodeReviewLocal")
