@echo off
setlocal
cd /d "%~dp0.."
where py >nul 2>nul && set "PY=py -3" || set "PY=python"
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r "apps\api\requirements.txt"
echo API_VENV_OK
