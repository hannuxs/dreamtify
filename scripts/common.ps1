# =====================================================================
# Fungsi bersama untuk dev.ps1, prod.ps1, install.ps1
# Catatan: file .ps1 sengaja ASCII saja (PowerShell 5.1 membaca file
# tanpa BOM sebagai ANSI).
# =====================================================================

$ErrorActionPreference = 'Stop'
$script:ProjectRoot = Split-Path -Parent $PSScriptRoot

# ---------------------------------------------------------------------
# Log berwarna
# ---------------------------------------------------------------------
function Write-Ok([string]$Message)   { Write-Host "[OK]     $Message" -ForegroundColor Green }
function Write-Skip([string]$Message) { Write-Host "[LEWATI] $Message" -ForegroundColor DarkGray }
function Write-Info([string]$Message) { Write-Host "[INFO]   $Message" -ForegroundColor Cyan }
function Write-Warn([string]$Message) { Write-Host "[PERHATIAN] $Message" -ForegroundColor Yellow }
function Write-Fail([string]$Message, [string]$Solution = '') {
    Write-Host "[GAGAL]  $Message" -ForegroundColor Red
    if ($Solution) { Write-Host "         -> $Solution" -ForegroundColor Yellow }
}

# ---------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------
function Find-Python312 {
    <# Mengembalikan path python.exe 3.12+ (bukan dari .venv), atau $null. #>
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $exe = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $exe) { $candidates += $exe.Trim() }
        } catch { }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }

    foreach ($exe in $candidates) {
        try {
            $ver = (& $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $ver -and ([version]$ver.Trim() -ge [version]'3.12')) {
                return $exe
            }
        } catch { }
    }
    return $null
}

function Get-VenvPython {
    return Join-Path $script:ProjectRoot '.venv\Scripts\python.exe'
}

function Get-FileSha256([string[]]$Paths) {
    $text = ($Paths | ForEach-Object { (Get-FileHash $_ -Algorithm SHA256).Hash }) -join ''
    $bytes = [Text.Encoding]::ASCII.GetBytes($text)
    $sha = [Security.Cryptography.SHA256]::Create()
    return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '')
}

function Initialize-Venv([string]$RequirementsFile, [switch]$AllowPyMySql) {
    <# Buat .venv bila belum ada; pasang ulang paket bila requirements berubah.
       -AllowPyMySql: bila mysqlclient gagal, pasang tanpa itu dan set DB_DRIVER=pymysql. #>
    $venvPy = Get-VenvPython
    if (-not (Test-Path $venvPy)) {
        $py = Find-Python312
        if (-not $py) {
            Write-Fail 'Python 3.12 tidak ditemukan.' 'Pasang Python 3.12 (64-bit) dari python.org, centang "Add python.exe to PATH".'
            exit 1
        }
        Write-Info "Membuat .venv dengan $py"
        & $py -m venv (Join-Path $script:ProjectRoot '.venv')
        if ($LASTEXITCODE -ne 0) { Write-Fail 'Gagal membuat .venv.'; exit 1 }
        Write-Ok 'Virtualenv .venv dibuat'
    } else {
        Write-Skip 'Virtualenv .venv sudah ada'
    }

    $reqPath = Join-Path $script:ProjectRoot $RequirementsFile
    $reqFiles = @($reqPath, (Join-Path $script:ProjectRoot 'requirements.txt')) | Select-Object -Unique
    $stamp = Join-Path $script:ProjectRoot '.venv\dreamtify-requirements.sha256'
    $hash = Get-FileSha256 $reqFiles
    if ((Test-Path $stamp) -and ((Get-Content $stamp -Raw).Trim() -eq $hash)) {
        Write-Skip 'Paket Python sudah sesuai requirements'
        return
    }
    Write-Info "Memasang paket dari $RequirementsFile (butuh internet)..."
    & $venvPy -m pip install --disable-pip-version-check -q --upgrade pip
    & $venvPy -m pip install --disable-pip-version-check -q -r $reqPath
    if ($LASTEXITCODE -ne 0 -and $AllowPyMySql) {
        Write-Warn 'Paket gagal dipasang, mencoba tanpa mysqlclient (memakai PyMySQL)...'
        $filtered = Join-Path $env:TEMP 'dreamtify-requirements.txt'
        Get-Content $reqPath | Where-Object { $_ -notmatch '^mysqlclient' } | Set-Content $filtered -Encoding ascii
        & $venvPy -m pip install --disable-pip-version-check -q -r $filtered
        Remove-Item $filtered -Force -ErrorAction SilentlyContinue
        if ($LASTEXITCODE -eq 0) { Set-DotEnvValue 'DB_DRIVER' 'pymysql' }
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'pip install gagal.' 'Cek koneksi internet, lalu jalankan ulang. Bila mysqlclient gagal, set DB_DRIVER=pymysql di .env.'
        exit 1
    }
    Set-Content -Path $stamp -Value $hash -Encoding ascii
    Write-Ok 'Paket Python terpasang'
}

