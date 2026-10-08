# Candle Lab B3

**Laboratório local para investigar como candles de futuros da B3 são formados negócio a negócio.**

Versão atual: **0.14.0**

O Candle Lab B3 nasceu de uma pergunta simples: **dois candles visualmente parecidos necessariamente foram formados da mesma maneira?**

Um candle tradicional mostra apenas abertura, máxima, mínima e fechamento. Ele não revela a ordem em que os preços foram visitados, quantas reversões ocorreram, quanto tempo o mercado permaneceu em cada região, quantos negócios participaram do movimento ou quais caminhos intrabar poderiam produzir o mesmo OHLC.

O projeto transforma esse candle pronto em um objeto de pesquisa. A aplicação importa negócios reais, reconstrói candles, permite reproduzir sua formação trade a trade, calcula métricas intrabar e compara milhares de trajetórias sem misturar dados históricos com simulações.

> **Princípio central:** replay real, referência externa, métricas derivadas e simulação contrafactual permanecem identificados separadamente.

---

## Para quem este projeto é útil

O projeto foi pensado principalmente para:

- traders e estudantes de mercado interessados em microestrutura;
- pesquisadores que desejam estudar formação intrabar;
- usuários de WIN/WDO que possuam histórico de negócios exportável;
- pessoas que desejam comparar candles além do simples desenho OHLC;
- desenvolvedores interessados em construir uma biblioteca histórica auditável de trades.

Ele **não é** um robô de operações, não envia ordens e não fornece recomendação de compra ou venda.

---

## O que o Candle Lab faz hoje

### 1. Importa negócios reais

A v0.10 foi ajustada com uma exportação real do Profit Ultra. Além de CSVs com cabeçalho, o importador reconhece o layout de Trades sem cabeçalho de 8 colunas observado no Profit, detecta quando o arquivo está em ordem cronológica inversa e preserva a sequência relativa do arquivo.

Quando o arquivo possui cabeçalho, são reconhecidos campos como:

- `Ativo`;
- `Data`;
- `Tempo` ou `Hora`;
- `Número do Negócio`;
- `Preço`;
- `Quantidade`;
- `Agente Comprador`;
- `Agente Vendedor`;
- `Agressor`.

A aplicação preserva a ordem da fonte, identifica duplicidades e registra a proveniência de cada lote importado.

### 2. Reconstrói candles a partir dos negócios

Os trades podem ser agregados em diferentes intervalos, como:

- 1 segundo;
- 5 segundos;
- 15 segundos;
- 1 minuto;
- 5 minutos.

O preço é armazenado internamente como número inteiro de ticks para evitar problemas de precisão decimal.

### 3. Isola um único candle

Depois de selecionar um candle, é possível observar:

- todos os negócios que pertencem a ele;
- trajetória intrabar;
- candle sendo formado progressivamente;
- Times & Trades;
- volume por preço;
- agressão acumulada, quando disponível;
- comprador/vendedor, quando a fonte fornece esses campos.

### 4. Replay negócio a negócio

O candle pode ser reproduzido:

- em ritmo uniforme, para estudar apenas a sequência;
- respeitando os intervalos reais entre timestamps;
- com diferentes multiplicadores de velocidade.

### 5. DNA do candle

O programa calcula métricas como:

- amplitude;
- distância total percorrida;
- eficiência direcional;
- corpo/range;
- localização do fechamento;
- ordem entre máxima e mínima;
- tempo até os extremos;
- revisitas a preços;
- reversões;
- VWAP intrabar;
- preço de maior volume;
- drawdown/drawup;
- intervalo entre negócios;
- volume/agressão por região do candle.

Veja `docs/METRICAS-DNA.md`.

### 6. Reconciliação com uma referência independente

É possível importar um segundo CSV contendo candles OHLC e confrontá-lo com os candles reconstruídos a partir dos trades.

Os resultados são classificados como:

- `EXACT`;
- `OHLC_MATCH`;
- `MISMATCH`;
- `NO_DATA`.

Quando há divergência de preço, o sistema informa a diferença em ticks.

### 7. Biblioteca histórica e qualidade dos pregões

Cada importação fica registrada com sua origem. O software também mede cobertura da sessão e tenta separar:

