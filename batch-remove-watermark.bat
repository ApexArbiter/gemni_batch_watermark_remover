@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Watermark removal - batch

if not exist "%~dp0batch-input" mkdir "%~dp0batch-input"
if not exist "%~dp0batch-output" mkdir "%~dp0batch-output"

set "INPUT_DIR=%~dp0batch-input"
set "MASK_FILE=%~dp0watermark-mask.png"
set "OUTPUT_DIR=%~dp0batch-output"

REM Device: use cpu now. After installing CUDA PyTorch, change to: cuda
set "DEVICE=cpu"

if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: Virtual environment not found. Run create-venv-and-install.bat first.
  pause
  exit /b 1
)

if not exist "%MASK_FILE%" (
  echo ERROR: watermark-mask.png not found next to this script.
  pause
  exit /b 1
)

call "%~dp0.venv\Scripts\activate.bat"

set PYTHONWARNINGS=ignore::FutureWarning
python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --mask "%MASK_FILE%" --model lama --device %DEVICE%
set "EC=%ERRORLEVEL%"

echo.
if not "%EC%"=="0" (
  echo.
  echo  ERROR  Batch job failed with exit code %EC%.
  echo         See messages above.
) else (
  echo.
  echo  Done.  You can close this window.
)
echo.
pause
exit /b %EC%
