@echo off
REM ============================================================
REM  DocRegistry Pro - start the DEV app at http://localhost:8510
REM  Double-click this file. Keep the black window open while you
REM  use the app; close it (or press Ctrl+C) to stop the dev app.
REM  Uses config.dev.yaml (DEV sheet, DEV test recipient, DEV group).
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

REM DEV messages are sent from the office number through the production WhatsApp
REM service, but only to the DEV test recipient and the DEV group (config.dev.yaml).
echo  WhatsApp   : office number -^> DEV test recipient + DEV group only
echo.

REM Open the browser once the server has had time to start
start "" cmd /c "timeout /t 8 >nul & start http://localhost:8510"

venv\Scripts\python.exe -m streamlit run app.py --server.port 8510 --server.headless true

echo.
echo Dev app stopped.
pause
