@echo off

setlocal EnableExtensions

cd /d "%~dp0"

title Install PyTorch with CUDA (GPU)



if not exist "%~dp0.venv\Scripts\activate.bat" (

  echo ERROR: .venv not found. Run setup.bat first.

  pause

  exit /b 1

)



call "%~dp0.venv\Scripts\activate.bat"



echo.

echo  This replaces the CPU-only torch in your venv with a CUDA build.

echo  RTX 3060 Ti: use a recent NVIDIA driver (Game Ready or Studio).

echo  You do NOT need the full CUDA Toolkit for pip wheels.

echo.

echo  If the install line fails, open https://pytorch.org/get-started/locally/

echo  and copy the exact Windows + Pip + CUDA command shown there.

echo.

pause



echo Uninstalling previous torch / torchvision...

pip uninstall -y torch torchvision torchaudio 2>nul



echo.

echo Installing PyTorch with CUDA 12.6 wheels (common for RTX 30 series)...

pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126

if errorlevel 1 (

  echo.

  echo ERROR: pip install failed. Try cu128 or cu124 from pytorch.org for your driver.

  pause

  exit /b 1

)



echo.

python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('Torch:', torch.__version__, 'CUDA build:', torch.version.cuda); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'n/a')"

if errorlevel 1 (

  echo ERROR: Python check failed.

  pause

  exit /b 1

)



echo.

echo Done. Use start-iopaint-webui-gpu.bat and batch-remove-watermark-gpu.bat

pause

exit /b 0


