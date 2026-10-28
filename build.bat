@echo off
REM Gera o app em dist\CodeReviewLocal\CodeReviewLocal.exe (precisa de Python 3.11+ e internet só agora)
setlocal
cd /d "%~dp0"
if not exist .venv (py -3 -m venv .venv || python -m venv .venv) || goto :erro
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller || goto :erro
powershell -ExecutionPolicy Bypass -File scripts\baixar_ferramentas.ps1 || goto :erro
python scripts\baixar_regras.py || echo Aviso: regras publicas do Semgrep nao baixadas, usando apenas as regras proprias.
pyinstaller build\CodeReviewLocal.spec --noconfirm --distpath dist --workpath build\tmp || goto :erro
echo.
echo OK: dist\CodeReviewLocal\CodeReviewLocal.exe
exit /b 0
:erro
echo FALHOU. Veja as mensagens acima.
exit /b 1
