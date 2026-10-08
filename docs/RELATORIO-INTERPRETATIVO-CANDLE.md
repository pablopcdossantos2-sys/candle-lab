# Relatório interpretativo do candle — v0.17

## Objetivo

A v0.17 transforma as métricas de microestrutura em uma descrição auditável da formação do candle.

O relatório procura responder:

1. Como o preço percorreu o candle?
2. Como a agressão se distribuiu ao longo da formação?
3. Quais preços concentraram maior agressão?
4. Quais agentes apareceram com maior participação?
5. Houve ondas de agressão e términos relevantes?
6. Quais hipóteses são compatíveis com o modo como o candle fechou?

A palavra **hipótese** é deliberada. O sistema não apresenta o fechamento como causalmente explicado apenas porque encontrou correlação entre fluxo e preço.

---

## Estrutura do relatório

O painel possui quatro camadas.

### 1. Evidências observadas

São fatos diretamente calculáveis a partir dos Trades e do candle:

- OHLC;
- corpo e sombras;
- localização do fechamento no range;
- volume agressor comprador;
- volume agressor vendedor;
- delta;
- cobertura do agressor;
- preços com maior concentração de agressão;
- principais agentes agressores;
- ondas de agressão;
- términos de onda;
- onda ainda aberta no fim do candle.

Essas frases não devem conter afirmações de causalidade.

### 2. Descrição cronológica

Os negócios são divididos, inicialmente, em três blocos cronológicos com número semelhante de trades:

- início;
- miolo;
- fase final.

Para cada bloco, o sistema descreve:

- agressão compradora;
- agressão vendedora;
- delta;
- lado dominante;
- deslocamento líquido do preço naquele trecho.

Exemplo conceitual:

> No início, predominou a agressão compradora, com delta +820, e o preço terminou o trecho 6 ticks acima. No miolo, o fluxo se equilibrou. Na fase final, predominou a agressão vendedora e o preço devolveu 4 ticks.

Isso ajuda a explicar um candle cuja forma final não é compatível com uma única direção de fluxo durante toda a sua formação.

### 3. Hipóteses explicativas

Cada hipótese contém:

- título;
- score;
- classificação FORTE, MODERADA ou FRACA;
- explicação;
- evidências a favor;
- contrapontos e limitações.

O score é uma **força interna da evidência disponível**, não uma probabilidade estatística de a hipótese ser verdadeira.

A biblioteca histórica futura deverá permitir calibrar probabilidades reais.

### 4. Síntese do fechamento

O sistema seleciona as hipóteses com maior suporte e produz um parágrafo curto sobre o fechamento.

A síntese sempre termina lembrando que são hipóteses derivadas de fluxo executado e trajetória de preço, e não demonstração causal.

---

## Qualidade da evidência

A interpretação recebe uma classificação:

- ALTA;
- MODERADA;
- LIMITADA.

A versão inicial combina:

- cobertura BUY/SELL no volume total;
- cobertura de identidade dos agentes;
- quantidade de negócios observados.

O objetivo é evitar que um candle com baixa cobertura de agressor receba uma narrativa excessivamente confiante.

---

## Hipóteses iniciais

### Agressão alinhada à alta

Pode aparecer quando:

- candle fecha acima da abertura;
- delta total é comprador;
- há cobertura suficiente;
- fechamento ocorre em região coerente com a direção.

Interpretação:

> A iniciativa compradora foi compatível com o deslocamento e pode ter ajudado a sustentar preços mais altos.

Isso não significa que a agressão compradora seja a única causa do candle.

### Agressão alinhada à baixa

É o equivalente vendedor.

---

## Divergência entre preço e delta

### Alta com delta vendedor

Exemplo:

```text
Close > Open
SELL agressor > BUY agressor
```

O sistema pode propor:

> Venda agressora absorvida ou incapaz de produzir queda sustentada.

Essa hipótese é especialmente importante para o projeto porque esforço agressor e resultado do preço apontam em direções diferentes.

Possíveis explicações incluem:

