@echo off

setlocal EnableExtensions

cd /d "%~dp0"

title Generate hand-paint mask PNGs



if not exist ".venv\Scripts\activate.bat" (

  echo Run setup.bat first.

  pause

  exit /b 1

)

call "%~dp0.venv\Scripts\activate.bat"



REM Optional: larger starter rectangle — easier to see / paint over (tweak 1.0–1.35).

set "INFLATE=1.15"



python "%~dp0generate_hand_paint_masks.py" --rules "%~dp0mask-rules.Images-default.json" --out "%~dp0masks" --inflate %INFLATE%

echo.

echo Next: edit PNGs in masks\ then set MASK_RULES_JSON to mask-rules.Images-handpaint.json

echo.

pause

exit /b %ERRORLEVEL%


