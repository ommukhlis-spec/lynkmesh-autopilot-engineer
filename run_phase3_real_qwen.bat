@echo off
setlocal
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  echo [SETUP] Creating virtual environment...
  py -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
python -m agent.main
pause
