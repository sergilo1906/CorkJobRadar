$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    throw 'Primero instala el proyecto con instalar.ps1'
}
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$previousBrowsers = $env:PLAYWRIGHT_BROWSERS_PATH
try {
    $env:TEMP = Join-Path $PSScriptRoot 'data\tmp'
    $env:TMP = $env:TEMP
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $PSScriptRoot 'data\playwright-browsers'
    New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
    & .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check --cache-dir data\pip-cache -r requirements-autoapply-lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Error instalando dependencias opcionales' }
    # The interactive human handoff needs the visible browser too.
    & .\.venv\Scripts\python.exe -m playwright install chromium --no-remove
    if ($LASTEXITCODE -ne 0) { throw 'Error instalando Chromium local' }
    & .\.venv\Scripts\python.exe -m corkjobradar autoapply doctor
    if ($LASTEXITCODE -ne 0) { throw 'Error en diagnóstico AutoApply' }
} finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
    $env:PLAYWRIGHT_BROWSERS_PATH = $previousBrowsers
}
