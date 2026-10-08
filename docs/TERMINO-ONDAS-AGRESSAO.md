# Término das ondas de agressão — v0.16

## Objetivo

A v0.16 acrescenta uma camada dedicada a identificar, dentro de um candle, quando uma onda de agressão executada perde força ou muda de lado.

A hipótese de pesquisa é que o encerramento de uma onda agressora pode anteceder:

- reversões;
- neutralização do movimento;
- perda de momentum;
- troca de controle entre compradores e vendedores;
- continuação após uma pausa.

O Candle Lab **não assume que todo término de agressão gera reversão**. O objetivo é registrar o evento de fluxo primeiro e medir a reação do preço depois.

## Regra metodológica principal: detecção causal

O instante de término é calculado usando somente negócios que já ocorreram até aquele momento.

Os negócios posteriores ao evento:

- não participam da detecção;
- não alteram retroativamente o instante detectado;
- são usados apenas em uma seção separada de validação histórica.

Isso permite testar futuramente se determinados tipos de término realmente antecedem mudanças de tendência com frequência acima do acaso.

## Janela de pressão

A implementação inicial usa uma janela móvel de negócios.

Valor padrão:

```text
25 negócios
```

Para cada novo negócio, a janela calcula:

```text
BUY = volume agressor comprador
SELL = volume agressor vendedor

Agressão direcionada = BUY + SELL

Dominância assinada =
(BUY - SELL) / (BUY + SELL)
```

Interpretação:

```text
+1,00 = somente compradores agressores
 0,00 = equilíbrio
-1,00 = somente vendedores agressores
```

Também é calculada a cobertura:

```text
(BUY + SELL) / volume total da janela
```

RLP e agressão não identificada não são inventados como BUY ou SELL.

## Início de uma onda

Por padrão, uma onda começa quando existem duas confirmações consecutivas com:

```text
cobertura agressora >= 50%
dominância absoluta >= 55%
```

Exemplo de onda compradora:

```text
dominância >= +0,55
```

Exemplo de onda vendedora:

```text
dominância <= -0,55
```

A confirmação consecutiva reduz a chance de tratar um único negócio isolado como uma nova onda.

## Tipos de término

A v0.16 classifica três formas principais.

### EXAUSTAO

O volume agressor do lado dominante cai fortemente em relação ao pico da própria onda e a dominância deixa de confirmar o lado anterior.

Por padrão, o volume da janela precisa cair para aproximadamente 35% ou menos do pico observado na onda.

### NEUTRALIZACAO

A dominância do lado original desaparece, mas ainda existe atividade relevante dos dois lados.

É uma situação de perda de controle sem tomada clara pelo lado oposto.

### TROCA_CONTROLE

O lado oposto passa a apresentar dominância suficientemente forte.

Exemplo:

```text
onda BUY
      ↓
dominância cai
      ↓
SELL alcança dominância oposta
      ↓
TROCA_CONTROLE
```

Esse evento é especialmente interessante para estudos de reversão.

## Confirmação do término

O fim não é marcado no primeiro sinal de fraqueza.

Por padrão são exigidas três confirmações consecutivas da condição de término.

Isso introduz algum atraso intencional, mas reduz falsos términos causados por oscilações de poucos negócios.

## Informações registradas em cada evento

Cada término armazena:

- lado da onda: BUY ou SELL;
- horário de início;
- número do negócio de início;
- preço de início;
- instante de maior pressão;
- maior volume agressor do lado dominante na janela;
- maior dominância observada;
- horário do término;
- número do negócio que confirmou o término;
- preço no término;
- tipo de término;
- volume do lado dominante na janela final;
- volume do lado oposto na janela final;
- cobertura agressora da janela final;
- queda percentual da pressão em relação ao pico;
- duração em negócios;
- duração em segundos;
- principais agentes agressores da onda.

## Principais agentes da onda

Durante cada episódio o Candle Lab soma apenas os negócios executados pelo lado agressor correspondente.

Para uma onda BUY:

```text
usa Agente Comprador dos negócios BUY
```

Para uma onda SELL:

```text
usa Agente Vendedor dos negócios SELL
```

O ranking mostra quantidade, número de negócios e participação do agente no volume agressor da onda.

## Marcadores no replay

No gráfico de trajetória intrabar, cada término confirmado recebe um marcador:

```text
T1
T2
T3
...
```

O marcador só aparece no replay depois que o negócio de confirmação aconteceu.

Assim, o replay não revela antecipadamente eventos que ainda não seriam conhecidos naquele instante.

## Resultado posterior — EX-POST

Depois do candle fechado, o Candle Lab mede separadamente o comportamento posterior ao término.

A janela padrão inicial é de 50 negócios posteriores.

Para uma onda BUY encerrada:

- movimento para baixo = reversão em relação à onda;
- movimento para cima = continuação.

Para uma onda SELL encerrada:

- movimento para cima = reversão;
- movimento para baixo = continuação.

A classificação histórica pode ser:

- `REVERSAO_COMPATIVEL`;
- `CONTINUACAO`;
- `ESTAGNACAO_OU_DISPUTA`;
- `SEM_JANELA_POSTERIOR`.

O limiar inicial para movimento relevante é 2 ticks.

Esses dados futuros **não fazem parte da detecção**.

## Proteção contra look-ahead

A suíte de testes verifica explicitamente que:

1. um evento é detectado em determinado índice;
2. negócios futuros são adicionados depois;
3. o índice do evento detectado não muda.

Esse teste é essencial para que uma análise histórica não produza falsos sinais perfeitos por olhar o futuro.

## Onda aberta no fechamento do candle

Se o candle termina enquanto a pressão ainda está ativa, o sistema não inventa um término.

O estado é:

```text
ABERTA_NO_FIM_DO_CANDLE
```

Isso também é informação útil para comparar o candle atual com o seguinte.

## Relação com mudança de tendência

O término de agressão é tratado como **candidato a evento precursor**, não como previsão garantida.

A pergunta que o Candle Lab poderá testar com uma biblioteca histórica maior é:

> Após quais tipos de término de agressão a probabilidade observada de reversão é maior?

Algumas dimensões futuras para esse estudo:

- EXAUSTAO vs TROCA_CONTROLE;
- tamanho da queda de pressão;
- dominância máxima anterior;
- intensidade da agressão por preço;
- posição do evento dentro do range do candle;
- proximidade da máxima/mínima;
- concentração em poucos agentes;
- horário do pregão;
- regime de volatilidade;
- formato do candle;
- comportamento dos candles seguintes.

## Limitações

Times & Trades mostra execuções, não toda a liquidez passiva disponível.

Portanto:

- fim da agressão executada não significa necessariamente fim do interesse comprador/vendedor;
- absorção não pode ser provada sem evidência mais completa do livro;
- um evento pode ser seguido de reversão, continuação ou lateralização;
- parâmetros iniciais precisam ser validados empiricamente em muitos pregões;
- a granularidade temporal da exportação do Profit é de 1 segundo, embora a ordem sequencial de negócios seja preservada pelo arquivo.

A camada v0.16 foi desenhada para tornar essas hipóteses mensuráveis em vez de tratá-las como pressupostos.
