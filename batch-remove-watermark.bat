@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Watermark removal - batch

if not exist "%~dp0batch-input" mkdir "%~dp0batch-input"
if not exist "%~dp0batch-output" mkdir "%~dp0batch-output"

set "INPUT_DIR=%~dp0batch-input"
set "MASK_FILE=%~dp0watermark-mask.png"
set "OUTPUT_DIR=%~dp0batch-output"

REM --- Mask mode ---------------------------------------------------------------
REM USE_CORNER_MASK=1 (default): rectangle from fractions per image — works when photo sizes differ.
REM USE_CORNER_MASK=0: single PNG (--mask); must match watermark placement after resize.
set "USE_CORNER_MASK=1"
set "CORNER_W_FRAC=0.12"
set "CORNER_H_FRAC=0.20"
set "CORNER_MARGIN_FRAC=0.08"
set "CORNER_PAD_FRAC=0"

REM Device: use cpu now. After installing CUDA PyTorch, change to: cuda
set "DEVICE=cpu"

REM Parallel processes (each loads LaMa = more RAM). Try 2-4 on CPU; use 1 if low RAM or GPU.
set "WORKERS=2"

if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: Virtual environment not found. Run setup.bat first.
  pause
  exit /b 1
)

if "%USE_CORNER_MASK%"=="0" (
  if not exist "%MASK_FILE%" (
    echo ERROR: watermark-mask.png not found next to this script ^(USE_CORNER_MASK=0^).
    pause
    exit /b 1
  )
)

call "%~dp0.venv\Scripts\activate.bat"

set PYTHONWARNINGS=ignore::FutureWarning
if "%USE_CORNER_MASK%"=="1" (
  python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --use-corner-mask --corner-w-frac %CORNER_W_FRAC% --corner-h-frac %CORNER_H_FRAC% --corner-margin-frac %CORNER_MARGIN_FRAC% --corner-pad-frac %CORNER_PAD_FRAC% --model lama --device %DEVICE% --workers %WORKERS%
) else (
  python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --mask "%MASK_FILE%" --model lama --device %DEVICE% --workers %WORKERS%
)
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
