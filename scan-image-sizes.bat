@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Scan image sizes

REM Default folder: Images (create it and put photos there, or pass another path).
set "SCAN_DIR=%~dp0Images"
if not "%~1"=="" set "SCAN_DIR=%~1"

if not exist ".venv\Scripts\activate.bat" (
  echo ERROR: Run setup.bat first.
  pause
  exit /b 1
)

call "%~dp0.venv\Scripts\activate.bat"
python "%~dp0scan_image_sizes.py" --input "%SCAN_DIR%" --csv "%~dp0image-sizes-report.csv"
echo.
pause
exit /b %ERRORLEVEL%