- compradores passivos absorvendo venda;
- venda agressora executada em níveis onde havia forte demanda passiva;
- perda de eficiência vendedora;
- mudança posterior de controle.

Sem MBO/MBP, absorção permanece hipótese.

### Baixa com delta comprador

É o equivalente oposto.

---

## Rejeição da máxima

A hipótese de perda de eficiência compradora próxima da máxima pode ganhar suporte quando aparecem juntos:

- sombra superior relevante;
- possível absorção perto da máxima;
- término de onda BUY próximo da máxima;
- fechamento abaixo do extremo.

O sistema descreve que a compra agressora pode ter encontrado dificuldade para transformar esforço em permanência nos preços mais altos.

---

## Rejeição da mínima

É o equivalente vendedor na mínima.

---

## Onda aberta no fechamento

Se uma onda BUY ou SELL ainda está ativa quando o candle termina, isso entra na explicação.

Exemplo:

> O candle terminou com uma onda BUY ainda aberta; a persistência da pressão compradora é compatível com um fechamento sustentado na região superior do range.

A palavra “compatível” é mantida para evitar causalidade não demonstrada.

---

## Disputa bilateral

Quando:

- delta total fica próximo de zero;
- fechamento ocorre no miolo do range;

o relatório pode propor:

> Disputa bilateral sem domínio agressor claro.

Isso é útil para diferenciar um candle pequeno por ausência de atividade de um candle pequeno produzido por forte atividade dos dois lados.

---

## Mudança de controle intrabar

Se o primeiro terço é dominado por BUY e o último por SELL, ou vice-versa, o relatório registra uma possível mudança de controle.

Isso ajuda a explicar:

- candles com sombras longas;
- reversões internas;
- fechamento distante do primeiro impulso;
- candles com corpo pequeno apesar de grande range.

---

## Score das hipóteses

O score inicial usa combinações explicáveis de:

- direção do fechamento;
- localização do fechamento no range;
- força do delta;
- cobertura do agressor;
- tamanho relativo das sombras;
- presença de possível absorção;
- término de onda próximo ao extremo;
- onda ainda aberta no fechamento.

Os pesos são heurísticos e versionados.

Eles deverão ser recalibrados quando existir uma biblioteca histórica grande o bastante para comparar:

- hipótese gerada;
- estrutura real do fluxo;
- comportamento posterior;
- repetibilidade entre pregões.

---

## Relatório durante o replay

O relatório interpretativo é uma análise **pós-fechamento**.

Ao iniciar o replay negócio a negócio, ele fica oculto.

Só reaparece quando o replay chega ao final do candle.

Isso impede que uma análise retrospectiva revele antecipadamente informações do restante do candle durante a observação da formação.

---

## Auditoria

O payload do relatório preserva:

- versão do motor interpretativo;
- versão do modelo de agressão;
- versão do modelo de ondas;
- DNA completo do candle;
- fatos usados;
- hipóteses;
- evidências a favor e contra.

O objetivo é permitir que qualquer frase importante possa ser rastreada às métricas que a originaram.

---

## O que o relatório não deve fazer

Ele não deve afirmar:

- “o candle subiu porque o agente X comprou”;
- “houve absorção comprovada”;
- “a tendência vai inverter”;
- “esse participante é o investidor final”;
- “a hipótese tem 80% de chance” apenas porque o score interno é 0,80.

O score atual mede coerência da evidência dentro do modelo, não probabilidade estatística validada.

---

## Próximas etapas

A camada interpretativa abre caminho para:

1. comparar explicações de candles semelhantes;
2. pesquisar quais hipóteses aparecem antes de determinados movimentos;
3. validar scores contra histórico;
4. medir se determinadas combinações de agressão e término de onda são recorrentes;
5. criar um catálogo de arquétipos explicativos;
6. futuramente, oferecer uma camada opcional de linguagem mais livre, desde que sempre grounded no relatório estruturado.

A prioridade continua sendo manter a interpretação auditável e separada de causalidade ou previsão não demonstradas.
