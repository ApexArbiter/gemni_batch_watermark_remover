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
REM Default JSON matches typical buckets (626 / 1024 / 1280x698 / ~1430x780 / 1600). Clear MASK_RULES_JSON to use CORNER_* only.
REM USE_CORNER_MASK=0 uses watermark-mask.png only when MASK_RULES_JSON is empty.

set "MASK_RULES_JSON=%~dp0mask-rules.Images-default.json"

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



if not "%MASK_RULES_JSON%"=="" (
  if not exist "%MASK_RULES_JSON%" (
    echo ERROR: mask rules file not found: %MASK_RULES_JSON%
    pause
    exit /b 1
  )
) else if "%USE_CORNER_MASK%"=="0" (
  if not exist "%MASK_FILE%" (
    echo ERROR: watermark-mask.png not found next to this script ^(USE_CORNER_MASK=0^).
    pause
    exit /b 1
  )
)



call "%~dp0.venv\Scripts\activate.bat"



set PYTHONWARNINGS=ignore::FutureWarning

if not "%MASK_RULES_JSON%"=="" (
  python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --mask-rules "%MASK_RULES_JSON%" --model lama --device %DEVICE% --workers %WORKERS%
) else if "%USE_CORNER_MASK%"=="1" (
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

