$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $PSScriptRoot 'data\tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { python -m venv .venv }
$requirements = if (Test-Path -LiteralPath 'requirements-lock.txt') { 'requirements-lock.txt' } else { 'requirements.txt' }
& .\.venv\Scripts\python.exe -m pip --disable-pip-version-check install --cache-dir .\data\pip-cache -r $requirements
if ($LASTEXITCODE -ne 0) { throw 'Error al instalar dependencias' }
& .\.venv\Scripts\python.exe -m corkjobradar doctor
if ($LASTEXITCODE -ne 0) { throw 'Comprobación fallida' }
