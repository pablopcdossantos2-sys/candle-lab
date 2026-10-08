# Índice temporal de linhas e bytes — v0.13

## Objetivo

A v0.13 transforma a relação entre candle selecionado no gráfico e linhas físicas do CSV Tick by Tick em uma camada explícita do Candle Lab.

A regra fundamental é:

~~~text
candle_start <= timestamp_do_trade < candle_end
~~~

Não é permitido estimar linhas usando média de negócios por minuto.

## Por que existe um índice?

O arquivo Tick do WIN pode possuir centenas de MB e milhões de linhas. Sem índice, cada nova seleção exige começar a varredura do CSV e avançar até o horário desejado.

Com o índice, o arquivo grande é lido integralmente uma única vez. Depois são guardados apenas metadados por minuto:

- início/fim temporal;
- primeira linha física;
- última linha física;
- offset inicial de byte;
- offset final de byte;
- quantidade de trades;
- primeiro/último timestamp na ordem física.

O índice contém centenas de registros, não milhões.

## Arquivo gerado

Os índices ficam em:

~~~text
data/indexes/*.cidx.json
~~~

Cada índice registra versão do formato, fonte, tamanho, impressão digital, SHA-256 integral calculado durante a indexação, contrato, ordem temporal, codificação, delimitador, linhas e buckets M1.

## Linha física x ordem cronológica

No layout real do Profit validado pelo projeto, o arquivo está em ordem descendente. Portanto, a linha física menor contém um negócio mais recente.

Exemplo:

~~~text
Linha 1000   14:40:59
...
Linha 1500   14:40:00
~~~

Nesse candle:

~~~text
source_row_min          = 1000
source_row_max          = 1500
chronological_open_row  = 1500
chronological_close_row = 1000
~~~

## M1, M2, M5 e M15

O índice-base é M1. Timeframes maiores são agregações exatas dos minutos contidos no intervalo semiaberto [start, end).

~~~text
M1  09:00 -> [09:00,09:01)
M2  09:00 -> [09:00,09:02)
M5  09:00 -> [09:00,09:05)
M15 09:00 -> [09:00,09:15)
~~~

## Gaps de liquidez

Não há procura manual por segundo 59, 58, 57. Se não existir trade no segundo final, o último negócio real anterior ao limite continua pertencendo naturalmente ao intervalo. Se não houver negócio em :00, o primeiro trade posterior ao início é a abertura observada.

## Offsets de byte

Além das linhas, cada minuto guarda byte_start e byte_end. Depois da primeira indexação, o Candle Lab usa seek no arquivo e lê apenas a faixa correspondente ao período selecionado.

## Validação automatizada

Os testes verificam linhas físicas M1, abertura/fechamento cronológicos em arquivo descendente, agregação de minutos, offsets de bytes, reuso do índice e igualdade byte a byte entre recorte indexado e recorte obtido por varredura completa.

## Interface

Após selecionar candles no gráfico:

1. cole o caminho do CSV grande;
2. clique em Preparar índice e localizar;
3. na primeira vez, aguarde a indexação completa;
4. veja a tabela com as linhas de cada candle;
5. clique em Recortar e importar intervalo localizado.

## CLI

~~~powershell
candle-lab index-trades "C:\Dados\WINV26_TRADES.csv" --symbol WINV26

candle-lab locate-lines "C:\Dados\WINV26_TRADES.csv" --symbol WINV26 --start "2026-10-07T14:40:00-03:00" --end "2026-10-07T14:50:00-03:00" --interval 60

candle-lab slice-trades "C:\Dados\WINV26_TRADES.csv" --symbol WINV26 --start "2026-10-07T14:40:00-03:00" --end "2026-10-07T14:50:00-03:00"
~~~

## Regra metodológica

O índice localiza fatos físicos do arquivo: linhas, bytes e timestamps. Ele não deduz quantidade de linhas por liquidez média, volume médio ou multiplicadores.