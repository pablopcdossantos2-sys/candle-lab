# Possíveis indicadores derivados do Candle Lab

Data da revisão de capacidades das plataformas: 2026-10-08.

Este documento não contém código de indicadores. Ele organiza quais ideias do Candle Lab podem ser transformadas em indicadores para TradingView/Pine Script e Profit Pro/NTSL, quais podem ser reproduzidas apenas aproximadamente e quais dependem de dados que as plataformas não expõem nativamente ao script.

## 1. Princípio de desenvolvimento

Os indicadores não devem ser criados simplesmente porque uma hipótese parece intuitiva.

Fluxo recomendado:

1. formular a hipótese no Candle Lab;
2. medir ocorrência histórica;
3. medir desfecho externo;
4. comparar com baseline;
5. verificar estabilidade em vários pregões;
6. congelar a regra;
7. implementar uma versão de indicador;
8. validar fora da amostra;
9. somente depois discutir uso operacional.

O indicador deve guardar a distinção entre:

- **dado observado**;
- **proxy da plataforma**;
- **heurística**;
- **sinal historicamente validado**.

---

# 2. Diferenças de dados entre Candle Lab, TradingView e Profit

## 2.1 Candle Lab

O Candle Lab trabalha, quando disponível, com o CSV Tick by Tick exportado pelo Profit.

Isso permite analisar:

- negócio individual;
- sequência exportada;
- preço;
- quantidade;
- lado agressor informado pela fonte;
- agente comprador;
- agente vendedor;
- RLP;
- agressão por preço;
- ondas de agressão dentro do candle;
- término das ondas;
- descrição pós-fechamento.

Essa é a referência de pesquisa mais detalhada do projeto.

---

## 2.2 TradingView / Pine Script

A documentação atual do Pine Script v6 disponibiliza `request.footprint()`.

Ela permite solicitar:

- buy volume;
- sell volume;
- volume delta;
- footprint rows;
- volume por row;
- delta por row;
- buy/sell imbalance;
- POC;
- Value Area.

Também é possível combinar footprint com `request.security()` e `request.security_lower_tf()`.

### Limitação conceitual importante

A documentação do TradingView descreve o footprint como uma classificação de volume de timeframes inferiores em buy/sell baseada na ação intrabar de preço.

Portanto:

> Buy/Sell do footprint do TradingView não deve ser declarado automaticamente como semanticamente idêntico ao campo de agressor real do Times & Trades exportado pelo Profit.

Os indicadores Pine derivados do Candle Lab precisam usar termos como:

- footprint buy/sell;
- delta do footprint;
- proxy de agressão;

quando a equivalência não tiver sido empiricamente validada.

### Disponibilidade atual

Segundo a documentação oficial consultada, `request.footprint()` está disponível para planos Premium e Ultimate.

---

## 2.3 Profit Pro / NTSL

A documentação NTSL atual possui funções nativas como:

- `AgressionVolBuy()`;
- `AgressionVolSell()`;
- `AgressionVolBalance()`;
- `AccAgressSaldo`;
- indicadores de agressão média.

As funções `AgressionVolBuy()` e `AgressionVolSell()` são documentadas para Profit Pro, Profit Ultra ou módulo Scalper.

Isso torna o Profit particularmente adequado para indicadores baseados em:

- agressão compradora;
- agressão vendedora;
- saldo;
- intensidade histórica;
- divergência preço x agressão.

### Agentes individuais

O Times & Trades do Profit possui informações de compradores/vendedores e ferramentas de análise de players.

Entretanto, na documentação NTSL padrão revisada para este documento não foi confirmada uma função equivalente que entregue ao script o identificador de cada agente/corretora negócio a negócio.

Portanto, indicadores de **concentração por agente** devem ser tratados como:

- Candle Lab nativo;
- ou dependentes de uma bridge/fonte externa;
- até que uma função NTSL oficial adequada seja confirmada.

---

# 3. Matriz de candidatos

