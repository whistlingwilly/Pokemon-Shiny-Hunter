@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Shiny Hunter ✨

set "PY="
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python314\python.exe" set "PY=%USERPROFILE%\AppData\Local\Programs\Python\Python314\python.exe"
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe" set "PY=%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe"

if not defined PY (
    for /f "tokens=*" %%F in ('where python 2^>nul') do (
        echo %%F | findstr /i "WindowsApps" >nul || (if not defined PY set "PY=%%F")
    )
)
if not defined PY (echo Python not found - install from python.org & pause & exit /b 1)

echo Installing dependencies...
"!PY!" -m pip install pyautogui mss numpy pillow pynput scipy --quiet --disable-pip-version-check
"!PY!" shiny_hunter.py
