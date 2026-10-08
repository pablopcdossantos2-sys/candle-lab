# Prompts para criação de indicadores Profit Pro / NTSL

Use este arquivo como pacote de especificações para uma IA responsável por criar indicadores derivados do Candle Lab para o Profit Pro da Nelogica.

Data de referência das capacidades consultadas: 2026-10-08.

---

# PROMPT BASE — obrigatório em todas as implementações

Você é um desenvolvedor especialista em NTSL, Profit Pro e leitura de fluxo.

Seu objetivo é criar um **indicador**, e não uma automação de ordens, inspirado nas hipóteses pesquisadas pelo projeto Candle Lab.

## Regras obrigatórias

1. Antes de escrever código, consulte o Manual NTSL oficial atualizado da Nelogica.
2. Não invente funções, propriedades ou assinaturas.
3. Informe quais funções oficiais foram usadas.
4. Priorize, quando adequadas:
   - `AgressionVolBuy()`;
   - `AgressionVolSell()`;
   - `AgressionVolBalance()`;
   - outras funções oficiais de agressão confirmadas no manual.
5. A documentação atual informa que `AgressionVolBuy()` e `AgressionVolSell()` estão disponíveis em Profit Pro, Profit Ultra ou módulo Scalper.
6. Não presuma que o Editor NTSL fornece identificação negócio a negócio de corretora/agente. Se precisar dessa informação, verifique primeiro o manual oficial. Se não existir função documentada, declare a limitação.
7. Não confunda volume de agressão agregado por candle com sequência Tick by Tick do Candle Lab.
8. Se a regra original depende de sequência intrabar que NTSL não consegue reconstruir historicamente, implemente uma aproximação claramente rotulada.
9. Não use dados futuros.
10. Não reposicione retrospectivamente sinais para um candle anterior depois que informações posteriores chegaram.
11. Todos os limiares importantes devem ser parâmetros configuráveis.
12. Evite divisão por zero.
13. Trate ausência/indisponibilidade de dados.
14. Não chame divergência de preço e agressão de “absorção confirmada”.
15. Não transforme score heurístico em probabilidade.
16. Não crie estratégia de compra/venda, ordens ou automação, salvo pedido explícito posterior.
17. Produza código compatível com o Editor de Estratégias/Indicadores do Profit conforme a documentação vigente.
18. Antes de finalizar, revise o código para:
    - nomes de funções válidos;
    - sintaxe NTSL;
    - inicialização de variáveis;
    - tipos;
    - comportamento no primeiro candle;
    - ausência de look-ahead;
    - plots suficientes e legíveis.

## Entregáveis obrigatórios

Entregue:

1. código NTSL completo;
2. explicação do algoritmo;
3. parâmetros de entrada;
4. funções oficiais utilizadas e referência no manual;
5. significado de cada Plot/PlotN/coloração;
6. critérios de alerta, se alertas forem possíveis na forma solicitada;
7. diferenças entre o indicador e o Candle Lab;
8. limitações históricas/intrabar;
9. roteiro de teste no Profit;
10. exemplos de situações em que deve e não deve sinalizar;
11. instruções de instalação no Editor de Estratégias;
12. nenhum código de execução de ordens.

---

# PROFIT-CL-01 — Alinhamento preço × agressão

Use o PROMPT BASE e crie o indicador **Candle Lab — Alinhamento Preço × Agressão**.

## Objetivo

Classificar a relação entre:

- direção do corpo;
- agressão de compra;
- agressão de venda;
- saldo de agressão;
- localização do fechamento no range.

## Dados

Verifique no manual atual e use preferencialmente:

```text
AgressionVolBuy()
AgressionVolSell()
AgressionVolBalance()
```

Não calcule uma função manual se a função oficial adequada já existir, a menos que precise validar consistência.

## Cálculos

```text
buy = agressão compradora
sell = agressão vendedora
directed = buy + sell
delta = buy - sell

deltaNormalized =
directed > 0
? delta / directed
: 0
```

Corpo:

```text
close > open  → alta
close < open  → baixa
```

Close location:

```text
(close-low)/(high-low)
```

com proteção de range zero.

## Estados

- ALINHAMENTO_COMPRA;
- ALINHAMENTO_VENDA;
- DIVERGENCIA_ALTA_DELTA_VENDEDOR;
- DIVERGENCIA_BAIXA_DELTA_COMPRADOR;
- EQUILIBRADO;
- SEM_DADO.

## Visual

