# =====================================================================
# install.ps1 - instalasi produksi Dreamtify. Dipanggil install.bat.
# Aman dijalankan ulang (update): kunci di .env tidak pernah ditimpa.
# Lihat docs/INSTALASI-SERVER.md.
# =====================================================================
param(
    [switch]$InstallMariaDB,
    [string]$MariaDBMsi = '',
    [switch]$NoService,
    [switch]$NonInteractive
)

. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $script:ProjectRoot
$env:DJANGO_ENV = 'prod'
$env:PYTHONUTF8 = '1'
$ask = -not $NonInteractive

function Ask([string]$Prompt, [string]$Default = '') {
    if (-not $ask) { return $Default }
    $label = if ($Default) { "$Prompt [$Default]" } else { $Prompt }
    $answer = (Read-Host $label).Trim()
    if ($answer) { return $answer }
    return $Default
}

function Get-ServerAddress {
    $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } | Select-Object -First 1
    if ($ip) { return $ip.IPAddress }
    return '127.0.0.1'
}

function Set-WebAddress([string]$Address, [int]$Port) {
    Set-DotEnvValue 'ALLOWED_HOSTS' "localhost,127.0.0.1,$Address"
    Set-DotEnvValue 'CSRF_TRUSTED_ORIGINS' "http://${Address}:$Port,http://localhost:$Port,http://127.0.0.1:$Port"
    Set-DotEnvValue 'SITE_URL' "http://${Address}:$Port"
}

function Set-RemoteDatabase {
    Set-DotEnvValue 'DB_HOST' (Ask 'Alamat server MariaDB (IP/domain)')
    Set-DotEnvValue 'DB_PORT' (Ask 'Port MariaDB' '3309')
    Set-DotEnvValue 'DB_NAME' (Ask 'Nama database' 'dreamtify')
    Set-DotEnvValue 'DB_USER' (Ask 'User database' 'dreamtify')
    $secure = Read-Host 'Sandi user database' -AsSecureString
    Set-DotEnvValue 'DB_PASSWORD' ("'" + (ConvertFrom-SecureToPlain $secure) + "'")
}