- sessões completas;
- sessões provavelmente completas;
- sessões parciais;
- sessões com lacunas;
- sessões cuja grade ainda não é conhecida.

Sessões de baixa qualidade ficam fora das análises comparativas por padrão.

Veja `docs/QUALIDADE-PREGAO.md`.

### 8. Busca de candles semelhantes

A aplicação possui dois rankings independentes:

**Semelhança visual** compara o desenho final do candle.

**Semelhança pelo DNA** compara características da dinâmica intrabar.

Isso permite encontrar casos em que dois candles parecem quase iguais, mas foram produzidos por trajetórias muito diferentes.

### 9. Famílias de trajetória

A v0.8 introduziu duas formas complementares de estudar a trajetória:

- famílias interpretáveis baseadas em regras;
- clusters empíricos descobertos pelo próprio histórico.

Entre as famílias atualmente reconhecidas estão impulso direto, varredura e reversão, continuação após pullback, V-shaped, V invertido, dupla excursão e range oscilatório.

O clustering é determinístico e implementado em Python puro.

Veja `docs/TRAJECTORY-FAMILIES.md`.

### 10. Estabilidade e transições — v0.9

A v0.9 deixa de olhar apenas para candles isolados e começa a estudar sua sequência temporal.

O programa agora mede:

- em quantos pregões determinada família apareceu;
- quão concentrada ou distribuída ela está na biblioteca;
- consistência entre sessões;
- distribuição por horário, volatilidade e regime;
- transições `família A → família B`;
- frequência condicional histórica dessas transições;
- sequências de três candles;
- candle anterior, atual e seguinte ao candle selecionado.

Transições só são contadas entre candles realmente consecutivos do mesmo pregão. Uma lacuna ou troca de sessão nunca cria uma transição artificial.

Veja `docs/ESTABILIDADE-TRANSICOES.md`.

### 11. Validação empírica — v0.10

A v0.10 foi validada com um recorte real do WINV26 de 07/10/2026 e o CSV de 1 minuto do mesmo pregão.

Nos 10 candles completamente cobertos pelo recorte (14:40–14:49), abertura, máxima, mínima, fechamento e quantidade coincidiram em **10/10 candles** com a referência exportada pelo Profit. O candle de fronteira das 14:50 foi corretamente excluído por estar incompleto no arquivo de Trades.

A versão também reconhece que, no CSV formatado de 1 minuto do Profit, `Volume` é financeiro e `Quantidade` é o total negociado em contratos.

Veja `docs/VALIDACAO-EMPIRICA-V010.md`.

### 12. Ingestão massiva e validação de pregão completo — v0.11

A v0.11 permite processar arquivos de Trades com centenas de MB sem carregar todos os negócios simultaneamente em memória.

A ingestão:

- calcula SHA-256 do arquivo;
- detecta a ordem invertida do Profit;
- lê o CSV em blocos;
- confirma cada bloco em uma transação DuckDB;
- registra o número da linha e o hash da fonte;
- preserva linhas textualmente idênticas;
- permite retomar uma importação interrompida;
- impede a segunda importação do mesmo arquivo;
- reconstrói candles diretamente em SQL;
- exporta Parquet por contrato/pregão;
- gera relatório HTML e JSON da reconciliação.

Para usuários comuns, basta dar dois cliques em:

`validar-pregao-completo.bat`

Veja `docs/TUTORIAL-VALIDACAO-PREGAO-COMPLETO.md`.

### 13. Visão geral → recorte seletivo → microestrutura — v0.12

A v0.12 muda o fluxo recomendado para evitar armazenar pregões inteiros de Tick by Tick quando o usuário deseja investigar apenas alguns candles.

O fluxo padrão passa a ser:

```text
CSV leve de candles de 1 ou 2 minutos
        ↓
gráfico do pregão inteiro
        ↓
seleção visual de um intervalo
        ↓
CSV grande de Trades permanece no disco original
        ↓
extração streaming somente do intervalo escolhido
        ↓
pequeno recorte em data/slices
        ↓
replay + DNA + volume por preço + pesquisa
```

