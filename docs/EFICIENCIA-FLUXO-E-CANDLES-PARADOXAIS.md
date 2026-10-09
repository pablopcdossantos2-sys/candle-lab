# Eficiência do fluxo e Detector de Candles Paradoxais — v0.20

## Objetivo

A v0.20 acrescenta ao Candle Lab uma camada dedicada a responder três perguntas diferentes:

1. **Quem tomou a iniciativa?**
2. **Quanto esforço agressor foi realizado?**
3. **Qual foi a resposta do preço a esse esforço?**

A ideia central é que volume agressor, isoladamente, não explica a formação do candle.

Uma grande quantidade de compra agressora pode:

- deslocar fortemente o preço para cima;
- produzir pouco avanço;
- produzir nenhuma mudança líquida;
- ou ocorrer enquanto o preço cai.

Essas situações têm significados microestruturais diferentes e precisam ser separadas.

---

## 1. Iniciativa

A iniciativa usa os negócios BUY/SELL reconhecidos.

O sistema registra:

- compra agressora;
- venda agressora;
- delta;
- lado predominante;
- dominância;
- relação entre lado do fluxo e direção do preço;
- participação do principal agente agressor quando identificável.

RLP permanece separado.

---

## 2. Esforço

O esforço é medido a partir da atividade agressora executada.

A versão inicial registra:

- volume agressor direcionado;
- participação desse volume no volume total;
- contratos agressores por segundo;
- negócios por segundo;
- esforço em cada terço cronológico do candle;
- esforço relativo à mediana das fases do próprio candle.

A comparação por fases é relativa ao candle, evitando aplicar um número absoluto como se fosse universal para todos os horários e regimes.

---

## 3. Resposta do preço

A resposta mede o resultado observado no preço.

São calculados:

- deslocamento líquido em ticks;
- range;
- ticks por 1.000 contratos de agressão direcionada;
- ticks por 1.000 contratos BUY;
- ticks favoráveis à venda por 1.000 contratos SELL;
- resposta do lado dominante.

Exemplo:

```text
Compra agressora: 1.200 contratos
Deslocamento: +12 ticks

Eficiência BUY = 10 ticks / 1.000 contratos
```

Se, posteriormente:

```text
Compra agressora: 1.500 contratos
Deslocamento: +1 tick

Eficiência BUY = 0,67 tick / 1.000 contratos
```

o esforço aumentou, mas sua eficiência caiu fortemente.

---

## 4. Fases intrabar

O candle é inicialmente dividido em três grupos de negócios com tamanho semelhante:

- INICIO;
- MEIO;
- FINAL.

Para cada fase são mostrados:

- BUY;
- SELL;
- lado dominante;
- dominância;
- velocidade do fluxo;
- mudança do preço;
- eficiência do lado dominante;
- classificação da eficiência.

As classificações iniciais são:

- ALTA;
- MODERADA;
- BAIXA;
- SEM_RESPOSTA;
- RESPOSTA_OPOSTA;
- FLUXO_EQUILIBRADO;
- SEM_DADOS.

ALTA/MODERADA/BAIXA são relativas às fases do próprio candle.

---

## 5. Esforço sem resultado

O evento `ESFORCO_SEM_RESULTADO` procura situações nas quais:

- a agressão da fase é igual ou superior à mediana interna do candle;
- mas a resposta do preço é baixa, nula ou contrária ao lado predominante.

Esse evento é compatível com hipóteses de:

- absorção passiva;
- resistência de liquidez;
- perda de eficiência;
- disputa em nível relevante.

Ele não prova nenhuma dessas hipóteses.

---

## 6. Perda de eficiência

O Candle Lab compara fases diferentes do mesmo lado.

Exemplo:

```text
INICIO
BUY = 800
eficiência = +8,0 ticks / 1.000 contratos

FINAL
BUY = 900
eficiência = +1,5 ticks / 1.000 contratos
```

A agressão permaneceu relevante, mas a capacidade de deslocar o preço caiu.

O sistema pode gerar:

```text
PERDA_EFICIENCIA_BUY
```

ou:

```text
PERDA_EFICIENCIA_SELL
```