- Plot do delta normalizado;
- linha zero;
- cores por estado;
- opção de PaintBar apenas se tecnicamente apropriada;
- texto/painel somente se suportado de forma limpa.

## Teste

Validar em WIN e WDO, incluindo candle sem range e agressão zero.

---

# PROFIT-CL-02 — Divergência preço × agressão / candidato a absorção

Use o PROMPT BASE e crie **Candle Lab — Divergência Preço × Agressão**.

## Tese

### Alta divergente

```text
Close > Open
AgressionVolBalance < 0
```

### Baixa divergente

```text
Close < Open
AgressionVolBalance > 0
```

## Filtros configuráveis

- delta normalizado mínimo;
- agressão total mínima;
- corpo/range mínimo;
- close location;
- período de intensidade relativa;
- exigir candle fechado.

## Intensidade

Compare o volume agressor atual com N candles anteriores.

Ofereça, se possível:

- razão contra média;
- z-score;
- média + múltiplos de desvio;
- percentil apenas se puder ser implementado com clareza e eficiência.

## Saída

Plot/cores/marcadores para:

- divergência altista;
- divergência baixista.

Texto conceitual:

> Candidato a absorção / incapacidade do agressor.

Nunca:

> Absorção confirmada.

---

# PROFIT-CL-03 — Intensidade relativa da agressão

Use o PROMPT BASE e crie **Candle Lab — Intensidade da Agressão**.

## Objetivo

Classificar o esforço agressor atual em relação ao histórico recente.

Dados sugeridos:

```text
aggressionTotal = AgressionVolBuy() + AgressionVolSell()
```

## Classes

- BAIXA;
- MODERADA;
- ALTA;
- EXTREMA.

## Inputs

- período;
- método de normalização;
- limiares;
- usar saldo absoluto ou volume total;
- plotar compra e venda separadamente.

## Métodos

Modo simples:

```text
ratio = aggressionTotal / Media(periodo, aggressionTotal)
```

Modo estatístico:

```text
z = (aggressionTotal - media) / desvio
```

Use somente funções NTSL oficialmente documentadas.

---

# PROFIT-CL-04 — Rejeição de extremo com agressão

Use o PROMPT BASE e crie **Candle Lab — Rejeição de Extremo com Agressão**.

## Objetivo

Identificar candles em que:

- houve agressão elevada;
- o preço testou extremo;
- o fechamento não permaneceu no extremo.

## Rejeição superior

Combinar:

- sombra superior / range;
- agressão compradora elevada;
- delta comprador ou intensidade compradora;
- fechamento afastado da máxima.

## Rejeição inferior

Condições espelhadas.

## Limitação

O Candle Lab mede agressão em cada nível de preço.

Se o NTSL padrão disponível não expuser agressão por nível dentro do candle, declare que esta versão Profit é **bar-level**.

Não invente função de footprint por preço.

## Score

Criar score transparente de 0–100 sem chamá-lo de probabilidade.

Componentes configuráveis:

- sombra;
- intensidade;
- delta;
- close location.

---

# PROFIT-CL-05 — Exaustão de onda agressora

Use o PROMPT BASE e crie **Candle Lab — Exaustão de Agressão**.

## Objetivo

Criar uma versão NTSL inspirada no detector causal v0.16.

## Observação crítica

O detector Candle Lab original usa negócios Tick by Tick.

Primeiro verifique se o ambiente NTSL permite, de modo histórico e documentado, acompanhar a evolução intrabar com granularidade equivalente.

Se não permitir, implemente uma **aproximação entre barras** ou baseada em timeframe menor.

## Máquina de estados

- NEUTRO;
- ONDA_BUY;
- ONDA_SELL;
- EXAUSTAO_BUY_CONFIRMADA;
- EXAUSTAO_SELL_CONFIRMADA.

## Pressão

Uma possível medida:

```text
dominance =
(buy - sell) / (buy + sell)
```

Durante a onda:

- registrar maior buy/sell;
- registrar maior dominância;
- calcular pressão atual / pico;
- confirmar término somente após M candles/sub-barras.

## Inputs

- activationDominance;
- releaseDominance;
- decayRatio;
- activationConfirmations;
- releaseConfirmations;
- período/timeframe de trabalho.

## Causalidade

O sinal de exaustão deve aparecer no candle que confirmou a condição, não no pico retroativo.

---

# PROFIT-CL-06 — Troca de controle

Use o PROMPT BASE e implemente **Candle Lab — Troca de Controle da Agressão**.

