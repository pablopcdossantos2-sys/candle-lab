# Changelog

## 0.18.0 — 2026-10-08
- adiciona motor de validação histórica das hipóteses do relatório interpretativo;
- mede repetibilidade e desfechos externos em horizontes configuráveis;
- exige continuidade temporal dentro do mesmo pregão;
- exclui dados sintéticos por padrão;
- quando há referência compatível, exige reconstrução EXACT do candle;
- calcula baseline direcional da própria biblioteca;
- calcula taxa de acerto, movimento >= 2 ticks, lift, excursão favorável/adversa e IC Wilson 95%;
- separa hipóteses direcionais de hipóteses apenas descritivas;
- adiciona painel `Validação histórica das hipóteses` à interface;
- adiciona endpoint `/api/research/hypothesis-validation`;
- adiciona testes para baseline, exclusão sintética, referência divergente e fronteira de pregão;
- documenta a metodologia em `docs/VALIDACAO-HISTORICA-HIPOTESES.md`;
- cria catálogo de possíveis indicadores em `docs/INDICADORES-POSSIVEIS-CANDLE-LAB.md`;
- adiciona pacote de prompts para TradingView/Pine Script;
- adiciona pacote de prompts para Profit Pro/NTSL;
- não implementa ainda os indicadores de plataforma: esta etapa é de pesquisa, especificação e preparação.


## 0.17.0 — 2026-10-08
- adiciona motor determinístico e auditável de interpretação do candle;
- gera descrição cronológica da agressão em início, miolo e fase final;
- separa evidências observadas de hipóteses explicativas;
- gera hipóteses para agressão alinhada, divergência preço/delta, possível absorção, rejeição de extremos, onda aberta, disputa bilateral e mudança de controle;
- adiciona score de qualidade da evidência com cobertura do agressor e identidade dos agentes;
- adiciona score e força interna para cada hipótese, explicitamente não tratados como probabilidade estatística;
- gera síntese textual sobre por que o candle pode ter fechado daquela maneira;
- adiciona painel `Relatório interpretativo do candle`;
- oculta o relatório durante replay parcial para evitar revelar informações futuras;
- adiciona botão para copiar o relatório em texto;
- preserva versões dos modelos e DNA no payload de auditoria;
- adiciona testes de interpretação direcional, divergência preço/delta, baixa cobertura e integração no detalhe do candle;
- documenta metodologia em `docs/RELATORIO-INTERPRETATIVO-CANDLE.md`.


## 0.16.0 — 2026-10-08
- adiciona detecção causal de ondas de agressão BUY/SELL por janela móvel de negócios;
- identifica término por `EXAUSTAO`, `NEUTRALIZACAO` e `TROCA_CONTROLE`;
- registra instante, negócio, preço, queda da pressão, duração e principais agentes de cada onda;
- mantém ondas ainda ativas como `ABERTA_NO_FIM_DO_CANDLE`, sem inventar término;
- adiciona avaliação posterior separada como `REVERSAO_COMPATIVEL`, `CONTINUACAO`, `ESTAGNACAO_OU_DISPUTA` ou `SEM_JANELA_POSTERIOR`;
- marca explicitamente que a avaliação posterior usa dados futuros e não participa da detecção;
- replay só revela um término depois do negócio que o confirmou;
- gráfico intrabar recebe marcadores T1/T2/T3 para os términos confirmados;
- adiciona teste que garante que anexar negócios futuros não altera retroativamente o instante detectado;
- adiciona documentação metodológica em `docs/TERMINO-ONDAS-AGRESSAO.md`.


