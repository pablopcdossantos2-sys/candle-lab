# Modelo de dados

## Trade

Cada negócio possui:

- contrato;
- timestamp;
- preço em ticks inteiros;
- quantidade;
- número/ID do negócio, quando disponível;
- lado agressor;
- comprador e vendedor, quando disponíveis;
- sequência original da fonte;
- origem.

Preço é armazenado em **ticks inteiros**. Exemplo: WIN em 145.000 com tick 5 → `price_ticks = 29000`.

## Candle

O candle é sempre derivado dos negócios:

- abertura = primeiro preço;
- máxima = maior preço;
- mínima = menor preço;
- fechamento = último preço;
- volume = soma das quantidades;
- negócios = número de registros.

## Proveniência

Importações são registradas como lotes com fonte, arquivo, cobertura temporal, registros recebidos/inseridos e diagnósticos.

## Índices derivados

Pesquisa, qualidade, famílias e transições são derivados/versionados. Eles podem ser reconstruídos sem alterar os negócios originais.
