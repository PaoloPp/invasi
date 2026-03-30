@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\run-local-windows.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed. Please review the error messages above.
  pause
)
endlocal
