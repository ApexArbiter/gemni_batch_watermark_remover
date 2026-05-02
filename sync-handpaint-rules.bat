@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Sync mask-rules from folder sizes

if not exist ".venv\Scripts\activate.bat" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
call "%~dp0.venv\Scripts\activate.bat"

REM Change batch-input to Images if you paint from that tree.
set "SCAN_DIR=%~dp0batch-input"

python "%~dp0sync_handpaint_rules.py" --input "%SCAN_DIR%" --rules-out "%~dp0mask-rules.Images-handpaint.json"
echo.
echo Recreate masks in mask-painter.html for any NEW sizes listed above, then run batch.
pause
exit /b %ERRORLEVEL%
