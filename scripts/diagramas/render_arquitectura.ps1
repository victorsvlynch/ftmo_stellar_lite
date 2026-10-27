<#
.SYNOPSIS
    Renderizador y validador del Diagrama de Arquitectura con Archify CLI.
.DESCRIPTION
    Ejecuta la validación y el renderizado interactivo del diagrama de arquitectura
    de FTMO Stellar Lite ($5,000) (arquitectura.json -> arquitectura.html).
    Soporta rutas con sistemas de archivos exFAT y NTFS utilizando staging seguro.
.EXAMPLE
    .\scripts\diagramas\render_arquitectura.ps1
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [switch]$ValidateOnly,

    [Parameter(Mandatory = $false)]
    [switch]$Open
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$jsonPath = Join-Path $scriptDir "arquitectura.json"
$htmlPath = Join-Path $scriptDir "arquitectura.html"

# Resolver Archify CLI (global, en .agents o vía npx)
$archifyCli = $null
$possibleCliPaths = @(
    (Join-Path $env:USERPROFILE ".agents\skills\archify\bin\archify.mjs"),
    (Join-Path $env:USERPROFILE ".gemini\antigravity-cli\skills\archify\bin\archify.mjs"),
    (Join-Path $scriptDir "..\..\node_modules\archify\bin\archify.mjs")
)

foreach ($p in $possibleCliPaths) {
    if (Test-Path $p) {
        $archifyCli = $p
        break
    }
}

# Configurar PATH para Node.js si está en Scoop
$scoopNode = Join-Path $env:USERPROFILE "scoop\apps\nodejs-lts\current"
if (Test-Path $scoopNode) {
    $env:PATH = "$scoopNode;$scoopNode\bin;$env:USERPROFILE\scoop\shims;" + $env:PATH
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " ARCHIFY: Renderizador de Diagramas de Arquitectura" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Entrada JSON: $jsonPath" -ForegroundColor Gray
Write-Host "Salida HTML:  $htmlPath" -ForegroundColor Gray

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js no está instalado o no se encuentra en el PATH. Instala Node.js para continuar."
    exit 1
}

if (-not $archifyCli) {
    Write-Host "`n[INFO] Archify CLI no encontrado localmente, instalando vía npx skills..." -ForegroundColor Yellow
    cmd.exe /c "npx --yes skills add tt-a1i/archify -y -g --agent *" | Out-Null
    $archifyCli = Join-Path $env:USERPROFILE ".agents\skills\archify\bin\archify.mjs"
}

if (-not (Test-Path $archifyCli)) {
    Write-Error "No se pudo localizar el script de Archify CLI ($archifyCli)."
    exit 1
}

Write-Host "`n[VALIDACION] Validando arquitectura.json con Archify CLI..." -ForegroundColor Yellow
& node $archifyCli validate architecture $jsonPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "La validacion de Archify fallo."
    exit $LASTEXITCODE
}
Write-Host "[OK] Validacion estructural completada con exito." -ForegroundColor Green

if ($ValidateOnly) {
    exit 0
}

Write-Host "`n[RENDER] Renderizando arquitectura.html interactivo..." -ForegroundColor Yellow
# Staging temporal en C:\ (NTFS) para maxima compatibilidad con sistemas exFAT
$tempHtml = Join-Path ([System.IO.Path]::GetTempPath()) "archify_render_ftmo_stellar.html"
if (Test-Path $tempHtml) { Remove-Item $tempHtml -Force }

& node $archifyCli render architecture $jsonPath $tempHtml
if ($LASTEXITCODE -ne 0) {
    Write-Error "El renderizado de Archify fallo."
    exit $LASTEXITCODE
}

Copy-Item $tempHtml $htmlPath -Force
Remove-Item $tempHtml -Force -ErrorAction SilentlyContinue

$info = Get-Item $htmlPath
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host " DIAGRAMA ACTUALIZADO CON EXITO (Archify CLI)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Archivo:    $htmlPath" -ForegroundColor White
Write-Host "Tamano:     $([math]::Round($info.Length / 1KB, 1)) KB" -ForegroundColor White

if ($Open) {
    Start-Process $htmlPath
}