O usuário seleciona o trecho diretamente no gráfico diário arrastando o mouse. Depois cola o caminho do CSV grande do Profit. O Candle Lab percorre esse arquivo sem copiá-lo integralmente para sua biblioteca.

O intervalo é tratado como `[início, fim)`, evitando incluir por engano negócios do candle seguinte.

A ingestão integral da v0.11 continua disponível para auditorias específicas, mas deixou de ser a opção recomendada para o uso cotidiano.

Veja `docs/TUTORIAL-FLUXO-SELETIVO.md`.

### 14. Índice temporal: candle → linhas → bytes — v0.13

A v0.13 acrescenta um índice leve do CSV Tick by Tick original. O arquivo grande é lido integralmente uma única vez e o Candle Lab registra, minuto a minuto:

- primeira e última linha física;
- offsets inicial e final de byte;
- quantidade real de negócios;
- primeiro e último timestamp;
- ordem física da fonte.

A regra é sempre:

`candle_start <= timestamp < candle_end`

Não são usadas médias de negócios por minuto.

Depois que o índice existe, uma nova seleção no gráfico é convertida imediatamente em linhas e bytes. A interface mostra, candle a candle, o intervalo físico de linhas e as linhas correspondentes à abertura e ao fechamento cronológicos.

Em arquivos descendentes do Profit, a abertura cronológica normalmente está em uma linha de número maior que o fechamento.

O recorte usa os offsets do índice para executar `seek` diretamente na região necessária do arquivo, em vez de reler centenas de MB anteriores.

Veja `docs/INDICE-TEMPORAL-LINHAS.md` e `docs/TUTORIAL-LOCALIZAR-LINHAS.md`.

### 15. Seleção precisa do intervalo — v0.14

A v0.14 elimina a dependência de acertar exatamente o minuto com o mouse no gráfico diário.

A seleção pode ser feita de três maneiras:

- clicar e arrastar sobre os candles;
- arrastar os marcadores verticais **INÍCIO** e **FIM** depois que a seleção existe;
- digitar diretamente os horários, por exemplo `14:40` e `14:50`.

O gráfico também ganhou:

- zoom horizontal em até 12 níveis;
- botões para mover a janela visível para a esquerda/direita;
- comando **Mostrar dia inteiro**;
- comando **Zoom na seleção**;
- `Ctrl + roda do mouse` para zoom;
- mais marcações de horário no eixo X à medida que o zoom aumenta.

A seleção continua vinculada aos candles reais do CSV OHLC, e o índice temporal v0.13 continua convertendo os limites selecionados em linhas e offsets de byte exatos do CSV Tick by Tick.

Veja `docs/TUTORIAL-INSTALACAO-E-USO-WINDOWS.md`.

### 16. Caminhos contrafactuais

O programa também pode criar uma trajetória diferente que preserve o mesmo OHLC.

Essa função é sempre marcada como **SIMULAÇÃO CONTRAFACTUAL**. Ela serve para mostrar que o mesmo candle final pode ser alcançado por caminhos distintos; não representa eventos que ocorreram no mercado.

---

# Como executar no Windows — modo simples

Esta é a forma recomendada para quem não costuma usar terminal.

## Etapa 1 — instalar o Python

O computador precisa ter **Python 3.11 ou mais recente**.

Se ainda não tiver Python:

1. acesse <https://www.python.org/downloads/>;
2. baixe o instalador para Windows;
3. durante a instalação, marque a opção **Add Python to PATH** quando ela aparecer;
4. conclua a instalação.

O Candle Lab instala suas próprias bibliotecas em uma pasta isolada chamada `.venv`; isso evita misturar as dependências do projeto com outros programas Python do computador.

## Etapa 2 — baixar o projeto

Na página deste repositório no GitHub:

1. clique no botão verde **Code**;
2. escolha **Download ZIP**;
3. salve o arquivo;
4. clique com o botão direito no ZIP e escolha **Extrair tudo**;
5. abra a pasta extraída.

Também é possível usar Git, mas isso não é necessário para um usuário comum.

## Etapa 3 — iniciar o Candle Lab

Dentro da pasta do projeto, dê dois cliques em:

`iniciar.bat`

Na primeira execução o iniciador:

