# Script para empaquetar toda la configuración de MT5, SSH Keys y el proyecto Python
$ErrorActionPreference = "Stop"

$baseDir = "L:\Python\FTMO_Stellar_Lite"
$exportDir = Join-Path $baseDir "EXPORT_PACK_PORTABILIDAD"

Write-Host ">>> Iniciando empaquetado de portabilidad..." -ForegroundColor Cyan

# 1. MT5 Files
$mt5Path = "C:\Program Files\MetaTrader 5"
$mt5Dest = Join-Path $exportDir "01_MT5_Configuracion"

Write-Host "1. Copiando archivos de MetaTrader 5..." -ForegroundColor Yellow
Copy-Item (Join-Path $mt5Path "MQL5\Experts\StellarLite_Webhook_Bridge.*") (Join-Path $mt5Dest "MQL5\Experts") -Force
Copy-Item (Join-Path $mt5Path "Config\*") (Join-Path $mt5Dest "Config") -Recurse -Force
Copy-Item (Join-Path $mt5Path "Profiles\*") (Join-Path $mt5Dest "Profiles") -Recurse -Force

# 2. SSH Keys
Write-Host "2. Copiando llaves SSH de Oracle Cloud VPS..." -ForegroundColor Yellow
$sshSource = Join-Path $env:USERPROFILE ".ssh"
$sshDest = Join-Path $exportDir "02_SSH_Keys_Oracle_VPS"
Get-ChildItem -Path $sshSource -Filter "*.key" | ForEach-Object {
    Copy-Item $_.FullName $sshDest -Force
    Write-Host "   -> Copiada llave: $($_.Name)" -ForegroundColor Green
}

# 3. Python Project files (excluyendo la propia carpeta de exportación y temporales)
Write-Host "3. Copiando código Python y bases de datos sincronizadas..." -ForegroundColor Yellow
$pyDest = Join-Path $exportDir "03_Codigo_Python_Proyecto"
Get-ChildItem -Path $baseDir -Exclude "EXPORT_PACK_PORTABILIDAD", "*.zip", "exportar_todo.ps1" | ForEach-Object {
    Copy-Item $_.FullName -Destination $pyDest -Recurse -Force
}

Write-Host ">>> Copia de componentes completada exitosamente!" -ForegroundColor Green
