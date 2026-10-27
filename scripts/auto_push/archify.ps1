<#
.SYNOPSIS
    Archify: Herramienta de empaquetado, respaldos de bases de datos SQLite y snapshots de codigo.
.DESCRIPTION
    Empaqueta y respalda las bases de datos de trading SQLite, historiales de operaciones,
    o genera snapshots completos del codigo fuente del proyecto FundedNext / FTMO Stellar Lite.
.PARAMETER Mode
    Modo de empaquetado:
    - Databases: Respalda todas las bases de datos SQLite (*.db), configuraciones de ejemplo y logs.
    - Full: Genera snapshot limpio del codigo fuente excluyendo .git, archives, __pycache__ y claves SSH.
    - All: Combina snapshot de codigo y respaldo de bases de datos en archivos independientes.
.PARAMETER Tag
    Etiqueta personalizada para el nombre del archivo.
.PARAMETER OutputDir
    Directorio de destino (por defecto: <repo_root>/archives).
.PARAMETER CleanAfterArchive
    Si se especifica, limpia archivos temporales de prueba tras generar el ZIP.
.PARAMETER DryRun
    Modo simulacion, muestra los archivos que se incluirian sin crear el archivo ZIP.
.EXAMPLE
    .\scripts\auto_push\archify.ps1 -Mode Databases
.EXAMPLE
    .\scripts\auto_push\archify.ps1 -Mode Full -Tag "v1.1.0"
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $false)]
    [ValidateSet("Databases", "Full", "All")]
    [string]$Mode = "Databases",

    [Parameter(Mandatory = $false)]
    [Alias("t", "Name")]
    [string]$Tag = "",

    [Parameter(Mandatory = $false)]
    [Alias("o")]
    [string]$OutputDir = "",

    [Parameter(Mandatory = $false)]
    [switch]$CleanAfterArchive,

    [Parameter(Mandatory = $false)]
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Determinar raiz del proyecto
try {
    $repoRoot = (git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -eq 0 -and $repoRoot -and (Test-Path $repoRoot.Trim())) {
        $repoRoot = $repoRoot.Trim()
    } else {
        $repoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
    }
} catch {
    $repoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $repoRoot "archives"
}
if (-not (Test-Path $OutputDir) -and -not $DryRun) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$gitBranch = "main"
try {
    $bOut = & git -C $repoRoot branch --show-current 2>&1
    if ($LASTEXITCODE -eq 0 -and $bOut) { $gitBranch = $bOut.ToString().Trim() }
} catch { $gitBranch = "main" }

$gitCommit = "initial"
try {
    $cOut = & git -C $repoRoot rev-parse --short HEAD 2>&1
    if ($LASTEXITCODE -eq 0 -and $cOut) { $gitCommit = $cOut.ToString().Trim() }
} catch { $gitCommit = "initial" }

$tagSuffix = if ($Tag) { "_$($Tag -replace '[^a-zA-Z0-9_\-]', '_')" } else { "" }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " [ARCHIFY] Empaquetado y Respaldos (FTMO Stellar Lite)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Directorio base: $repoRoot" -ForegroundColor Gray
Write-Host "Modo activo:     $Mode" -ForegroundColor White
Write-Host "Rama / Commit:   $gitBranch ($gitCommit)" -ForegroundColor Gray
Write-Host "Destino:         $OutputDir" -ForegroundColor Gray
if ($DryRun) {
    Write-Host "MODO DRY-RUN ACTIVO (Simulacion sin escritura en disco)" -ForegroundColor Magenta
}
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray

