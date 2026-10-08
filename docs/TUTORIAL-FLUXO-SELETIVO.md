# Tutorial — fluxo seletivo do Candle Lab v0.14

Este é o fluxo recomendado para analisar um pregão real sem armazenar um arquivo Tick by Tick gigantesco dentro do Candle Lab.

A ideia é simples:

```text
1. ver o dia inteiro em candles de 1 ou 2 minutos
2. escolher visualmente o trecho interessante
3. usar o CSV grande de Trades apenas como fonte
4. extrair somente aquele intervalo
5. analisar a microestrutura do recorte
```

## O que você precisa ter

Do Profit, mantenha dois arquivos:

- um CSV leve do pregão em **1 minuto** ou **2 minutos**;
- o CSV grande de **Trades/Tick by Tick** do mesmo contrato e pregão.

O CSV grande pode continuar em qualquer pasta do seu computador. Não é necessário copiá-lo para dentro do projeto.

## Passo 1 — iniciar o Candle Lab

Abra a pasta do projeto e dê dois cliques em:

```text
iniciar.bat
```

A interface abrirá no navegador em:

```text
http://127.0.0.1:8765
```

## Passo 2 — importar o gráfico diário

Na seção **1 — Importar gráfico diário**:

1. selecione o CSV de candles exportado pelo Profit;
2. informe o contrato real, por exemplo `WINV26`;
3. confirme o tick size;
4. escolha o intervalo usado na exportação:
   - 60 segundos = 1 minuto;
   - 120 segundos = 2 minutos;
5. clique em **Importar gráfico**.

O arquivo de 1 ou 2 minutos é pequeno e passa a ser a visão geral do pregão.

## Passo 3 — visualizar o pregão inteiro

Na seção **2 — Visão geral do pregão**:

1. escolha o ativo;
2. escolha o pregão/timeframe;
3. observe o gráfico completo de candles.

O gráfico diário funciona mesmo que nenhum Tick by Tick tenha sido importado.

## Passo 4 — selecionar os candles com precisão

A interface oferece três métodos complementares:

1. **Clique e arraste** para criar rapidamente uma seleção;
2. **Marcadores INÍCIO/FIM**: depois que a seleção existe, arraste cada marcador até a fronteira desejada;
3. **Campos de horário**: digite, por exemplo, `14:40` e `14:50` e clique em **Aplicar horários**.

Também há controles de zoom:

- `−` e `+`;
- controle deslizante;
- `◀` e `▶` para mover a janela;
- **Mostrar dia inteiro**;
- **Zoom na seleção**;
- `Ctrl + roda do mouse` sobre o gráfico.

Quanto maior o zoom, menos candles ficam visíveis e mais marcações de horário aparecem no eixo horizontal.

Ao confirmar uma seleção, o Candle Lab mostra hora inicial, hora final e quantidade de candles.

Exemplo:

```text
14:40:00 → 14:50:00
10 candles
```

O intervalo é tratado como:

```text
[início, fim)
```

Ou seja, no exemplo acima entram negócios a partir de 14:40:00 e anteriores a 14:50:00. Negócios de 14:50:00 pertencem ao candle seguinte e não entram no recorte.

### Tamanho recomendado

Para investigação detalhada, comece com algo entre **5 e 30 minutos**.

A interface aceita intervalos maiores, mas o objetivo do fluxo seletivo é justamente evitar processar e armazenar dados de que você não precisa.

## Passo 5 — localizar o CSV grande de Trades

No Explorador de Arquivos do Windows:

1. localize o CSV grande de Trades;
2. clique com o botão direito;
3. escolha **Copiar como caminho**.

Dependendo da versão do Windows, talvez seja necessário manter Shift pressionado para essa opção aparecer.

Você obterá algo parecido com:

```text
"C:\Users\pablo\Documents\Dados\WINV26_2026-10-07_TRADES.csv"
```

Não há problema se o caminho vier entre aspas.

## Passo 6 — colar o caminho no Candle Lab e preparar o índice

Na seção **3 — Localizar as linhas no CSV Tick by Tick**:

1. cole o caminho;
2. confira o tick size;
3. clique em **Preparar índice e localizar**;
4. aguarde a primeira indexação daquele arquivo;
5. confira a tabela de linhas de cada candle.

O Candle Lab não envia esse arquivo para a internet.

