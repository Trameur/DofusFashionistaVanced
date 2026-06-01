# One-time setup: download + extract portable MySQL 8.0.46 (matches prod) and init its data dir.
# After this, run_windows11.ps1 starts the server and imports prod_dump.sql on first launch.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$ver    = '8.0.46'
$root   = Join-Path $env:LOCALAPPDATA 'Fashionista'
$base   = Join-Path $root "mysql-$ver-winx64"
$data   = Join-Path $root 'data'
$zip    = Join-Path $root "mysql-$ver-winx64.zip"
$mysqld = Join-Path $base 'bin\mysqld.exe'

New-Item -ItemType Directory -Force -Path $root | Out-Null

if (-not (Test-Path -LiteralPath $mysqld)) {
    if (-not (Test-Path -LiteralPath $zip)) {
        $url = "https://cdn.mysql.com/Downloads/MySQL-8.0/mysql-$ver-winx64.zip"
        Write-Host "Telechargement de MySQL $ver (~236 Mo)..."
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -UserAgent 'Mozilla/5.0'
    }
    Write-Host "Extraction..."
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $root)
}

if (-not (Test-Path -LiteralPath (Join-Path $data 'mysql'))) {
    Write-Host "Initialisation du repertoire de donnees..."
    New-Item -ItemType Directory -Force -Path $data | Out-Null
    & $mysqld --initialize-insecure "--datadir=$data" "--basedir=$base"
}

Write-Host "MySQL $ver pret dans $base"
