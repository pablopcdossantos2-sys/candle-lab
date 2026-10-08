# Ingestão massiva — v0.11

> Esta camada continua suportada na v0.12, mas passou a ser um modo avançado de auditoria. O fluxo cotidiano recomendado é a extração seletiva documentada em `ARQUITETURA-FLUXO-SELETIVO.md`.

## Objetivo

Processar exportações de Trades do Profit com centenas de MB sem materializar o pregão inteiro em memória.

A primeira necessidade concreta é um CSV de aproximadamente 726 MB do WINV26.

## Identidade do arquivo

Antes da importação, o Candle Lab calcula SHA-256 em streaming.

O hash é usado para:

- reconhecer o mesmo arquivo numa segunda execução;
- impedir duplicação integral;
- localizar checkpoints;
- compor a identidade das ocorrências importadas.

## Identidade de uma ocorrência

No layout Profit real validado não existe Número do Negócio.

Por isso, uma ocorrência da importação massiva é identificada por:

```text
SHA-256 do arquivo + número da linha da fonte
```

Isso é deliberado: linhas textualmente idênticas podem representar negócios distintos e não devem ser removidas.

## Ordem temporal

O arquivo real recebido está em ordem descendente.

Não é necessário inverter 726 MB em memória.

Para esse caso:

```text
sequence_no = -source_row
```

Logo:

```sql
ORDER BY ts ASC, sequence_no ASC
```

reproduz a mesma ordem que obteríamos invertendo o arquivo completo.

## Blocos e transações

O padrão inicial é:

```text
100.000 linhas por bloco
```

Cada bloco é:

1. lido;
2. normalizado;
3. inserido;
4. confirmado por transação;
5. registrado em `bulk_imports`.

Somente depois do commit o checkpoint avança.

## Retomada

São preservados:

- `processed_rows`;
- `inserted_rows`;
- `byte_offset`;
- diagnósticos acumulados.

Em uma nova execução com o mesmo SHA-256, a leitura recomeça no byte offset confirmado.

## Reconstrução de candles

Depois da ingestão, o Candle Lab não carrega milhões de trades para calcular OHLC.

O DuckDB agrega diretamente no banco:

- `first(price_ticks ORDER BY ts, sequence_no)`;
- `max(price_ticks)`;
- `min(price_ticks)`;
- `last(price_ticks ORDER BY ts, sequence_no)`;
- `sum(quantity)`;
- `count(*)`.

Assim, a reconciliação final trabalha com centenas de candles em vez de milhões de linhas.

## Parquet

Ao final de `bulk-validate`, cada pregão validado é exportado como:

```text
data/parquet/<CONTRATO>/<AAAA-MM-DD>.parquet
```

com compressão ZSTD.

## Relatórios

A rotina produz:

```text
data/reports/*.html
data/reports/*.json
```

Esses arquivos são pequenos e podem ser compartilhados sem enviar o CSV bruto.

## Segurança metodológica

- SHA-256 igual identifica o mesmo arquivo, não necessariamente todos os possíveis recortes equivalentes do mercado.
- Arquivos diferentes que contenham períodos sobrepostos não são automaticamente deduplicados entre si, pois a exportação validada não possui um ID oficial do negócio.
- A sequência intrassegundo deriva da ordem preservada no arquivo do Profit.
- Coincidência com o CSV de 1 minuto valida a reconstrução contra essa referência, não certifica os dados como feed oficial da B3.
