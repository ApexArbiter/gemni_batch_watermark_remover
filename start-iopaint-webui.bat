@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: Virtual environment not found. Run create-venv-and-install.bat first.
  pause
  exit /b 1
)

call "%~dp0.venv\Scripts\activate.bat"

REM Folders next to this project (edit if you want different paths)
if not exist "%~dp0iopaint-input" mkdir "%~dp0iopaint-input"
if not exist "%~dp0iopaint-masks" mkdir "%~dp0iopaint-masks"
if not exist "%~dp0iopaint-output" mkdir "%~dp0iopaint-output"

echo Starting IOPaint at http://127.0.0.1:8080
echo Put images in: %~dp0iopaint-input
echo Results download to: %~dp0iopaint-output
echo.
echo NOTE: iopaint-masks is NOT auto-filled. IOPaint never saves your brush to disk.
echo       That folder only lists mask PNGs you add yourself (optional).
echo       For batch: use make_corner_mask.py or paint externally, then batch-remove-watermark.bat
echo Close this window to stop the server.
echo.

REM LaMa on CPU; file manager tabs: input / output / mask (mask = pre-made files only)
iopaint start --model=lama --device=cpu --port=8080 --inbrowser ^
  --input="%~dp0iopaint-input" ^
  --mask-dir="%~dp0iopaint-masks" ^
  --output-dir="%~dp0iopaint-output"

if errorlevel 1 (
  echo ERROR: IOPaint exited with an error. See messages above.
  pause
  exit /b 1
)
