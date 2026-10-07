# Validação empírica v0.10 — WINV26 · 07/10/2026

Esta validação usa dois arquivos reais exportados do Profit Ultra e fornecidos ao projeto para teste:

- um recorte de Trades/Tick by Tick do WINV26;
- o arquivo de candles de 1 minuto do mesmo contrato e pregão.

Os arquivos brutos **não são versionados no repositório**. Este documento registra somente resultados agregados e implicações para o importador.

## Layout observado — Trades

O recorte recebido possui 92.441 linhas e aproximadamente 9,05 MiB.

O Profit exportou este arquivo:

- sem cabeçalho;
- separado por vírgulas;
- com 8 colunas;
- em ordem cronológica inversa (mais recente → mais antigo);
- com timestamp limitado ao segundo.

As 8 posições observadas foram interpretadas como:

1. Ativo
2. Data
3. Hora
4. Agente Comprador
5. Preço
6. Quantidade
7. Agente Vendedor
8. Agressor

O recorte vai de 14:40:00 até 14:50:00. Os minutos 14:40–14:49 estão inteiramente contidos no recorte; 14:50 contém apenas o começo do candle e foi classificado como fronteira parcial.

## Layout observado — 1 minuto

O arquivo de referência possui 565 candles, de 09:00 a 18:24, com:

- Ativo
- Data
- Hora
- Abertura
- Máximo
- Mínimo
- Fechamento
- Volume
- Quantidade

Neste layout formatado:

- ponto é separador de milhar;
- vírgula é separador decimal;
- `Volume` é financeiro;
- `Quantidade` é a quantidade negociada em contratos.

Para reconciliação com o Candle Lab, `Quantidade` deve ser comparada ao volume interno do candle.

## Resultado da reconstrução

Foram usados apenas os 10 candles completamente cobertos pelo recorte de Trades:

- 14:40
- 14:41
- 14:42
- 14:43
- 14:44
- 14:45
- 14:46
- 14:47
- 14:48
- 14:49

Resultado:

| Métrica | Resultado |
| --- | ---: |
| Candles completos comparados | 10 |
| Aberturas exatas | 10/10 |
| Máximas exatas | 10/10 |
| Mínimas exatas | 10/10 |
| Fechamentos exatos | 10/10 |
| Quantidade exata | 10/10 |
| Candles EXACT | 10/10 |
| Taxa exata | **100%** |

No conjunto completo desses 10 minutos:

- 92.243 linhas de negócios foram utilizadas;
- 317.809 contratos foram somados;
- a quantidade agregada bateu exatamente com a referência.

O candle das 14:50 foi excluído da taxa porque o recorte contém somente o segundo 14:50:00 (198 linhas / 641 contratos), enquanto a referência de 1 minuto contém o candle inteiro.

## Volume financeiro

Nos 10 candles completos, a coluna `Volume` do arquivo de 1 minuto coincide exatamente com a soma observada de:

`preço × quantidade × 0,20`

para o WIN deste recorte.

Isso confirma empiricamente que a coluna `Volume` dessa exportação não deve ser confundida com a quantidade de contratos.

## Agressão

No recorte:

- Comprador: 31.974 registros;
- Vendedor: 35.363 registros;
- RLP: 25.104 registros.

Assim, 72,84% dos registros possuem lado BUY/SELL diretamente utilizável nas métricas atuais. Os 27,16% marcados como RLP são preservados como tal e não são forçados artificialmente para compra ou venda.

Comprador e vendedor estavam preenchidos em 100% das linhas.

## Duplicatas aparentes

Há muitas linhas com os 8 campos textualmente idênticos. Elas **não podem ser removidas como duplicatas**.

A validação de quantidade mostra que esses registros repetidos participam do volume real. Como o layout não traz Número do Negócio, o Candle Lab passa a preservar cada ocorrência pela posição/sequência do arquivo.

## Ordem intrassegundo

Como o timestamp possui apenas precisão de 1 segundo, a ordem exata dentro do mesmo segundo não pode ser reconstruída a partir do horário isoladamente.

O arquivo recebido está invertido. Ao reverter a sequência completa do arquivo, abertura e fechamento dos 10 candles coincidiram exatamente com a referência. Por isso, a v0.10 preserva a posição relativa do arquivo depois da normalização.

Isso é evidência forte de consistência com a exportação do Profit, mas não deve ser chamado de número oficial de sequência da B3.

## Mudanças implementadas na v0.10

- reconhecimento automático do layout Profit sem cabeçalho de 8 colunas;
- suporte a data com ano de dois dígitos;
- detecção de arquivo descendente e reversão determinística;
- preservação de linhas idênticas pela sequência;
- preservação de `RLP` sem inferência BUY/SELL;
- suporte ao CSV de 1 minuto formatado em padrão brasileiro;
- uso de `Quantidade` como volume em contratos na referência Profit;
- aceitação de `Máximo` e `Mínimo`;
- reconciliação limitada aos candles totalmente cobertos pelo recorte;
- estado `PARTIAL_SOURCE_WINDOW` para fronteiras incompletas;
- upload web escrito em blocos, evitando carregar o arquivo recebido inteiro em memória durante a etapa de transferência;
- comando `candle-lab empirical-validate`.

## Limitação ainda aberta

Embora o upload agora seja gravado em blocos, o importador analítico ainda materializa os trades normalizados em memória antes da inserção.

Portanto, o arquivo original de aproximadamente 726 MB **não deve ser usado ainda como primeiro teste de carga completa**. A próxima melhoria de engenharia deve ser um pipeline de ingestão em chunks diretamente para DuckDB/Parquet.

Essa mudança será necessária antes de validar um pregão inteiro de WIN em uma única importação.
