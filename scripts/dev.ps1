# =====================================================================
# dev.ps1 - menjalankan Dreamtify mode pengembangan di port 8383.
# Dipanggil oleh dev.bat. Argumen opsional: seed (isi data demo).
# Otomatis (non-interaktif): set $env:MARIADB_ROOT_PASSWORD agar
# pembuatan database tidak menanyakan password root.
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
$dbHost = if ($cfg.DB_HOST) { $cfg.DB_HOST } else { '127.0.0.1' }
$dbPort = if ($cfg.DB_PORT) { [int]$cfg.DB_PORT } else { 3309 }
$webPort = if ($cfg.WEB_PORT) { [int]$cfg.WEB_PORT } else { 8383 }
$dbName = if ($cfg.DB_NAME_DEV) { $cfg.DB_NAME_DEV } else { 'dreamtify_dev' }

# 3. MariaDB -------------------------------------------------------------
if (-not (Test-TcpPort $dbHost $dbPort)) {
    Write-Fail "MariaDB tidak bisa dihubungi di ${dbHost}:${dbPort}." `
        "Pastikan layanan MariaDB berjalan (services.msc -> MariaDB) dan memakai port $dbPort. Lihat docs/10-instalasi-windows.md."
    exit 1
}
Write-Ok "MariaDB terhubung di ${dbHost}:${dbPort}"

$script:RootPw = $env:MARIADB_ROOT_PASSWORD
function Get-RootPassword([string]$Purpose) {
    if (-not $script:RootPw) {
        $answer = Read-Host "$Purpose Butuh password root MariaDB (tidak disimpan). Lanjut? [Y/n]"
        if ($answer -and $answer -notmatch '^[Yy]') { return $null }
        $script:RootPw = ConvertFrom-SecureToPlain (Read-Host 'Password root MariaDB' -AsSecureString)
    }
    return $script:RootPw
}
function Get-MariaDbBinOrExit {
    $bin = Find-MariaDbBin $cfg.MARIADB_BIN
    if (-not $bin) {
        Write-Fail 'Folder bin MariaDB tidak ditemukan.' 'Isi MARIADB_BIN di .env, mis. C:\Program Files\MariaDB 11.4\bin'
        exit 1
    }
    return $bin
}

$check = (& $venvPy manage.py cek_db | Select-Object -Last 1)
if ($check -like 'GAGAL:*') {
    $code = ($check -split ':')[1]
    if ($code -in '1045', '1049', '1044') {
        Write-Warn "Database '$dbName' atau user '$($cfg.DB_USER)' belum siap ($check)."
        $rootPw = Get-RootPassword 'Buat database & user sekarang?'
        if (-not $rootPw) { Write-Fail 'Dibatalkan.'; exit 1 }
        $res = Initialize-AppDatabase -Bin (Get-MariaDbBinOrExit) -HostName $dbHost -Port $dbPort -RootPassword $rootPw `
            -Databases @($dbName) -User $cfg.DB_USER -Password $cfg.DB_PASSWORD
        if (-not $res.Ok) {
            Write-Fail "Gagal membuat database: $($res.Output)" 'Cek password root MariaDB lalu jalankan dev.bat lagi.'
            exit 1
        }
        Write-Ok "Database '$dbName' dan user '$($cfg.DB_USER)' siap"
        $check = (& $venvPy manage.py cek_db | Select-Object -Last 1)
    }
    if ($check -like 'GAGAL:*') {
        Write-Fail "Tidak bisa masuk ke database: $check" 'Cek DB_USER / DB_PASSWORD / DB_NAME_DEV di .env.'
        exit 1
    }
}
Write-Ok "Login database '$dbName' berhasil"

# Tabel zona waktu MariaDB (dibutuhkan Django untuk filter tanggal WIB)
if ($check -eq 'OK:TZ') {
    $rootPw = Get-RootPassword 'Tabel zona waktu MariaDB belum diisi. Isi sekarang?'
    if ($rootPw) {
        $res = Install-TimeZoneTables -Bin (Get-MariaDbBinOrExit) -HostName $dbHost -Port $dbPort -RootPassword $rootPw
        if ($res.Ok) { Write-Ok 'Tabel zona waktu MariaDB terisi' }
        else { Write-Warn "Gagal mengisi zona waktu: $($res.Output)" }
    } else {
        Write-Warn 'Zona waktu MariaDB belum diisi; filter tanggal di admin bisa error.'
    }
} else {
    Write-Skip 'Tabel zona waktu MariaDB sudah ada'
}

# 4. Migrasi ------------------------------------------------------------
Invoke-Manage migrate --noinput
if ($LASTEXITCODE -ne 0) { Write-Fail 'migrate gagal (lihat pesan di atas).'; exit 1 }
Invoke-Manage createcachetable
if ($LASTEXITCODE -ne 0) { Write-Fail 'createcachetable gagal.'; exit 1 }
Write-Ok 'Database ter-migrasi'
Invoke-Manage seed_initial
if ($LASTEXITCODE -ne 0) { Write-Fail 'seed_initial gagal (lihat pesan di atas).'; exit 1 }

# 5. Opsi seed ----------------------------------------------------------
if ($Rest -contains 'seed') {
    Invoke-Manage seed_demo
    if ($LASTEXITCODE -ne 0) { Write-Fail 'seed_demo gagal (lihat pesan di atas).'; exit 1 }
}

# 6. Server ---------------------------------------------------------------
Write-Host ''
Write-Ok "Membuka http://localhost:$webPort  (dari HP: http://<IP-laptop>:$webPort)"
Write-Info 'Tekan Ctrl+C untuk berhenti.'
Write-Host ''
& $venvPy manage.py runserver "0.0.0.0:$webPort"
exit $LASTEXITCODE
