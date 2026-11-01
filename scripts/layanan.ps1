# =====================================================================
# layanan.ps1 - mengelola layanan web Dreamtify di server.
# Pemakaian (PowerShell Administrator):
#   scripts\layanan.ps1 status|start|stop|restart|logs
# Setelah mengubah .env, jalankan: scripts\layanan.ps1 restart
# (database & tabel disiapkan otomatis saat web start).
# =====================================================================
param(
    [Parameter(Position = 0)][ValidateSet('status', 'start', 'stop', 'restart', 'logs')][string]$Action = 'status'
)

. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $script:ProjectRoot
$taskName = 'Dreamtify Web'
$cfg = Read-DotEnv
$webPort = if ($cfg.WEB_PORT) { [int]$cfg.WEB_PORT } else { 8383 }

function Stop-Web {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    # Task hanya menghentikan cmd.exe; proses Python pendengar port dihentikan terpisah
    Get-NetTCPConnection -LocalPort $webPort -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Write-Ok 'Web dihentikan'
}

function Start-Web {
    Start-ScheduledTask -TaskName $taskName
    Write-Ok 'Web dijalankan (butuh beberapa detik untuk menyiapkan database)'
}

switch ($Action) {
    'status' {
        foreach ($name in 'Dreamtify Web', 'Dreamtify Berkala', 'Dreamtify Harian') {
            $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
            if ($task) {
                $info = $task | Get-ScheduledTaskInfo
                Write-Info "$name : $($task.State), terakhir $($info.LastRunTime), kode $($info.LastTaskResult)"
            } else {
                Write-Warn "$name belum terdaftar. Jalankan install.bat"
            }
        }
        if (Test-WebHealth $webPort) { Write-Ok "Web sehat di port $webPort" } else { Write-Warn "Web tidak menjawab di port $webPort" }
    }
    'start' { Start-Web }
    'stop' { Stop-Web }
    'restart' {
        Stop-Web
        Start-Sleep -Seconds 2
        Start-Web
    }
    'logs' {
        foreach ($file in 'logs\web.log', 'logs\app.log', 'logs\daily.log') {
            if (Test-Path $file) {
                Write-Info $file
                Get-Content $file -Tail 30 | Out-Host
            }
        }
    }
}
exit 0
