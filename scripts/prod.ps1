# =====================================================================
# prod.ps1 - menjalankan Dreamtify mode produksi. Dipanggil prod.bat.
# Setiap start: database & tabel disiapkan otomatis sesuai .env.
# Argumen: --service (dipakai Scheduled Task, tanpa pertanyaan)
# =====================================================================
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)

. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $script:ProjectRoot
$env:DJANGO_ENV = 'prod'
$env:PYTHONUTF8 = '1'
$service = $Rest -contains '--service'

$venvPy = Get-VenvPython
if (-not (Test-Path $venvPy) -or -not (Test-Path (Get-EnvPath))) {
    Write-Fail '.venv atau .env belum ada.' 'Jalankan install.bat dulu.'
    exit 1
}
$cfg = Read-DotEnv
$webPort = if ($cfg.WEB_PORT) { [int]$cfg.WEB_PORT } else { 8383 }

if (Test-TcpPort '127.0.0.1' $webPort) {
    $msg = "Port $webPort sudah dipakai."
    if (Get-ScheduledTask -TaskName 'Dreamtify Web' -ErrorAction SilentlyContinue) {
        Write-Fail $msg 'Web kemungkinan sudah berjalan sebagai layanan. Cek: scripts\layanan.ps1 status'
    } else {
        Write-Fail $msg 'Tutup program lain yang memakai port itu, atau ubah WEB_PORT di .env.'
    }
    exit 1
}

if (-not (Invoke-DatabaseSetup -AllowPrompt:(-not $service))) { exit 1 }

Invoke-Manage collectstatic --noinput -v 0
if ($LASTEXITCODE -ne 0) { Write-Fail 'collectstatic gagal (lihat pesan di atas).'; exit 1 }
Write-Ok 'File statis siap'

Invoke-Manage check --deploy --fail-level ERROR
if ($LASTEXITCODE -ne 0) { Write-Fail 'Pemeriksaan konfigurasi gagal (lihat pesan di atas).'; exit 1 }

Write-Ok "Web berjalan di port $webPort. Log: logs\web.log"
& $venvPy manage.py serve
exit $LASTEXITCODE
