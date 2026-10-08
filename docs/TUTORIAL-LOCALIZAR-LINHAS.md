# Tutorial — localizar as linhas dos candles no CSV grande

Este tutorial cobre a v0.14 do Candle Lab.

## 1. Importe o gráfico diário

Use o CSV de 1 ou 2 minutos exportado do Profit. O Candle Lab exibirá o pregão completo.

## 2. Selecione os candles

Você pode:

- clicar e arrastar;
- aumentar o zoom e mover a janela do gráfico;
- arrastar os marcadores **INÍCIO** e **FIM**;
- digitar diretamente os horários nos campos **Início** e **Fim**.

Exemplo: digite `14:40` e `14:50`, clique em **Aplicar horários** e, se desejar, use **Zoom na seleção** para conferir os limites.

## 3. Cole o caminho do CSV Tick by Tick

No Explorador do Windows, use Copiar como caminho no arquivo original e cole o caminho na seção Localizar as linhas no CSV Tick by Tick.

## 4. Clique em Preparar índice e localizar

Na primeira utilização daquele arquivo, o Candle Lab lê o CSV completo uma vez para construir o índice. Nas próximas seleções, o índice é reutilizado.

## 5. Leia a tabela

A tabela informa, candle a candle:

- linhas físicas do CSV;
- linha cronológica da abertura;
- linha cronológica do fechamento;
- número real de negócios;
- faixa de bytes.

Em arquivo descendente, a linha da abertura pode ter número maior do que a linha do fechamento.

## 6. Gere o recorte

Clique em Recortar e importar intervalo localizado. O programa usa os offsets de byte para saltar diretamente à região correta.

## 7. Analise os candles

Na Biblioteca de microestrutura, clique nos candles importados para abrir replay, DNA e volume por preço.

## Onde o índice fica?

~~~text
data\indexes
~~~

O índice pode ser mantido mesmo que você apague os recortes de data\slices. Se o arquivo original for alterado, o Candle Lab detectará a mudança e criará um novo índice.