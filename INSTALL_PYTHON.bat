@echo off
title Install Python for MediVision AI
color 0B
echo.
echo  ================================================================
echo   MediVision AI — Python Setup Helper
echo  ================================================================
echo.
echo  This will check if Python is installed and help you install it.
echo.

:: Check if real Python is available
python --version >nul 2>&1
IF NOT ERRORLEVEL 1 (
  echo  Python is already installed:
  python --version
  echo.
  echo  Now installing required packages...
  python -m pip install flask flask-cors werkzeug --quiet
  echo  All done! Run START_APP.bat to start MediVision AI.
  pause
  exit /b 0
)

echo  Python is NOT installed.
echo.
echo  STEPS TO INSTALL PYTHON:
echo  ─────────────────────────────────────────────────────────────────
echo  1. Click OK to open the Python download page
echo  2. Click "Download Python 3.x.x" (the big yellow button)
echo  3. Run the downloaded installer
echo  4. IMPORTANT: Check the box "Add python.exe to PATH"
echo  5. Click "Install Now"
echo  6. Wait for installation to complete
echo  7. RESTART YOUR COMPUTER
echo  8. Run START_APP.bat
echo  ─────────────────────────────────────────────────────────────────
echo.
echo  Press any key to open the Python download page...
pause >nul
start https://www.python.org/downloads/
echo.
echo  After installing Python and restarting, run START_APP.bat
pause
