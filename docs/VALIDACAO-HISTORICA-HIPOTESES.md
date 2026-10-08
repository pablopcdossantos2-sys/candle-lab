# Validação histórica das hipóteses — v0.18

## Objetivo

A v0.18 acrescenta uma camada de validação histórica para as hipóteses explicativas produzidas pelo Relatório Interpretativo do Candle.

A regra metodológica é importante:

> O Candle Lab não pode usar o mesmo candle para gerar uma hipótese e depois dizer que esse mesmo candle “provou” a hipótese.

Por isso, esta camada mede duas coisas diferentes:

1. **repetibilidade** — quantas vezes uma hipótese aparece na biblioteca;
2. **consequência externa** — o que acontece em candles posteriores, que não participaram da geração da hipótese.

Essa abordagem permite começar a selecionar quais ideias merecem virar indicadores.

---

## Unidade de estudo

Para cada candle elegível:

1. o Candle Lab reconstrói o candle a partir dos Trades;
2. gera DNA, mapa de agressão, ondas e relatório interpretativo;
3. registra os códigos das hipóteses;
4. procura candles futuros contíguos;
5. mede o comportamento posterior em horizontes configuráveis.

Horizontes padrão:

- 1 candle;
- 3 candles;
- 5 candles.

---

## Proteção de qualidade

Quando existe referência OHLC/Quantidade para o mesmo timeframe, o candle só entra no estudo se a reconstrução dos Trades for **EXACT** contra a referência.

São excluídos:

- dados sintéticos, por padrão;
- candles sem referência quando a referência está disponível;
- candles divergentes da referência;
- grupos inválidos;
- desfechos que exigiriam atravessar lacuna da biblioteca;
- desfechos que atravessariam a fronteira entre pregões.

Se não existir referência disponível, a ferramenta pode estudar a biblioteca Tick, mas marca explicitamente:

`TICK_LIBRARY_UNVERIFIED_BY_REFERENCE`

Esse resultado recebe menor peso metodológico.

---

## Baseline

Cada resultado direcional é comparado com a linha de base da própria biblioteca.

Exemplo:

```text
Hipótese: REJEICAO_MAXIMA
Direção esperada: DOWN
Horizonte: 3 candles

Ocorrências com desfecho: 140
Fechamento abaixo: 88 / 140 = 62,9%

Baseline da biblioteca:
qualquer candle fecha abaixo após 3 candles = 49,7%

Lift:
+13,2 pontos percentuais
```

O lift é:

```text
taxa da hipótese - taxa base da mesma direção
```

Ele não deve ser interpretado sozinho como vantagem estatística comprovada.

---

## Intervalo de confiança

A taxa direcional recebe intervalo de confiança Wilson de 95%.

A intenção é impedir que algo como:

```text
3 acertos em 4 casos = 75%
```

pareça mais robusto do que realmente é.

---

## Estado da amostra

A versão inicial usa rótulos transparentes:

```text
< 30 casos     AMOSTRA_INSUFICIENTE
30–99          EXPLORATORIA
100–499        PRELIMINAR
>= 500         AMOSTRA_MAIOR
```

Esses rótulos não transformam automaticamente um resultado em evidência científica.

O número de pregões independentes, regimes de mercado e estabilidade fora da amostra também deverá ser considerado antes de promover uma hipótese a indicador operacional.

---

## Hipóteses com direção externa pré-registrada

### AGRESSAO_ALINHADA_ALTA

Alvo exploratório: continuação para cima.

### AGRESSAO_ALINHADA_BAIXA

Alvo exploratório: continuação para baixo.

### ALTA_COM_DELTA_VENDEDOR

Alvo exploratório: continuidade/resiliência para cima.

A ideia é testar se a divergência preço x agressão vendedora é compatível historicamente com incapacidade da venda de produzir queda.

### BAIXA_COM_DELTA_COMPRADOR

Equivalente para baixo.

### REJEICAO_MAXIMA

Alvo exploratório: movimento posterior para baixo.

### REJEICAO_MINIMA

Alvo exploratório: movimento posterior para cima.

### ONDA_ABERTA_SUSTENTA_FECHAMENTO

Direção esperada definida pelo lado da onda que permaneceu aberta no fechamento.