Essa situação é particularmente importante para estudos de exaustão e mudança de controle.

---

## 7. Agressão acelerando com eficiência em queda

Outro sinal procura situações em que:

- contratos agressores por segundo aumentam;
- ao mesmo tempo, a eficiência cai de forma importante.

Isso é mais informativo do que simplesmente observar volume alto.

Conceitualmente:

```text
mais esforço
+
menos resultado
=
deterioração da eficiência
```

---

## 8. Detector de Candles Paradoxais

O detector não tenta prever automaticamente uma reversão.

Seu objetivo é **priorizar candles para investigação**.

A v0.20 reconhece inicialmente:

### BAIXA_COM_COMPRA_AGRESSORA_DOMINANTE

```text
Close < Open
BUY > SELL
```

O candle caiu apesar de predominância de compra agressora.

### ALTA_COM_VENDA_AGRESSORA_DOMINANTE

```text
Close > Open
SELL > BUY
```

O candle subiu apesar de predominância de venda agressora.

### AGRESSAO_FORTE_SEM_DESLOCAMENTO

Uma fase apresentou esforço relevante sem deslocamento proporcional.

### PERDA_EFICIENCIA_BUY / SELL

O lado continuou agredindo, mas sua capacidade de deslocar o preço caiu.

### AGRESSAO_ACELERA_E_EFICIENCIA_CAI

A velocidade de execução aumentou enquanto o resultado por unidade de esforço piorou.

---

## 9. Prioridade de investigação

Cada sinal recebe um score heurístico e uma prioridade:

- BAIXA;
- MODERADA;
- ALTA;
- MUITO_ALTA.

Esse score **não é probabilidade de reversão**.

Ele serve apenas para ordenar casos potencialmente interessantes para estudo.

---

## 10. Relação com o relatório interpretativo

A v0.20 conecta eficiência do fluxo ao Relatório Interpretativo.

O relatório passa a poder registrar:

- `EFICIENCIA_FLUXO`;
- `CANDLE_PARADOXAL`;
- `ESFORCO_AGRESSOR_SEM_RESULTADO`;
- `PERDA_EFICIENCIA_FLUXO`.

Assim, a explicação textual não depende apenas de delta, geometria e ondas de agressão.

---

## 11. Causalidade e limitações

A eficiência de fluxo mede associação entre:

```text
agressão executada
       ↓
resposta observada do preço
```

Ela não mede impacto causal puro.

O Times & Trades não mostra integralmente:

- liquidez passiva disponível;
- cancelamentos;
- reposição de ordens;
- intenção de ordens não executadas;
- todos os mecanismos de arbitragem;
- estímulos externos simultâneos.

Portanto, uma eficiência baixa é evidência de que o esforço agressor produziu pouco resultado, mas a explicação para isso ainda precisa ser investigada.

---

## 12. Próxima etapa de pesquisa

Com uma biblioteca histórica maior, o Candle Lab poderá responder:

- perdas de eficiência BUY costumam anteceder queda?
- perdas de eficiência SELL costumam anteceder alta?
- divergência preço × fluxo tem poder informacional fora da amostra?
- quais combinações de velocidade, dominância e perda de eficiência antecedem mudança de controle?
- quais agentes aparecem com maior frequência em episódios de esforço sem resultado?
- candles paradoxais formam famílias recorrentes?

A prioridade é validar esses eventos historicamente antes de convertê-los em indicadores operacionais.


## 13. Varredura do pregão inteiro

A v0.20 também permite varrer todos os candles disponíveis no pregão selecionado.

A ferramenta:

1. reconstrói cada candle a partir dos negócios armazenados;
2. calcula agressão e composição BUY/SELL;
3. calcula eficiência do fluxo;
4. executa o Detector de Candles Paradoxais;
5. ordena os resultados pelo score de prioridade;
6. permite abrir diretamente um candle encontrado para análise detalhada.

A tabela de varredura mostra horário, abertura, fechamento, prioridade, score e os principais sinais detectados.

Essa função foi criada para reduzir o trabalho manual de procurar candle a candle por situações incomuns.
