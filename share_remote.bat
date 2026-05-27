@echo off
REM ════════════════════════════════════════════════════════════════
REM  MediVision AI — Remote Share via Cloudflare Tunnel
REM  Gives you a public https://*.trycloudflare.com URL
REM  FREE · No signup · No port forwarding · Works from any phone/PC anywhere
REM ════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion
title MediVision AI - Remote Share

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║   MediVision AI - Share Remotely with Friends               ║
echo  ║   Cloudflare Tunnel - FREE - Public HTTPS URL                ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

REM Step 1 — Check Flask is running on 5001
echo [1/4] Checking if MediVision app is running on port 5001...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:5001/welcome' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ⚠  Flask is NOT running. Starting it now in a new window...
    start "MediVision App" cmd /c "python app.py"
    echo   Waiting 5 seconds for Flask to start...
    timeout /t 5 /nobreak >nul
    powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:5001/welcome' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if errorlevel 1 (
        echo   ✗ Could not reach Flask. Run start.bat manually first.
        pause
        exit /b 1
    )
)
echo   ✓ Flask is reachable at http://localhost:5001
echo.

REM Step 2 — Check cloudflared.exe
echo [2/4] Checking Cloudflare Tunnel client...
if not exist "%~dp0cloudflared.exe" (
    echo   ⚠  cloudflared.exe not found. Downloading from Cloudflare...
    echo   This is a one-time download (~25 MB)...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%~dp0cloudflared.exe' -UseBasicParsing"
    if errorlevel 1 (
        echo   ✗ Download failed. Check internet connection.
        pause
        exit /b 1
    )
    echo   ✓ Downloaded cloudflared.exe
)
echo   ✓ cloudflared ready

REM Step 3 — Start the tunnel
echo.
echo [3/4] Starting Cloudflare Tunnel to localhost:5001...
echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║                                                              ║
echo  ║   YOUR PUBLIC URL WILL APPEAR BELOW IN 10-15 SECONDS         ║
echo  ║                                                              ║
echo  ║   Look for the line: https://something.trycloudflare.com     ║
echo  ║                                                              ║
echo  ║   Share that URL with your friends — they can open it on     ║
echo  ║   ANY phone, ANY PC, ANYWHERE in the world.                  ║
echo  ║                                                              ║
echo  ║   PRESS CTRL+C IN THIS WINDOW TO STOP SHARING                ║
echo  ║                                                              ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.
"%~dp0cloudflared.exe" tunnel --url http://localhost:5001

pause
