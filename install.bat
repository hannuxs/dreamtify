@echo off
rem Dreamtify - instalasi produksi. Klik kanan -> Run as administrator.
rem Aman dijalankan ulang untuk update.
rem Opsi: -NoService  -NonInteractive  -InstallMariaDB -MariaDBMsi C:\path\mariadb.msi
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" %*
set "EXITCODE=%ERRORLEVEL%"
echo.
if "%EXITCODE%"=="0" (echo Instalasi selesai.) else (echo [GAGAL] Instalasi berhenti dengan kode %EXITCODE%. Baca pesan di atas dan folder logs.)
echo %CMDCMDLINE% | find /i "/c" >nul && pause
endlocal & exit /b %EXITCODE%