| ID | Indicador | Candle Lab | TradingView | Profit NTSL | Prioridade |
|---|---|---|---|---|---|
| CL-01 | Alinhamento preço × delta | Exato no recorte | Nativo com footprint, mas proxy | Nativo com agressão | Alta |
| CL-02 | Divergência preço × delta / absorção candidata | Exato + hipótese | Muito viável com footprint | Muito viável | Muito alta |
| CL-03 | Intensidade relativa da agressão | Exato | Viável | Viável | Alta |
| CL-04 | Rejeição de extremo com agressão | Exato por preço | Muito viável com footprint rows | Parcial/bar-level | Muito alta |
| CL-05 | Exaustão de onda agressora | Tick-level causal | Aproximação LTF/footprint | Aproximação/intrabar | Muito alta |
| CL-06 | Troca de controle BUY↔SELL | Tick-level causal | Aproximação LTF/footprint | Muito viável em fluxo agregado | Muito alta |
| CL-07 | Persistência de agressão no fechamento | Tick-level | Aproximação | Viável | Alta |
| CL-08 | Eficiência esforço × resultado | Exato | Viável | Viável | Muito alta |
| CL-09 | Estado composto de microestrutura | Exato | Viável com adaptações | Viável | Média/alta |
| CL-10 | Sinal calibrado pelas hipóteses históricas | Futuro | Viável após calibração | Viável após calibração | Posterior |
| CL-11 | Concentração por agente / fingerprint | Exato quando agente existe | Não nativo | Não confirmado em NTSL padrão | Pesquisa |
| CL-12 | Painel explicativo do candle | Exato | Viável parcialmente | Viável parcialmente | Média |

---

# 4. CL-01 — Alinhamento preço × delta

## Ideia

Responder:

> O preço e o lado agressor dominante caminharam na mesma direção?

Exemplos:

- candle de alta + delta positivo → alinhamento comprador;
- candle de baixa + delta negativo → alinhamento vendedor;
- candle de alta + delta negativo → divergência;
- candle de baixa + delta positivo → divergência.

## Métricas

- delta absoluto;
- delta normalizado;
- corpo do candle;
- close location;
- cobertura do dado;
- intensidade relativa.

Possível score:

```text
delta_normalizado = (buy - sell) / (buy + sell)

alinhamento =
sinal(delta_normalizado) × sinal(close - open)
```

## Visualização

- histograma de delta;
- cor de candle;
- marcador de alinhamento;
- tabela com BUY, SELL, delta e cobertura.

## TradingView

Usar `request.footprint()` quando disponível.

O nome do indicador deve deixar explícito que usa footprint do TradingView.

## Profit

Usar preferencialmente `AgressionVolBuy`, `AgressionVolSell` e/ou `AgressionVolBalance`.

---

# 5. CL-02 — Divergência preço × delta / absorção candidata

## Ideia

É um dos candidatos prioritários do projeto.

### Caso comprador

```text
candle sobe
+
delta é vendedor
```

Hipótese:

- venda agressora não conseguiu produzir queda;
- possível absorção por demanda passiva;
- perda de eficiência da venda.

### Caso vendedor

```text
candle cai
+
delta é comprador
```

## Filtros possíveis

- delta mínimo normalizado;
- cobertura mínima;
- corpo mínimo;
- close location;
- intensidade mínima;
- número mínimo de footprint imbalances;
- comparação com média histórica.

## Saída

Não chamar o evento de “absorção comprovada”.

Nome recomendado:

> Divergência preço × agressão — candidato a absorção

## Prioridade

Muito alta para validação histórica e implementação futura.

---

# 6. CL-03 — Intensidade relativa da agressão

## Ideia

Classificar se a agressão atual é pequena ou grande em relação ao contexto.

No Candle Lab a intensidade é comparada entre níveis dentro do candle.

Em plataformas com dados bar-level, uma versão alternativa pode comparar:

```text
agressão atual
vs.
distribuição histórica das últimas N barras
```

## Classes possíveis

- baixa;
- moderada;
- alta;
- extrema.

## Métodos possíveis

- percentil;
- mediana e MAD;
- z-score robusto;
- razão contra média/mediana.

## Uso

Serve como filtro para quase todos os demais indicadores.

---

# 7. CL-04 — Rejeição de extremo com agressão

## Ideia

Detectar situações em que há esforço agressor relevante na máxima/mínima, mas o preço fecha afastado do extremo.

### Rejeição de máxima

Possíveis condições:

- sombra superior relevante;
- forte buy volume perto da máxima;
- delta positivo no extremo;
- pouca permanência nos níveis altos;
- fechamento abaixo da máxima;
- possível término de onda BUY.

### Rejeição de mínima

Equivalente para venda.

## TradingView

É um dos indicadores mais promissores para `request.footprint()`, porque Pine pode acessar rows do footprint, volume e delta por faixa de preço.

## Profit

Uma versão bar-level é viável com volume agressor + geometria do candle.

Para reproduzir a localização exata por preço é necessário verificar quais funções do Profit/NTSL expõem informação granular equivalente.

---

# 8. CL-05 — Exaustão de onda agressora

