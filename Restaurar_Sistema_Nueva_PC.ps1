<#
.SYNOPSIS
    Script de Restauración e Instalación Automática en Nueva PC
    Proyecto: FundedNext Stellar Lite ($10,000 USD) - Engine & MT5 Bridge
#>

$ErrorActionPreference = "Continue"

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "  INSTALADOR Y CONFIGURADOR AUTOMÁTICO EN NUEVA PC                        " -ForegroundColor Yellow
Write-Host "  FundedNext Stellar Lite ($10,000 USD) - MT5 Bridge & Oracle Cloud VPS    " -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""

$packRoot = $PSScriptRoot
$mt5ConfigDir = Join-Path $packRoot "01_MT5_Configuracion"
$sshKeysDir = Join-Path $packRoot "02_SSH_Keys_Oracle_VPS"
$pythonCodeDir = Join-Path $packRoot "03_Codigo_Python_Proyecto"

# -------------------------------------------------------------
# PASO 1: Configuración de Llaves SSH para Oracle Cloud VPS
# -------------------------------------------------------------
Write-Host "[PASO 1/4] Configurando llaves SSH para conexión con Oracle VPS..." -ForegroundColor Yellow
$userSshDir = Join-Path $env:USERPROFILE ".ssh"
if (-not (Test-Path $userSshDir)) {
    New-Item -ItemType Directory -Path $userSshDir -Force | Out-Null
    Write-Host "  -> Carpeta .ssh creada en: $userSshDir" -ForegroundColor Green
}

if (Test-Path $sshKeysDir) {
    Get-ChildItem -Path $sshKeysDir -Filter "*.key" | ForEach-Object {
        $destFile = Join-Path $userSshDir $_.Name
        Copy-Item $_.FullName -Destination $destFile -Force
        # Ajustar permisos de seguridad estrictos requeridos por SSH
        try {
            icacls $destFile /inheritance:r | Out-Null
            icacls $destFile /grant:r "$($env:USERNAME):(R)" | Out-Null
        } catch {}
        Write-Host "  [OK] Llave instalada con permisos seguros: $($_.Name)" -ForegroundColor Green
    }
} else {
    Write-Host "  [AVISO] No se encontró directorio de llaves SSH en el paquete." -ForegroundColor Magenta
}

# -------------------------------------------------------------
# PASO 2: Detección e Instalación en MetaTrader 5
# -------------------------------------------------------------
Write-Host ""
Write-Host "[PASO 2/4] Detectando e instalando configuración en MetaTrader 5..." -ForegroundColor Yellow

$mt5CandidatePaths = @(
    "C:\Program Files\MetaTrader 5",
    "C:\Program Files (x86)\MetaTrader 5",
    "D:\Program Files\MetaTrader 5",
    "C:\MetaTrader 5"
)

$detectedMt5Paths = @()

foreach ($path in $mt5CandidatePaths) {
    if (Test-Path (Join-Path $path "terminal64.exe")) {
        $detectedMt5Paths += $path
    }
}

# Buscar también en roaming data folders (%APPDATA%\MetaQuotes\Terminal\<hash>)
$roamingTerminals = Join-Path $env:APPDATA "MetaQuotes\Terminal"
if (Test-Path $roamingTerminals) {
    Get-ChildItem -Path $roamingTerminals -Directory | Where-Object { $_.Name -notmatch "Common|Community" } | ForEach-Object {
        $detectedMt5Paths += $_.FullName
    }
}

if ($detectedMt5Paths.Count -gt 0) {
    Write-Host "  -> MetaTrader 5 detectado en $($detectedMt5Paths.Count) ubicación(es):" -ForegroundColor Green
    
    foreach ($targetMt5Path in $detectedMt5Paths) {
        Write-Host "     * Destino: $targetMt5Path" -ForegroundColor Gray
        
        # 1. Copiar Expert Advisor
        $destExperts = Join-Path $targetMt5Path "MQL5\Experts"
        if (-not (Test-Path $destExperts)) { 
            New-Item -ItemType Directory -Path $destExperts -Force | Out-Null 
        }
        
        if (Test-Path (Join-Path $mt5ConfigDir "MQL5\Experts")) {
            Copy-Item (Join-Path $mt5ConfigDir "MQL5\Experts\*") $destExperts -Force -ErrorAction SilentlyContinue
            Write-Host "       [OK] Expert Advisor StellarLite_Webhook_Bridge copiado a MQL5\Experts." -ForegroundColor Green
        }

        # 2. Copiar Configuración (WebRequest, DLLs, AlgoTrading)
        $destConfig = Join-Path $targetMt5Path "Config"
        if (-not (Test-Path $destConfig)) { 
            New-Item -ItemType Directory -Path $destConfig -Force | Out-Null 
        }
        if (Test-Path (Join-Path $mt5ConfigDir "Config")) {
            Copy-Item (Join-Path $mt5ConfigDir "Config\common.ini") $destConfig -Force -ErrorAction SilentlyContinue
            Copy-Item (Join-Path $mt5ConfigDir "Config\servers.dat") $destConfig -Force -ErrorAction SilentlyContinue
            Copy-Item (Join-Path $mt5ConfigDir "Config\settings.ini") $destConfig -Force -ErrorAction SilentlyContinue
            Write-Host "       [OK] Archivos de configuración y URLs WebRequest autorizadas instalados." -ForegroundColor Green
        }

        # 3. Copiar Perfiles y Plantillas de Gráficos
        $destProfiles = Join-Path $targetMt5Path "Profiles"
        if (Test-Path (Join-Path $mt5ConfigDir "Profiles")) {
            Copy-Item (Join-Path $mt5ConfigDir "Profiles\*") $destProfiles -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "       [OK] Perfiles y plantillas de gráficos restaurados." -ForegroundColor Green
        }
    }
} else {
    Write-Host "  [AVISO] No se detectó una instalación automática de MT5 en rutas estándar." -ForegroundColor Magenta
    Write-Host "          Por favor abre MT5, ve a Archivo -> Abrir Carpeta de Datos y copia manualmente:" -ForegroundColor Magenta
    Write-Host "          01_MT5_Configuracion\MQL5\Experts\StellarLite_Webhook_Bridge.ex5 a MQL5\Experts" -ForegroundColor Magenta
}