## Objetivo

Separar:

```text
perda de BUY
```

de

```text
SELL realmente assumiu controle
```

e o inverso.

## Estados

- BUY_DOMINANTE;
- NEUTRALIZACAO;
- SELL_DOMINANTE;
- TROCA_BUY_PARA_SELL;
- TROCA_SELL_PARA_BUY.

## Regra

Exigir:

- onda anterior existente;
- dominância oposta acima de limiar;
- volume mínimo;
- M confirmações.

## Visual

- Plot da dominância;
- níveis horizontais de ativação/troca;
- marcador de handoff;
- PaintBar opcional.

## Testes

1. BUY forte → equilíbrio → SELL forte;
2. BUY forte → equilíbrio → BUY volta;
3. um único candle SELL após longa BUY — não sinalizar se confirmação M > 1.

---

# PROFIT-CL-07 — Persistência da agressão no fechamento

Use o PROMPT BASE e crie **Candle Lab — Persistência da Agressão**.

## Objetivo

Distinguir candles que fecham com pressão ainda ativa daqueles em que a pressão já perdeu força.

## BUY persistente

Possíveis condições:

- dominância BUY ainda acima do limiar;
- pressão atual / pico >= limiar;
- fechamento próximo da máxima;
- nenhuma condição de término confirmada.

## SELL equivalente

## Saída

- Plot de score de persistência;
- estado BUY/SELL/NEUTRO;
- marcador no fechamento do candle.

## Validação

O código deve facilitar comparação futura com continuação em:

- 1 candle;
- 3 candles;
- 5 candles.

---

# PROFIT-CL-08 — Eficiência esforço × resultado

Use o PROMPT BASE e crie **Candle Lab — Eficiência da Agressão**.

## Pergunta

> Quanto deslocamento de preço foi obtido para o esforço agressor?

## Dados

- `AgressionVolBuy()`;
- `AgressionVolSell()`;
- `AgressionVolBalance()`;
- corpo;
- range;
- ATR opcional.

## Métricas

Criar medidas robustas.

Evitar:

```text
body / delta
```

sem proteção, porque delta próximo de zero explode o resultado.

Possível construção:

```text
deltaNorm = abs(delta)/(buy+sell)
resultNorm = abs(close-open)/max(range, MinPriceIncrement)
```

e depois classificar combinações.

## Estados

- COMPRA_EFICIENTE;
- VENDA_EFICIENTE;
- MUITO_ESFORCO_POUCO_RESULTADO_COMPRA;
- MUITO_ESFORCO_POUCO_RESULTADO_VENDA;
- EQUILIBRADO.

Use nomenclatura “pouco resultado” em vez de “absorção comprovada”.

---

# PROFIT-CL-09 — Estado composto de microestrutura

Use o PROMPT BASE e crie **Candle Lab — Estado da Microestrutura** somente depois que os módulos simples tiverem sido testados.

## Estados

- BUY_IMPULSE;
- SELL_IMPULSE;
- BUY_EXHAUSTION;
- SELL_EXHAUSTION;
- BUY_ABSORPTION_CANDIDATE;
- SELL_ABSORPTION_CANDIDATE;
- CONTROL_HANDOFF_BUY_TO_SELL;
- CONTROL_HANDOFF_SELL_TO_BUY;
- BALANCED_DISPUTE;
- LOW_INFORMATION.

## Requisitos

- regras mutuamente priorizadas;
- mostrar qual condição gerou o estado;
- score auditável;
- parâmetros externos;
- sem pesos escondidos;
- sem probabilidades falsas.

---

# PROFIT-CL-10 — Indicador calibrado pela validação histórica

NÃO implemente até receber relatório de validação histórica do Candle Lab.

Quando receber:

1. ler N, baseline, lift, IC 95% e horizonte;
2. eliminar amostras insuficientes;
3. verificar se a regra é tecnicamente reproduzível no NTSL;
4. não substituir variável ausente por proxy sem avisar;
5. preservar versão dos parâmetros;
6. criar modo diagnóstico;
7. permitir ligar/desligar cada componente;
8. não usar resultado in-sample como prova de vantagem;
9. solicitar teste fora da amostra;
10. não criar ordens automáticas.

---

# PROFIT-CL-11 — Concentração por agente

ANTES de escrever qualquer código:

