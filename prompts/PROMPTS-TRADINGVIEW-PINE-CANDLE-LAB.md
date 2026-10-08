# Prompts para criação de indicadores TradingView / Pine Script

Use este arquivo como pacote de especificações para uma IA responsável por implementar indicadores derivados do Candle Lab.

Data de referência das capacidades consultadas: 2026-10-08.

---

# PROMPT BASE — obrigatório em todas as implementações

Você é um desenvolvedor especialista em Pine Script e microestrutura de mercado.

Seu objetivo é criar um indicador para TradingView inspirado nas hipóteses pesquisadas pelo projeto Candle Lab.

## Regras obrigatórias

1. Antes de escrever código, consulte a documentação oficial atual do Pine Script.
2. Use a versão mais recente estável disponível. Na data desta especificação, a referência é Pine Script v6.
3. Não invente funções.
4. Quando usar volume footprint, prefira as APIs oficiais `request.footprint()`, `footprint.*()` e `volume_row.*()`, se disponíveis para o usuário.
5. Lembre que o footprint do TradingView classifica buy/sell a partir de dados intrabar da própria plataforma. Não o descreva como semanticamente idêntico ao agressor real do Times & Trades do Profit sem validação.
6. Se usar `request.security_lower_tf()`, explique limites de intrabars, diferenças histórico/realtime e possibilidade de repaint.
7. Não use `lookahead_on` de forma que introduza informação futura.
8. Um alerta só pode disparar depois que todas as condições necessárias estiverem confirmadas.
9. Não implemente ordens, strategy.entry, strategy.exit ou automação. A tarefa é criar um **indicador**, salvo instrução explícita em contrário.
10. Todos os limiares importantes devem ser inputs configuráveis.
11. O indicador precisa tratar `na` e ausência de footprint sem quebrar.
12. Sempre informar quando uma parte do modelo Candle Lab foi substituída por proxy.
13. Não usar o termo “absorção confirmada”. Usar “candidato a absorção”, “divergência preço × delta” ou equivalente.
14. O código deve ser legível, modular e comentado.
15. Evite repaint quando tecnicamente possível. Se alguma métrica puder repintar, declare isso na documentação entregue.
16. Não otimizar parâmetros usando o mesmo trecho histórico usado para demonstrar o indicador.
17. Não transformar score heurístico em probabilidade.
18. Use `syminfo.mintick` para trabalhar com ticks quando apropriado.
19. O indicador deve funcionar com WIN/WDO e também ser genericamente aplicável a outros símbolos quando a fonte de footprint existir.
20. Antes de finalizar, faça uma revisão linha a linha em busca de:
    - look-ahead;
    - arrays vazios;
    - divisão por zero;
    - excesso de labels/boxes;
    - limites de objetos Pine;
    - chamadas `request.*()` redundantes.

## Entregáveis

Entregue:

1. código Pine completo e compilável;
2. explicação da lógica;
3. lista de inputs;
4. significado de plots, cores e marcadores;
5. condições de alerta;
6. diferenças em relação ao Candle Lab;
7. limitações da fonte do TradingView;
8. possíveis causas de repaint;
9. roteiro de teste manual;
10. casos de teste sugeridos;
11. versão do Pine utilizada;
12. links da documentação oficial consultada.

Não finalize enquanto não verificar que todas as funções usadas existem na documentação oficial atual.

---

# TV-CL-01 — Alinhamento preço × delta

Use o PROMPT BASE e implemente o indicador **Candle Lab — Price × Delta Alignment**.

## Objetivo

Classificar cada candle conforme a relação entre:

- direção do corpo;
- buy volume;
- sell volume;
- delta;
- localização do fechamento no range.

## Fonte preferencial

Use `request.footprint()`.

Extraia, quando disponível:

- total buy volume;
- total sell volume;
- delta;
- total volume.

## Cálculos

Calcule:

