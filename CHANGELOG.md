# Changelog

## 0.13.0 — 2026-10-07
- índice temporal persistente de 1 minuto para o CSV Tick by Tick original;
- mapeamento exato de candles para linhas físicas do arquivo;
- distinção entre linha física, linha da abertura cronológica e linha do fechamento cronológico;
- offsets de byte por minuto;
- SHA-256 integral calculado durante a primeira indexação;
- cache do índice em `data/indexes/*.cidx.json`;
- agregação do índice M1 para candles M2/M5/M15;
- endpoint `/api/time-index/locate`;
- tabela de linhas na interface antes da extração;
- recorte por `seek` direto nos bytes localizados;
- comandos `index-trades` e `locate-lines`;
- `slice-trades` passa a reutilizar o índice;
- teste de igualdade byte a byte entre recorte indexado e varredura completa;
- documentação metodológica e tutorial do localizador.


## 0.12.0 — 2026-10-07
- fluxo recomendado alterado para visão geral → seleção → microestrutura;
- gráfico diário construído apenas com o CSV leve de 1/2 minutos;
- seleção visual de candles por arraste do mouse;
- extração streaming de um intervalo diretamente do CSV grande de Trades;
- o arquivo Tick completo pode permanecer fora da biblioteca;
- recortes pequenos são gravados em `data/slices`;
- intervalo de extração usa semântica `[início, fim)`;
- detecção e preservação da ordem descendente do Profit;
- endpoint local para recortar e importar o trecho selecionado;
- comando `candle-lab slice-trades`;
- biblioteca de microestrutura separada da visão geral OHLC;
- ingestão integral v0.11 mantida como modo avançado/opcional;
- testes de recorte seletivo e de biblioteca composta apenas por OHLC.


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
