<#
.SYNOPSIS
    Script de Empaquetado y Exportación Total de Portabilidad
    Proyecto: FundedNext Stellar Lite ($10,000 USD) - Engine & MT5 Bridge
.DESCRIPTION
    Empaqueta automáticamente:
    1. Archivos y configuración de MetaTrader 5 (EA compilado .ex5/.mq5, Config, Profiles).
    2. Llaves privadas SSH para Oracle Cloud VPS.
    3. Todo el código fuente de Python, bases de datos SQLite sincronizadas y scripts batch.
    4. Scripts de auto-instalación en 1 clic para la nueva PC (INSTALAR_EN_NUEVA_PC.bat).
    5. Comprime todo en PACK_PORTABILIDAD_FTMO_STELLAR_LITE.zip listo para transferir.
#>

$ErrorActionPreference = "Stop"

$baseDir = "L:\Python\FTMO_Stellar_Lite"
$exportDir = Join-Path $baseDir "EXPORT_PACK_PORTABILIDAD"
$zipOutput = Join-Path $baseDir "PACK_PORTABILIDAD_FTMO_STELLAR_LITE.zip"

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "  GENERADOR DE PAQUETE DE PORTABILIDAD - FUNDEDNEXT $10,000 USD           " -ForegroundColor Yellow
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "-> Directorio Base: $baseDir" -ForegroundColor Gray
Write-Host "-> Directorio Exportación: $exportDir" -ForegroundColor Gray
Write-Host ""

# Limpiar carpeta de exportación previa si existe
if (Test-Path $exportDir) {
    Write-Host "Limpiando carpeta de exportación previa..." -ForegroundColor Gray
    Remove-Item -Path $exportDir -Recurse -Force
}

# Crear estructura de carpetas
$mt5DestExperts = Join-Path $exportDir "01_MT5_Configuracion\MQL5\Experts"
$mt5DestConfig  = Join-Path $exportDir "01_MT5_Configuracion\Config"
$mt5DestProfiles= Join-Path $exportDir "01_MT5_Configuracion\Profiles"
$sshDest        = Join-Path $exportDir "02_SSH_Keys_Oracle_VPS"
$pyDest         = Join-Path $exportDir "03_Codigo_Python_Proyecto"

New-Item -ItemType Directory -Path $mt5DestExperts -Force | Out-Null
New-Item -ItemType Directory -Path $mt5DestConfig -Force | Out-Null
New-Item -ItemType Directory -Path $mt5DestProfiles -Force | Out-Null
New-Item -ItemType Directory -Path $sshDest -Force | Out-Null
New-Item -ItemType Directory -Path $pyDest -Force | Out-Null

# -------------------------------------------------------------
# 1. Copiar Archivos de MetaTrader 5
# -------------------------------------------------------------
Write-Host "[1/5] Empaquetando componentes de MetaTrader 5..." -ForegroundColor Yellow

# Copiar Asesor Experto desde proyecto o MT5 Program Files
$eaFiles = @("StellarLite_Webhook_Bridge.ex5", "StellarLite_Webhook_Bridge.mq5")
foreach ($ea in $eaFiles) {
    $eaSource = Join-Path $baseDir $ea
    if (Test-Path $eaSource) {
        Copy-Item $eaSource -Destination $mt5DestExperts -Force
        Write-Host "   -> EA copiado desde proyecto: $ea" -ForegroundColor Green
    }
}

# Si existen archivos de configuración en Program Files de MT5, copiarlos
$mt5ProgramFiles = "C:\Program Files\MetaTrader 5"
if (Test-Path (Join-Path $mt5ProgramFiles "Config")) {
    Copy-Item (Join-Path $mt5ProgramFiles "Config\*") -Destination $mt5DestConfig -Recurse -Force
    Write-Host "   -> Configuración MT5 copiada desde Program Files." -ForegroundColor Green
}
if (Test-Path (Join-Path $mt5ProgramFiles "Profiles")) {
    Copy-Item (Join-Path $mt5ProgramFiles "Profiles\*") -Destination $mt5DestProfiles -Recurse -Force
    Write-Host "   -> Perfiles y plantillas MT5 copiados desde Program Files." -ForegroundColor Green
}

# -------------------------------------------------------------
# 2. Copiar Llaves SSH de Oracle Cloud VPS
# -------------------------------------------------------------
Write-Host ""
Write-Host "[2/5] Empaquetando llaves privadas SSH de Oracle VPS..." -ForegroundColor Yellow
$userSsh = Join-Path $env:USERPROFILE ".ssh"
$copiedKeys = 0
if (Test-Path $userSsh) {
    Get-ChildItem -Path $userSsh -Filter "*.key" | ForEach-Object {
        Copy-Item $_.FullName -Destination $sshDest -Force
        Write-Host "   -> Llave SSH empaquetada: $($_.Name)" -ForegroundColor Green
        $copiedKeys++
    }
}