1. cria o ambiente `.venv`;
2. instala as dependências do Candle Lab;
3. inicia o servidor local;
4. abre a interface no navegador.

O endereço padrão é:

`http://127.0.0.1:8765`

O programa é executado **no próprio computador**. Esse endereço não é um site público na internet: `127.0.0.1` significa a própria máquina.

Nas execuções seguintes, basta usar `iniciar.bat` novamente. O ambiente já criado é reutilizado.

## Etapa 4 — testar sem possuir dados reais

Na tela inicial, clique em **Carregar amostra**.

A demonstração é gerada deterministicamente pelo próprio programa, usa o símbolo reservado `WINLAB06` e contém:

- 2.880 negócios sintéticos;
- 72 candles de 1 minuto;
- 6 pregões artificiais;
- diferentes trajetórias, regimes e níveis de volatilidade.

Esses registros **não são dados reais de mercado**. Eles existem para testar todas as funcionalidades com segurança e não exigem que um CSV sintético grande seja armazenado no repositório.

Depois de carregar a amostra:

1. selecione `WINLAB06`;
2. escolha um pregão;
3. mantenha o timeframe de 1 minuto;
4. clique em um candle;
5. use **Reproduzir**;
6. observe Times & Trades, trajetória, DNA e volume por preço;
7. execute **Pesquisar biblioteca**;
8. execute **Descobrir famílias**;
9. execute **Analisar estabilidade e transições**.

---

# Como usar seus próprios dados — fluxo recomendado

A v0.12 separa a **visão geral do dia** da **microestrutura detalhada**.

1. Exporte do Profit o gráfico do dia em candles de 1 ou 2 minutos.
2. Importe esse CSV na área **Importar gráfico diário**.
3. No gráfico completo, arraste o mouse sobre os candles que deseja estudar.
4. Mantenha o CSV grande de Trades no local original do seu computador.
5. Use **Copiar como caminho** no Windows e cole esse caminho no Candle Lab.
6. Clique em **Preparar índice e localizar**. Na primeira utilização, aguarde a indexação do arquivo; nas seguintes o índice será reutilizado.
7. Confira a tabela de linhas físicas e abertura/fechamento de cada candle.
8. Clique em **Recortar e importar intervalo localizado**.
9. Abra os candles do recorte na Biblioteca de microestrutura.

O Candle Lab gera apenas um pequeno arquivo em `data/slices`. Você pode apagá-lo depois e recriá-lo a qualquer momento a partir do CSV original.

A importação integral de um pregão continua disponível como ferramenta avançada, mas não é necessária para a análise normal.

## Exemplo com WIN

Ao importar um arquivo do WIN, normalmente será necessário informar:

- contrato real, por exemplo `WINV26`, caso o CSV não possua a coluna `Ativo`;
- tick de preço: `5`.

## Exemplo com WDO

Em geral:

- contrato real, por exemplo `WDOV26`;
- tick de preço: `0,5`.

Confirme sempre as especificações vigentes do contrato e a semântica dos campos da sua fonte.

### Por que armazenar o contrato real?

Prefira `WINV26`, `WINZ26`, `WDOV26` etc. a um símbolo contínuo genérico como `WINFUT`.

Isso evita misturar vencimentos diferentes sem uma regra explícita de rollover.

---

# Onde os dados ficam

Por padrão:

- banco local: `data/candle_lab.duckdb`;
- índices temporais reutilizáveis: `data/indexes/*.cidx.json`;
- recortes seletivos: `data/slices/*.csv`;
- Parquet de auditorias integrais, quando usados: `data/parquet/<CONTRATO>/<DATA>.parquet`;
- relatórios: `data/reports`.

O CSV grande original de Trades pode permanecer fora da pasta do projeto.

Os CSVs importados **não são modificados**.

Esses arquivos locais não são versionados no GitHub por causa do `.gitignore`.

---

# Forma alternativa: iniciar pelo PowerShell

Abra a pasta do projeto no Explorador de Arquivos. Clique na barra de endereço, digite `powershell` e pressione Enter.

Depois execute:

```powershell
.\iniciar.ps1
```

Se o Windows bloquear scripts PowerShell por política local, use preferencialmente `iniciar.bat`, que não depende da política de execução de `.ps1`.

