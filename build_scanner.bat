@echo off
REM Builds ShinyScanner.exe with PyInstaller (run from this folder, NOT as Admin)
setlocal

where python >nul 2>&1
if errorlevel 1 (
    echo Python not found in PATH.
    pause
    exit /b 1
)

python -m pip install --upgrade pyinstaller numpy Pillow

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name ShinyScanner ^
    --clean ^
    "%~dp0shiny_scanner.py"

echo.
echo Build complete.
echo See:  %~dp0dist\ShinyScanner.exe
pause