# ---------------------------------------------------------------------
# File .env
# ---------------------------------------------------------------------
function Get-EnvPath { return Join-Path $script:ProjectRoot '.env' }

function Read-DotEnv([string]$Path = (Get-EnvPath)) {
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith('#')) { continue }
        $i = $t.IndexOf('=')
        if ($i -lt 1) { continue }
        $key = $t.Substring(0, $i).Trim()
        $val = $t.Substring($i + 1).Trim()
        if ($val.Length -ge 2 -and (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'")))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        $values[$key] = $val
    }
    return $values
}

function Set-DotEnvValue([string]$Key, [string]$Value, [string]$Path = (Get-EnvPath)) {
    <# Ubah KEY=... bila ada, tambahkan bila belum. Tulis UTF-8 tanpa BOM. #>
    $lines = @()
    if (Test-Path $Path) { $lines = [IO.File]::ReadAllLines($Path) }
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=") { $found = $true; "$Key=$Value" } else { $line }
    }
    if (-not $found) { $out = @($out) + "$Key=$Value" }
    [IO.File]::WriteAllLines($Path, [string[]]$out, (New-Object Text.UTF8Encoding($false)))
}

function New-RandomString([int]$Length = 32) {
    $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'.ToCharArray()
    $bytes = New-Object byte[] ($Length * 2)
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $sb = New-Object Text.StringBuilder
    foreach ($b in $bytes) {
        if ($b -ge (256 - (256 % $chars.Length))) { continue }  # hindari bias modulo
        [void]$sb.Append($chars[$b % $chars.Length])
        if ($sb.Length -ge $Length) { break }
    }
    if ($sb.Length -lt $Length) { return New-RandomString $Length }
    return $sb.ToString()
}

function New-FernetKey {
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_')
}

function New-DotEnvFile {
    <# Salin .env.example -> .env dan isi semua rahasia dengan nilai acak. #>
    $example = Join-Path $script:ProjectRoot '.env.example'
    $target = Get-EnvPath
    Copy-Item $example $target
    # Normalisasi ke UTF-8 tanpa BOM
    [IO.File]::WriteAllLines($target, [IO.File]::ReadAllLines($example), (New-Object Text.UTF8Encoding($false)))
    Set-DotEnvValue 'SECRET_KEY' (New-RandomString 50)
    Set-DotEnvValue 'DB_PASSWORD' (New-RandomString 24)
    Set-DotEnvValue 'FIELD_ENCRYPTION_KEYS' (New-FernetKey)
    Set-DotEnvValue 'NIK_HASH_PEPPER' (New-RandomString 40)
}

# ---------------------------------------------------------------------
# Jaringan & MariaDB
# ---------------------------------------------------------------------
function Test-TcpPort([string]$HostName, [int]$Port, [int]$TimeoutMs = 2000) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $ar = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $ar.AsyncWaitHandle.WaitOne($TimeoutMs)) { return $false }
        $client.EndConnect($ar)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Find-MariaDbBin([string]$Configured = '') {
    <# Folder bin MariaDB: dari .env, registry, lalu Program Files (versi terbaru). #>
    if ($Configured -and (Test-Path (Join-Path $Configured 'mariadb.exe'))) { return $Configured }
    $dirs = @()
    foreach ($root in 'HKLM:\SOFTWARE\MariaDB*', 'HKLM:\SOFTWARE\WOW6432Node\MariaDB*') {
        Get-Item $root -ErrorAction SilentlyContinue | ForEach-Object {
            $loc = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).INSTALLDIR
            if ($loc) { $dirs += (Join-Path $loc 'bin') }
        }
    }
    $dirs += Get-ChildItem "$env:ProgramFiles\MariaDB*" -Directory -ErrorAction SilentlyContinue |
        Sort-Object { [version](($_.Name -replace '[^0-9.]', '') + '.0') } -Descending |
        ForEach-Object { Join-Path $_.FullName 'bin' }
    foreach ($d in $dirs) {
        if (Test-Path (Join-Path $d 'mariadb.exe')) { return $d }
    }
    return $null
}

