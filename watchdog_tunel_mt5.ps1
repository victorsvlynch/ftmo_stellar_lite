# watchdog_tunel_mt5.ps1 - Guardian Activo 24/7 del Puente Webhook MT5 (Puerto 8000)
# Verifica cada 15 segundos que http://127.0.0.1:8000/api/health responda realmente (HTTP 200).
# Si detecta cualquier caida (proceso ssh muerto, micro-corte de router o tunel 'zombie' congelado),
# limpia el puerto 8000 y reconstruye el tunel SSH automaticamente en segundos.

$ErrorActionPreference = "SilentlyContinue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogFile = Join-Path $ScriptDir "watchdog_tunel.log"
$VpsHost = "ubuntu@157.137.225.144"

# Resolver clave privada SSH
$KeyCandidates = @(
    "$env:USERPROFILE\.ssh\oracle_vps.key",
    "$env:USERPROFILE\.ssh\ssh-key-2026-10-26.key",
    (Join-Path $ScriptDir "VPS-Oracle\oracle_vps.key"),
    (Join-Path $ScriptDir "VPS-Oracle\ssh-key-2026-10-26.key")
)
$SshKey = $null
foreach ($cand in $KeyCandidates) {
    if (Test-Path $cand) {
        $SshKey = $cand
        break
    }
}

function Write-WatchdogLog([string]$msg) {
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "[$ts] $msg"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Test-WebhookHealth {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 4 -ErrorAction Stop
        if ($resp.StatusCode -eq 200 -and $resp.Content -match "ONLINE") {
            return $true
        }
    } catch {
        return $false
    }
    return $false
}

function Reset-SshTunnel {
    Write-WatchdogLog "ALERTA: http://127.0.0.1:8000/api/health no responde. Limpiando procesos ssh zombies y reconectando..."
    
    # 1. Matar cualquier proceso que tenga tomado el puerto 8000 o procesos ssh colgados hacia el puerto 8000
    Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.OwningProcess -gt 4) {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
    Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'ssh.exe' -and $_.CommandLine -like '*8000*' } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2

    # 2. Asegurar que stellar_webhook este activo en el VPS
    if ($SshKey) {
        Start-Process -FilePath "ssh.exe" -ArgumentList "-i `"$SshKey`" -o StrictHostKeyChecking=no -o ConnectTimeout=5 $VpsHost `"sudo systemctl start stellar_webhook`"" -WindowStyle Hidden -Wait
        
        # 3. Levantar nuevo tunel SSH limpio con KeepAlive estricto
        $sshArgs = "-i `"$SshKey`" -o StrictHostKeyChecking=no -o ServerAliveInterval=15 -o ServerAliveCountMax=2 -o ConnectTimeout=8 -o ExitOnForwardFailure=yes -N -n -L 8000:localhost:8000 $VpsHost"
        Start-Process -FilePath "ssh.exe" -ArgumentList $sshArgs -WindowStyle Hidden
        Start-Sleep -Seconds 3

        if (Test-WebhookHealth) {
            Write-WatchdogLog "EXITO: Tunel SSH reconstruido y verificado ONLINE en http://127.0.0.1:8000/api/health."
        } else {
            Write-WatchdogLog "AVISO: Reintento completado; esperando recuperacion de internet para siguiente ciclo."
        }
    }
}

Write-WatchdogLog "=== INICIANDO WATCHDOG ACTIVO 24/7 DEL PUENTE WEBHOOK MT5 (SONDEO CADA 15s) ==="
$failCount = 0
$fridayCounter = 0
$ScriptGuardian = Join-Path $ScriptDir "friday_guardian.py"

while ($true) {
    if (Test-WebhookHealth) {
        $failCount = 0
    } else {
        $failCount++
        if ($failCount -ge 2) {
            Reset-SshTunnel
            $failCount = 0
        }
    }

    # Guardián de Viernes: Cada 60 segundos (4 ciclos de 15s) verifica si es viernes >= 15:30 EST
    $fridayCounter++
    if ($fridayCounter -ge 4) {
        $fridayCounter = 0
        if (Test-Path $ScriptGuardian) {
            Start-Process -FilePath "python.exe" -ArgumentList "`"$ScriptGuardian`"" -WorkingDirectory $ScriptDir -WindowStyle Hidden
        }
    }

    Start-Sleep -Seconds 15
}
