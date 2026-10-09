# Tutorial — capturar liquidez passiva do Profit Ultra para o Candle Lab

Atualizado em 08/10/2026.

## Objetivo

Este tutorial responde a uma pergunta específica:

> O Profit Ultra consegue fornecer dados do Livro de Ofertas / DOM / profundidade de mercado para estudarmos liquidez passiva no Candle Lab?

A resposta é **sim para dados em tempo real**, mas com uma limitação importante: **a documentação oficial consultada não mostra uma exportação nativa do histórico completo do book de pregões passados para CSV, nem uma reconstrução retroativa de MBP/MBO pelo Replay de Mercado**.

Portanto, há três situações diferentes:

1. **Trades históricos** — o Profit consegue exportar; é o que o Candle Lab já usa.
2. **Book em tempo real** — o Profit pode disponibilizar por RTD/DDE, e a ProfitDLL oferece callbacks próprios de profundidade e ofertas.
3. **Histórico completo do book anterior ao início da coleta** — não há evidência, na documentação oficial consultada, de exportação retroativa nativa pelo Profit Ultra.

---

## O que a documentação oficial confirma

### Exportação histórica nativa

A opção **Exportar Dados Históricos** do Profit exporta candles e também intervalos de Trades. Para WIN, a documentação informa limite histórico de Trades de 8 dias.

Ela não documenta exportação do histórico do Livro de Ofertas, da fila ou de eventos add/edit/delete das ofertas.

Fonte oficial:

- https://ajuda.nelogica.com.br/hc/pt-br/articles/360044287672-Como-exportar-dados-hist%C3%B3ricos-de-ativos-para-o-Excel

### Replay de Mercado

O Replay utiliza os negócios/trades do dia solicitado. A própria documentação informa que a reprodução não considera as condições de fila e liquidez que existiam em tempo real.

Isso significa que o Replay é útil para reexaminar execuções, mas **não serve para reconstruir fielmente o book passivo histórico**.

Fonte oficial:

- https://ajuda.nelogica.com.br/hc/pt-br/articles/360043469772-Replay-de-Mercado

### Livro de Ofertas

O Livro de Ofertas mostra as ordens de compra e venda disponíveis e sua profundidade. É exatamente a informação que queremos estudar para absorção, reposição e retirada de liquidez.

Fonte oficial:

- https://ajuda.nelogica.com.br/hc/pt-br/articles/360049025732-Livro-de-ofertas

### RTD/DDE

O Profit possui exportação em tempo real por RTD/DDE. A documentação oficial menciona explicitamente janelas vinculadas de **Times & Trades ou Livro de Ofertas**.

Portanto, é possível usar o Livro de Ofertas como uma fonte **ao vivo** para Excel/LibreOffice. Isso não cria sozinho um histórico: é necessário registrar sucessivos estados em outro arquivo ou programa.

Fonte oficial:

- https://ajuda.nelogica.com.br/hc/pt-br/articles/360044293432-Como-configurar-RTD-DDE-no-Profit

### Mapa de Fluxo

O Profit possui uma ferramenta chamada **Mapa de Fluxo**, que mostra liquidez atual e passada dentro da própria ferramenta, junto com agressões e volume. É muito útil para inspeção visual.

A documentação consultada não descreve exportação dessa série histórica do Mapa de Fluxo para um arquivo que possamos importar diretamente no Candle Lab.

Fonte oficial:

- https://ajuda.nelogica.com.br/hc/pt-br/articles/360047356632-Mapa-de-Fluxo

### BookMap

O BookMap do Profit é um módulo opcional. Ele registra o book apenas depois que a ferramenta é aberta, não carrega book retroativo anterior à abertura e mantém aproximadamente duas horas de histórico visível.

Por isso, ele pode ser útil para comparação visual, mas não resolve sozinho a criação de uma biblioteca histórica longa para o Candle Lab.

Fontes oficiais:

- https://ajuda.nelogica.com.br/hc/pt-br/articles/48881247357211-Como-funciona-o-Plugin-BookMap
- https://ajuda.nelogica.com.br/hc/pt-br/articles/49139017160603-Como-visualizar-o-hist%C3%B3rico-do-book-com-o-BookMap

### ProfitDLL

A ProfitDLL é uma solução contratada separadamente. Ela permite:

- `SubscribePriceDepth`: profundidade agregada por preço — equivalente ao que queremos chamar de MBP;
- `SubscribeOfferBook`: ofertas individuais, com agente, lado, posição, preço, quantidade e eventos add/edit/delete — uma fonte muito mais granular para reconstrução do livro.