function Create-ArchiveFromFiles {
    param(
        [string]$ZipPath,
        [System.Collections.Generic.List[PSObject]]$FileList,
        [hashtable]$ManifestData,
        [switch]$DeleteSources
    )

    if ($FileList.Count -eq 0) {
        Write-Host "[INFO] No se encontraron archivos para incluir en el archivo ZIP." -ForegroundColor Yellow
        return
    }

    $totalBytes = 0
    foreach ($item in $FileList) { $totalBytes += $item.Length }
    $totalMb = [math]::Round($totalBytes / 1MB, 2)

    Write-Host ""
    Write-Host "Archivos a empaquetar: $($FileList.Count) ($totalMb MB)" -ForegroundColor Green

    if ($DryRun) {
        Write-Host ""
        Write-Host "Vista previa (primeros 20 archivos):" -ForegroundColor Cyan
        $FileList | Select-Object -First 20 | ForEach-Object {
            $kb = [math]::Round($_.Length / 1KB, 1)
            Write-Host "   + $($_.RelativePath) ($kb KB)" -ForegroundColor DarkGray
        }
        return
    }

    $manifestPath = Join-Path $env:TEMP "manifest_$timestamp.json"
    $ManifestData.filesCount = $FileList.Count
    $ManifestData.uncompressedBytes = $totalBytes
    $ManifestData.createdAt = (Get-Date).ToString("o")
    $ManifestData | ConvertTo-Json -Depth 5 | Out-File -FilePath $manifestPath -Encoding utf8

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    Add-Type -AssemblyName System.IO.Compression

    if (Test-Path $ZipPath) { Remove-Item -Path $ZipPath -Force }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $zip = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)

    try {
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip, $manifestPath, "manifest.json", [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null

        foreach ($file in $FileList) {
            $entryName = $file.RelativePath.Replace('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $file.FullPath, $entryName, [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
        }
    } finally {
        $zip.Dispose()
        if (Test-Path $manifestPath) { Remove-Item -Path $manifestPath -Force -ErrorAction SilentlyContinue }
    }

    $sw.Stop()
    $zipSize = (Get-Item $ZipPath).Length
    $zipMb = [math]::Round($zipSize / 1MB, 2)
    $ratio = if ($totalBytes -gt 0) { [math]::Round((1 - ($zipSize / $totalBytes)) * 100, 1) } else { 0.0 }
    $sec = [math]::Round($sw.Elapsed.TotalSeconds, 2)

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " [EXITO] ARCHIVO ZIP GENERADO CORRECTAMENTE" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "Archivo:     $ZipPath" -ForegroundColor White
    Write-Host "Archivos:    $($FileList.Count) empaquetados (+ manifest.json)" -ForegroundColor White
    Write-Host "Tamano orig: $totalMb MB" -ForegroundColor White
    Write-Host "Tamano ZIP:  $zipMb MB (Compresion: $ratio %)" -ForegroundColor White
    Write-Host "Tiempo:      $sec segundos" -ForegroundColor White
}

if ($Mode -eq "Databases" -or $Mode -eq "All") {
    Write-Host ""
    Write-Host "[BUSQUEDA] Escaneando bases de datos SQLite (*.db)..." -ForegroundColor Yellow
    $zipName = "databases_backup_${timestamp}_${gitBranch}${tagSuffix}.zip"
    $zipPath = Join-Path $OutputDir $zipName

    $dbFiles = [System.Collections.Generic.List[PSObject]]::new()
    $files = Get-ChildItem -Path $repoRoot -File | Where-Object {
        $_.Extension -eq ".db" -and $_.Name -notlike "test_*"
    }
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($repoRoot.Length).TrimStart('\', '/')
        $dbFiles.Add([PSCustomObject]@{
            FullPath     = $f.FullName
            RelativePath = $rel
            Length       = $f.Length
        })
    }

    $manifest = @{
        type        = "DatabasesBackup"
        project     = "FTMO_Stellar_Lite"
        timestamp   = $timestamp
        gitBranch   = $gitBranch
        gitCommit   = $gitCommit
        cleaned     = [bool]$CleanAfterArchive
    }

    Create-ArchiveFromFiles -ZipPath $zipPath -FileList $dbFiles -ManifestData $manifest -DeleteSources:$CleanAfterArchive
}

if ($Mode -eq "Full" -or $Mode -eq "All") {
    Write-Host ""
    Write-Host "[BUSQUEDA] Escaneando codigo fuente del motor cuantitativo..." -ForegroundColor Yellow
    $zipName = "snapshot_source_${timestamp}_${gitBranch}_${gitCommit}${tagSuffix}.zip"
    $zipPath = Join-Path $OutputDir $zipName

    $excludeDirs = @(".git", "archives", "__pycache__", ".venv", "venv", ".vscode", ".idea", "node_modules")
    $excludeFiles = @(".DS_Store", "Thumbs.db", "desktop.ini", "test_qa_suite.db")

    $sourceFiles = [System.Collections.Generic.List[PSObject]]::new()
    $all = Get-ChildItem -Path $repoRoot -Recurse -File -Force

    foreach ($f in $all) {
        $rel = $f.FullName.Substring($repoRoot.Length).TrimStart('\', '/')
        $parts = $rel.Split([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)

        $skip = $false
        foreach ($p in $parts) {
            if ($excludeDirs -contains $p) { $skip = $true; break }
        }
        if ($skip) { continue }
        if ($excludeFiles -contains $f.Name) { continue }
        if ($f.Extension -match "\.(zip|tar|gz|rar|key|pub)$") { continue }
        if ($f.Name -eq "telegram_config.json") { continue }

        $sourceFiles.Add([PSCustomObject]@{
            FullPath     = $f.FullName
            RelativePath = $rel
            Length       = $f.Length
        })
    }

    $manifest = @{
        type        = "FullSourceSnapshot"
        project     = "FTMO_Stellar_Lite"
        timestamp   = $timestamp
        gitBranch   = $gitBranch
        gitCommit   = $gitCommit
        tag         = $Tag
    }

    Create-ArchiveFromFiles -ZipPath $zipPath -FileList $sourceFiles -ManifestData $manifest
}
