# =====================================================================
# dev.ps1 - menjalankan Dreamtify mode pengembangan di port 8383.
# Dipanggil oleh dev.bat. Argumen opsional: seed (isi data demo).
# Bila MariaDB di komputer ini belum punya user aplikasi, password root
# ditanyakan (atau dari $env:MARIADB_ROOT_PASSWORD).
# =====================================================================
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)

. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $script:ProjectRoot
$env:DJANGO_ENV = 'dev'
$env:PYTHONUTF8 = '1'

Write-Host ''
Write-Host '  Dreamtify - mode dev' -ForegroundColor Cyan
Write-Host '  ---------------------' -ForegroundColor Cyan

# 1. Python & paket ---------------------------------------------------
Initialize-Venv 'requirements-dev.txt'
$venvPy = Get-VenvPython

# 2. File .env ----------------------------------------------------------
if (-not (Test-Path (Get-EnvPath))) {
    New-DotEnvFile
    Write-Ok '.env dibuat dari .env.example (nilai rahasia acak)'
} else {
    Write-Skip '.env sudah ada'
}
$cfg = Read-DotEnv
$webPort = if ($cfg.WEB_PORT) { [int]$cfg.WEB_PORT } else { 8383 }

# 3. Database, tabel, data awal (sesuai .env; boleh di server lain) --------
if (-not (Invoke-DatabaseSetup -AllowPrompt)) { exit 1 }

# 4. Opsi seed ----------------------------------------------------------
if ($Rest -contains 'seed') {
    Invoke-Manage seed_demo
    if ($LASTEXITCODE -ne 0) { Write-Fail 'seed_demo gagal (lihat pesan di atas).'; exit 1 }
}

# 5. Server ---------------------------------------------------------------
Write-Host ''
Write-Ok "Membuka http://localhost:$webPort  (dari HP: http://<IP-laptop>:$webPort)"
Write-Info 'Tekan Ctrl+C untuk berhenti.'
Write-Host ''
& $venvPy manage.py runserver "0.0.0.0:$webPort"
exit $LASTEXITCODE