```text
directedVolume = buyVolume + sellVolume

deltaNormalized =
directedVolume > 0
? delta / directedVolume
: na

bodyDirection =
close > open  -> +1
close < open  -> -1
close == open -> 0

alignment =
sign(deltaNormalized) * bodyDirection
```

Também calcule:

```text
closeLocation = (close - low) / (high - low)
```

com proteção para range zero.

## Estados mínimos

- ALIGNED_BUY;
- ALIGNED_SELL;
- DIVERGENCE_UP_NEGATIVE_DELTA;
- DIVERGENCE_DOWN_POSITIVE_DELTA;
- BALANCED;
- NO_FOOTPRINT.

## Inputs

- mínimo absoluto de delta normalizado;
- cobertura/volume mínimo quando aplicável;
- opção de exigir candle confirmado;
- opção de colorir candles;
- opção de exibir painel;
- opção de alertas.

## Visualização

- histograma do delta normalizado;
- linha zero;
- cores diferentes para alinhamento/divergência;
- label opcional no gráfico;
- painel com buy, sell, delta e estado.

## Alertas

Criar alertcondition para:

- alinhamento comprador confirmado;
- alinhamento vendedor confirmado;
- divergência de alta;
- divergência de baixa.

Não disparar antes da confirmação do candle se o modo confirmado estiver ativo.

---

# TV-CL-02 — Divergência preço × delta / candidato a absorção

Use o PROMPT BASE e implemente **Candle Lab — Price/Delta Divergence**.

## Tese

Procurar:

### Caso A

```text
close > open
delta < 0
```

### Caso B

```text
close < open
delta > 0
```

Esses eventos devem ser descritos como **divergência preço × delta** e não como absorção comprovada.

## Filtros

Inputs configuráveis para:

- |deltaNormalized| mínimo;
- volume total mínimo;
- body/range mínimo;
- close location mínimo/máximo;
- intensidade relativa mínima;
- exigir footprint disponível;
- usar somente candles confirmados.

## Intensidade histórica

Opcionalmente compare `abs(delta)` ou `directedVolume` com os últimos N candles.

Ofereça método:

- percentil aproximado;
- z-score;
- razão contra média;
- razão contra mediana, se viável sem complexidade excessiva.

## Score

Crie score de 0 a 100 usando componentes transparentes.

Exemplo conceitual:

- força da divergência;
- intensidade;
- corpo;
- close location.

Não chame o score de probabilidade.

## Saída

- marcador acima/abaixo do candle;
- score;
- delta;
- texto “Absorption candidate” ou “Price/Delta divergence”;
- alertcondition.

## Testes

Inclua exemplos esperados:

1. alta + delta negativo forte;
2. baixa + delta positivo forte;
3. alta + delta positivo — não sinalizar;
4. delta quase zero — não sinalizar;
5. footprint ausente — estado NO_DATA.

---

# TV-CL-03 — Intensidade relativa da agressão

Use o PROMPT BASE e implemente **Candle Lab — Aggression Intensity**.

## Objetivo

Classificar a atividade agressora relativa do candle em:

- LOW;
- MODERATE;
- HIGH;
- EXTREME.

## Fonte

Use:

```text
directedVolume = buyVolume + sellVolume
```

do footprint.

## Métodos

Ofereça pelo menos dois modos:

### Modo A — razão contra média

```text
ratio = directedVolume / sma(directedVolume, N)
```

### Modo B — z-score

Use média e desvio padrão.

Se implementar percentil, faça de forma computacionalmente segura para Pine.

## Inputs

- período N;
- método;
- limiares;
- filtro de volume;
- exibir fundo;
- exibir histograma;
- alerts para HIGH/EXTREME.

## Requisito

Explique que essa intensidade é entre candles históricos e não é exatamente a mesma classificação por níveis internos usada no Candle Lab.

---

# TV-CL-04 — Rejeição de extremo com footprint

Use o PROMPT BASE e implemente **Candle Lab — Footprint Extreme Rejection**.

## Objetivo

