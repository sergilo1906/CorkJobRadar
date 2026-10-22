$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Ejecuta instalar.ps1 primero' }
& .\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
