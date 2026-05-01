@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo === Step 1: Python version ===
py -3.11 --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3.11 is not installed for the py launcher.
  echo Install "Windows installer 64-bit" from:
  echo   https://www.python.org/downloads/release/python-31111/
  echo During setup: check "Add python.exe to PATH" and optionally "py launcher".
  echo Then run this script again.
  pause
  exit /b 1
)
py -3.11 --version

echo.
echo === Step 2: Create virtual environment ".venv" ===
if exist ".venv\Scripts\python.exe" (
  echo .venv already exists. Remove the folder first if you want a clean reinstall.
) else (
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo ERROR: Failed to create venv.
    pause
    exit /b 1
  )
)

echo.
echo === Step 3: Upgrade pip and install IOPaint CPU stack ===
call "%~dp0.venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :pipfail

REM IOPaint pulls CPU PyTorch wheels from PyPI; no separate CUDA install needed.
pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto :pipfail

echo.
echo === Done ===
where iopaint >nul 2>&1
iopaint --version 2>nul
echo You can now double-click start-iopaint-webui.bat or batch-remove-watermark.bat
pause
exit /b 0

:pipfail
echo ERROR: pip install failed. Scroll above for the red error text.
pause
exit /b 1
