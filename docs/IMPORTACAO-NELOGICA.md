# Importação Nelogica / Profit

A v0.10 foi ajustada com base em exportações reais do Profit Ultra.

## Layout de Trades observado

O arquivo de Trades/Tick by Tick real recebido veio **sem cabeçalho**, separado por vírgulas e com 8 colunas nesta ordem:

1. Ativo
2. Data
3. Hora
4. Agente Comprador
5. Preço
6. Quantidade
7. Agente Vendedor
8. Agressor

O export também veio em ordem **mais recente → mais antigo**. O Candle Lab detecta esse padrão e reverte a sequência completa antes da reconstrução.

A data pode usar ano com dois dígitos, como `07/10/26`.

O timestamp observado possui precisão de 1 segundo. Como o layout não traz Número do Negócio, a sequência relativa dentro do mesmo segundo é preservada pela posição do arquivo após a normalização, mas não deve ser tratada como sequência oficial da B3.

## Agressor

Valores observados incluem:

- `Comprador` → BUY;
- `Vendedor` → SELL;
- `RLP` → preservado como informação da fonte e tratado como lado não determinado para métricas BUY/SELL.

O Candle Lab não força RLP para compra ou venda.

## Linhas textualmente idênticas

Não deduplique esse layout apenas porque duas linhas são iguais.

Na primeira amostra real, milhares de ocorrências tinham os mesmos 8 campos, mas a soma de Quantidade só conciliava com o candle de referência quando todas eram preservadas. Cada ocorrência recebe uma sequência local própria.

## CSV de 1 minuto formatado

O arquivo de candles real veio com:

- Ativo;
- Data;
- Hora;
- Abertura;
- Máximo;
- Mínimo;
- Fechamento;
- Volume;
- Quantidade.

No modo formatado do Profit:

- ponto funciona como separador de milhar;
- vírgula funciona como separador decimal;
- `Volume` é financeiro;
- `Quantidade` representa os contratos negociados.

Para reconciliar com o volume interno do Candle Lab, usa-se **Quantidade**, não Volume financeiro.

## Regras adicionais

- Prefira o contrato real (`WINV26`) a séries contínuas (`WINFUT`).
- Preserve o CSV original exportado; não abra e salve novamente no Excel antes de importar.
- O relatório de importação informa perfil detectado, ordem da fonte, precisão temporal, cobertura de agressor e alertas.
- Arquivos grandes são recebidos pela interface em blocos de 8 MiB, mas a ingestão analítica completa de centenas de MB ainda será otimizada para processamento em chunks diretamente no banco.

Veja também `docs/VALIDACAO-EMPIRICA-V010.md`.
