# Estabilidade e transições — v0.9

A v0.9 estuda a sequência temporal das famílias intrabar.

## Estabilidade

Por família são medidos:

- suporte total;
- número de pregões;
- prevalência entre sessões;
- consistência da participação entre pregões;
- dispersão por horário, volatilidade e regime;
- score heurístico 0–100.

Rótulos: `DISTRIBUIDA`, `MODERADA`, `CONCENTRADA` e `AMOSTRA_PEQUENA`.

“Estabilidade” é descrição da biblioteca atual, não persistência futura.

## Transições

Uma transição só é contada quando dois candles são realmente consecutivos no mesmo pregão e separados exatamente pelo timeframe analisado.

Não são criadas transições:

- atravessando uma lacuna;
- entre o último candle de um pregão e o primeiro do dia seguinte.

A frequência `A → B` é contagem histórica condicionada às saídas observadas de A. Não é probabilidade futura.

A camada também conta motivos/sequências de três candles e mostra anterior → atual → próximo para o candle selecionado.