# También buscar en VPS-Oracle dentro del proyecto si hace falta
$vpsDir = Join-Path $baseDir "VPS-Oracle"
if (Test-Path $vpsDir) {
    Get-ChildItem -Path $vpsDir -Filter "*.key" | ForEach-Object {
        $destFile = Join-Path $sshDest $_.Name
        if (-not (Test-Path $destFile)) {
            Copy-Item $_.FullName -Destination $sshDest -Force
            Write-Host "   -> Llave SSH empaquetada desde VPS-Oracle: $($_.Name)" -ForegroundColor Green
            $copiedKeys++
        }
    }
}

if ($copiedKeys -eq 0) {
    Write-Host "   [AVISO] No se encontraron archivos .key en .ssh ni VPS-Oracle." -ForegroundColor Magenta
}

# -------------------------------------------------------------
# 3. Copiar Código Python, Bases de Datos $10K y Scripts
# -------------------------------------------------------------
Write-Host ""
Write-Host "[3/5] Empaquetando código Python y bases de datos sincronizadas a $10,000..." -ForegroundColor Yellow

$excludeList = @(
    "EXPORT_PACK_PORTABILIDAD",
    "PACK_PORTABILIDAD_FTMO_STELLAR_LITE.zip",
    "archives",
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "compile.log",
    "ssh_tunnel.log"
)

Get-ChildItem -Path $baseDir -Force | Where-Object {
    $item = $_
    $skip = $false
    foreach ($ex in $excludeList) {
        if ($item.Name -like $ex) { $skip = $true; break }
    }
    return (-not $skip)
} | ForEach-Object {
    Copy-Item $_.FullName -Destination $pyDest -Recurse -Force
}
Write-Host "   -> Código Python, DBs SQLite ($10K) y lanzadores batch copiados." -ForegroundColor Green

# -------------------------------------------------------------
# 4. Copiar Scripts de Instalación Raíz del Paquete
# -------------------------------------------------------------
Write-Host ""
Write-Host "[4/5] Añadiendo instaladores automáticos de 1-Clic a la raíz del paquete..." -ForegroundColor Yellow

$installerFiles = @(
    "INSTALAR_EN_NUEVA_PC.bat",
    "Restaurar_Sistema_Nueva_PC.ps1",
    "LEEME_INSTRUCCIONES_PORTABILIDAD.md"
)

foreach ($instFile in $installerFiles) {
    $src = Join-Path $baseDir $instFile
    if (Test-Path $src) {
        Copy-Item $src -Destination $exportDir -Force
        Write-Host "   -> Instalador añadido: $instFile" -ForegroundColor Green
    }
}

# -------------------------------------------------------------
# 5. Generar Archivo ZIP de Portabilidad Total
# -------------------------------------------------------------
Write-Host ""
Write-Host "[5/5] Comprimiendo paquete ZIP (PACK_PORTABILIDAD_FTMO_STELLAR_LITE.zip)..." -ForegroundColor Yellow

if (Test-Path $zipOutput) {
    Remove-Item $zipOutput -Force
}

Compress-Archive -Path "$exportDir\*" -DestinationPath $zipOutput -CompressionLevel Optimal

$zipInfo = Get-Item $zipOutput
$zipSizeMb = [Math]::Round($zipInfo.Length / 1MB, 2)
$fileCount = (Get-ChildItem -Path $exportDir -Recurse -File).Count

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Green
Write-Host "  ¡PAQUETE PORTABLE GENERADO EXITOSAMENTE!                                " -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Green
Write-Host "  • Archivo ZIP    : $zipOutput" -ForegroundColor White
Write-Host "  • Tamaño         : $zipSizeMb MB" -ForegroundColor White
Write-Host "  • Total Archivos : $fileCount archivos empaquetados" -ForegroundColor White
Write-Host "  • Carpeta Origen : $exportDir" -ForegroundColor White
Write-Host ""
Write-Host "Instrucciones de uso en la nueva PC:" -ForegroundColor Cyan
Write-Host "  1. Lleva el archivo ZIP en una memoria USB o descárgalo de la nube." -ForegroundColor Gray
Write-Host "  2. Descomprímelo en cualquier carpeta de tu nueva PC (ej. C:\FTMO_Stellar_Lite)." -ForegroundColor Gray
Write-Host "  3. Haz doble clic en INSTALAR_EN_NUEVA_PC.bat." -ForegroundColor Gray
Write-Host "==========================================================================" -ForegroundColor Green
