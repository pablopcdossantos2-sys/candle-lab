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