A documentação classifica ambos como **tempo real**. Há função própria para histórico de trades, mas não foi encontrada função equivalente para solicitar retroativamente o histórico completo do book.

Fontes oficiais:

- https://ajuda.nelogica.com.br/hc/pt-br/articles/11168755650459-Fun%C3%A7%C3%B5es-Real-Time-DLL
- https://ajuda.nelogica.com.br/hc/pt-br/articles/22396517026203-Ecossistema-ProfitDLL-e-primeiros-passos
- https://ajuda.nelogica.com.br/hc/pt-br/articles/51583791325211-Como-obter-acesso-%C3%A0-ProfitDLL

---

# Caminho recomendado sem contratar uma nova fonte de dados

Para o Candle Lab, o primeiro experimento deve usar o que já está disponível no Profit Ultra: **Livro de Ofertas + RTD/DDE**.

O objetivo inicial não é produzir uma base perfeita de MBO. É validar se conseguimos registrar, junto aos Trades, estados sucessivos da liquidez passiva com timestamps suficientemente úteis.

## Etapa 1 — abra o contrato correto

1. Abra o Profit Ultra no Windows.
2. Use o contrato específico que está sendo negociado, por exemplo `WINV26`.
3. Não use outro vencimento ao mesmo tempo no experimento.
4. Confirme que o Times & Trades e o gráfico estão apontando para o mesmo ativo.

## Etapa 2 — abra o Livro de Ofertas

1. No Profit, abra **Ferramentas → Livro de Ofertas**.
2. Selecione `WINV26`.
3. Para o primeiro teste, mantenha visíveis os níveis próximos ao melhor bid e ao melhor ask.
4. Não aplique filtros por player ou quantidade no primeiro experimento. Queremos primeiro observar o livro sem filtros adicionais.

O livro deve mostrar pelo menos:

- lado compra/venda;
- preço;
- quantidade;
- número/posição da oferta quando disponível;
- agente, quando o modo escolhido disponibilizar essa informação.

## Etapa 3 — habilite a exportação em tempo real

1. No menu principal do Profit, abra **Arquivo → Exportar em Tempo Real (RTD/DDE)**.
2. Ative a transferência de dados.
3. Se utilizar Microsoft Excel, escolha preferencialmente **RTD**.
4. Se utilizar LibreOffice, use **DDE**, conforme as opções disponibilizadas pelo Profit.
5. Mantenha apenas uma exportação em tempo real ativa por vez, porque a própria documentação da Nelogica informa essa limitação.

## Etapa 4 — vincule o Livro de Ofertas

A documentação da Nelogica confirma que o RTD/DDE aceita uma janela de **Livro de Ofertas** vinculada.

A posição exata do comando pode variar entre builds do Profit. Com o Livro aberto:

1. procure no menu de contexto da janela ou em suas opções a função de vincular/exportar a janela para Excel;
2. procure nomes como **Linkar Janela com Excel (RTD)** ou **Exportar em Tempo Real (RTD/DDE)**;
3. gere/copiei o vínculo;
4. cole no Excel;
5. mantenha a janela do Livro de Ofertas aberta no Profit.

Se aparecer a mensagem de que a janela vinculada foi fechada, reabra o mesmo Livro de Ofertas antes de continuar.

## Etapa 5 — confirme que os dados são realmente dinâmicos

No Excel:

1. observe o melhor bid e o melhor ask;
2. espere alguns segundos durante o pregão;
3. confirme que preço e quantidade mudam automaticamente;
4. compare visualmente uma ou duas mudanças com o Livro aberto no Profit.

Não prossiga para armazenamento se o Excel estiver apenas mostrando valores estáticos.

## Etapa 6 — faça um teste curto de captura

Para o primeiro experimento, escolha um intervalo de apenas **5 a 10 minutos**.

Durante esse período:

1. mantenha Profit e Excel abertos;
2. não mude o ativo;
3. não troque a aba do Livro vinculada;
4. mantenha o Times & Trades sendo coletado/exportado separadamente;
5. anote o horário de início e de fim.

O RTD mostra o estado atual da janela; ele não cria automaticamente uma linha histórica para cada alteração. Para formar uma base para o Candle Lab, um registrador deverá copiar sucessivos estados do RTD para um arquivo append-only.

---

# Formato que o Candle Lab deverá gravar

Para uma captura de profundidade agregada por preço, o formato mínimo recomendado é:

```text
timestamp
symbol
side
level
price
quantity
orders
source
```

Exemplo:

