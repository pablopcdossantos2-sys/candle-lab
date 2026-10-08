# Tutorial — validar um pregão completo com um CSV grande

> **Modo avançado/opcional desde a v0.12.** Para o uso normal, prefira `docs/TUTORIAL-FLUXO-SELETIVO.md`, que mantém o CSV grande fora da biblioteca e extrai apenas o trecho escolhido.

Este tutorial foi criado para a v0.11 do Candle Lab B3 e foi pensado para quem não costuma trabalhar com terminal.

O objetivo é processar, no próprio computador, o arquivo grande de **Trades/Tick by Tick** exportado pelo Profit e compará-lo ao arquivo de **1 minuto** do mesmo contrato e pregão.

Você **não precisa enviar o CSV de centenas de MB ao ChatGPT**. Ao final, o Candle Lab gera um relatório pequeno em HTML e JSON.

---

## Antes de começar

Você precisa ter os dois arquivos exportados do Profit:

1. o CSV grande de **Trades**;
2. o CSV de **1 minuto** do mesmo contrato e dia.

Exemplo:

```text
WINV26_2026-10-07_TRADES.csv
WINV26_2026-10-07_1MIN.csv
```

Não abra e salve novamente o CSV de Trades no Excel. Use o arquivo original exportado pelo Profit.

---

## Passo 1 — atualizar ou baixar o Candle Lab

Se você ainda não possui a versão mais recente:

1. abra o repositório do Candle Lab no GitHub;
2. clique em **Code**;
3. clique em **Download ZIP**;
4. extraia o ZIP para uma pasta;
5. abra a pasta extraída.

Se já possui uma cópia obtida pelo Git, atualize a branch `main` normalmente.

---

## Passo 2 — localizar o novo iniciador

Dentro da pasta do projeto existe:

```text
validar-pregao-completo.bat
```

Esse é o arquivo recomendado para esta etapa.

Você **não precisa abrir PowerShell manualmente**.

Dê dois cliques em `validar-pregao-completo.bat`.

Na primeira utilização, o script também prepara o ambiente Python se ele ainda não existir.

---

## Passo 3 — informar o CSV grande de Trades

A janela exibirá:

```text
PASSO 1 - Arquivo grande de Trades
```

No Explorador de Arquivos do Windows:

1. encontre o CSV grande de Trades;
2. use a opção **Copiar como caminho** no menu de contexto;
3. volte para a janela do Candle Lab;
4. cole o caminho;
5. pressione **Enter**.

Exemplo:

```text
C:\Users\pablo\Documents\Candle-Lab\Dados\WINV26_2026-10-07_TRADES.csv
```

Pode colar o caminho com aspas. O script remove as aspas automaticamente.

---

## Passo 4 — informar o CSV de 1 minuto

Faça o mesmo com o arquivo de 1 minuto.

Exemplo:

```text
C:\Users\pablo\Documents\Candle-Lab\Dados\WINV26_2026-10-07_1MIN.csv
```

---

## Passo 5 — informar o contrato

Quando aparecer:

```text
Digite o contrato
```

digite o contrato real presente nos arquivos.

Exemplo:

```text
WINV26
```

Evite usar `WINFUT` nesta validação.

---

## Passo 6 — informar o tick size

Para WIN, normalmente use:

```text
5
```

Para WDO, normalmente use:

```text
0,5
```

O script aceita tanto vírgula quanto ponto e normaliza o valor.

---

## Passo 7 — confirmar o intervalo

Para o arquivo de candles de 1 minuto, pressione apenas **Enter** quando aparecer:

```text
Intervalo da referencia em segundos [60]
```

Assim o valor padrão continuará sendo 60 segundos.

---

## Passo 8 — acompanhar o processamento

O Candle Lab mostrará algo semelhante a:

```text
[1/4] Calculando hash SHA-256 do arquivo...
[2/4] Importando:  18.42% · 1.420.000 linhas · 133,8/726,0 MiB
[2/4] Importando:  36.71% · 2.830.000 linhas · 266,5/726,0 MiB
...
[3/4] Importando referência OHLC e reconciliando...
[4/4] Concluído.
```

A memória não precisa conter todos os trades ao mesmo tempo. O arquivo é lido em blocos e os blocos confirmados são gravados no DuckDB.

### Se o processo for interrompido

Não apague o banco `data/candle_lab.duckdb`.

Execute novamente:

```text
validar-pregao-completo.bat
```

e informe **os mesmos arquivos**.

O Candle Lab calcula o SHA-256, reconhece o arquivo e retoma a partir do último bloco confirmado.

---

## Passo 9 — abrir o relatório

Ao terminar, o relatório HTML é aberto automaticamente.

Ele fica também em:

```text
data\reports
```

Serão criados dois arquivos:

```text
WINV26_validacao_YYYYMMDD-HHMMSS.html
WINV26_validacao_YYYYMMDD-HHMMSS.json
```

O HTML é para leitura humana.

O JSON contém os dados estruturados para auditoria e análise posterior.

---

## Passo 10 — o que enviar para continuar o projeto

Depois da validação, **não envie novamente o CSV de 726 MB**.

Envie apenas um destes arquivos:

```text
WINV26_validacao_....html
```

ou:

```text
WINV26_validacao_....json
```

Com esse relatório podemos verificar:

- número total de trades importados;
- intervalo realmente coberto;
- quantidade negociada;
- número de candles reconstruídos;
- número de candles EXACT;
- divergências OHLC;
- divergências de quantidade;
- candles de fronteira excluídos;
- tempo de ingestão;
- pico aproximado de memória Python.

---

## O que a v0.11 faz para proteger os dados

A ingestão massiva usa:

- SHA-256 do arquivo;
- número da linha original;
- commits por blocos;
- ponto de retomada;
- preservação de linhas textualmente idênticas;
- detecção da ordem invertida do Profit;
- sequência intrassegundo derivada da ordem normalizada da fonte;
- arquivo Parquet por contrato/pregão.

Importar exatamente o mesmo arquivo novamente não cria uma segunda cópia dos negócios.

---

## Limitação importante

O arquivo real do Profit que validamos possui timestamps com precisão de apenas um segundo e não contém Número do Negócio.

Portanto, a ordem intrassegundo utilizada pelo Candle Lab é a ordem preservada pela exportação do Profit depois de normalizarmos o arquivo descendente. Ela funcionou perfeitamente na primeira validação de 10 candles, mas não deve ser confundida com uma sequência oficial de execução fornecida pela B3.
