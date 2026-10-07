# Validação e reconciliação

Um CSV de referência OHLC pode ser importado separadamente dos trades.

Cada candle recebe:

- `EXACT`: OHLC e campos opcionais coincidem;
- `OHLC_MATCH`: preços coincidem, volume/contagem divergem;
- `MISMATCH`: pelo menos um preço diverge;
- `NO_DATA`: referência existe, mas faltam trades.

Diferenças de preços são mostradas em ticks.

## Distinção metodológica

Gerar uma referência a partir dos próprios trades e compará-la prova **consistência interna**, não validação externa. Validação real exige uma referência independente.