```csv
2026-10-08T10:31:02.120-03:00,WINV26,BID,1,205910,180,12,profit_rtd
2026-10-08T10:31:02.120-03:00,WINV26,ASK,1,205915,240,18,profit_rtd
2026-10-08T10:31:02.120-03:00,WINV26,BID,2,205905,350,25,profit_rtd
2026-10-08T10:31:02.120-03:00,WINV26,ASK,2,205920,190,14,profit_rtd
```

Se futuramente usarmos `SubscribeOfferBook` da ProfitDLL, o formato deve ser orientado a eventos:

```text
timestamp
symbol
action          # ADD / EDIT / DELETE / FLUSH
side            # BID / ASK
price
quantity
position
agent
order_id        # quando disponível
source
```

Esse segundo formato é muito mais adequado para reconstruir a fila.

---

# O que conseguiremos medir com snapshots de profundidade

Mesmo sem MBO completo, sucessivos estados do MBP permitem estimar:

- liquidez disponível no bid e no ask;
- desequilíbrio de profundidade;
- surgimento e desaparecimento de paredes;
- consumo aparente de liquidez;
- reposição de liquidez após agressões;
- retirada de liquidez sem execução;
- spread;
- velocidade de mudança da profundidade;
- relação entre agressão e resposta do livro.

Exemplo:

```text
Ask 205.915 antes:       500
Compra agressora:        180
Ask 205.915 depois:      470
```

Se nenhuma nova oferta tivesse entrado, esperaríamos aproximadamente 320 contratos restantes. Como vemos 470, há evidência de cerca de 150 contratos de reposição líquida observada entre os estados.

Essa conta é uma **estimativa de snapshots**, não uma reconstrução evento a evento. Cancelamentos, novas ordens e execuções podem ter ocorrido entre duas observações.

---

# Limitação crítica do RTD/DDE

Para pesquisa de microestrutura, não devemos tratar o RTD/DDE como equivalente a um feed MBO.

Se o book mudar várias vezes entre duas leituras do nosso registrador, eventos intermediários podem desaparecer.

Por isso, os dados precisam receber metadados de qualidade:

```text
capture_mode = SNAPSHOT
requested_interval_ms = ...
observed_interval_ms = ...
dropped_or_unknown_events = true
depth_levels = ...
```

O Candle Lab deve separar claramente:

- `TRADES_EXECUTED`: negócios realmente executados;
- `BOOK_SNAPSHOT`: fotografia da liquidez em um instante;
- `BOOK_EVENT`: evento individual add/edit/delete, quando futuramente disponível;
- `INFERRED_LIQUIDITY_EVENT`: evento inferido pela diferença entre snapshots.

Nunca devemos misturar esses quatro conceitos.

---

# Caminho ideal para pesquisa de alta fidelidade

Se em algum momento houver acesso à ProfitDLL, o caminho tecnicamente mais adequado será:

1. inicializar a DLL em modo Market Data;
2. assinar o contrato específico;
3. usar `SubscribeTicker` para os trades;
4. usar `SubscribePriceDepth` para profundidade agregada;
5. usar `SubscribeOfferBook` se quisermos ofertas individuais;
6. enfileirar os callbacks imediatamente;
7. persistir os eventos em uma thread/processo separado;
8. sincronizar tudo por timestamp;
9. importar esse log no Candle Lab.

O callback do livro de ofertas informa ações como add/edit/delete. Isso permite estudar reposição, retirada e permanência das ordens de forma muito superior a snapshots de Excel.

A ProfitDLL, porém, é um produto contratado separadamente. A assinatura Profit Ultra, por si só, não deve ser presumida como licença da DLL.

---

# Conclusão para o Candle Lab

Para **pregões passados que já terminaram**, a documentação oficial pesquisada não oferece um caminho nativo no Profit Ultra para baixar um CSV completo do book histórico que existia naquele momento.

Para **pregões futuros**, podemos começar a formar nossa própria biblioteca:

```text
Profit Ultra
    │
    ├── Trades exportados → Candle Lab
    │
    └── Livro de Ofertas em tempo real
               │
             RTD/DDE
               │
        registrador de snapshots
               │
        arquivo de profundidade
               │
            Candle Lab
```

Isso permite iniciar a pesquisa sem contratar imediatamente uma fonte histórica de MBO.

A primeira meta deve ser pequena: **capturar 5–10 minutos de WIN, sincronizar Book + Trades e verificar se conseguimos identificar consumo, reposição e retirada de liquidez em torno de um candle selecionado**.

Se esse experimento funcionar e a resolução do RTD for suficiente, expandimos a coleta. Se ficar claro que eventos importantes são perdidos entre snapshots, a arquitetura já estará pronta para substituir a entrada RTD por um feed evento a evento no futuro.
