@echo off
REM ============================================================
REM  DocRegistry Pro - start the DEV app at http://localhost:8510
REM  Double-click this file. Keep the black windows open while you
REM  use the app; close them (or press Ctrl+C) to stop the dev app and
REM  the DEV WhatsApp sender. Uses config.dev.yaml (never the live sheet).
REM ============================================================
title DocRegistry Pro - DEV (localhost:8510)
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] The project's venv was not found in "%~dp0venv".
    echo         Create it first:  python -m venv venv
    echo         then:             venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Already running? Just open the browser.
netstat -ano | findstr /R /C:":8510 .*LISTENING" >nul
if %errorlevel%==0 (
    echo Dev app is already running - opening http://localhost:8510
    start "" http://localhost:8510
    timeout /t 3 >nul
    exit /b 0
)

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set BRANCH=%%b
echo.
echo  Starting DocRegistry Pro DEV app...
echo  Git branch : %BRANCH%
echo  URL        : http://localhost:8510
echo  (the browser opens in a few seconds; first load takes ~20s)
echo.

REM Use the DEV settings: dev Google Sheet, dev WhatsApp sender, dev group, dev test numbers
set DOCREGISTRY_CONFIG=config.dev.yaml
echo  Settings   : config.dev.yaml (DEV sheet + DEV WhatsApp)

REM Start the DEV WhatsApp sender in its own window (its own login: baileys_service/auth_info_dev)
netstat -ano | findstr /R /C:":3001 .*LISTENING" >nul
if errorlevel 1 (
    echo  Starting the DEV WhatsApp sender on http://localhost:3001 ...
    start "DocRegistry DEV WhatsApp (localhost:3001)" cmd /k "cd /d "%~dp0baileys_service" && set AUTH_DIR=auth_info_dev&& set PORT=3001&& node server.js"
) else (
    echo  DEV WhatsApp sender already running on http://localhost:3001
)
echo.

REM Open the browser once the server has had time to start
start "" cmd /c "timeout /t 8 >nul & start http://localhost:8510"

venv\Scripts\python.exe -m streamlit run app.py --server.port 8510 --server.headless true

echo.
echo Dev app stopped.
pause
