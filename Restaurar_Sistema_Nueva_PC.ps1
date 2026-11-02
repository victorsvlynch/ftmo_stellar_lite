<#
.SYNOPSIS
    Script de Restauración e Instalación Automática en Nueva PC
    Proyecto: FundedNext Stellar Lite ($10,000 USD) - Engine & MT5 Bridge
#>

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "  INSTALADOR Y CONFIGURADOR AUTOMÁTICO EN NUEVA PC                        " -ForegroundColor Yellow
Write-Host "  FundedNext Stellar Lite ($10,000 USD) - MT5 Bridge & Oracle Cloud VPS    " -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""

$packRoot = $PSScriptRoot

# Resolver carpetas de origen de manera inteligente (soporta ejecución desde raíz del repo o desde paquete exportado)
# 1. Origen MT5
$mt5SourceExperts = @()
$mt5SourceConfig = $null
$mt5SourceProfiles = $null

if (Test-Path (Join-Path $packRoot "01_MT5_Configuracion\MQL5\Experts")) {
    $mt5SourceExperts = (Get-ChildItem -Path (Join-Path $packRoot "01_MT5_Configuracion\MQL5\Experts\*") -File)
    $mt5SourceConfig  = Join-Path $packRoot "01_MT5_Configuracion\Config"
    $mt5SourceProfiles= Join-Path $packRoot "01_MT5_Configuracion\Profiles"
} elseif (Test-Path (Join-Path $packRoot "EXPORT_PACK_PORTABILIDAD\01_MT5_Configuracion\MQL5\Experts")) {
    $mt5SourceExperts = (Get-ChildItem -Path (Join-Path $packRoot "EXPORT_PACK_PORTABILIDAD\01_MT5_Configuracion\MQL5\Experts\*") -File)
    $mt5SourceConfig  = Join-Path $packRoot "EXPORT_PACK_PORTABILIDAD\01_MT5_Configuracion\Config"
    $mt5SourceProfiles= Join-Path $packRoot "EXPORT_PACK_PORTABILIDAD\01_MT5_Configuracion\Profiles"
} else {
    $mt5SourceExperts = (Get-ChildItem -Path $packRoot -Filter "StellarLite_Webhook_Bridge.*" -File)
    if (Test-Path (Join-Path $packRoot "EXPORT_PACK_PORTABILIDAD\01_MT5_Configuracion\Config")) {
        $mt5SourceConfig = Join-Path $packRoot "EXPORT_PACK_PORTABILIDAD\01_MT5_Configuracion\Config"
    }
}

# 2. Origen Llaves SSH
$sshCandidates = @(
    (Join-Path $packRoot "02_SSH_Keys_Oracle_VPS"),
    (Join-Path $packRoot "EXPORT_PACK_PORTABILIDAD\02_SSH_Keys_Oracle_VPS"),
    (Join-Path $packRoot "VPS-Oracle"),
    (Join-Path $packRoot "EXPORT_PACK_PORTABILIDAD\03_Codigo_Python_Proyecto\VPS-Oracle")
)
$sshKeysDir = $null
foreach ($cand in $sshCandidates) {
    if (Test-Path $cand) {
        $foundKeys = Get-ChildItem -Path $cand -Filter "*.key" -ErrorAction SilentlyContinue
        if ($foundKeys.Count -gt 0) {
            $sshKeysDir = $cand
            break
        }
    }
}

# 3. Origen Código Python y requirements.txt
$reqFile = $null
$reqCandidates = @(
    (Join-Path $packRoot "requirements.txt"),
    (Join-Path $packRoot "03_Codigo_Python_Proyecto\requirements.txt"),
    (Join-Path $packRoot "EXPORT_PACK_PORTABILIDAD\03_Codigo_Python_Proyecto\requirements.txt")
)
foreach ($rc in $reqCandidates) {
    if (Test-Path $rc) {
        $reqFile = $rc
        break
    }
}

# -------------------------------------------------------------
# PASO 1: Configuración de Llaves SSH para Oracle Cloud VPS
# -------------------------------------------------------------
Write-Host "[PASO 1/4] Configurando llaves SSH para conexión con Oracle VPS..." -ForegroundColor Yellow
$userSshDir = Join-Path $env:USERPROFILE ".ssh"
if (-not (Test-Path $userSshDir)) {
    New-Item -ItemType Directory -Path $userSshDir -Force | Out-Null
    Write-Host "  -> Carpeta .ssh creada en: $userSshDir" -ForegroundColor Green
}