function Invoke-MariaDbSql {
    <# Jalankan SQL sebagai root. Password lewat file opsi sementara (bukan argumen). #>
    param([string]$Bin, [string]$HostName, [int]$Port, [string]$RootPassword, [string]$Sql)
    $opt = [IO.Path]::GetTempFileName()
    $sqlFile = [IO.Path]::GetTempFileName()
    $outFile = [IO.Path]::GetTempFileName()
    $errFile = [IO.Path]::GetTempFileName()
    try {
        $pw = $RootPassword.Replace('\', '\\').Replace('"', '\"')
        $optText = "[client]`r`nuser=root`r`npassword=`"$pw`"`r`nhost=$HostName`r`nport=$Port`r`n"
        $utf8 = New-Object Text.UTF8Encoding($false)
        [IO.File]::WriteAllText($opt, $optText, $utf8)
        [IO.File]::WriteAllText($sqlFile, $Sql, $utf8)
        $p = Start-Process -FilePath (Join-Path $Bin 'mariadb.exe') `
            -ArgumentList "--defaults-extra-file=`"$opt`"", '--batch' `
            -RedirectStandardInput $sqlFile -RedirectStandardOutput $outFile -RedirectStandardError $errFile `
            -NoNewWindow -Wait -PassThru
        $output = ([IO.File]::ReadAllText($outFile) + [IO.File]::ReadAllText($errFile)).Trim()
        return @{ Ok = ($p.ExitCode -eq 0); Output = $output }
    } finally {
        Remove-Item $opt, $sqlFile, $outFile, $errFile -Force -ErrorAction SilentlyContinue
    }
}

function Test-LocalDbHost([string]$HostName) {
    return @('127.0.0.1', 'localhost', '::1', $env:COMPUTERNAME) -contains $HostName
}

function Test-WebHealth([int]$Port) {
    try {
        return (Invoke-WebRequest "http://127.0.0.1:$Port/sehat/" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200
    } catch {
        return $false
    }
}

function Invoke-DatabaseSetup {
    <#
      Dipakai dev/prod/install: siapkan database sesuai .env (host boleh di server lain).
      Akses root hanya dipakai bila MariaDB ada di komputer ini dan user aplikasi belum bisa masuk.
      Mengembalikan $true bila siap.
    #>
    param([switch]$AllowPrompt)
    $cfg = Read-DotEnv
    $dbHost = if ($cfg.DB_HOST) { $cfg.DB_HOST } else { '127.0.0.1' }
    $dbPort = if ($cfg.DB_PORT) { [int]$cfg.DB_PORT } else { 3309 }
    $local = Test-LocalDbHost $dbHost

    if (-not (Test-TcpPort $dbHost $dbPort)) {
        if ($local) {
            Write-Fail "MariaDB tidak bisa dihubungi di ${dbHost}:${dbPort}." "Pastikan layanan MariaDB berjalan dan memakai port $dbPort (atau ubah DB_PORT di .env)."
        } else {
            Write-Fail "Server MariaDB ${dbHost}:${dbPort} tidak bisa dihubungi." 'Cek DB_HOST & DB_PORT di .env, firewall, dan bind-address di server MariaDB.'
        }
        return $false
    }
    Write-Ok "MariaDB terhubung di ${dbHost}:${dbPort}"

    $venvPy = Get-VenvPython
    $check = (& $venvPy manage.py cek_db | Select-Object -Last 1)
    if ($check -like 'GAGAL:*') {
        $code = ($check -split ':')[1]
        if ($code -eq '1049') {
            # Database belum ada: siapkan_db mencoba membuatnya dengan user aplikasi
            Invoke-Manage siapkan_db
            if ($LASTEXITCODE -eq 0) { return $true }
        }
        if ($local -and ($code -in '1044', '1045', '1049')) {
            $rootPw = $script:RootPw
            if (-not $rootPw) { $rootPw = $env:MARIADB_ROOT_PASSWORD }
            if (-not $rootPw -and $AllowPrompt) {
                $rootPw = ConvertFrom-SecureToPlain (Read-Host 'Database/user belum siap. Password root MariaDB (tidak disimpan)' -AsSecureString)
            }
            if (-not $rootPw) {
                Write-Fail "Database atau user belum siap ($check)." 'Jalankan install.bat, atau cek DB_USER / DB_PASSWORD di .env.'
                return $false
            }
            $bin = Find-MariaDbBin $cfg.MARIADB_BIN
            if (-not $bin) {
                Write-Fail 'Folder bin MariaDB tidak ditemukan.' 'Isi MARIADB_BIN di .env, mis. C:\Program Files\MariaDB 11.4\bin'
                return $false
            }
            $names = @($cfg.DB_NAME, $cfg.DB_NAME_DEV) | Where-Object { $_ }
            $res = Initialize-AppDatabase -Bin $bin -HostName $dbHost -Port $dbPort -RootPassword $rootPw `
                -Databases $names -User $cfg.DB_USER -Password $cfg.DB_PASSWORD
            if (-not $res.Ok) {
                Write-Fail "Gagal membuat database: $($res.Output)" 'Cek password root MariaDB.'
                return $false
            }
            Write-Ok "Database dan user '$($cfg.DB_USER)' siap"
        } elseif ($code -ne '1049') {
            # siapkan_db mencetak penjelasan sesuai kode error
            Invoke-Manage siapkan_db
            return $false
        } else {
            return $false
        }
    }
    Invoke-Manage siapkan_db
    return ($LASTEXITCODE -eq 0)
}

