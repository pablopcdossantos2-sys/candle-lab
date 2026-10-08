# Tutorial — da hipótese do Candle Lab ao indicador

Este tutorial descreve o fluxo recomendado para transformar uma hipótese pesquisada no Candle Lab em um futuro indicador para TradingView ou Profit Pro.

Nenhum dos passos abaixo cria automaticamente uma estratégia de compra e venda. O objetivo é preservar a sequência:

```text
observação
→ hipótese
→ validação histórica
→ seleção de candidato
→ especificação
→ implementação do indicador
→ validação fora da amostra
```

## 1. Construa uma biblioteca real

Importe recortes Tick by Tick reais e, sempre que possível, a referência OHLC/Quantidade correspondente.

A validação ganha qualidade quando:

- há muitos candles reais;
- as ocorrências estão distribuídas em vários pregões;
- existem diferentes horários e regimes;
- a reconstrução pode ser reconciliada com referência externa.

Dados sintéticos são excluídos por padrão da validação histórica.

## 2. Abra a Validação histórica das hipóteses

Na interface do Candle Lab:

1. escolha o ativo;
2. escolha o timeframe;
3. abra **Validação histórica das hipóteses**;
4. informe horizontes, por exemplo `1,3,5`;
5. clique em **Validar hipóteses na biblioteca**.

O Candle Lab irá regenerar as interpretações dos candles elegíveis e medir o comportamento posterior.

## 3. Leia primeiro N e o status da amostra

Não comece pelo maior percentual.

Observe:

- N;
- status da amostra;
- taxa direcional;
- baseline;
- lift;
- IC Wilson 95%;
- excursão favorável;
- excursão adversa.

Rótulos atuais:

```text
N < 30       AMOSTRA_INSUFICIENTE
30–99        EXPLORATORIA
100–499      PRELIMINAR
>= 500       AMOSTRA_MAIOR
```

Esses estados não são certificados de vantagem operacional.

## 4. Entenda o baseline

Exemplo:

```text
REJEICAO_MAXIMA
horizonte 3 candles
taxa DOWN = 61%
baseline DOWN = 49%
lift = +12 p.p.
```

O dado relevante não é apenas “61%”, mas quanto ele difere do comportamento normal da biblioteca.

## 5. Observe o intervalo de confiança

Uma taxa alta com poucos casos pode ter um intervalo de confiança muito amplo.

Evite promover um candidato quando o resultado depender de poucas ocorrências.

## 6. Baixe o relatório JSON

Depois que a validação terminar, clique em:

```text
Baixar relatório JSON
```

O arquivo inclui:

- versão do modelo;
- ativo;
- timeframe;
- modo de referência;
- baselines;
- exclusões;
- ocorrências;
- resultados direcionais;
- horizontes;
- taxas;
- lift;
- IC 95%;
- excursões;
- advertências.

Guarde esse JSON junto com a especificação futura do indicador.

## 7. Consulte o catálogo de candidatos

Leia:

```text
docs/INDICADORES-POSSIVEIS-CANDLE-LAB.md
```

O catálogo organiza os candidatos CL-01 a CL-12 e explica quais são:

- prioritários;
- reproduzíveis;
- aproximáveis;
- dependentes de dados que a plataforma pode não expor.

## 8. Escolha a plataforma

### TradingView

Use:

```text
prompts/PROMPTS-TRADINGVIEW-PINE-CANDLE-LAB.md
```

O pacote contém um PROMPT BASE e prompts específicos dos candidatos.

Para um indicador calibrado, forneça também o JSON e use o **PROMPT DE INTEGRAÇÃO COM RELATÓRIO HISTÓRICO DO CANDLE LAB**.

### Profit Pro / NTSL

Use:

```text
prompts/PROMPTS-PROFIT-NTSL-CANDLE-LAB.md
```

Também entregue o JSON e use o prompt de integração histórica.

## 9. O que enviar para a IA

Envie juntos:

1. o prompt específico do indicador;
2. o PROMPT BASE da plataforma;
3. o JSON da validação histórica;
4. esta instrução adicional:

> Não escreva código antes de verificar a documentação oficial atual da plataforma e antes de indicar quais variáveis do Candle Lab são NATIVAS, PROXY ou INDISPONÍVEIS.

## 10. Não force equivalência entre fontes

O Candle Lab pode trabalhar com agressor real informado pelo CSV do Profit.

O TradingView footprint classifica buy/sell com metodologia própria da plataforma.

O Profit/NTSL possui funções agregadas de agressão, mas isso não significa automaticamente que toda sequência Tick by Tick ou identidade de agente do Candle Lab esteja disponível ao script.

Portanto, a IA deve declarar diferenças semânticas.

## 11. Exija modo diagnóstico

Todo indicador futuro deve permitir verificar:

- quais condições dispararam;
- valores das métricas;
- limiares;
- disponibilidade da fonte;
- estado da máquina de ondas, quando existir.

O objetivo é permitir comparação com o Candle Lab.

## 12. Valide fora da amostra

Depois que um indicador for criado:

1. congele parâmetros;
2. escolha período não usado para definir as regras;
3. compare sinais com o Candle Lab;
4. compare resultado com baseline;
5. procure divergências entre plataforma e fonte original;
6. só depois considere nova calibração.

Não ajuste repetidamente o indicador no mesmo histórico até obter um resultado bonito.

## 13. Ordem recomendada

Comece pelos candidatos mais simples e auditáveis:

```text
CL-01 Alinhamento preço × delta
CL-03 Intensidade relativa
CL-08 Eficiência esforço × resultado
```

Depois:

```text
CL-02 Divergência / absorção candidata
CL-04 Rejeição de extremo
CL-06 Troca de controle
```

Em seguida:

```text
CL-05 Exaustão
CL-07 Persistência no fechamento
```

Somente depois combine os módulos em estados compostos ou scores historicamente calibrados.

## 14. Regra de promoção de um indicador

Um candidato não deve ser promovido apenas porque:

- possui alto score interno;
- teve poucos casos muito bons;
- parece intuitivo;
- funciona em um único pregão;
- apresenta lift positivo in-sample.

A promoção deve considerar, no mínimo:

- amostra;
- baseline;
- intervalo de confiança;
- estabilidade;
- fidelidade da variável na plataforma;
- validação fora da amostra.

## 15. Arquivos desta etapa

```text
docs/VALIDACAO-HISTORICA-HIPOTESES.md
docs/INDICADORES-POSSIVEIS-CANDLE-LAB.md
docs/TUTORIAL-VALIDACAO-E-INDICADORES.md
prompts/PROMPTS-TRADINGVIEW-PINE-CANDLE-LAB.md
prompts/PROMPTS-PROFIT-NTSL-CANDLE-LAB.md
```

Esses documentos formam o pacote de pesquisa e especificação anterior à implementação dos indicadores.
