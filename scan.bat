@echo off
REM Shiny Scanner — runs the scanner directly with Python
setlocal

where python >nul 2>&1
if errorlevel 1 (
    echo Python not found in PATH.
    echo Install from https://www.python.org/downloads/  ^(check "Add to PATH"^)
    pause
    exit /b 1
)

REM Ensure dependencies are installed
python -c "import numpy, PIL" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install numpy Pillow
)

python "%~dp0shiny_scanner.py"
pause