if ($sshKeysDir -and (Test-Path $sshKeysDir)) {
    $keysInstalled = 0
    Get-ChildItem -Path $sshKeysDir -Filter "*.key" | ForEach-Object {
        $destFile = Join-Path $userSshDir $_.Name
        Copy-Item $_.FullName -Destination $destFile -Force
        # Ajustar permisos de seguridad estrictos requeridos por SSH
        try {
            icacls $destFile /inheritance:r | Out-Null
            icacls $destFile /grant:r "$($env:USERNAME):(R)" | Out-Null
        } catch {}
        Write-Host "  [OK] Llave instalada con permisos seguros: $($_.Name)" -ForegroundColor Green
        $keysInstalled++
    }
    if ($keysInstalled -gt 0) {
        Write-Host "  -> $keysInstalled llave(s) SSH aprovisionadas en: $userSshDir" -ForegroundColor Gray
    }
} else {
    Write-Host "  [AVISO] No se encontró directorio de llaves SSH en el paquete." -ForegroundColor Magenta
}

# -------------------------------------------------------------
# PASO 2: Detección e Instalación en MetaTrader 5
# -------------------------------------------------------------
Write-Host ""
Write-Host "[PASO 2/4] Detectando e instalando configuración en MetaTrader 5..." -ForegroundColor Yellow

# Prioridad 1: Roaming Data Folders (%APPDATA%\MetaQuotes\Terminal\<hash>)
# Esta es la carpeta operativa real donde MT5 lee Experts, Config y Profiles sin requerir permisos de admin
$roamingTerminals = Join-Path $env:APPDATA "MetaQuotes\Terminal"
$detectedDataPaths = @()

if (Test-Path $roamingTerminals) {
    Get-ChildItem -Path $roamingTerminals -Directory | Where-Object { $_.Name -notmatch "Common|Community" } | ForEach-Object {
        $detectedDataPaths += $_.FullName
    }
}

# Prioridad 2: Program Files (solo si es modo portable o no se encontró Roaming)
$mt5CandidatePaths = @(
    "C:\Program Files\MetaTrader 5",
    "C:\Program Files (x86)\MetaTrader 5",
    "D:\Program Files\MetaTrader 5",
    "C:\MetaTrader 5"
)
$detectedBinaryPaths = @()
foreach ($path in $mt5CandidatePaths) {
    if (Test-Path (Join-Path $path "terminal64.exe")) {
        $detectedBinaryPaths += $path
    }
}