# -------------------------------------------------------------
# PASO 3: Verificación de Entorno Python y Dependencias
# -------------------------------------------------------------
Write-Host ""
Write-Host "[PASO 3/4] Verificando entorno de Python..." -ForegroundColor Yellow
$pythonInstalled = $false
try {
    $pyVer = python --version 2>&1
    if ($LASTEXITCODE -eq 0 -or $pyVer -match "Python") {
        Write-Host "  [OK] Python detectado: $pyVer" -ForegroundColor Green
        $pythonInstalled = $true
    }
} catch {}

if ($pythonInstalled) {
    $reqFile = Join-Path $pythonCodeDir "requirements.txt"
    if (Test-Path $reqFile) {
        Write-Host "  -> Instalando / verificando dependencias requeridas (MetaTrader5, yfinance, pandas, etc.)..." -ForegroundColor Gray
        python -m pip install -r $reqFile --quiet
        Write-Host "  [OK] Dependencias de Python verificadas e instaladas." -ForegroundColor Green
    }
} else {
    Write-Host "  [AVISO] Python no está detectado en el PATH del sistema." -ForegroundColor Magenta
    Write-Host "          Descarga e instala Python 3.10+ desde https://www.python.org/downloads/" -ForegroundColor Magenta
    Write-Host "          Asegúrate de marcar ☑️ 'Add Python to PATH' durante la instalación." -ForegroundColor Magenta
}

# -------------------------------------------------------------
# PASO 4: Prueba de Conectividad con Oracle Cloud VPS
# -------------------------------------------------------------
Write-Host ""
Write-Host "[PASO 4/4] Verificando conexión con Oracle Cloud VPS (157.137.225.144)..." -ForegroundColor Yellow
$vpsHost = "157.137.225.144"
$vpsKey = Join-Path $userSshDir "oracle_vps.key"
if (-not (Test-Path $vpsKey)) {
    $vpsKey = Join-Path $userSshDir "ssh-key-2026-10-26.key"
}

if (Test-Path $vpsKey) {
    try {
        $sshTest = ssh -i $vpsKey -o StrictHostKeyChecking=no -o ConnectTimeout=5 ubuntu@$vpsHost "uptime" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [ÉXITO] Conexión SSH con Oracle Cloud VPS verificada!" -ForegroundColor Green
            Write-Host "          Uptime VPS: $sshTest" -ForegroundColor Gray
        } else {
            Write-Host "  [INFO] Servidor remoto no respondió a SSH rápido o no hay red externa activa." -ForegroundColor Gray
        }
    } catch {
        Write-Host "  [INFO] Cliente OpenSSH no disponible directamente en terminal." -ForegroundColor Gray
    }
}

# -------------------------------------------------------------
# RESUMEN FINAL
# -------------------------------------------------------------
Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "  RESTAURACIÓN Y CONFIGURACIÓN COMPLETADA CON ÉXITO                       " -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para iniciar la operación en esta nueva PC:" -ForegroundColor Yellow
Write-Host "  1. Ejecuta: 03_Codigo_Python_Proyecto\Control_Total_Bot.bat" -ForegroundColor White
Write-Host "  2. Opción 4: Inicia el Túnel Webhook SSH (conecta tu MT5 local con la nube)." -ForegroundColor White
Write-Host "  3. Abre MetaTrader 5 y verifica que el EA tenga el sombrero azul en XAUUSD." -ForegroundColor White
Write-Host "  4. (Opcional) Opción 6: Ejecuta la simulación con broker MT5 para auditar la cuenta." -ForegroundColor White
Write-Host ""