# ---------------------------------------------------------------------
# 1. Hak Administrator
# ---------------------------------------------------------------------
$identity = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = $identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin -and -not $NoService) {
    if (-not $ask) {
        Write-Fail 'Butuh hak Administrator.' 'Jalankan dari PowerShell Administrator, atau tambahkan -NoService.'
        exit 1
    }
    Write-Info 'Meminta hak Administrator...'
    $forward = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($InstallMariaDB) { $forward += '-InstallMariaDB' }
    if ($MariaDBMsi) { $forward += '-MariaDBMsi', "`"$MariaDBMsi`"" }
    $p = Start-Process powershell -Verb RunAs -ArgumentList $forward -Wait -PassThru
    exit $p.ExitCode
}

$logDir = Join-Path $script:ProjectRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("install-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmm'))
Start-Transcript -Path $logFile -Force | Out-Null

try {
    Write-Host ''
    Write-Host '  Dreamtify - instalasi produksi' -ForegroundColor Cyan
    Write-Host '  ------------------------------' -ForegroundColor Cyan
    if ($isAdmin) { Write-Ok 'Berjalan sebagai Administrator' } else { Write-Skip 'Tanpa Administrator (-NoService)' }

    # -----------------------------------------------------------------
    # 2. Python
    # -----------------------------------------------------------------
    if (-not (Test-Path (Get-VenvPython)) -and -not (Find-Python312)) {
        $answer = Ask 'Python 3.12 tidak ditemukan. Pasang lewat winget? [Y/n]' 'Y'
        if ($ask -and $answer -match '^[Yy]' -and (Get-Command winget -ErrorAction SilentlyContinue)) {
            & winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
            $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
        }
        if (-not (Find-Python312)) {
            Write-Fail 'Python 3.12 tidak ditemukan.' 'Pasang Python 3.12 64-bit dari python.org, centang "Add python.exe to PATH", lalu jalankan ulang.'
            exit 1
        }
    }
    Write-Ok 'Python 3.12 tersedia'

    # -----------------------------------------------------------------
    # 3. Paket Python (mysqlclient gagal -> PyMySQL)
    # -----------------------------------------------------------------
    $firstRun = -not (Test-Path (Get-EnvPath))
    if ($firstRun) { New-DotEnvFile; Write-Ok '.env dibuat (rahasia acak)' } else { Write-Skip '.env sudah ada, kunci tidak diubah' }
    Initialize-Venv 'requirements.txt' -AllowPyMySql

    # -----------------------------------------------------------------
    # 4. Pengaturan .env
    # -----------------------------------------------------------------
    $cfg = Read-DotEnv
    $webPort = if ($cfg.WEB_PORT) { [int]$cfg.WEB_PORT } else { 8383 }
    if ($firstRun -and $ask) {
        $where = Ask 'MariaDB ada di (1) server ini, atau (2) server lain?' '1'
        if ($where -eq '2') { Set-RemoteDatabase }
    }
    if ($ask -and $cfg.SITE_URL -match 'localhost|127\.0\.0\.1') {
        $address = Ask 'IP/domain server ini (untuk membuka web)' (Get-ServerAddress)
        Set-WebAddress $address $webPort
        Write-Ok "Alamat web: http://${address}:$webPort"
    }
    $cfg = Read-DotEnv
    $dbHost = if ($cfg.DB_HOST) { $cfg.DB_HOST } else { '127.0.0.1' }

    # -----------------------------------------------------------------
    # 5. MariaDB
    # -----------------------------------------------------------------
    if ($InstallMariaDB) {
        if (-not (Test-LocalDbHost $dbHost)) {
            Write-Fail '-InstallMariaDB hanya untuk MariaDB di server ini, sedangkan DB_HOST menunjuk server lain.'
            exit 1
        }
        if (-not $MariaDBMsi -or -not (Test-Path $MariaDBMsi)) {
            Write-Fail 'File MSI MariaDB tidak ditemukan.' 'Pakai: install.bat -InstallMariaDB -MariaDBMsi C:\path\mariadb.msi'
            exit 1
        }
        if (Get-Service MariaDB -ErrorAction SilentlyContinue) {
            Write-Skip 'Layanan MariaDB sudah ada'
        } else {
            $rootSecure = Read-Host 'Buat password root MariaDB' -AsSecureString
            $script:RootPw = ConvertFrom-SecureToPlain $rootSecure
            $port = if ($cfg.DB_PORT) { $cfg.DB_PORT } else { '3309' }
            $msiArgs = "/i `"$MariaDBMsi`" PORT=$port PASSWORD=`"$($script:RootPw)`" SERVICENAME=MariaDB UTF8=1 /qn"
            $p = Start-Process msiexec -ArgumentList $msiArgs -Wait -PassThru
            if ($p.ExitCode -ne 0) { Write-Fail "Pemasangan MariaDB gagal (kode $($p.ExitCode))."; exit 1 }
            Write-Ok 'MariaDB terpasang'
        }
    }

    # -----------------------------------------------------------------
    # 6. Database, tabel, data awal
    # -----------------------------------------------------------------
    if (-not (Invoke-DatabaseSetup -AllowPrompt:$ask)) { exit 1 }

    # -----------------------------------------------------------------
    # 7. File statis & Owner
    # -----------------------------------------------------------------
    Invoke-Manage collectstatic --noinput -v 0
    if ($LASTEXITCODE -ne 0) { Write-Fail 'collectstatic gagal (lihat pesan di atas).'; exit 1 }
    Write-Ok 'File statis siap'

    if ($ask) {
        & (Get-VenvPython) manage.py buat_owner
        if ($LASTEXITCODE -ne 0) { Write-Warn 'Akun Owner belum dibuat. Ulangi: scripts\tugas.bat buat_owner' }
    } else {
        Write-Skip 'Mode non-interaktif: pembuatan Owner dilewati'
    }

    # Cadangan untuk backup harian (penting bila MariaDB di server lain)
    if (Find-MariaDbBin $cfg.MARIADB_BIN) {
        Write-Ok 'Program backup MariaDB ditemukan'
    } else {
        Write-Warn 'mariadb-dump tidak ada di komputer ini, jadi backup harian akan GAGAL.'
        Write-Info 'Solusi: unduh MariaDB versi ZIP, ekstrak, lalu isi MARIADB_BIN di .env dengan folder bin-nya.'
    }

    # -----------------------------------------------------------------
    # 8. Firewall & layanan
    # -----------------------------------------------------------------
    if ($NoService) {
        Write-Skip 'Firewall & Scheduled Task dilewati (-NoService). Jalankan web dengan prod.bat'
    } else {
        $ruleName = "Dreamtify Web $webPort"
        if (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue) {
            Write-Skip 'Aturan firewall sudah ada'
        } else {
            New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $webPort -Action Allow | Out-Null
            Write-Ok "Firewall membuka port $webPort"
        }
        Register-DreamtifyTasks
        & (Join-Path $PSScriptRoot 'layanan.ps1') restart

        # -------------------------------------------------------------
        # 9. Tes hidup
        # -------------------------------------------------------------
        $healthy = $false
        foreach ($i in 1..30) {
            if (Test-WebHealth $webPort) { $healthy = $true; break }
            Start-Sleep -Seconds 2
        }
        if (-not $healthy) {
            Write-Fail 'Web belum menjawab setelah 60 detik.' 'Cek logs\app.log, atau jalankan scripts\layanan.ps1 logs.'
            exit 1
        }
        Write-Ok 'Web sehat (database terhubung)'
    }

    # -----------------------------------------------------------------
    # 10. Ringkasan
    # -----------------------------------------------------------------
    $cfg = Read-DotEnv
    Write-Host ''
    Write-Host '  Selesai!' -ForegroundColor Green
    Write-Host "  Web    : $($cfg.SITE_URL)"
    Write-Host "  Admin  : $($cfg.SITE_URL)/kelola/"
    Write-Host "  Log    : $logFile"
    Write-Host ''
    Write-Host '  ================================================================' -ForegroundColor Yellow
    Write-Host '  PENTING: SALIN FILE .env KE TEMPAT AMAN (bukan di server ini).' -ForegroundColor Yellow
    Write-Host '  Tanpa kunci di dalamnya, NIK & rekening tidak bisa dibaca lagi,' -ForegroundColor Yellow
    Write-Host '  walaupun database masih utuh.' -ForegroundColor Yellow
    Write-Host '  ================================================================' -ForegroundColor Yellow
} finally {
    Stop-Transcript | Out-Null
}
exit 0
