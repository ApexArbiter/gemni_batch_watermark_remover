@echo off
REM Optional: use this ONLY if you accept Python 3.12 instead of 3.11.
REM IOPaint 1.6.0 works with Python 3.12 on Windows (CPU torch from PyPI).

setlocal EnableExtensions
cd /d "%~dp0"

py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3.12 not found via py launcher.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
)
call "%~dp0.venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
  echo ERROR: pip install failed.
  pause
  exit /b 1
)
echo Done.
pause
