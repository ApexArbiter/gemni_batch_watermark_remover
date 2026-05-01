@echo off

setlocal EnableExtensions

cd /d "%~dp0"

title Watermark removal - batch (GPU)



if not exist "%~dp0batch-input" mkdir "%~dp0batch-input"

if not exist "%~dp0batch-output" mkdir "%~dp0batch-output"



set "INPUT_DIR=%~dp0batch-input"

set "MASK_FILE=%~dp0watermark-mask.png"

set "OUTPUT_DIR=%~dp0batch-output"

REM --- Mask mode ---------------------------------------------------------------
REM Set MASK_RULES_JSON=path\to\rules.json for size-based masks (see mask-rules.example.json).
set "MASK_RULES_JSON="
REM USE_CORNER_MASK=1 (default): one set of corner fractions for every photo.
REM USE_CORNER_MASK=0: watermark-mask.png only.
set "USE_CORNER_MASK=1"
set "CORNER_W_FRAC=0.12"
set "CORNER_H_FRAC=0.20"
set "CORNER_MARGIN_FRAC=0.08"
set "CORNER_PAD_FRAC=0"



REM CUDA PyTorch: run install-gpu-pytorch.bat once first.

set "DEVICE=cuda"



REM GPU batch always uses 1 process: each extra worker would load another LaMa on the same VRAM → OOM.

REM Use batch-remove-watermark.bat with WORKERS^>1 if you want CPU parallelism.



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
  python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --mask-rules "%MASK_RULES_JSON%" --model lama --device %DEVICE% --workers 1
) else if "%USE_CORNER_MASK%"=="1" (
  python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --use-corner-mask --corner-w-frac %CORNER_W_FRAC% --corner-h-frac %CORNER_H_FRAC% --corner-margin-frac %CORNER_MARGIN_FRAC% --corner-pad-frac %CORNER_PAD_FRAC% --model lama --device %DEVICE% --workers 1
) else (
  python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --mask "%MASK_FILE%" --model lama --device %DEVICE% --workers 1
)

set "EC=%ERRORLEVEL%"



echo.

if not "%EC%"=="0" (

  echo.

  echo  ERROR  Batch job failed with exit code %EC%.

  echo         CUDA OOM: close games/browsers using the GPU; this script uses 1 GPU worker only.

  echo         Or use batch-remove-watermark.bat ^(CPU^) if GPU memory is tight.

) else (

  echo.

  echo  Done.  You can close this window.

)

echo.

pause

exit /b %EC%


