# Arquitetura do fluxo seletivo — v0.12

## Princípio

A biblioteca não precisa duplicar todo o histórico Tick disponível ao usuário.

O Candle Lab distingue:

- **visão geral**: candles OHLC leves de 1/2 minutos;
- **fonte bruta externa**: CSV grande de Trades no disco do usuário;
- **recorte de pesquisa**: apenas os Trades do intervalo escolhido;
- **artefatos derivados**: métricas, replay e índices.

## Fluxo

```text
Profit — OHLC 1/2 min
        ↓
reference_candles
        ↓
gráfico diário
        ↓
seleção [start,end)
        │
        │                    Profit — Trades grande
        │                              ↓
        └──────────────────────→ slice.py
                                       ↓
                              data/slices/*.csv
                                       ↓
                              importador normal
                                       ↓
                                   DuckDB
                                       ↓
                      replay / DNA / pesquisa
```

## Benefícios

- menor uso de disco;
- menor tempo até a primeira análise;
- a base Tick original permanece intocada;
- evita manter duas cópias de milhões de negócios;
- permite estudar apenas zonas de interesse;
- facilita excluir e recriar dados derivados.

## Otimização para arquivos monotônicos

O export real validado do Profit está em ordem descendente.

Para um intervalo `[start,end)`, o extrator:

- ignora `timestamp >= end`;
- copia `start <= timestamp < end`;
- interrompe a leitura quando encontra `timestamp < start`.

Portanto, ele não precisa necessariamente percorrer o restante do arquivo depois de alcançar o intervalo escolhido.

## Persistência

OHLC diário permanece em `reference_candles`.

Recortes Tick são gravados em `data/slices` e importados para `trades`.

A ingestão integral `bulk.py` continua disponível, mas é considerada um modo avançado e não o caminho padrão.


## Idempotência entre recortes

Cada recorte registra:

- uma impressão digital rápida da fonte original (tamanho + blocos inicial/final);
- o ordinal da linha não vazia na fonte.

A chave derivada `fingerprint + source_row` evita duplicar negócios quando recortes se sobrepõem.

A impressão digital rápida não é apresentada como SHA-256 integral da fonte; seu objetivo é identidade operacional sem exigir uma segunda leitura completa de centenas de MB.

## Reconciliação de ilhas

Como o usuário pode importar trechos não contíguos, a reconciliação no modo seletivo usa apenas candles que possuem Trades armazenados.

Candles fora das seleções são ignorados deliberadamente, em vez de classificados como `NO_DATA`.
