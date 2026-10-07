@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [Candle Lab B3] Preparando o ambiente pela primeira vez...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  python -m pip install -e .
) else (
  call .venv\Scripts\activate.bat
)
start "" http://127.0.0.1:8765
python -m candle_lab.cli serve
endlocal
