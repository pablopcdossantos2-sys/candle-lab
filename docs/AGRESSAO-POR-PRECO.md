# Agressão por preço e principais agressores — v0.15

## Objetivo

Esta camada procura ajudar a responder uma das perguntas centrais do Candle Lab:

> Como a agressão executada ao longo do candle se distribuiu pelos níveis de preço e quais agentes participaram mais ativamente desse processo?

O foco é reconstruir fatos observáveis do Times & Trades e organizar esses fatos para estudo da formação intrabar.

## O que o Candle Lab observa diretamente

Quando o CSV contém os campos `Agente Comprador`, `Agente Vendedor` e `Agressor`, para cada negócio é possível observar:

- preço;
- quantidade;
- comprador;
- vendedor;
- lado agressor informado pela fonte;
- ordem temporal preservada pelo arquivo.

Se o lado agressor é `BUY`, o agente comprador é atribuído à agressão compradora.

Se o lado agressor é `SELL`, o agente vendedor é atribuído à agressão vendedora.

`RLP` permanece separado e não é transformado artificialmente em BUY ou SELL.

## Importante: agente não significa necessariamente investidor final

O campo de agente da exportação representa a identificação fornecida pela fonte, normalmente relacionada ao agente/corretora participante da execução. O Candle Lab não afirma que esse identificador revele o beneficiário final da ordem.

## Métricas por nível de preço

Para cada preço negociado dentro do candle, o sistema calcula:

- volume total;
- número de negócios;
- volume agressor comprador;
- volume agressor vendedor;
- volume agressor direcionado = BUY + SELL;
- volume RLP;
- volume sem lado identificado;
- delta = BUY - SELL;
- direção dominante;
- dominância = `abs(delta) / (BUY + SELL)`;
- participação do nível no volume agressor direcionado do candle;
- principais agentes compradores agressores;
- principais agentes vendedores agressores;
- número de visitas ao nível;
- excursão favorável/adversa posterior à última ocorrência do nível.

## Intensidade da agressão

A intensidade é baseada no volume agressor direcionado acumulado em cada preço.

Ela é **relativa aos níveis do próprio candle**, e não um limite absoluto de mercado.

Quando há pelo menos quatro níveis com agressão direcionada:

```text
BAIXA      abaixo do percentil 40
MODERADA   percentil 40 até abaixo de 70
ALTA       percentil 70 até abaixo de 90
EXTREMA    percentil 90 ou superior
```

Com menos de quatro níveis, o sistema usa a razão do volume daquele preço contra a mediana dos níveis do candle para evitar percentis muito instáveis.

Por isso, `EXTREMA` significa 'extrema em relação a este candle', não 'extrema em qualquer contexto de mercado'.

## Intensidade x dominância

Esses conceitos são diferentes.

Um nível pode ter intensidade EXTREMA e dominância baixa se houver grande volume de compra e grande volume de venda no mesmo preço.

Exemplo:

```text
BUY  = 1.000
SELL =   950
volume direcionado = 1.950
delta = +50
dominância ≈ 2,6%
```

Esse nível possui grande atividade agressora, mas forte disputa entre os lados.

## Principais agressores

O ranking é feito pela quantidade executada como agressor.

Para cada agente são mostrados:

- quantidade agressora;
- número de negócios;
- participação no volume daquele lado.

O ranking existe em dois níveis:

1. ranking geral do candle;
2. ranking específico de cada nível de preço.

## Cobertura

Duas coberturas são apresentadas:

- `Cobertura agressor`: parcela do volume total que possui BUY ou SELL conhecido;
- `Identidade agente`: parcela da agressão BUY/SELL em que o agente correspondente está identificado.

Isso impede que rankings incompletos sejam apresentados como se cobrissem todo o candle.

## Leitura de resposta do preço

A v0.15 inclui uma heurística descritiva simples.

### Impulso compatível

Pode ser marcado quando:

- intensidade é ALTA ou EXTREMA;
- existe dominância direcional relevante;
- depois da última negociação naquele nível o preço se desloca pelo menos 2 ticks na direção da agressão;
- a excursão favorável supera a adversa.

### Possível absorção

Pode ser marcado quando:

- intensidade é ALTA ou EXTREMA;
- existe dominância direcional relevante;
- o preço revisita o nível;
- a agressão não consegue produzir mais de 1 tick de continuação favorável.

Esse rótulo é deliberadamente **POSSÍVEL ABSORÇÃO**.

Sem livro de ofertas MBO/MBP, o sistema não observa integralmente a liquidez passiva disponível e, portanto, não pode provar absorção.

### Sem janela pós-agressão

Se a última agressão relevante ocorre no fim do candle e não existem negócios posteriores dentro do candle, o sistema não tenta inferir absorção nem impulso.

## Relação com a hipótese central do projeto

A análise permite testar hipóteses como:

- candles visualmente semelhantes tiveram concentração agressora nos mesmos níveis?;
- uma máxima foi formada após agressão compradora extrema ou após incapacidade da compra de continuar?;
- uma mínima foi acompanhada por agressão vendedora concentrada em poucos agentes?;
- corpos longos apresentam maior dominância direcional do que candles de rejeição?;
- níveis de possível absorção aparecem próximos das sombras?;
- quais agentes aparecem repetidamente nos níveis de maior agressão em diferentes candles?

Essas perguntas podem ser investigadas empiricamente, mas correlação entre agressão observada e forma final do candle não deve ser apresentada automaticamente como causalidade.

## Próximas extensões naturais

A camada v0.15 cria a base para estudos futuros de:

- comparação de perfis de agressão entre candles;
- fingerprints de agentes;
- persistência de agressor entre níveis consecutivos;
- concentração por agente;
- agressão por janela temporal intrabar;
- reação do preço após clusters de agressão;
- integração futura com livro MBO/MBP para testar absorção com evidência mais forte.