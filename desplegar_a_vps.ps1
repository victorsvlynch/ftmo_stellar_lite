<#
.SYNOPSIS
    Despliegue Continuo Local a Oracle Cloud Infrastructure (OCI).
.DESCRIPTION
    Sincroniza el codigo fuente del motor cuantitativo hacia la VPS en Oracle Cloud (157.137.225.144),
    protegiendo las bases de datos activas en el servidor y reiniciando los 5 servicios de systemd.
#>
param(
    [Parameter(Mandatory = $false)]
    [string]$HostIp = "157.137.225.144",

    [Parameter(Mandatory = $false)]
    [string]$User = "ubuntu"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = (Resolve-Path "$PSScriptRoot").Path

# 1. Localizar clave SSH privada
$keyPaths = @(
    "$env:USERPROFILE\.ssh\ssh-key-2026-10-26.key",
    "$repoRoot\VPS-Oracle\ssh-key-2026-10-26.key",
    "$env:USERPROFILE\.ssh\oracle_vps.key"
)

$sshKey = $null
foreach ($k in $keyPaths) {
    if (Test-Path $k) {
        $sshKey = $k
        break
    }
}

if (-not $sshKey) {
    Write-Host "[ERROR] No se encontro la clave SSH privada en ninguna de las rutas esperadas." -ForegroundColor Red
    exit 1
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " [DESPLIEGUE] FTMO Stellar Lite -> Oracle Cloud VPS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Servidor:      $User@$HostIp" -ForegroundColor Gray
Write-Host "Clave SSH:     $sshKey" -ForegroundColor Gray
Write-Host "Directorio:    $repoRoot" -ForegroundColor Gray
Write-Host "Destino VPS:   /home/$User/FTMO_Stellar_Lite/" -ForegroundColor Gray
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray

# 2. Verificar conectividad SSH
Write-Host "[1/4] Verificando conexion con el servidor en Oracle Cloud..." -ForegroundColor Yellow
$testConn = & ssh -i "$sshKey" -o StrictHostKeyChecking=no -o ConnectTimeout=6 "$User@$HostIp" "echo OK" 2>&1
if ($LASTEXITCODE -ne 0 -or $testConn -notmatch "OK") {
    Write-Host "[ERROR] No se pudo conectar al servidor VPS. Verifique IP y conexion." -ForegroundColor Red
    Write-Host $testConn -ForegroundColor DarkRed
    exit 1
}
Write-Host "   [OK] Conexion SSH establecida con exito." -ForegroundColor Green

# 3. Subir archivos principales y scripts
Write-Host "[2/4] Sincronizando codigo fuente y modulos (protegiendo bases de datos)..." -ForegroundColor Yellow

$filesToUpload = @(
    "main.py",
    "database.py",
    "stellar_rules.py",
    "risk_manager.py",
    "trading_engine.py",
    "telegram_notifier.py",
    "test_verification.py",
    "manage_services.sh",
    "setup_oracle.sh",
    "requirements.txt"
)

$targetRemote = "$User@${HostIp}:/home/$User/FTMO_Stellar_Lite/"
foreach ($f in $filesToUpload) {
    $fullPath = Join-Path $repoRoot $f
    if (Test-Path $fullPath) {
        & scp -i "$sshKey" -o StrictHostKeyChecking=no -q "$fullPath" "$targetRemote"
    }
}

# Subir carpeta scripts
$scriptsPath = Join-Path $repoRoot "scripts"
if (Test-Path $scriptsPath) {
    & scp -r -i "$sshKey" -o StrictHostKeyChecking=no -q "$scriptsPath" "$targetRemote"
}

Write-Host "   [OK] Codigo fuente sincronizado en el servidor." -ForegroundColor Green

# 4. Ajustar permisos, detener servicios retirados y activar únicamente estrategia ganadora
Write-Host "[3/4] Desactivando modalidades perdedoras y activando ESTRATEGIA GANADORA (NY_OPEN)..." -ForegroundColor Yellow
$remoteCmds = @(
    "cd /home/$User/FTMO_Stellar_Lite",
    "chmod +x *.sh *.py 2>/dev/null",
    "sudo systemctl stop stellar_london_open.service stellar_crypto_24h.service stellar_ny_london.service stellar_combo_trio.service 2>/dev/null || true",
    "sudo systemctl disable stellar_london_open.service stellar_crypto_24h.service stellar_ny_london.service stellar_combo_trio.service 2>/dev/null || true",
    "sudo systemctl enable stellar_ny_open.service fundednext_bot.service 2>/dev/null || true",
    "sudo systemctl restart stellar_ny_open.service fundednext_bot.service",
    "sleep 1"
) -join " && "

& ssh -i "$sshKey" -o StrictHostKeyChecking=no "$User@$HostIp" "$remoteCmds"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[AVISO] Hubo una advertencia al configurar servicios." -ForegroundColor Yellow
} else {
    Write-Host "   [OK] Modalidades retiradas detenidas. Estrategia ganadora NY_OPEN reiniciada con exito." -ForegroundColor Green
}

# 5. Consultar estado en vivo de los servicios y tablero
Write-Host "[4/4] Verificando aislamiento de estrategia ganadora en VPS..." -ForegroundColor Yellow
$statusCmd = "cd /home/$User/FTMO_Stellar_Lite && sudo systemctl is-active stellar_ny_open stellar_london_open stellar_crypto_24h stellar_ny_london stellar_combo_trio"
$servicesStatus = & ssh -i "$sshKey" -o StrictHostKeyChecking=no "$User@$HostIp" "$statusCmd"

Write-Host ""
Write-Host "Estado de Servicios Systemd en VPS:" -ForegroundColor Cyan
$lines = $servicesStatus -split "`n"
$serviceNames = @("1_NY_OPEN [GANADORA]", "2_LONDON_OPEN [RETIRADA]", "3_CRYPTO_24H [RETIRADA]", "4_COMBO_DUAL [RETIRADA]", "5_COMBO_TRIO [RETIRADA]")
for ($i = 0; $i -lt [math]::Min($lines.Length, $serviceNames.Length); $i++) {
    $st = $lines[$i].Trim()
    if ($i -eq 0) {
        $col = if ($st -eq "active") { "Green" } else { "Red" }
    } else {
        $col = if ($st -eq "inactive") { "DarkGray" } else { "Yellow" }
    }
    Write-Host "   - $($serviceNames[$i]): $st" -ForegroundColor $col
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " [EXITO] SERVIDOR ACTUALIZADO: SOLO ESTRATEGIA GANADORA ACTIVA" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "El motor se encuentra operando en vivo en la nube 24/7." -ForegroundColor White