Detectar esforço agressor próximo da máxima/mínima sem permanência correspondente do preço.

## Fonte

Use footprint rows.

Percorra `footprint.rows()` e identifique rows cuja faixa esteja:

- nos X ticks superiores do candle;
- nos X ticks inferiores do candle.

Some:

- buy volume;
- sell volume;
- delta;
- total volume;
- imbalances.

## Rejeição de máxima

Condições configuráveis:

- sombra superior / range >= limiar;
- buy volume elevado nas rows superiores;
- delta positivo ou buy imbalance perto da máxima;
- fechamento afastado da máxima.

## Rejeição de mínima

Condições espelhadas.

## Score

Combinar:

- tamanho relativo da sombra;
- intensidade da agressão no extremo;
- divergência entre agressão e fechamento;
- número de imbalances.

## Saída

- marcador R↑ para rejeição da máxima;
- marcador R↓ para rejeição da mínima;
- score;
- boxes opcionais nas rows relevantes.

## Segurança

Limite quantidade de boxes/labels.

Se footprint row data não estiver disponível, não substitua silenciosamente por volume comum; retorne NO_FOOTPRINT ou use fallback somente se o usuário ativar explicitamente o modo proxy.

---

# TV-CL-05 — Exaustão de onda agressora

Use o PROMPT BASE e implemente **Candle Lab — Aggression Wave Exhaustion**.

## Objetivo

Criar uma aproximação, no TradingView, do detector causal v0.16 do Candle Lab.

## Restrição fundamental

O Candle Lab original usa sequência Tick by Tick.

Pine não deve fingir possuir a mesma sequência se estiver trabalhando com footprints ou barras de timeframe inferior.

Rotule o resultado como:

> LTF/footprint approximation of aggression-wave exhaustion

## Dados

Prioridade:

1. footprint em timeframe inferior solicitado via mecanismos oficiais suportados;
2. séries de delta de sub-barras;
3. fallback para delta por candle somente se explicitamente ativado.

## Máquina de estados

Estados:

- NEUTRAL;
- BUY_WAVE;
- SELL_WAVE;
- BUY_EXHAUSTION_CONFIRMED;
- SELL_EXHAUSTION_CONFIRMED.

## Conceito

Ativar onda após N confirmações de dominância.

Durante onda:

- registrar pico de pressão;
- calcular razão pressão atual / pico;
- medir dominância atual;
- confirmar exaustão após M observações consecutivas.

Inputs:

- janela;
- activationDominance;
- releaseDominance;
- decayRatio;
- activationConfirmations;
- releaseConfirmations.

## Requisito de causalidade

O marcador precisa aparecer apenas quando a confirmação ocorreu.

Não reposicionar o marcador retrospectivamente em um candle anterior.

## Alertas

- BUY exhaustion confirmed;
- SELL exhaustion confirmed.

---

# TV-CL-06 — Troca de controle

Use o PROMPT BASE e implemente **Candle Lab — Aggression Control Handoff**.

## Objetivo

Detectar:

```text
BUY dominance → SELL dominance
SELL dominance → BUY dominance
```

## Modelo

Manter estado anterior de onda.

Confirmar troca apenas quando:

- havia onda ativa;
- dominância oposta cruza limiar;
- cobertura/volume é suficiente;
- condição permanece por M confirmações.

Distinguir:

- NEUTRALIZATION;
- CONTROL_HANDOFF.

Não classificar toda perda de BUY como SELL takeover.

## Visual

- marcador BUY→SELL;
- marcador SELL→BUY;
- cor de fundo opcional;
- painel com dominância anterior e atual.

## Alertas

Somente após confirmação.

---

# TV-CL-07 — Persistência da pressão no fechamento

Use o PROMPT BASE e implemente **Candle Lab — Aggression Persistence at Close**.

## Objetivo

Identificar candles que fecham enquanto o mesmo lado continua dominante, sem término confirmado da onda.

## Exemplos