---

# Instalação manual para usuários avançados

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
candle-lab serve
```

Depois abra:

`http://127.0.0.1:8765`

---

# Linha de comando

A interface gráfica é suficiente para o uso normal. Os comandos abaixo são úteis para pesquisa reproduzível e automação.

### Analisar um CSV sem gravar no banco

```powershell
candle-lab analyze sample_data\nelogica_tick_exemplo.csv --tick-size 5 --interval 60 --source profit_csv
```

### Importar trades

```powershell
candle-lab import sample_data\nelogica_tick_exemplo.csv --tick-size 5 --source profit_csv
```

### Reconciliar trades com OHLC de referência

```powershell
candle-lab reconcile sample_data\nelogica_tick_exemplo.csv sample_data\reference_exemplo_1m.csv --symbol WINEXEMPLO --tick-size 5 --interval 60
```

### Criar o índice temporal e localizar linhas

```powershell
candle-lab index-trades "C:\Dados\WINV26_TRADES.csv" --symbol WINV26

candle-lab locate-lines "C:\Dados\WINV26_TRADES.csv" --symbol WINV26 --start "2026-10-07T14:40:00-03:00" --end "2026-10-07T14:50:00-03:00" --interval 60
```

### Gerar um recorte seletivo pela linha de comando

A interface gráfica é o modo recomendado. Para automação:

```powershell
candle-lab slice-trades "C:\Dados\WINV26_TRADES.csv" --symbol WINV26 --start "2026-10-07T14:40:00-03:00" --end "2026-10-07T14:50:00-03:00"
```

### Validação de um pregão completo com arquivo grande — modo avançado

A v0.11 possui um comando que importa em chunks e retoma automaticamente em caso de interrupção:

```powershell
candle-lab bulk-validate WINV26_TRADES.csv WINV26_1MIN.csv --symbol WINV26 --tick-size 5 --interval 60
```

Para quem não usa terminal, execute `validar-pregao-completo.bat`.

### Validação empírica de um recorte real

Esse comando ignora candles de fronteira que não estejam totalmente cobertos pelo arquivo de Trades:

```powershell
candle-lab empirical-validate WINV26_TRADES.csv WINV26_1MIN.csv --symbol WINV26 --tick-size 5 --interval 60
```

### Reavaliar qualidade dos pregões

```powershell
candle-lab quality --symbol WINV26
```

### Pesquisar candles semelhantes

```powershell
candle-lab research --symbol WINV26 --start "2026-10-07T10:00:00-03:00" --interval 60 --same-time --same-volatility --same-context-regime --limit 8
```

### Descobrir famílias intrabar

```powershell
candle-lab trajectory --symbol WINV26 --interval 60
```

### Analisar estabilidade e transições — v0.9

```powershell
candle-lab transitions --symbol WINV26 --interval 60
```

Para incluir a sequência ao redor de um candle específico:

```powershell
candle-lab transitions --symbol WINV26 --interval 60 --start "2026-10-07T10:32:00-03:00"
```

As saídas analíticas da CLI são JSON, facilitando auditoria e estudos posteriores.

---

# Testes do projeto

Com o ambiente instalado:

```powershell
python -m unittest discover -s tests -v
```

O workflow em `.github/workflows/tests.yml` executa a suíte no GitHub Actions em Windows e Linux, com versões suportadas de Python.

---

# Estrutura do repositório

```text
candle-lab/
├─ src/candle_lab/
│  ├─ candles.py          # agregação OHLC
│  ├─ importers.py        # leitura/normalização de CSV
│  ├─ metrics.py          # DNA do candle
│  ├─ quality.py          # qualidade/cobertura de pregões
│  ├─ reconciliation.py   # comparação com OHLC externo
│  ├─ research.py         # índice e similaridade multi-pregão
│  ├─ trajectory.py       # famílias e clustering intrabar
│  ├─ transitions.py      # estabilidade e sequências v0.9
│  ├─ storage.py          # DuckDB/Parquet
│  └─ web/                # aplicação local
├─ docs/                  # documentação metodológica
├─ sample_data/           # dados sintéticos e exemplos
├─ scripts/               # geração reproduzível das amostras
├─ tests/                 # testes automatizados
├─ iniciar.bat            # inicializador simples do Windows
├─ iniciar.ps1            # inicializador PowerShell
└─ pyproject.toml         # dependências e configuração do pacote
```