function Register-DreamtifyTasks {
    <# Tiga Scheduled Task (akun SYSTEM). Idempoten: task lama diperbarui. #>
    $root = $script:ProjectRoot
    $system = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $webSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
    $jobSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
    $tugas = Join-Path $root 'scripts\tugas.bat'

    Register-ScheduledTask -TaskName 'Dreamtify Web' -Force -Principal $system -Settings $webSettings `
        -Trigger (New-ScheduledTaskTrigger -AtStartup) `
        -Action (New-ScheduledTaskAction -Execute (Join-Path $root 'prod.bat') -Argument '--service' -WorkingDirectory $root) | Out-Null

    $every15 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15)
    Register-ScheduledTask -TaskName 'Dreamtify Berkala' -Force -Principal $system -Settings $jobSettings -Trigger $every15 `
        -Action (New-ScheduledTaskAction -Execute $tugas -Argument 'run_periodic' -WorkingDirectory $root) | Out-Null

    Register-ScheduledTask -TaskName 'Dreamtify Harian' -Force -Principal $system -Settings $jobSettings `
        -Trigger (New-ScheduledTaskTrigger -Daily -At '02:30') `
        -Action (New-ScheduledTaskAction -Execute $tugas -Argument 'run_daily' -WorkingDirectory $root) | Out-Null
    Write-Ok 'Scheduled Task terdaftar: Dreamtify Web, Berkala, Harian'
}

function Initialize-AppDatabase {
    <# Buat database (utf8mb4_unicode_ci) + user aplikasi dan hak akses. Idempoten. #>
    param([string]$Bin, [string]$HostName, [int]$Port, [string]$RootPassword,
          [string[]]$Databases, [string]$User, [string]$Password)
    $sql = New-Object Text.StringBuilder
    foreach ($db in $Databases) {
        [void]$sql.AppendLine("CREATE DATABASE IF NOT EXISTS ``$db`` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    }
    foreach ($h in 'localhost', '127.0.0.1') {
        [void]$sql.AppendLine("CREATE USER IF NOT EXISTS '$User'@'$h' IDENTIFIED BY '$Password';")
        [void]$sql.AppendLine("ALTER USER '$User'@'$h' IDENTIFIED BY '$Password';")
        foreach ($db in $Databases) {
            [void]$sql.AppendLine("GRANT ALL PRIVILEGES ON ``$db``.* TO '$User'@'$h';")
        }
        # Database tes Django (test_dreamtify_dev, dst.)
        [void]$sql.AppendLine("GRANT ALL PRIVILEGES ON ``test_dreamtify%``.* TO '$User'@'$h';")
    }
    [void]$sql.AppendLine('FLUSH PRIVILEGES;')
    return Invoke-MariaDbSql -Bin $Bin -HostName $HostName -Port $Port -RootPassword $RootPassword -Sql $sql.ToString()
}

function ConvertFrom-SecureToPlain([Security.SecureString]$Secure) {
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

function Invoke-Manage {
    <# Jalankan manage.py dengan Python .venv; output langsung ke layar. Cek $LASTEXITCODE setelahnya. #>
    $venvPy = Get-VenvPython
    & $venvPy (Join-Path $script:ProjectRoot 'manage.py') @args | Out-Host
}
