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

function Initialize-Venv([string]$RequirementsFile) {
    <# Buat .venv bila belum ada; pasang ulang paket bila requirements berubah. #>
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

function Install-TimeZoneTables {
    <#
      Isi tabel zona waktu MariaDB (dibutuhkan Django untuk lookup tanggal dengan
      USE_TZ, mis. CONVERT_TZ). Di Windows tidak ada /usr/share/zoneinfo, jadi
      sumbernya paket Python `tzdata`. Hanya zona yang dipakai; idempoten.
    #>
    param([string]$Bin, [string]$HostName, [int]$Port, [string]$RootPassword,
          [string[]]$Zones = @('UTC', 'Asia/Jakarta', 'Asia/Makassar', 'Asia/Jayapura'))
    $venvPy = Get-VenvPython
    $zoneDir = (& $venvPy -c "import tzdata, os; print(os.path.join(os.path.dirname(tzdata.__file__), 'zoneinfo'))").Trim()
    $tool = Join-Path $Bin 'mariadb-tzinfo-to-sql.exe'
    if (-not (Test-Path $tool)) { $tool = Join-Path $Bin 'mysql_tzinfo_to_sql.exe' }
    $sql = New-Object Text.StringBuilder
    [void]$sql.AppendLine('USE mysql;')
    foreach ($zone in ($Zones | Select-Object -Unique)) {
        $file = Join-Path $zoneDir ($zone -replace '/', '\')
        if (-not (Test-Path $file)) { continue }
        [void]$sql.AppendLine("SET @old_tz = (SELECT Time_zone_id FROM time_zone_name WHERE Name = '$zone');")
        [void]$sql.AppendLine('DELETE FROM time_zone_transition WHERE Time_zone_id = @old_tz;')
        [void]$sql.AppendLine('DELETE FROM time_zone_transition_type WHERE Time_zone_id = @old_tz;')
        [void]$sql.AppendLine('DELETE FROM time_zone WHERE Time_zone_id = @old_tz;')
        [void]$sql.AppendLine("DELETE FROM time_zone_name WHERE Name = '$zone';")
        $out = [IO.Path]::GetTempFileName()
        try {
            $p = Start-Process -FilePath $tool -ArgumentList "`"$file`"", $zone -RedirectStandardOutput $out `
                -NoNewWindow -Wait -PassThru
            if ($p.ExitCode -ne 0) { return @{ Ok = $false; Output = "tzinfo gagal untuk $zone" } }
            [void]$sql.AppendLine([IO.File]::ReadAllText($out))
        } finally {
            Remove-Item $out -Force -ErrorAction SilentlyContinue
        }
    }
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
