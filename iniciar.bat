@echo off
setlocal
cd /d "%~dp0"
title Candle Lab B3

echo.
echo ============================================================
echo  Candle Lab B3 - Inicializador
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Primeira execucao: preparando o ambiente local...
  echo.

  where py >nul 2>&1
  if %errorlevel%==0 (
    py -3 -m venv .venv
  ) else (
    where python >nul 2>&1
    if not %errorlevel%==0 (
      echo ERRO: Python nao foi encontrado neste computador.
      echo.
      echo Instale Python 3.11 ou superior e marque a opcao
      echo "Add Python to PATH" durante a instalacao.
      echo Depois, execute este arquivo novamente.
      echo.
      pause
      exit /b 1
    )
    python -m venv .venv
  )

  if not exist ".venv\Scripts\python.exe" (
    echo ERRO: nao foi possivel criar o ambiente Python.
    pause
    exit /b 1
  )

  echo [2/3] Instalando as dependencias do Candle Lab...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 goto :install_error
  ".venv\Scripts\python.exe" -m pip install -e .
  if errorlevel 1 goto :install_error
) else (
  echo [1/3] Ambiente local encontrado.
  echo [2/3] Dependencias prontas.
)

echo [3/3] Iniciando o Candle Lab...
echo.
echo O navegador abrira em http://127.0.0.1:8765
echo Mantenha esta janela aberta enquanto estiver usando a ferramenta.
echo Para encerrar, volte a esta janela e pressione Ctrl+C.
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul & start "" http://127.0.0.1:8765"
".venv\Scripts\python.exe" -m candle_lab.cli serve
exit /b %errorlevel%

:install_error
echo.
echo ERRO: nao foi possivel instalar as dependencias.
echo Verifique sua conexao com a internet e tente novamente.
echo.
pause
exit /b 1