---

# Documentação técnica

Para aprofundar o projeto:

- `docs/ESPECIFICACAO-MVP.md` — escopo e evolução funcional;
- `docs/ARQUITETURA.md` — arquitetura do sistema;
- `docs/MODELO-DE-DADOS.md` — organização dos dados;
- `docs/IMPORTACAO-NELOGICA.md` — regras do importador;
- `docs/METRICAS-DNA.md` — definições das métricas;
- `docs/VALIDACAO-RECONCILIACAO.md` — validação com referência externa;
- `docs/BIBLIOTECA-HISTORICA.md` — proveniência e biblioteca;
- `docs/PESQUISA-COMPARATIVA.md` — similaridade multi-pregão;
- `docs/QUALIDADE-PREGAO.md` — cobertura e elegibilidade;
- `docs/TRAJECTORY-FAMILIES.md` — famílias e clustering;
- `docs/ESTABILIDADE-TRANSICOES.md` — estabilidade e sequências v0.9;
- `docs/VALIDACAO-V08.md` — validação funcional da camada de trajetórias;
- `docs/VALIDACAO-EMPIRICA-V010.md` — primeira validação com dados reais do WINV26;
- `docs/TUTORIAL-INSTALACAO-E-USO-WINDOWS.md` — instalação e uso completos para usuários de Windows;
- `docs/TUTORIAL-FLUXO-SELETIVO.md` — fluxo recomendado: gráfico diário, seleção e recorte Tick;
- `docs/INDICE-TEMPORAL-LINHAS.md` — regra exata candle → linhas → bytes;
- `docs/TUTORIAL-LOCALIZAR-LINHAS.md` — tutorial para preparar o índice e localizar candles;
- `docs/VALIDACAO-INDICE-TEMPORAL-V013.md` — validação do mapa de linhas/bytes com o recorte real do WINV26;
- `docs/TUTORIAL-VALIDACAO-PREGAO-COMPLETO.md` — auditoria opcional do pregão inteiro.

---

# Limitações atuais

O projeto ainda está em desenvolvimento. Entre as limitações conhecidas:

- o acesso a um histórico amplo e realmente completo de microestrutura depende da fonte de dados do usuário;
- a reconstrução de livro de ofertas MBO/MBP ainda é uma etapa futura;
- a grade de negociação possui simplificações e ainda não identifica automaticamente todas as exceções históricas, feriados e vencimentos especiais;
- clusters dependem do dataset e da versão do modelo;
- frequências de transição descrevem a biblioteca atual e não devem ser interpretadas como previsão;
- dados sintéticos demonstram funcionamento do pipeline, não validam comportamento real do WIN/WDO;
- a v0.10 foi validada em um recorte real de 10 minutos do WINV26;
- a v0.11 mantém ingestão integral em chunks como ferramenta de auditoria;
- a v0.12 passa a recomendar recortes seletivos e não exige armazenar um pregão Tick inteiro;
- a extração seletiva e o índice temporal foram desenhados para o layout real sem cabeçalho do Profit já validado pelo projeto;
- o índice v0.13 trabalha com buckets-base de 1 minuto e exige fronteiras alinhadas ao minuto para que o mapa de linhas seja exato;
- a v0.14 melhora a precisão da seleção na interface, mas não altera a granularidade física do índice M1.

---

# Filosofia de pesquisa

O Candle Lab procura preservar algumas regras metodológicas desde o início:

1. **não apresentar simulação como histórico real**;
2. **não misturar contratos diferentes silenciosamente**;
3. **registrar a origem dos dados**;
4. **medir qualidade antes de comparar pregões**;
5. **evitar look-ahead em métricas que descrevem o contexto no instante do candle**;
6. **manter algoritmos explicáveis e versionados**;
7. **distinguir descrição estatística de previsão**.

A pergunta que orienta o projeto continua sendo:

> **Quantas estruturas internas diferentes podem existir por trás de candles que parecem iguais?**
