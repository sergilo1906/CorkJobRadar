@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set TEMP=%~dp0data\tmp
set TMP=%TEMP%
if not exist "%TEMP%" mkdir "%TEMP%"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
".venv\Scripts\python.exe" -m pip --disable-pip-version-check install --cache-dir data\pip-cache -r requirements-lock.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m corkjobradar doctor
