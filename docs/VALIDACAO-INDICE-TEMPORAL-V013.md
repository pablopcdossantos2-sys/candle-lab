# Validação real do índice temporal — WINV26 · 07/10/2026

Este documento registra a primeira validação do índice temporal v0.13 usando o mesmo recorte real do WINV26 já utilizado na validação empírica da v0.10.

Arquivo analisado:

- 92.441 linhas;
- aproximadamente 9,05 MiB;
- janela observada: 14:40:00 até 14:50:00;
- ordem física: DESCENDING.

## Intervalo principal

Para a seleção [14:40:00,14:50:00):

- linha física mínima: 199;
- linha física máxima: 92.441;
- linha cronológica da abertura do intervalo: 92.441;
- linha cronológica do fechamento do intervalo: 199;
- negócios: 92.243;
- byte inicial: 20.683;
- byte final exclusivo: 9.494.281;
- bytes cobertos: 9.473.598.

O total de 92.243 negócios coincide exatamente com o conjunto usado anteriormente para reconciliar 10/10 candles de 1 minuto contra a referência do Profit.

## Mapa candle a candle

| Candle | Linhas físicas | Linha da abertura | Linha do fechamento | Trades | Byte inicial | Byte final |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 14:40 | 83.643–92.441 | 92.441 | 83.643 | 8.799 | 8.592.538 | 9.494.281 |
| 14:41 | 72.752–83.642 | 83.642 | 72.752 | 10.891 | 7.468.366 | 8.592.538 |
| 14:42 | 66.962–72.751 | 72.751 | 66.962 | 5.790 | 6.879.137 | 7.468.366 |
| 14:43 | 62.921–66.961 | 66.961 | 62.921 | 4.041 | 6.467.903 | 6.879.137 |
| 14:44 | 56.117–62.920 | 62.920 | 56.117 | 6.804 | 5.765.334 | 6.467.903 |
| 14:45 | 39.252–56.116 | 56.116 | 39.252 | 16.865 | 4.020.324 | 5.765.334 |
| 14:46 | 25.829–39.251 | 39.251 | 25.829 | 13.423 | 2.647.593 | 4.020.324 |
| 14:47 | 17.572–25.828 | 25.828 | 17.572 | 8.257 | 1.808.980 | 2.647.593 |
| 14:48 | 7.358–17.571 | 17.571 | 7.358 | 10.214 | 758.047 | 1.808.980 |
| 14:49 | 199–7.357 | 7.357 | 199 | 7.159 | 20.683 | 758.047 |

## Candle parcial das 14:50

O arquivo começa com 198 linhas de 14:50:00. Esse minuto está incompleto no recorte e, por isso, não pertence à seleção [14:40,14:50). O índice o mantém como bucket separado, sem contaminar os dez candles completos.

## Conclusão

A indexação física confirma a relação esperada para a exportação descendente do Profit:

- a abertura cronológica de cada candle está na linha física de maior número;
- o fechamento cronológico está na linha física de menor número;
- o número real de trades é a quantidade de linhas do intervalo, sem estimativas;
- os offsets de byte permitem acesso direto ao trecho depois da primeira indexação.