@echo off
rem Dreamtify - mode pengembangan (http://localhost:8383)
rem Pemakaian: dev.bat            -> jalankan server dev
rem            dev.bat seed       -> isi data demo dulu
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" %*
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo [GAGAL] dev.bat berhenti dengan kode %EXITCODE%. Baca pesan di atas.
  rem Jeda hanya bila dibuka dengan klik ganda (jendela akan langsung tertutup)
  echo %CMDCMDLINE% | find /i "/c" >nul && pause
)
endlocal & exit /b %EXITCODE%
