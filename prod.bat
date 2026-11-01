@echo off
rem Dreamtify - mode produksi (waitress, port WEB_PORT di .env)
rem Pemakaian: prod.bat              -> jalankan di jendela ini
rem            prod.bat --service    -> dipakai Scheduled Task "Dreamtify Web"
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\prod.ps1" %*
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" if /i not "%~1"=="--service" (
  echo.
  echo [GAGAL] prod.bat berhenti dengan kode %EXITCODE%. Baca pesan di atas.
  echo %CMDCMDLINE% | find /i "/c" >nul && pause
)
endlocal & exit /b %EXITCODE%