1. consulte o Manual NTSL atual;
2. procure funções oficiais que exponham identificação de comprador/vendedor/agente/corretora por negócio;
3. verifique se estão acessíveis ao Editor de Estratégias;
4. se não encontrar função documentada, **não implemente uma falsa aproximação com AgressionVolBuy/Sell**.

Nesse caso, entregue apenas um relatório dizendo:

- por que o indicador não pode ser reproduzido fielmente em NTSL padrão;
- quais dados faltam;
- se uma bridge externa seria necessária;
- como o Candle Lab calcula essa métrica a partir do CSV.

---

# Fontes oficiais que a IA deve consultar novamente antes de codificar

Manual NTSL:

https://downloadserver-cdn.nelogica.com.br/content/profit/manual_ntsl/ManualNTSL.pdf

Página oficial de documentação NTSL:

https://ajuda.nelogica.com.br/hc/pt-br/articles/360046443212-Documenta%C3%A7%C3%A3o-NTSL-Compilado-de-fun%C3%A7%C3%B5es-e-instru%C3%A7%C3%B5es-de-usabilidade

Times & Trades:

https://ajuda.nelogica.com.br/hc/pt-br/articles/360054569632-Times-Trades

A documentação pode mudar. A IA deve verificar as funções antes de produzir o código final.


---

# PROFIT-CL-12 — Painel explicativo do candle

Use o PROMPT BASE e crie **Candle Lab — Painel de Microestrutura**.

## Objetivo

Criar um painel/indicador compacto com as variáveis de agressão que forem oficialmente acessíveis ao NTSL.

Mostrar, quando documentado e disponível:

- agressão compradora;
- agressão vendedora;
- saldo;
- delta normalizado;
- intensidade relativa;
- relação preço × agressão;
- divergência;
- estado de onda aproximado;
- eficiência esforço × resultado;
- hipótese dominante;
- qualidade/disponibilidade do dado.

## Regra de fidelidade

O Candle Lab possui sequência Tick by Tick e, em alguns arquivos, identificação de agentes.

O painel NTSL não deve afirmar que reproduz essas dimensões se elas não estiverem expostas ao script.

Sempre incluir uma linha de fonte/metodologia, por exemplo:

```text
Fonte: agressão agregada NTSL
Granularidade: candle
Modelo de onda: aproximação entre barras
```

## Estados sugeridos

- ALINHADO_COMPRA;
- ALINHADO_VENDA;
- DIVERGENCIA_ALTA;
- DIVERGENCIA_BAIXA;
- BUY_DOMINANTE;
- SELL_DOMINANTE;
- BUY_EXAURIDA;
- SELL_EXAURIDA;
- TROCA_CONTROLE;
- BAIXA_INFORMACAO.

## Arquitetura

Reutilize as funções dos indicadores CL-01/02/03/05/06/08 quando possível.

Não copie regras em vários lugares.

## Visual

Use apenas recursos NTSL oficialmente documentados.

Priorize legibilidade:

- Plot/PlotN para séries;
- PaintBar apenas como opção;
- PlotText apenas se não poluir o gráfico;
- parâmetros para ligar/desligar componentes.

## Alertas

Se o ambiente permitir alertas na forma proposta, os eventos precisam ser confirmados sem look-ahead.

Não gerar recomendações de compra/venda.

---

# PROMPT DE INTEGRAÇÃO COM RELATÓRIO HISTÓRICO DO CANDLE LAB

Use este prompt quando o usuário fornecer o JSON baixado em **Validação histórica das hipóteses**.

## Objetivo

Transformar resultados do Candle Lab em uma especificação NTSL somente quando:

- houver amostra razoável;
- o desfecho externo for claramente definido;
- a variável original puder ser reproduzida ou aproximada de forma honesta no Profit.

## Procedimento

1. leia o relatório inteiro;
2. apresente tabela com hipótese, horizonte, N, taxa, baseline, lift e IC 95%;
3. identifique o status da amostra;
4. descarte resultados `AMOSTRA_INSUFICIENTE` como candidatos operacionais;
5. consulte o Manual NTSL atual para cada variável necessária;
6. classifique cada variável como:
   - NATIVA;
   - PROXY;
   - INDISPONIVEL;
7. não substitua variável INDISPONIVEL silenciosamente;
8. produza primeiro a especificação do indicador;
9. registre a versão do JSON e dos parâmetros;
10. deixe uma janela fora da amostra para teste posterior.

Se a hipótese depender de agente/corretora individual e o NTSL atual não expuser essa identidade, conclua que a reprodução fiel é inviável em NTSL padrão.
