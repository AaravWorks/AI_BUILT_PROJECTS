@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH.
    echo Install Python 3.10 or newer and enable "Add Python to PATH".
    pause
    exit /b 1
)

python main.py
pause
