@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Project setup — venv and IOPaint

echo.
echo  ========================================================================
echo   Setup: virtual environment + IOPaint (CPU PyTorch from PyPI)
echo  ========================================================================
echo.

REM --- Folders used by batch + Web UI ---
if not exist "batch-input" mkdir "batch-input"
if not exist "batch-output" mkdir "batch-output"
if not exist "iopaint-input" mkdir "iopaint-input"
if not exist "iopaint-masks" mkdir "iopaint-masks"
if not exist "iopaint-output" mkdir "iopaint-output"

REM --- Create .venv if missing (try py 3.12, 3.11, 3.13, then python) ---
if exist ".venv\Scripts\python.exe" (
  echo Virtual environment already exists: .venv
  echo Skipping venv creation. Will still upgrade pip and install packages.
  goto :have_venv
)

echo Creating virtual environment in .venv ...
py -3.12 -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto :have_venv

if exist ".venv" rmdir /s /q ".venv" 2>nul
py -3.11 -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto :have_venv

if exist ".venv" rmdir /s /q ".venv" 2>nul
py -3.13 -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto :have_venv

if exist ".venv" rmdir /s /q ".venv" 2>nul
python -m venv .venv 2>nul
if exist ".venv\Scripts\python.exe" goto :have_venv

echo ERROR: Could not create .venv
echo Install Python 3.11+ from https://www.python.org/downloads/
echo Enable "py launcher" and "Add python.exe to PATH", then run this script again.
pause
exit /b 1

:have_venv
echo OK: .venv is ready.

call "%~dp0.venv\Scripts\activate.bat"
if errorlevel 1 (
  echo ERROR: Could not activate .venv
  pause
  exit /b 1
)

echo.
echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo.
echo Installing IOPaint ^(this may take several minutes^)...
pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto :fail

echo.
echo  ========================================================================
echo   Setup finished OK
echo  ========================================================================
echo.
echo   Next steps:
echo   - Put images in batch-input, then run batch-remove-watermark.bat
echo   - Create watermark-mask.png with make_corner_mask.py if you have not yet
echo   - Web UI: start-iopaint-webui.bat
echo   - GPU: run install-gpu-pytorch.bat once, then batch-remove-watermark-gpu.bat
echo.
iopaint --version 2>nul
echo.
pause
exit /b 0

:fail
echo.
echo ERROR: A pip step failed. Scroll up for details.
pause
exit /b 1
