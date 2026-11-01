# =====================================================================
# restore.ps1 - memulihkan database dari file backup .sql.gz.
# Pemakaian: powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 backups\dreamtify-YYYYMMDD-HHMM.sql.gz
#   -Target <nama_db>  database tujuan (default DB_NAME dari .env)
#   -Yes               lewati konfirmasi (untuk uji otomatis)
# ISI DATABASE TUJUAN AKAN DITIMPA. Hentikan layanan web dulu.
# Kata sandi lewat file opsi sementara, bukan argumen.
# =====================================================================
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$File,
    [string]$Target = '',
    [switch]$Yes
)

. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $script:ProjectRoot

if (-not (Test-Path $File)) {
    Write-Fail "File backup tidak ditemukan: $File"
    exit 1
}
$cfg = Read-DotEnv
$dbHost = if ($cfg.DB_HOST) { $cfg.DB_HOST } else { '127.0.0.1' }
$dbPort = if ($cfg.DB_PORT) { [int]$cfg.DB_PORT } else { 3309 }
$dbUser = if ($cfg.DB_USER) { $cfg.DB_USER } else { 'dreamtify' }
if (-not $Target) { $Target = if ($cfg.DB_NAME) { $cfg.DB_NAME } else { 'dreamtify' } }

$bin = Find-MariaDbBin $cfg.MARIADB_BIN
if (-not $bin) {
    Write-Fail 'Folder bin MariaDB tidak ditemukan.' 'Isi MARIADB_BIN di .env.'
    exit 1
}

Write-Warn "Isi database '$Target' akan DITIMPA dari $(Split-Path $File -Leaf)."
if (-not $Yes) {
    $answer = Read-Host "Ketik nama database ($Target) untuk melanjutkan"
    if ($answer -ne $Target) {
        Write-Info 'Dibatalkan.'
        exit 1
    }
}

$sqlFile = [IO.Path]::GetTempFileName()
$optFile = [IO.Path]::GetTempFileName()
$outFile = [IO.Path]::GetTempFileName()
$errFile = [IO.Path]::GetTempFileName()
try {
    # 1. Ekstrak .gz
    $in = [IO.File]::OpenRead((Resolve-Path $File).Path)
    $gzip = New-Object IO.Compression.GZipStream($in, [IO.Compression.CompressionMode]::Decompress)
    $out = [IO.File]::Create($sqlFile)
    try { $gzip.CopyTo($out) } finally { $out.Dispose(); $gzip.Dispose(); $in.Dispose() }
    Write-Ok 'File backup diekstrak'

    # 2. Impor
    $pw = ([string]$cfg.DB_PASSWORD).Replace('\', '\\').Replace('"', '\"')
    $optText = "[client]`r`nuser=$dbUser`r`npassword=`"$pw`"`r`nhost=$dbHost`r`nport=$dbPort`r`n"
    [IO.File]::WriteAllText($optFile, $optText, (New-Object Text.UTF8Encoding($false)))
    $p = Start-Process -FilePath (Join-Path $bin 'mariadb.exe') `
        -ArgumentList "--defaults-extra-file=`"$optFile`"", '--default-character-set=utf8mb4', $Target `
        -RedirectStandardInput $sqlFile -RedirectStandardOutput $outFile -RedirectStandardError $errFile `
        -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        Write-Fail 'Impor gagal.' ([IO.File]::ReadAllText($errFile).Trim())
        exit 1
    }
    Write-Ok "Database '$Target' dipulihkan"
    Write-Info 'Salin balik backups\media ke media, dan pastikan .env sama (kunci enkripsi).'
} finally {
    Remove-Item $sqlFile, $optFile, $outFile, $errFile -Force -ErrorAction SilentlyContinue
}