### MUDANCA_CONTROLE_INTRABAR

Direção esperada definida pelo lado dominante na fase final do candle.

---

## Hipóteses descritivas sem alvo pré-registrado

Nem toda explicação deve ser forçada a produzir sinal direcional.

Exemplo inicial:

`DISPUTA_EQUILIBRADA`

A v0.18 registra frequência e força da hipótese, mas não inventa um alvo direcional.

No futuro poderemos pré-registrar um desfecho apropriado, por exemplo:

- expansão de range;
- persistência de lateralização;
- aumento de volatilidade;
- rompimento do range.

Só depois disso ela deve entrar numa validação de “acerto”.

---

## Métricas por hipótese e horizonte

Para cada combinação hipótese × horizonte:

- ocorrências totais;
- ocorrências com desfecho contíguo disponível;
- direção esperada;
- número de acertos direcionais;
- taxa de acerto;
- número de movimentos de pelo menos 2 ticks;
- taxa de movimentos de pelo menos 2 ticks;
- baseline;
- lift em pontos percentuais;
- IC Wilson 95%;
- deslocamento médio alinhado;
- excursão favorável média;
- excursão adversa média;
- score médio da hipótese;
- resultado separado por confiança FORTE/MODERADA/FRACA.

---

## O que esta camada valida e o que não valida

Ela pode sustentar frases como:

> Na biblioteca atual, a hipótese REJEICAO_MAXIMA ocorreu 180 vezes e foi seguida por fechamento inferior três candles depois em 61% dos casos, contra baseline de 49%.

Ela **não** sustenta automaticamente:

> A compra foi causalmente absorvida e por isso o mercado caiu.

A causalidade continua exigindo evidência adicional.

---

## Uso para criação de indicadores

A validação histórica passa a funcionar como um funil:

```text
Hipótese do Candle Lab
        ↓
Repetibilidade histórica
        ↓
Desfecho externo
        ↓
Comparação com baseline
        ↓
Estabilidade por contexto
        ↓
Candidato a indicador
        ↓
Implementação TradingView / Profit
        ↓
Validação fora da amostra
```

O objetivo é reduzir a chance de criar indicadores apenas porque uma explicação parece intuitiva.

---

## Critérios recomendados antes de promover um candidato

Não são regras absolutas, mas um candidato deve idealmente apresentar:

1. amostra suficientemente grande;
2. ocorrências distribuídas por vários pregões;
3. resultado positivo em mais de um período de mercado;
4. lift que não dependa de poucos outliers;
5. excursão favorável coerente com a tese;
6. excursão adversa aceitável;
7. comportamento semelhante em janelas fora da amostra;
8. versão da regra congelada antes do teste final.

A etapa futura deve acrescentar divisão treino/validação/teste e walk-forward.

---

## Interface

Na seção **Validação histórica das hipóteses**, o usuário informa horizontes, por exemplo:

`1,3,5`

e recebe uma tabela com:

- hipótese;
- horizonte;
- N;
- direção esperada;
- taxa de acerto;
- baseline;
- lift;
- IC 95%;
- status da amostra.

---

## Limitação atual da biblioteca

O repositório não contém um histórico amplo de microestrutura real.

A validação empírica real depende dos recortes que o usuário importar para o DuckDB local.

Portanto, a v0.18 entrega **a infraestrutura do estudo**; resultados robustos só surgirão à medida que a biblioteca real crescer.


---

## Exportação do relatório

Depois de executar **Validar hipóteses na biblioteca**, a interface habilita:

`Baixar relatório JSON`

O arquivo contém, entre outros:

- versão do modelo;
- símbolo e timeframe;
- modo de referência;
- candles elegíveis e exclusões;
- baselines;
- ocorrências por hipótese;
- resultados direcionais por horizonte;
- N;
- taxa de acerto direcional;
- taxa de movimento mínimo;
- lift;
- intervalo Wilson de 95%;
- excursão favorável/adversa;
- resultados por confiança;
- advertências metodológicas.

Esse JSON é o formato recomendado para entregar a uma IA que posteriormente criará um indicador. Os prompts em `prompts/` obrigam a IA a ler N, baseline, lift, intervalo de confiança e disponibilidade real das variáveis antes de escrever código.
