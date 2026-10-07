# Qualidade do pregão

Antes de comparar sessões, o Candle Lab mede a qualidade observável do dataset.

Estados atuais:

- `COMPLETE`;
- `LIKELY_COMPLETE`;
- `PARTIAL_START`;
- `PARTIAL_END`;
- `PARTIAL_BOTH`;
- `GAPPED`;
- `REVIEW`;
- `UNKNOWN_SCHEDULE`.

O score considera cobertura temporal, proximidade dos limites nominais, minutos ativos e lacunas observadas.

## Atenção

“Completo segundo a grade” não significa que a fonte foi certificada pela B3. Uma lacuna também pode refletir pausa real/leilão, não necessariamente perda de dados.

A grade de WIN/WDO é versionada e ainda possui simplificações para exceções históricas e vencimentos.