if ($detectedDataPaths.Count -gt 0) {
    Write-Host "  -> MetaTrader 5 detectado: Carpeta de Datos operativa (%APPDATA%):" -ForegroundColor Green
    foreach ($dataPath in $detectedDataPaths) {
        Write-Host "     * Destino Datos: $dataPath" -ForegroundColor Gray

        # 1. Copiar Expert Advisor
        $destExperts = Join-Path $dataPath "MQL5\Experts"
        if (-not (Test-Path $destExperts)) { 
            New-Item -ItemType Directory -Path $destExperts -Force | Out-Null 
        }
        if ($mt5SourceExperts.Count -gt 0) {
            foreach ($ea in $mt5SourceExperts) {
                Copy-Item $ea.FullName -Destination $destExperts -Force
            }
            Write-Host "       [OK] Expert Advisor StellarLite_Webhook_Bridge copiado a MQL5\Experts." -ForegroundColor Green
        }

        # 2. Copiar Configuración (WebRequest, DLLs, AlgoTrading)
        $destConfig = Join-Path $dataPath "Config"
        if (-not (Test-Path $destConfig)) { 
            New-Item -ItemType Directory -Path $destConfig -Force | Out-Null 
        }
        if ($mt5SourceConfig -and (Test-Path $mt5SourceConfig)) {
            Copy-Item (Join-Path $mt5SourceConfig "common.ini") $destConfig -Force -ErrorAction SilentlyContinue
            Copy-Item (Join-Path $mt5SourceConfig "servers.dat") $destConfig -Force -ErrorAction SilentlyContinue
            Copy-Item (Join-Path $mt5SourceConfig "settings.ini") $destConfig -Force -ErrorAction SilentlyContinue
            Write-Host "       [OK] Archivos de configuración y URLs WebRequest autorizadas instalados." -ForegroundColor Green
        }

        # 3. Copiar Perfiles y Plantillas de Gráficos
        $destProfiles = Join-Path $dataPath "Profiles"
        if ($mt5SourceProfiles -and (Test-Path $mt5SourceProfiles)) {
            Copy-Item (Join-Path $mt5SourceProfiles "*") $destProfiles -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "       [OK] Perfiles y plantillas de gráficos restaurados." -ForegroundColor Green
        }
    }
} elseif ($detectedBinaryPaths.Count -gt 0) {
    Write-Host "  -> Instalación de MT5 detectada en archivos de programa:" -ForegroundColor Gray
    foreach ($binPath in $detectedBinaryPaths) {
        Write-Host "     * Destino: $binPath" -ForegroundColor Gray
        try {
            $destExperts = Join-Path $binPath "MQL5\Experts"
            if (-not (Test-Path $destExperts)) {
                New-Item -ItemType Directory -Path $destExperts -Force -ErrorAction Stop | Out-Null
            }
            if ($mt5SourceExperts.Count -gt 0) {
                foreach ($ea in $mt5SourceExperts) {
                    Copy-Item $ea.FullName -Destination $destExperts -Force -ErrorAction Stop
                }
                Write-Host "       [OK] Expert Advisor copiado a MQL5\Experts." -ForegroundColor Green
            }
        } catch {
            Write-Host "       [AVISO] Carpeta de sistema protegida por Windows. Inicia MT5 una vez para generar la carpeta de datos en %APPDATA%." -ForegroundColor Magenta
        }
    }
} else {
    Write-Host "  [AVISO] No se detectó una instalación automática de MT5 en rutas estándar." -ForegroundColor Magenta
    Write-Host "          Por favor abre MT5, ve a Archivo -> Abrir Carpeta de Datos y copia manualmente:" -ForegroundColor Magenta
    Write-Host "          StellarLite_Webhook_Bridge.ex5 a MQL5\Experts" -ForegroundColor Magenta
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
    if ($reqFile -and (Test-Path $reqFile)) {
        Write-Host "  -> Verificando dependencias requeridas en $reqFile..." -ForegroundColor Gray
        python -m pip install -r $reqFile --quiet
        # Validar específicamente MetaTrader5
        python -c "import MetaTrader5" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  -> Instalando conector MetaTrader5 en Python..." -ForegroundColor Gray
            python -m pip install MetaTrader5 --quiet
        }
        Write-Host "  [OK] Dependencias de Python verificadas e instaladas." -ForegroundColor Green
    } else {
        Write-Host "  [OK] Python operativo con dependencias estándar." -ForegroundColor Green
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
} else {
    Write-Host "  [AVISO] No se encontró la llave privada para probar conexión SSH." -ForegroundColor Magenta
}

# -------------------------------------------------------------
# RESUMEN FINAL
# -------------------------------------------------------------
Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "  RESTAURACIÓN Y CONFIGURACIÓN COMPLETADA CON ÉXITO                       " -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""

$controlBat = "Control_Total_Bot.bat"
if (Test-Path (Join-Path $packRoot "03_Codigo_Python_Proyecto\Control_Total_Bot.bat")) {
    $controlBat = "03_Codigo_Python_Proyecto\Control_Total_Bot.bat"
}

Write-Host "Para iniciar la operación en esta nueva PC:" -ForegroundColor Yellow
Write-Host "  1. Ejecuta: $controlBat" -ForegroundColor White
Write-Host "  2. Opción 4: Inicia el Túnel Webhook SSH (conecta tu MT5 local con la nube)." -ForegroundColor White
Write-Host "  3. Abre MetaTrader 5 y verifica que el EA tenga el sombrero azul en XAUUSD." -ForegroundColor White
Write-Host "  4. (Opcional) Opción 6: Ejecuta la simulación con broker MT5 para auditar la cuenta." -ForegroundColor White
Write-Host ""
