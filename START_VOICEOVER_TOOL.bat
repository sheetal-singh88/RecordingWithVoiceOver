@echo off
setlocal EnableDelayedExpansion
title Voiceover Generator — Setup ^& Launch
color 0A

echo.
echo  ============================================================
echo   Voiceover Generator — One-Click Launcher
echo  ============================================================
echo.

:: ── 1. Check Python ──────────────────────────────────────────────────────────
echo  [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo.
    echo  ERROR: Python is not installed or not on your PATH.
    echo.
    echo  Please install Python 3.8+ from:
    echo    https://www.python.org/downloads/
    echo.
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  OK — %PYVER%

:: ── 2. Install Python dependencies ───────────────────────────────────────────
echo.
echo  [2/3] Installing dependencies (flask, gtts, pydub, moviepy)...
echo  moviepy will auto-download its own FFmpeg binary on first run — no
echo  manual FFmpeg installation needed.
echo.
python -m pip install --quiet --upgrade pip
python -m pip install --quiet flask flask-cors gtts mutagen moviepy
if errorlevel 1 (
    color 0C
    echo.
    echo  ERROR: pip install failed. Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo  OK — all dependencies ready

:: ── 3. Start server + open browser ───────────────────────────────────────────
echo.
echo  [3/3] Starting Voiceover Generator server on http://localhost:5050 ...
echo.
echo  ============================================================
echo   Server is running. Opening the tool in your browser now.
echo   Press Ctrl+C in this window to stop the server.
echo  ============================================================
echo.

:: Open the HTML tool in the default browser after a short delay
set "HTML_PATH=%~dp0voiceover_tool.html"
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start "" \"%HTML_PATH%\""

:: Start the Flask server (this blocks — window stays open)
cd /d "%~dp0"
python generate_voiceover.py --serve --port 5050

:: If server exits unexpectedly
echo.
color 0E
echo  Server stopped. Press any key to exit.
pause >nul
