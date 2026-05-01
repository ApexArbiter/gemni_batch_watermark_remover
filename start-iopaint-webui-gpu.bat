@echo off

setlocal EnableExtensions

cd /d "%~dp0"

title IOPaint Web UI (GPU)



if not exist ".venv\Scripts\activate.bat" (

  echo ERROR: Virtual environment not found. Run setup.bat first.

  pause

  exit /b 1

)



call "%~dp0.venv\Scripts\activate.bat"



if not exist "%~dp0iopaint-input" mkdir "%~dp0iopaint-input"

if not exist "%~dp0iopaint-masks" mkdir "%~dp0iopaint-masks"

if not exist "%~dp0iopaint-output" mkdir "%~dp0iopaint-output"



echo Starting IOPaint at http://127.0.0.1:8080  (device=cuda)

echo Requires: install-gpu-pytorch.bat completed successfully.

echo Close this window to stop the server.

echo.



iopaint start --model=lama --device=cuda --port=8080 --inbrowser ^

  --input="%~dp0iopaint-input" ^

  --mask-dir="%~dp0iopaint-masks" ^

  --output-dir="%~dp0iopaint-output"



if errorlevel 1 (

  echo ERROR: IOPaint exited. If CUDA errors, reinstall GPU PyTorch or set device=cpu in start-iopaint-webui.bat

  pause

  exit /b 1

)


