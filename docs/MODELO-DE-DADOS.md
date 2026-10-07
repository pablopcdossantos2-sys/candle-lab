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


## Proveniência de arquivos grandes — v0.11

A tabela `trades` ganhou campos opcionais:

- `source_file_hash`: SHA-256 do CSV de origem;
- `source_row`: posição da ocorrência no arquivo.

Eles são especialmente importantes porque o layout real de Trades do Profit observado não contém Número do Negócio e pode possuir várias linhas textualmente idênticas.

A tabela `bulk_imports` registra:

- hash e tamanho do arquivo;
- caminho e nome;
- contrato e tick size;
- ordem detectada da fonte;
- status `PENDING/RUNNING/FAILED/COMPLETED`;
- linhas processadas/inseridas;
- byte offset confirmado;
- primeiro/último timestamp;
- tempo acumulado;
- diagnósticos.

O checkpoint só avança depois do commit do bloco correspondente. Isso torna a retomada idempotente para o mesmo arquivo.
