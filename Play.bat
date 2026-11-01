@echo off
rem RetroRemakeRSPS - double-click to play.
cd /d "%~dp0"
where javaw >nul 2>nul
if errorlevel 1 (
  echo Java is not installed. Install Java 8 or newer from https://adoptium.net and run this again.
  start "" https://adoptium.net
  pause
  exit /b 1
)
start "" javaw -jar "%~dp0RetroRemakeRSPS.jar"