## Ideia

Adaptar o modelo v0.16:

1. identificar dominância;
2. registrar pico da pressão;
3. medir queda da pressão;
4. exigir confirmações;
5. marcar término.

Modelo conceitual:

```text
PRESSÃO BUY
      ↑
     pico
      ↓
queda persistente
      ↓
EXAUSTÃO
```

## TradingView

Não presumir acesso ao mesmo fluxo negócio a negócio do Candle Lab.

Possíveis aproximações:

- footprints de sub-barras;
- `request.security_lower_tf()`;
- sequência de deltas de timeframe inferior;
- atualização realtime do footprint atual.

Versão histórica e versão realtime podem ter comportamento diferente.

## Profit

Pode usar séries de agressão nativas.

Ainda deve ser verificado se a lógica intrabar exata é reconstruível no histórico da estratégia ou se o indicador precisa operar por sub-barras.

---

# 9. CL-06 — Troca de controle BUY ↔ SELL

## Ideia

Detectar a transição:

```text
BUY dominante
→ neutralização
→ SELL dominante
```

ou o inverso.

## Variáveis

- dominância anterior;
- dominância atual;
- cobertura;
- intensidade;
- confirmações;
- velocidade da transição;
- posição no range.

## Sinal visual

- marcador BUY→SELL;
- marcador SELL→BUY;
- intensidade da troca;
- distância até máxima/mínima.

## Hipótese a validar

Trocas abruptas próximas a extremos podem ter comportamento diferente de neutralizações graduais.

---

# 10. CL-07 — Persistência da agressão no fechamento

## Ideia

No Candle Lab uma onda pode terminar como:

`ABERTA_NO_FIM_DO_CANDLE`

O indicador procuraria distinguir:

- candle que fecha com pressão ainda ativa;
- candle que fecha depois de a pressão ter terminado.

## Aplicação

Possível filtro de continuação.

Exemplo:

```text
candle fecha perto da máxima
+
delta comprador
+
pressão BUY ainda ativa
```

versus:

```text
candle fecha perto da máxima
+
onda BUY já terminou
```

Esses dois candles podem ter OHLC semelhante, mas microestrutura diferente.

---

# 11. CL-08 — Eficiência esforço × resultado

## Ideia

Medir quanto deslocamento de preço foi obtido por unidade de agressão.

Exemplos conceituais:

```text
muito BUY + grande alta = esforço eficiente
muito BUY + preço parado = esforço ineficiente
muito BUY + queda = divergência extrema
```

Possíveis métricas:

```text
eficiência_buy =
movimento_favorável_em_ticks / buy_volume

eficiência_delta =
deslocamento_líquido / abs(delta)
```

Melhor usar versões normalizadas/robustas para evitar divisão instável.

## Por que é prioritário

Essa métrica se conecta diretamente à pergunta:

> A agressão conseguiu produzir resultado no preço?

Pode ser uma forma mais robusta de operacionalizar “absorção” sem afirmar que observamos diretamente a liquidez passiva.

---

# 12. CL-09 — Estado composto de microestrutura

## Ideia

Em vez de um sinal binário, classificar o candle em estados.

Exemplo:

- BUY_IMPULSE;
- SELL_IMPULSE;
- BUY_EXHAUSTION;
- SELL_EXHAUSTION;
- BUY_ABSORPTION_CANDIDATE;
- SELL_ABSORPTION_CANDIDATE;
- CONTROL_HANDOFF;
- BALANCED_DISPUTE;
- LOW_INFORMATION.

## Variáveis

- delta;
- intensidade;
- eficiência esforço/resultado;
- close location;
- wick;
- footprint imbalance;
- estado de onda;
- cobertura.

## Uso

Pode funcionar como base para alertas e filtros de estratégia.

---

# 13. CL-10 — Indicador calibrado pela validação histórica

## Ideia

Este indicador **não deve ser implementado ainda**.

Ele só deve nascer depois que a biblioteca histórica produzir evidência suficiente.

Em vez de pesos escolhidos intuitivamente:

```text
score = 0,4 delta + 0,3 wick + 0,3 intensidade
```

os pesos devem ser derivados da validação do Candle Lab.

Exemplo futuro:

```text
REJEICAO_MAXIMA forte
+ TROCA_CONTROLE
+ delta extremo
+ contexto de volatilidade X
= score empiricamente calibrado
```

O indicador deverá preservar versão dos parâmetros e período usado na calibração.

---

# 14. CL-11 — Concentração por agente / fingerprint

## Ideia

