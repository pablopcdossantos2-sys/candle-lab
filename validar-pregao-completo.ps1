$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Candle Lab B3 - Validacao de pregao completo (v0.11)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "O ambiente do Candle Lab ainda nao existe." -ForegroundColor Yellow
    Write-Host "Preparando a instalacao local pela primeira vez..." -ForegroundColor Yellow
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv
    } else {
        Write-Host ""
        Write-Host "Python nao foi encontrado. Instale Python 3.11 ou superior e execute este arquivo novamente." -ForegroundColor Red
        Read-Host "Pressione Enter para fechar"
        exit 1
    }
    & $python -m pip install --upgrade pip
    & $python -m pip install -e .
}

function Read-ExistingCsv([string]$Prompt) {
    while ($true) {
        $value = (Read-Host $Prompt).Trim().Trim('"')
        if (Test-Path -LiteralPath $value -PathType Leaf) {
            if ([System.IO.Path]::GetExtension($value).ToLowerInvariant() -eq ".csv") {
                return (Resolve-Path -LiteralPath $value).Path
            }
            Write-Host "O arquivo precisa possuir extensao .csv." -ForegroundColor Yellow
        } else {
            Write-Host "Arquivo nao encontrado. Copie o caminho completo e tente novamente." -ForegroundColor Yellow
        }
    }
}

Write-Host "PASSO 1 - Arquivo grande de Trades" -ForegroundColor Green
Write-Host "No Explorador do Windows, clique com o botao direito no CSV de Trades e escolha 'Copiar como caminho'." -ForegroundColor Gray
$trades = Read-ExistingCsv "Cole aqui o caminho do CSV de Trades"

Write-Host ""
Write-Host "PASSO 2 - Arquivo de 1 minuto" -ForegroundColor Green
$reference = Read-ExistingCsv "Cole aqui o caminho do CSV de 1 minuto"

Write-Host ""
Write-Host "PASSO 3 - Contrato" -ForegroundColor Green
$symbol = (Read-Host "Digite o contrato (ex.: WINV26)").Trim().ToUpperInvariant()
if ([string]::IsNullOrWhiteSpace($symbol)) {
    Write-Host "O contrato nao pode ficar vazio." -ForegroundColor Red
    Read-Host "Pressione Enter para fechar"
    exit 1
}

$tickText = (Read-Host "Tick size [5 para WIN; 0,5 para WDO]").Trim()
if ([string]::IsNullOrWhiteSpace($tickText)) { $tickText = "5" }
$tickText = $tickText.Replace(",", ".")

$intervalText = (Read-Host "Intervalo da referencia em segundos [60]").Trim()
if ([string]::IsNullOrWhiteSpace($intervalText)) { $intervalText = "60" }

$reportDir = Join-Path $PSScriptRoot "data\reports"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportBase = Join-Path $reportDir ($symbol + "_validacao_" + $stamp)

Write-Host ""
Write-Host "O Candle Lab vai:" -ForegroundColor Cyan
Write-Host "  1. calcular o hash do arquivo;" -ForegroundColor Gray
Write-Host "  2. importar os Trades em blocos;" -ForegroundColor Gray
Write-Host "  3. reconciliar os candles com o CSV de 1 minuto;" -ForegroundColor Gray
Write-Host "  4. criar relatorios JSON e HTML." -ForegroundColor Gray
Write-Host ""
Write-Host "Nao feche esta janela enquanto a importacao estiver em andamento." -ForegroundColor Yellow
Write-Host "Se houver uma interrupcao, execute este arquivo novamente com os mesmos CSVs: a importacao sera retomada." -ForegroundColor Yellow
Write-Host ""

& $python -m candle_lab.cli bulk-validate $trades $reference --symbol $symbol --tick-size $tickText --interval $intervalText --report $reportBase

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "A validacao terminou com erro. Leia a mensagem acima; o progresso confirmado no banco foi preservado." -ForegroundColor Red
    Read-Host "Pressione Enter para fechar"
    exit $LASTEXITCODE
}

$html = $reportBase + ".html"
$json = $reportBase + ".json"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Validacao concluida" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Relatorio HTML: $html"
Write-Host "Relatorio JSON: $json"
Write-Host ""
Write-Host "Para compartilhar o resultado sem enviar o CSV gigante, envie apenas o arquivo HTML ou JSON." -ForegroundColor Cyan

if (Test-Path $html) {
    Start-Process $html
}

Read-Host "Pressione Enter para fechar"
