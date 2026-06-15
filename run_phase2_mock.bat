@echo off
setlocal
cd /d %~dp0
python -m agent.main --mock
pause