Medir se poucos agentes concentram grande parte da agressão.

Métricas possíveis:

- participação do maior agressor;
- participação dos 3 maiores;
- HHI de concentração;
- persistência do mesmo agente entre níveis;
- entrada/saída do principal agressor;
- fingerprint de agente por horário/preço.

## Status

Extremamente interessante no Candle Lab.

### TradingView

Não há, nas capacidades Pine revisadas, identificação de corretora/agente negócio a negócio.

Não implementar como se essa informação existisse.

### Profit

O Times & Trades possui análise de players, mas a disponibilidade equivalente no Editor NTSL não foi confirmada na documentação padrão revisada.

Manter como pesquisa Candle Lab/bridge até confirmação oficial.

---

# 15. CL-12 — Painel explicativo do candle

## Ideia

Trazer parte do Relatório Interpretativo para a plataforma:

- delta;
- intensidade;
- divergência;
- estado da onda;
- eficiência;
- hipótese dominante;
- qualidade do dado.

Não é necessário reproduzir o texto completo.

Um painel compacto pode mostrar:

```text
Fluxo: SELL dominante
Delta: -4.820
Intensidade: extrema
Preço × delta: divergente
Onda: SELL exaurida
Hipótese: possível absorção vendedora
Qualidade: alta
```

---

# 16. Ordem recomendada de implementação

## Fase A — indicadores simples e verificáveis

1. CL-01 Alinhamento preço × delta
2. CL-03 Intensidade relativa
3. CL-08 Eficiência esforço × resultado

Objetivo: validar se TradingView e Profit reproduzem métricas básicas de forma coerente com o Candle Lab.

## Fase B — hipóteses centrais

4. CL-02 Divergência / absorção candidata
5. CL-04 Rejeição de extremo
6. CL-06 Troca de controle

## Fase C — dinâmica de ondas

7. CL-05 Exaustão
8. CL-07 Persistência no fechamento

## Fase D — composição

9. CL-09 Estado composto
10. CL-10 Score historicamente calibrado

## Pesquisa paralela

11. CL-11 Fingerprint por agente

---

# 17. Regras obrigatórias para qualquer implementação futura

Toda IA encarregada de escrever um indicador deve:

1. consultar a documentação atual da plataforma antes de programar;
2. informar a versão de Pine/NTSL usada;
3. não inventar funções;
4. não usar look-ahead;
5. explicar possibilidade de repaint;
6. distinguir agressão real de proxy;
7. não usar palavras como “absorção confirmada” sem dados que a comprovem;
8. permitir configuração dos limiares;
9. criar alertas apenas para eventos já confirmados;
10. indicar no código quais regras vieram do Candle Lab;
11. explicar quais partes não podem ser reproduzidas na plataforma;
12. produzir uma seção de validação e casos de teste;
13. não inserir ordens de compra/venda ou automação se a tarefa pediu apenas indicador;
14. manter os cálculos auditáveis.

---

# 18. Fontes oficiais consultadas

## TradingView

Pine Script — Other timeframes and data / `request.footprint()`:

https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/

Pine Script — Release notes:

https://www.tradingview.com/pine-script-docs/release-notes/

Pine Script — Limitations:

https://www.tradingview.com/pine-script-docs/writing/limitations/

## Nelogica

Manual NTSL oficial:

https://downloadserver-cdn.nelogica.com.br/content/profit/manual_ntsl/ManualNTSL.pdf

Página oficial da documentação NTSL:

https://ajuda.nelogica.com.br/hc/pt-br/articles/360046443212-Documenta%C3%A7%C3%A3o-NTSL-Compilado-de-fun%C3%A7%C3%B5es-e-instru%C3%A7%C3%B5es-de-usabilidade

Times & Trades:

https://ajuda.nelogica.com.br/hc/pt-br/articles/360054569632-Times-Trades


---

## Arquivo de entrada para as futuras IAs

Antes de solicitar a implementação de um candidato historicamente calibrado:

1. execute **Validação histórica das hipóteses**;
2. baixe o relatório JSON;
3. entregue o JSON junto com o prompt específico da plataforma;
4. exija que a IA descarte ou marque como exploratórias amostras insuficientes;
5. exija verificação da documentação oficial da plataforma;
6. mantenha uma etapa fora da amostra antes de qualquer uso operacional.

Os arquivos de prompts são:

- `prompts/PROMPTS-TRADINGVIEW-PINE-CANDLE-LAB.md`;
- `prompts/PROMPTS-PROFIT-NTSL-CANDLE-LAB.md`.
