$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[Candle Lab B3] Preparando o ambiente pela primeira vez..."
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv } else { python -m venv .venv }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install -e .
}
Start-Process "http://127.0.0.1:8765"
& .\.venv\Scripts\python.exe -m candle_lab.cli serve