## 0.15.0 — 2026-10-08
- adiciona análise de agressão executada por nível de preço;
- identifica principais agentes compradores e vendedores agressores no candle e em cada preço;
- calcula BUY, SELL, delta, dominância, cobertura do agressor e cobertura de identidade do agente;
- classifica intensidade da agressão como BAIXA, MODERADA, ALTA ou EXTREMA em relação ao próprio candle;
- preserva RLP e agressão indefinida separadamente;
- adiciona heurísticas descritivas de `IMPULSO_COMPATIVEL`, `POSSIVEL_ABSORCAO`, `PRESSAO_SEM_CONFIRMACAO` e `SEM_JANELA_POS_AGRESSAO`;
- adiciona painel `Mapa de agressão por preço` ao Laboratório do candle;
- adiciona rankings gerais de principais agressores;
- documenta limitações: Times & Trades não substitui livro MBO/MBP e não prova causalidade;
- adiciona testes para atribuição do agente agressor, intensidade, RLP e proteção contra falsa absorção no fim do candle.


## 0.14.4 — 2026-10-07
- corrige `Parameter argument/count mismatch` ao gravar `session_quality` no DuckDB;
- `INSERT` de qualidade passa a declarar explicitamente todas as colunas;
- adiciona teste de persistência real do payload de qualidade;
- não exige apagar índice temporal, recortes ou banco local já existentes.


## 0.14.3 — 2026-10-07
- adiciona barra de progresso à ação `Recortar e importar intervalo localizado`;
- extração seletiva reporta progresso pelos bytes efetivamente lidos da faixa localizada;
- interface mostra porcentagem geral e etapa atual da tarefa;
- progresso distingue preparação, localização, extração, normalização, gravação, catálogo e conclusão;
- recorte/importação passa a rodar como tarefa local consultável pela interface;
- endpoint de compatibilidade síncrono permanece disponível;
- testes automatizados verificam progresso inicial/final e os controles da interface.


## 0.14.2 — 2026-10-07
- corrige preços do Profit com ponto como separador de milhar, por exemplo `205.935` → `205935`;
- mantém a interpretação decimal genérica separada da regra específica do Profit;
- amplia a detecção de arquivos de Trades com cabeçalho do Profit;
- recortes seletivos usam a mesma normalização numérica específica da fonte;
- indexação temporal passa a reportar progresso por bytes efetivamente lidos;
- interface mostra porcentagem, linhas processadas, bytes/MB lidos e minutos indexados;
- construção do índice roda como tarefa local e a interface consulta o progresso até a conclusão;
- quando o índice já existe, a interface informa que nenhuma nova leitura integral foi necessária;
- testes automatizados cobrem o preço `205.935`, progresso final em 100% e contrato da interface.


## 0.14.1 — 2026-10-07
- localizador seletivo deixa de exigir exclusivamente o layout sem cabeçalho de 8 colunas;
- suporte a arquivos de Trades com cabeçalho reconhecível;
- suporte a colunas extras em exportações do Profit;
- suporte a layout sem cabeçalho de 9 colunas com Número do Negócio;
- linhas exibidas passam a refletir a linha física real do CSV original, inclusive com cabeçalho;
- valores brasileiros em CSV separado por ponto e vírgula são normalizados no recorte derivado;
- formato do índice temporal atualizado para 1.1 e índices antigos são reconstruídos automaticamente.


## 0.14.0 — 2026-10-07
- seleção de intervalo redesenhada no gráfico diário;
- zoom horizontal em até 30 níveis;
- maior densidade de marcações temporais no eixo X conforme o zoom aumenta;
- botões para panorâmica esquerda/direita e retorno ao dia inteiro;
- comando `Zoom na seleção`;
- suporte a `Ctrl + roda do mouse` para zoom;
- marcadores verticais arrastáveis **INÍCIO** e **FIM**;
- campos de horário de início/fim sincronizados com a seleção;
- seleção automática ao digitar horários como `14:40`–`14:50`;
- validação de fronteiras de candle conforme o timeframe exibido;
- tutorial completo de instalação e uso no Windows;
- inicializador Windows com mensagens de primeira execução e erro de Python mais claras;
- CI passa a validar também `iniciar.ps1`.


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
