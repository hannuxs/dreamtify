@echo off
rem Menjalankan perintah manage.py dalam MODE PRODUKSI (dipakai Scheduled Task).
rem Contoh: scripts\tugas.bat run_daily
rem Tanpa ini manage.py memakai mode dev (database DB_NAME_DEV).
setlocal
cd /d "%~dp0.."
set "DJANGO_ENV=prod"
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" manage.py %*
endlocal & exit /b %ERRORLEVEL%
