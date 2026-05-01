@echo off

setlocal EnableExtensions

cd /d "%~dp0"

title Watermark removal - batch (GPU)



if not exist "%~dp0batch-input" mkdir "%~dp0batch-input"

if not exist "%~dp0batch-output" mkdir "%~dp0batch-output"



set "INPUT_DIR=%~dp0batch-input"

set "MASK_FILE=%~dp0watermark-mask.png"

set "OUTPUT_DIR=%~dp0batch-output"



REM Same script as CPU batch; requires CUDA PyTorch (run install-gpu-pytorch.bat once).

set "DEVICE=cuda"



REM One worker per GPU avoids loading LaMa multiple times into VRAM.

set "WORKERS=1"



if not exist ".venv\Scripts\activate.bat" (

  echo ERROR: Virtual environment not found. Run setup.bat first.

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

python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --mask "%MASK_FILE%" --model lama --device %DEVICE% --workers %WORKERS%

set "EC=%ERRORLEVEL%"



echo.

if not "%EC%"=="0" (

  echo.

  echo  ERROR  Batch job failed with exit code %EC%.

  echo         If CUDA failed, run install-gpu-pytorch.bat and try again.

) else (

  echo.

  echo  Done.  You can close this window.

)

echo.

pause

exit /b %EC%


