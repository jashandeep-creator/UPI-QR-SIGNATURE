@echo off
title Build UPI Invoice QR (.exe)
cd /d "%~dp0"

echo [1/4] Creating a clean build environment (first time only)...
if not exist ".build_env\Scripts\python.exe" (
    python -m venv .build_env
    if errorlevel 1 goto :error
)

echo.
echo [2/4] Installing only the packages this app needs...
".build_env\Scripts\python.exe" -m pip install --upgrade pip
".build_env\Scripts\python.exe" -m pip install pyinstaller pymupdf qrcode pillow
if errorlevel 1 goto :error

echo.
echo [3/4] Building the .exe (about 1 to 2 minutes)...
".build_env\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --collect-all pymupdf --name "UPI Invoice QR" UPI.py
if errorlevel 1 goto :error

echo.
echo [4/4] Done!
echo Your app is here:  dist\UPI Invoice QR.exe
echo Copy that single file to any Windows PC. No Python needed.
pause
exit /b 0

:error
echo.
echo Something went wrong. Make sure Python is installed and added to PATH.
pause
exit /b 1
