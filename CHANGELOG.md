# Changelog

## 0.11.0 — 2026-10-07
- ingestão massiva de Trades em chunks configuráveis;
- SHA-256 do arquivo antes da importação;
- importação retomável após interrupção;
- commits por bloco no DuckDB;
- rastreamento por hash da fonte e número da linha;
- proteção contra reimportar exatamente o mesmo arquivo;
- preservação de linhas idênticas da exportação Profit;
- reconstrução OHLC diretamente em SQL, sem carregar o pregão inteiro em objetos Python;
- reconciliação do pregão completo com referência de 1 minuto;
- exportação Parquet por contrato/pregão;
- relatórios HTML e JSON;
- comandos `bulk-import` e `bulk-validate`;
- iniciador `validar-pregao-completo.bat` e tutorial passo a passo para Windows.


## 0.10.0 — 2026-10-07
- primeira validação empírica com exportação real do WINV26;
- 10/10 candles completos reconciliados exatamente em OHLC e quantidade;
- importador para Trades Profit sem cabeçalho, 8 colunas e ordem cronológica inversa;
- suporte a datas com ano de dois dígitos;
- preservação de RLP sem inferência BUY/SELL;
- preservação de ocorrências textualmente idênticas pela sequência do arquivo;
- leitura correta do CSV de 1 minuto formatado do Profit;
- `Quantidade` passa a ser usada como volume em contratos na referência;
- candles de fronteira incompletos recebem `PARTIAL_SOURCE_WINDOW`;
- comando `candle-lab empirical-validate`;
- upload web gravado em blocos de 8 MiB;
- painel web para importar referência OHLC e exibir reconciliação.


## 0.9.0 — 2026-10-07
- estabilidade descritiva das famílias intrabar entre pregões e contextos;
- matrizes de transição de famílias e clusters;
- sequências de três candles;
- análise anterior → atual → próximo do candle selecionado;
- transições não atravessam lacunas ou fronteiras entre pregões;
- comando `candle-lab transitions`;
- interface e documentação atualizadas;
- amostra sintética de 2.880 negócios gerada deterministicamente pelo programa.

## 0.8.0
- famílias de trajetória interpretáveis;
- clustering determinístico de trajetórias normalizadas;
- medóides, coesão e distribuição contextual.

## 0.7.0
- score de qualidade por pregão;
- cobertura, lacunas e elegibilidade científica;
- regimes multiescala e gap de abertura.

## 0.6.0
- pesquisa comparativa multi-pregão;
- similaridade visual e similaridade pelo DNA separadas.

## 0.5.0
- reconciliação OHLC independente;
- proveniência e biblioteca histórica.

## 0.4.0
- importador Nelogica/Profit aprimorado;
- replay com cadência temporal;
- DNA intrabar expandido.

## 0.3.0
- DuckDB/Parquet;
- primeira interface local de replay.