Como o servidor do aplicativo está rodando localmente no mesmo computador, ele abre o arquivo diretamente do disco. Na primeira utilização, lê o arquivo uma vez para criar um índice M1 com linhas e offsets de byte. Nas seleções seguintes, reutiliza esse índice.

## Passo 7 — como o índice localiza os candles

Para um arquivo descendente do Profit, o programa:

1. identifica o layout;
2. identifica o contrato;
3. detecta que os horários estão do mais recente para o mais antigo;
4. ignora as linhas posteriores ao intervalo;
5. copia somente as linhas pertencentes ao trecho escolhido;
6. para de ler assim que passa do início do intervalo;
7. grava o pequeno recorte em:

```text
data\slices
```

Por exemplo:

```text
data\slices\WINV26_20261007-144000_145000_TRADES.csv
```

Esse arquivo preserva a ordem original do Profit. O importador normaliza essa ordem apenas na camada analítica.

## Passo 8 — gerar o recorte e abrir a Biblioteca de microestrutura

Depois que a tabela de linhas estiver correta, clique em **Recortar e importar intervalo localizado**. O Candle Lab usa os offsets de byte para saltar diretamente ao trecho necessário. Em seguida, vá à seção **Biblioteca de microestrutura**.

Selecione:

- o ativo;
- o pregão;
- o timeframe.

Os candles correspondentes ao trecho aparecerão.

Clique em um deles para abrir:

- replay negócio a negócio;
- trajetória intrabar;
- Times & Trades;
- volume por preço;
- agressão;
- DNA;
- simulação contrafactual;
- pesquisa comparativa.

## Passo 9 — manter ou apagar o recorte

Os arquivos em:

```text
data\slices
```

são derivados do CSV grande original.

Você pode mantê-los para voltar àquela análise depois ou apagá-los para economizar espaço.

Se forem apagados, basta selecionar novamente o mesmo trecho e recriá-los.

## O que NÃO é mais necessário

Para o uso cotidiano, você não precisa:

- importar os 726 MB inteiros para o DuckDB;
- criar Parquet do pregão inteiro;
- manter duplicada toda a base Tick;
- validar todos os 565 candles antes de estudar um trecho.

A ingestão integral criada na v0.11 continua disponível apenas para auditorias, testes de consistência e pesquisas que realmente precisem do dia completo em Tick by Tick.

## Quando usar 1 minuto ou 2 minutos?

Use **1 minuto** quando quiser localizar movimentos com maior precisão.

Use **2 minutos** quando preferir um gráfico diário mais compacto.

A microestrutura do recorte continua vindo dos Trades reais; o timeframe da visão geral apenas ajuda a escolher o trecho.

## Problemas comuns

### “Nenhum negócio foi encontrado”

Confira:

- contrato;
- data;
- intervalo selecionado;
- se o CSV grande corresponde ao mesmo pregão.

### “Arquivo não encontrado”

Use novamente **Copiar como caminho** e cole o caminho completo.

### O gráfico diário aparece, mas a Biblioteca está vazia

Isso é normal antes do passo 6.

O gráfico diário vem do CSV OHLC. A Biblioteca de microestrutura só recebe dados depois que você cria um recorte Tick.

### Posso usar o arquivo de 726 MB novamente?

Sim. Ele funciona como fonte permanente. Você pode criar quantos recortes quiser sem modificá-lo.


## Recortes sobrepostos

Você pode estudar intervalos que se sobreponham.

Exemplo:

```text
primeiro recorte: 14:40–14:50
segundo recorte: 14:45–15:00
```

O Candle Lab identifica cada ocorrência pela impressão digital rápida da fonte original e pela posição da linha no CSV grande. Os negócios de 14:45–14:50 já existentes não são inseridos novamente.

## Vários recortes separados no mesmo dia

Também é permitido estudar, por exemplo:

```text
10:00–10:10
14:40–14:50
```

A reconciliação seletiva compara apenas os candles efetivamente importados. O período intermediário não é tratado como erro ou `NO_DATA`, pois sua ausência foi intencional.


## Índice temporal persistente

O índice fica em:

~~~text
data\indexes
~~~

Ele é pequeno e pode ser reutilizado para todas as seleções futuras do mesmo CSV original.

Para detalhes sobre a regra candle → linhas → bytes, veja:

~~~text
docs\INDICE-TEMPORAL-LINHAS.md
docs\TUTORIAL-LOCALIZAR-LINHAS.md
~~~
