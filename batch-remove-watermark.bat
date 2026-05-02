@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

title Watermark removal - batch



if not exist "%~dp0batch-input" mkdir "%~dp0batch-input"

if not exist "%~dp0batch-output" mkdir "%~dp0batch-output"



set "INPUT_DIR=%~dp0batch-input"

set "MASK_FILE=%~dp0watermark-mask.png"

set "OUTPUT_DIR=%~dp0batch-output"



REM --- Mask mode ---------------------------------------------------------------
REM Uses handpaint JSON if any masks\gemini_*.png exists (see sync-handpaint-rules.bat).
REM Clear MASK_RULES_JSON entirely to use CORNER_* only. USE_CORNER_MASK=0 needs empty MASK_RULES_JSON + watermark-mask.png.

set "MASK_RULES_JSON=%~dp0mask-rules.Images-default.json"
dir /b "%~dp0masks\gemini_*.png" 2>nul | findstr /r "." >nul
if not errorlevel 1 set "MASK_RULES_JSON=%~dp0mask-rules.Images-handpaint.json"

set "USE_CORNER_MASK=1"

set "CORNER_W_FRAC=0.12"

set "CORNER_H_FRAC=0.20"

set "CORNER_MARGIN_FRAC=0.08"

set "CORNER_PAD_FRAC=0"



REM Device: use cpu now. After installing CUDA PyTorch, change to: cuda

set "DEVICE=cpu"



REM --- Workers (CPU only; GPU batch stays at 1) --------------------------------
REM Each worker = separate Python process + full LaMa in RAM (~1-2 GB typical).
REM LaMa inside one process often does not use every core, so total CPU%% can stay
REM moderate with few workers — raising workers usually speeds the batch until RAM fills.
for /f %%i in ('powershell -NoProfile -Command "$c=[int]((Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors); if($c -lt 1){$c=4}; [Math]::Max(2,[Math]::Min(12,[int][Math]::Round($c*0.6)]))"') do set "AUTOW=%%i"
if not defined AUTOW set "AUTOW=4"

REM To skip the prompt (e.g. Task Scheduler): set SKIP_WORKER_PROMPT=1 before calling this script.

if defined SKIP_WORKER_PROMPT (
  set "WORKERS=!AUTOW!"
) else (
  echo.
  echo  Parallel workers: suggested !AUTOW! for this PC ^(each worker uses a lot of RAM^).
  echo  Press Enter to use that, or type a number 2-16 and Enter.
  set "WORKERS="
  set /p "WORKERS=  Workers: "
  if "!WORKERS!"=="" set "WORKERS=!AUTOW!"
)



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

echo.
echo  Using !WORKERS! parallel worker^(s^).

set PYTHONWARNINGS=ignore::FutureWarning

if "!WORKERS!"=="0" set "WORKERS=1"

if not "%MASK_RULES_JSON%"=="" (
  python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --mask-rules "%MASK_RULES_JSON%" --model lama --device %DEVICE% --workers !WORKERS!
) else if "%USE_CORNER_MASK%"=="1" (
  python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --use-corner-mask --corner-w-frac %CORNER_W_FRAC% --corner-h-frac %CORNER_H_FRAC% --corner-margin-frac %CORNER_MARGIN_FRAC% --corner-pad-frac %CORNER_PAD_FRAC% --model lama --device %DEVICE% --workers !WORKERS!
) else (
  python -W "ignore::FutureWarning" "%~dp0batch_inpaint_recursive.py" --input "%INPUT_DIR%" --output "%OUTPUT_DIR%" --mask "%MASK_FILE%" --model lama --device %DEVICE% --workers !WORKERS!
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

