@echo off
REM ══════════════════════════════════════════════════════════════
REM  Shiny Hunter — Installer Builder
REM  Produces:  installer_output\ShinyHunterSetup_vX.Y.Z.exe
REM
REM  Requirements:
REM    1. Run build_exe.bat first (creates dist\ShinyHunter.exe)
REM    2. Inno Setup must be installed
REM       Download free from: https://jrsoftware.org/isinfo.php
REM
REM  The resulting .exe is a proper Windows installer with:
REM    - Setup wizard
REM    - Start menu shortcut
REM    - Desktop icon option
REM    - Uninstaller
REM ══════════════════════════════════════════════════════════════

setlocal
cd /d "%~dp0"

echo.
echo  ✦  Shiny Hunter Installer Builder
echo  ══════════════════════════════════════
echo.

REM ── Check that ShinyHunter.exe exists ─────────────────────────
if not exist "dist\ShinyHunter.exe" (
    echo  ERROR: dist\ShinyHunter.exe not found.
    echo  Run build_exe.bat first.
    echo.
    pause & exit /b 1
)
echo  Found dist\ShinyHunter.exe  OK
echo.

REM ── Find Inno Setup ───────────────────────────────────────────
set ISCC=
for %%p in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"
    "%ProgramFiles%\Inno Setup 5\ISCC.exe"
) do (
    if exist %%p set ISCC=%%p
)

if "%ISCC%"=="" (
    echo  Inno Setup not found.
    echo.
    echo  Download and install it from:
    echo    https://jrsoftware.org/isinfo.php
    echo.
    echo  Then run this script again.
    echo.
    start https://jrsoftware.org/isinfo.php
    pause & exit /b 1
)

echo  Inno Setup found: %ISCC%
echo.

REM ── Build installer ──────────────────────────────────────────
echo  Building installer...
mkdir installer_output 2>nul

%ISCC% "ShinyHunter_Setup.iss"
if errorlevel 1 (
    echo.
    echo  ERROR: Inno Setup build failed.
    pause & exit /b 1
)

echo.
echo  ══════════════════════════════════════
echo  ✦  INSTALLER COMPLETE
echo  ══════════════════════════════════════
echo.
echo  Output:  installer_output\ShinyHunterSetup_v*.exe
echo.
echo  Upload this file to a GitHub Release and users can
echo  download and install it with a double-click.
echo.
echo  Auto-update: the app will check GitHub on startup and
echo  prompt users to download new releases automatically.
echo.
pause
