@echo off
title MediVision AI - Pharmacy OS
color 0E
cls

echo.
echo  ===============================================================
echo                     MediVision AI - Pharmacy OS
echo                   (c) Selvam Medicals - SS ^& Co
echo  ===============================================================
echo.

REM Move to script directory
cd /d "%~dp0"

REM Check Python
where python.exe >nul 2>nul
if errorlevel 1 (
  echo  [ERROR] Python not found. Install Python 3.10+ from python.org
  pause
  exit /b 1
)

REM First-run dependency install
if not exist ".deps-installed" (
  echo  [SETUP] First-time setup - installing dependencies...
  python.exe -m pip install --quiet flask python-dotenv pytesseract pillow python-pptx 2>nul
  echo done > .deps-installed
  echo  [SETUP] Dependencies installed.
  echo.
)

REM Get local IP for phone access
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R /C:"IPv4 Address"') do (
  for /f "tokens=* delims= " %%b in ("%%a") do (
    set "LOCAL_IP=%%b"
    goto :gotip
  )
)
:gotip

echo  [INFO] Starting MediVision AI...
echo.
echo  +-----------------------------------------------------------+
echo  ^|                                                           ^|
echo  ^|   Access URLs:                                            ^|
echo  ^|                                                           ^|
echo  ^|   On THIS PC:   http://localhost:5001                     ^|
echo  ^|   On PHONE:     http://%LOCAL_IP%:5001
echo  ^|                                                           ^|
echo  ^|   - Make sure phone is on the SAME Wi-Fi                  ^|
echo  ^|   - First-time: visit /license to activate                ^|
echo  ^|   - Press Ctrl+C to stop the server                       ^|
echo  ^|                                                           ^|
echo  +-----------------------------------------------------------+
echo.

REM Auto-open browser after 3 seconds
start "" /MIN cmd /c "timeout /t 3 >nul && start http://localhost:5001/portal"

REM Backup database before running
if exist "database.db" (
  if not exist "backups" mkdir backups
  for /f "tokens=2 delims==" %%i in ('wmic os get localdatetime /value') do set DT=%%i
  set BACKUP_NAME=database_%DT:~0,8%.db
  if not exist "backups\%BACKUP_NAME%" (
    copy /Y "database.db" "backups\%BACKUP_NAME%" >nul
    echo  [BACKUP] Today's backup: backups\%BACKUP_NAME%
    echo.
  )
)

REM Launch Flask
python.exe app.py

echo.
echo  MediVision AI stopped. Press any key to close window.
pause >nul
