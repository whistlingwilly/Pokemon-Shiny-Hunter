@echo off
REM ══════════════════════════════════════════════════════════════
REM  Shiny Hunter — Build Script
REM  Produces:  dist\ShinyHunter.exe  (~15-20MB, no Python needed)
REM
REM  Run from this folder. Do NOT run as Administrator.
REM  First run will install PyInstaller automatically.
REM ══════════════════════════════════════════════════════════════

setlocal
cd /d "%~dp0"

echo.
echo  ✦  Shiny Hunter Build
echo  ══════════════════════════════════════
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found.
    echo  Install Python 3.10+ from https://www.python.org/downloads/
    echo  Check "Add Python to PATH" during install.
    echo.
    pause & exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Python %PYVER% found.
echo.

echo  Installing dependencies...
python -m pip install --quiet --upgrade ^
    pyautogui mss Pillow pynput pyinstaller
if errorlevel 1 (
    echo  ERROR: pip install failed.
    pause & exit /b 1
)
echo  Dependencies OK.
echo.

echo  Building ShinyHunter.exe...
echo  (This takes 1-2 minutes on first run)
echo.

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name ShinyHunter ^
    --add-data "updater.py;." ^
    --add-data "assets/zones;assets/zones" ^
    --add-data "shiny_scanner.py;." ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "pynput.keyboard._win32" ^
    --hidden-import "pynput.mouse._win32" ^
    --exclude-module numpy ^
    --exclude-module scipy ^
    --exclude-module matplotlib ^
    --exclude-module pandas ^
    --exclude-module tkinter.test ^
    --clean ^
    shiny_hunter.py

if errorlevel 1 (
    echo.
    echo  ERROR: Build failed. See output above.
    pause & exit /b 1
)

for %%F in ("dist\ShinyHunter.exe") do set SIZE=%%~zF
set /a SIZE_MB=%SIZE% / 1048576
echo.
echo  ══════════════════════════════════════
echo  ✦  BUILD COMPLETE
echo  ══════════════════════════════════════
echo.
echo  Output:  dist\ShinyHunter.exe  (%SIZE_MB% MB)
echo.
if %SIZE_MB% GTR 25 (
    echo  WARNING: File is over 25MB - too large for GitHub releases.
    echo  Contact support for help reducing size.
) else (
    echo  Size OK for GitHub releases ^(under 25MB^).
)
echo.
echo  To create a Windows installer, run build_installer.bat next.
echo.
pause