BUY persistence candidate:

- onda BUY ativa;
- close location alta;
- dominância ainda acima do limiar;
- pressão atual ainda representa fração mínima do pico.

SELL equivalente.

## Saída

- marcador P-BUY;
- marcador P-SELL;
- score de persistência;
- alertcondition.

## Comparação histórica

O indicador deve permitir exportação visual/alerta para que posteriormente seja comparado com:

- continuação em 1 candle;
- 3 candles;
- 5 candles.

---

# TV-CL-08 — Eficiência esforço × resultado

Use o PROMPT BASE e implemente **Candle Lab — Aggression Efficiency**.

## Objetivo

Medir quanto resultado de preço foi obtido para o esforço agressor.

## Variáveis

- buyVolume;
- sellVolume;
- delta;
- range;
- body;
- closeLocation;
- ATR opcional.

## Métricas sugeridas

Evite divisão direta instável por delta pequeno.

Crie versões normalizadas, por exemplo:

```text
effort = abs(delta) / max(directedVolume, eps)

result = abs(close-open) / max(high-low, syminfo.mintick)

efficiency = result / max(effort, eps)
```

Também ofereça uma métrica de “high effort / low result”.

## Estados

- EFFICIENT_BUY;
- EFFICIENT_SELL;
- HIGH_EFFORT_LOW_RESULT_BUY;
- HIGH_EFFORT_LOW_RESULT_SELL;
- BALANCED.

## Objetivo científico

O estado “high effort / low result” é candidato operacional para a ideia de perda de eficiência/absorção, mas não deve ser rotulado como causalidade comprovada.

---

# TV-CL-09 — Estado composto de microestrutura

Use o PROMPT BASE e implemente **Candle Lab — Microstructure State** somente depois que CL-01, CL-02, CL-03, CL-05/06 e CL-08 estiverem validados individualmente.

## Estados mínimos

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

- cada estado deve ter regras explícitas;
- estados devem ser mutuamente priorizados;
- mostrar qual regra venceu;
- painel com componentes do score;
- não usar pesos “mágicos” sem inputs/documentação;
- não chamar score de probabilidade.

---

# TV-CL-10 — Indicador calibrado por validação histórica

NÃO IMPLEMENTE este indicador sem receber antes um arquivo/relatório de validação histórica do Candle Lab.

Quando esse relatório for fornecido:

1. leia taxas, baseline, lift, IC 95%, N e estabilidade;
2. descarte hipóteses com amostra insuficiente;
3. não escolha apenas o melhor resultado in-sample;
4. solicite divisão treino/validação/teste se não existir;
5. reproduza apenas regras tecnicamente possíveis no Pine;
6. mantenha no código a versão dos parâmetros do Candle Lab;
7. crie painel mostrando quais componentes dispararam;
8. não chame a saída de “probabilidade” sem calibração estatística apropriada.

---

# Fontes oficiais que a IA deve consultar novamente antes de codificar

- https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/
- https://www.tradingview.com/pine-script-docs/release-notes/
- https://www.tradingview.com/pine-script-docs/writing/limitations/
- https://www.tradingview.com/pine-script-docs/language/type-system/

A documentação pode mudar. Não use este prompt como substituto de verificação oficial.


---

# TV-CL-11 — Concentração por agente / fingerprint

Use o PROMPT BASE, mas **não escreva código imediatamente**.

## Objetivo

Avaliar se é possível reproduzir, no Pine Script atual, a métrica do Candle Lab que mede concentração da agressão por agente/corretora.

## Etapa obrigatória de viabilidade

Antes de programar:

1. consulte a documentação oficial atual do Pine;
2. verifique se existe API documentada que exponha identidade de agente/corretora por negócio;
3. diferencie footprint buy/sell de identificação de participante;
4. procure apenas APIs oficiais, sem assumir acesso ao Times & Trades de outra plataforma.

## Regra de decisão

Se não existir identificação de agente/corretora acessível ao script:

- **não invente uma aproximação**;
- não use footprint buy/sell como se fosse identificação de player;
- entregue um relatório técnico explicando a impossibilidade de reprodução fiel;
- proponha, separadamente, métricas possíveis apenas com volume/footprint, como concentração por row ou imbalance, deixando claro que são outra variável.

## Se houver API oficial futura

Somente então implemente:

- participação do maior agente;
- participação dos 3 maiores;
- HHI de concentração;
- persistência do mesmo agente;
- entrada/saída do principal agressor.

## Entregável

O resultado principal pode ser um relatório de inviabilidade. Isso é uma conclusão válida e preferível a código baseado em dados inexistentes.

---

# TV-CL-12 — Painel explicativo do candle

Use o PROMPT BASE e implemente **Candle Lab — Candle Microstructure Explainer**.

## Objetivo

Criar um painel compacto que resuma apenas variáveis que o TradingView realmente consegue observar ou aproximar.

O painel deve mostrar, quando disponíveis:

- buy volume do footprint;
- sell volume do footprint;
- delta;
- delta normalizado;
- intensidade relativa;
- relação preço × delta;
- estado de divergência;
- estado de onda aproximado;
- eficiência esforço × resultado;
- hipótese dominante compatível;
- qualidade/disponibilidade do dado.

## Regras de linguagem

Não reproduza automaticamente o texto completo do relatório interpretativo do Candle Lab.

Use estados curtos e auditáveis, por exemplo:

```text
Fluxo: BUY dominante
Delta: +12.450
Intensidade: HIGH
Preço × delta: alinhado
Onda: BUY ativa
Eficiência: alta
Leitura: continuação compatível
Fonte: TradingView footprint
```

ou:

```text
Preço × delta: divergente
Leitura: candidato a absorção
```

Nunca usar “absorção confirmada”.

## Arquitetura

Reutilize funções dos módulos simples CL-01/02/03/05/06/08 em vez de duplicar cálculos.

O painel deve ter um modo diagnóstico que mostre quais condições foram verdadeiras.

## Disponibilidade

Se `request.footprint()` retornar `na`:

- exibir NO_FOOTPRINT;
- não preencher valores com volume comum sem autorização explícita;
- não gerar hipóteses baseadas em delta inexistente.

## Alertas

Não criar um alerta genérico “compre/venda”.

Se o usuário habilitar alertas, crie condições para estados objetivos, por exemplo:

- divergência preço × delta confirmada;
- exaustão aproximada confirmada;
- troca de controle confirmada;
- pressão persistente no fechamento.

## Validação

Inclua um roteiro para comparar visualmente os estados do painel com candles já analisados no Candle Lab.

---

# PROMPT DE INTEGRAÇÃO COM RELATÓRIO HISTÓRICO DO CANDLE LAB

Use este prompt quando o usuário fornecer um arquivo JSON exportado pela seção **Validação histórica das hipóteses**.

Você é responsável por transformar apenas resultados historicamente sustentados e tecnicamente reproduzíveis em requisitos de indicador Pine.

## Procedimento obrigatório

1. leia `model_version`, `reference_mode`, `input`, `baselines`, `directional_results` e `warnings`;
2. liste as hipóteses por horizonte;
3. mostre N, taxa, baseline, lift e IC Wilson 95%;
4. descarte ou marque como exploratória qualquer linha com `AMOSTRA_INSUFICIENTE`;
5. não trate `PRELIMINAR` ou `AMOSTRA_MAIOR` como prova de causalidade;
6. verifique se a variável original é observável no TradingView;
7. se houver apenas proxy, documente a mudança semântica;
8. proponha uma especificação antes de escrever código;
9. congele os parâmetros escolhidos e registre a versão do relatório usada;
10. reserve um período fora da amostra para validação final.

Não selecione automaticamente a linha de maior lift. Considere tamanho da amostra, intervalo de confiança, estabilidade entre horizontes e viabilidade de reprodução.
