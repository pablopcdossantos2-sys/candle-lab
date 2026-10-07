# Arquitetura

O Candle Lab B3 é uma aplicação local em Python.

## Fluxo

```text
CSV / fonte histórica
      ↓
importers.py
      ↓
Trade normalizado
      ↓
DuckDB + Parquet
      ↓
candles.py
      ↓
┌────────────┬──────────────┬─────────────┐
│ Replay/DNA │ Reconciliação│ Pesquisa    │
└────────────┴──────────────┴─────────────┘
                              ↓
                       trajectory.py
                              ↓
                       transitions.py
```

## Camadas

- **models.py**: contratos internos `Trade` e `Candle`.
- **importers.py**: normalização de CSV e perfil Nelogica.
- **storage.py**: persistência DuckDB, índice e snapshots Parquet.
- **candles.py**: agregação determinística.
- **metrics.py**: DNA intrabar.
- **quality.py**: qualidade/cobertura do pregão.
- **reconciliation.py**: comparação com OHLC independente.
- **research.py**: similaridade visual/DNA e regimes.
- **trajectory.py**: taxonomia + clustering.
- **transitions.py**: estabilidade e sequências temporais.
- **web/**: FastAPI e interface local.

A arquitetura preserva negócios originais e evita misturar replay real com simulação contrafactual.


## Ingestão massiva — v0.11

Arquivos grandes do Profit usam um caminho próprio:

```text
CSV grande no disco
      ↓
SHA-256 + probe do layout
      ↓
leitura de até N linhas
      ↓
normalização do bloco
      ↓
transação DuckDB
      ↓
checkpoint (linha + byte offset)
      ↓
próximo bloco
```

O arquivo não precisa ser convertido integralmente em uma lista de objetos Python.

Para o layout descendente observado no Profit, `sequence_no = -source_row`. Assim, `ORDER BY ts, sequence_no` reproduz a reversão completa do arquivo e preserva a ordem relativa intrassegundo.

A reconstrução de OHLC do pregão inteiro é executada no DuckDB com agregações ordenadas `first(... ORDER BY ts, sequence_no)` e `last(... ORDER BY ts, sequence_no)`.

