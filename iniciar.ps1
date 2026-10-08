$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Candle Lab B3 - Inicializador" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "[1/3] Primeira execução: preparando o ambiente local..." -ForegroundColor Yellow

    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv
    } else {
        Write-Host "Python não foi encontrado." -ForegroundColor Red
        Write-Host "Instale Python 3.11 ou superior, marque 'Add Python to PATH' e execute novamente."
        Read-Host "Pressione Enter para fechar"
        exit 1
    }

    Write-Host "[2/3] Instalando as dependências do Candle Lab..." -ForegroundColor Yellow
    & $python -m pip install --upgrade pip
    & $python -m pip install -e .
} else {
    Write-Host "[1/3] Ambiente local encontrado." -ForegroundColor Green
    Write-Host "[2/3] Dependências prontas." -ForegroundColor Green
}

Write-Host "[3/3] Iniciando o Candle Lab..." -ForegroundColor Green
Write-Host "O navegador abrirá em http://127.0.0.1:8765"
Write-Host "Mantenha esta janela aberta. Para encerrar, pressione Ctrl+C."
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:8765"
} | Out-Null

& $python -m candle_lab.cli serve
