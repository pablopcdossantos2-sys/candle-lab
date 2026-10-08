# Tutorial de instalação e uso — Candle Lab B3

Este é o tutorial recomendado para usuários do Windows que não têm familiaridade com terminal, Python ou GitHub.

O fluxo normal do Candle Lab é:

~~~text
CSV leve de candles de 1/2 minutos
        ↓
gráfico diário
        ↓
seleção do intervalo
        ↓
índice do CSV Tick by Tick
        ↓
linhas e bytes exatos
        ↓
recorte pequeno
        ↓
laboratório de microestrutura
~~~

O arquivo Tick by Tick grande pode continuar no local original do computador. O Candle Lab não precisa guardar uma segunda cópia integral dele.

---

## Parte 1 — instalar o Candle Lab

### 1. Instalar o Python

O Candle Lab requer Python 3.11 ou superior.

1. Acesse o site oficial do Python.
2. Baixe uma versão atual do Python 3 para Windows.
3. Execute o instalador.
4. Quando a opção aparecer, marque **Add Python to PATH**.
5. Conclua a instalação.

Depois disso, não é necessário abrir Python manualmente.

### 2. Baixar o projeto do GitHub

1. Abra a página do repositório Candle Lab.
2. Clique em **Code**.
3. Escolha **Download ZIP**.
4. Salve o arquivo.
5. Clique com o botão direito no ZIP e escolha **Extrair tudo**.
6. Abra a pasta extraída.

Não é necessário instalar Git para esse procedimento.

### 3. Primeira execução

Dentro da pasta do projeto, dê dois cliques em:

~~~text
iniciar.bat
~~~

Na primeira execução, o iniciador faz automaticamente:

1. verifica se o Python está disponível;
2. cria a pasta local `.venv`;
3. instala as dependências;
4. inicia o servidor local;
5. abre o navegador em `http://127.0.0.1:8765`.

A instalação das dependências exige conexão com a internet na primeira vez.

Se o iniciador disser que Python não foi encontrado, instale o Python e execute `iniciar.bat` novamente.

### 4. Execuções seguintes

Nas próximas vezes, basta dar dois cliques em:

~~~text
iniciar.bat
~~~

Não é necessário repetir a instalação.

Mantenha a janela preta do Candle Lab aberta enquanto estiver usando a ferramenta. Para encerrar, volte a essa janela e pressione **Ctrl+C**.

---

## Parte 2 — arquivos necessários

Para o fluxo seletivo, mantenha dois arquivos exportados do Profit para o mesmo contrato e pregão:

1. um CSV leve de candles de **1 minuto** ou **2 minutos**;
2. o CSV grande de **Trades / Tick by Tick**.

Exemplo:

~~~text
WINV26_2026-10-07_1MIN.csv
WINV26_2026-10-07_TRADES.csv
~~~

O CSV grande pode ter centenas de MB. Não é necessário copiá-lo para a pasta do Candle Lab.

---

## Parte 3 — importar o gráfico diário

Na seção **1 — Importar gráfico diário**:

1. clique no campo do CSV;
2. selecione o arquivo de candles de 1 ou 2 minutos;
3. informe o contrato real, por exemplo `WINV26`;
4. confirme o tick size;
5. informe o timeframe usado no arquivo:
   - 60 segundos = 1 minuto;
   - 120 segundos = 2 minutos;
   - 300 segundos = 5 minutos;
   - 900 segundos = 15 minutos;
6. clique em **Importar gráfico**.

Esse arquivo será usado para mostrar o dia inteiro e como referência OHLC.

---

## Parte 4 — escolher o intervalo no gráfico

Vá à seção **2 — Gráfico diário para seleção**.

Há três maneiras de definir o intervalo. Elas podem ser combinadas.

### Método A — clique simples ou clique e arraste

- Um **clique simples** cria inicialmente uma seleção de um único candle e faz aparecer os marcadores INÍCIO/FIM.
- Para criar uma faixa de uma vez, mantenha o botão esquerdo pressionado e arraste do primeiro ao último candle.

Depois disso, os limites podem ser corrigidos pelos marcadores, sem precisar repetir o clique inicial.

### Método B — usar os marcadores INÍCIO e FIM

Depois que existe uma seleção, aparecem dois marcadores verticais:

~~~text
INÍCIO 14:40
FIM    14:50
~~~

Para corrigir um dos limites:

1. coloque o mouse sobre o marcador;
2. mantenha o botão esquerdo pressionado;
3. arraste o marcador para a esquerda ou para a direita;
4. solte quando chegar ao candle desejado.

Isso evita ter que tentar clicar repetidamente exatamente no minuto correto.

### Método C — digitar os horários

Acima do gráfico existem os campos:

~~~text
Início
Fim
~~~

Exemplo:

~~~text
Início: 14:40
Fim:    14:50
~~~

Digite os dois horários e clique em **Aplicar horários**.

A área correspondente será selecionada automaticamente no gráfico e os marcadores serão posicionados nos limites.

Os horários precisam coincidir com as fronteiras do timeframe exibido. Em um gráfico de 2 minutos, por exemplo, um horário que caia entre duas fronteiras de candle não será aceito como limite exato.

---

## Parte 5 — usar o zoom

A barra acima do gráfico contém:

- **−**: diminuir o zoom;
- controle deslizante de zoom;
- **+**: aumentar o zoom;
- **◀ / ▶**: mover a janela visível para horários anteriores ou posteriores;
- **Mostrar dia inteiro**: voltar ao pregão completo;
- **Zoom na seleção**: centralizar e ampliar o intervalo escolhido.

Também é possível manter **Ctrl** pressionado e usar a roda do mouse sobre o gráfico para aumentar ou diminuir o zoom.

Quando o zoom aumenta, menos candles ficam visíveis e o eixo horizontal passa a mostrar **mais marcações de horário relativas à região exibida**.

O zoom muda apenas a visualização. Ele não altera os dados nem o intervalo selecionado.

---

## Parte 6 — entender o intervalo

O Candle Lab usa intervalos semiabertos:

~~~text
[início, fim)
~~~

Portanto:

~~~text
14:40 a 14:50
~~~

significa:

~~~text
timestamp >= 14:40:00
timestamp <  14:50:00
~~~

O negócio de 14:50:00 pertence ao próximo candle e não entra no recorte anterior.

---

## Parte 7 — informar o CSV Tick by Tick

No Explorador de Arquivos do Windows:

1. encontre o CSV grande de Trades;
2. clique com o botão direito;
3. escolha **Copiar como caminho**;
4. volte ao Candle Lab;
5. cole o caminho em **3 — Localizar as linhas no CSV Tick by Tick**.

Exemplo:

~~~text
"C:\Users\pablo\Documents\Dados\WINV26_2026-10-07_TRADES.csv"
~~~

As aspas podem permanecer.

---

## Parte 8 — preparar o índice e localizar as linhas

Clique em:

~~~text
Preparar índice e localizar
~~~

### Na primeira utilização daquele CSV

O Candle Lab lê o arquivo completo uma vez e cria um índice leve. Durante essa leitura, a interface mostra uma barra de progresso com:

- porcentagem já lida;
- quantidade de linhas processadas;
- MB/GB já percorridos em relação ao tamanho total;
- quantidade de minutos já indexados.

Exemplo:

~~~text
37,4% · 2.850.000 linhas · 268,1 MB de 717,4 MB · 214 minutos indexados
~~~

A porcentagem é calculada pelos **bytes efetivamente lidos do arquivo**, não por uma estimativa de negócios por minuto.

O índice é salvo em:

~~~text
data\indexes
~~~

O índice guarda, minuto a minuto:

- linhas físicas;
- offsets de byte;
- número real de negócios;
- timestamps;
- ordem física da fonte.

Ele não copia todos os trades.

### Nas próximas seleções

O índice é reutilizado e a localização é muito mais rápida.

A tabela exibida mostra para cada candle:

- linhas físicas;
- linha da abertura cronológica;
- linha do fechamento cronológico;
- negócios;
- bytes.

Nenhuma média de negócios por minuto é usada.

---

## Parte 9 — gerar o recorte

Depois de conferir a tabela, clique em:

~~~text
Recortar e importar intervalo localizado
~~~

A partir da v0.14.3, essa etapa possui uma **segunda barra de progresso**, independente da barra usada para construir o índice.

Ela informa a porcentagem geral e a fase atual, por exemplo:

~~~text
15,0%  Localizando os bytes exatos do intervalo
42,7%  Extraindo · 5,3 MB de 12,4 MB · 48.320 negócios
80,0%  Normalizando e validando os negócios
90,0%  Gravando o recorte na biblioteca local
96,0%  Atualizando metadados e mapa de candles
100,0% Recorte criado, validado e importado
~~~

Durante a fase de extração, o avanço é calculado pelos **bytes realmente lidos da faixa selecionada**. As fases seguintes avançam quando cada etapa efetivamente é concluída.

O Candle Lab usa os offsets do índice para saltar diretamente à região necessária do CSV grande.

O pequeno arquivo derivado fica em:

~~~text
data\slices
~~~

O arquivo Tick by Tick original não é alterado.

---

## Parte 10 — analisar a microestrutura

Na seção **Biblioteca de microestrutura**:

1. escolha o ativo;
2. escolha o pregão;
3. escolha o timeframe;
4. clique em um candle.

O laboratório passa a mostrar recursos como:

- replay negócio a negócio;
- trajetória intrabar;
- Times & Trades;
- volume por preço;
- agressão, quando disponível;
- DNA do candle;
- comparação com outros candles;
- famílias de trajetória;
- simulação contrafactual claramente separada dos dados reais.

---

## Parte 11 — exemplo recomendado para o primeiro teste

Use o pregão real já empregado na validação do projeto.

1. importe o CSV de 1 minuto do WINV26;
2. selecione **14:40 a 14:50**;
3. se quiser, digite diretamente:
   - Início = `14:40`
   - Fim = `14:50`
4. clique em **Aplicar horários**;
5. use **Zoom na seleção** para conferir visualmente;
6. cole o caminho do CSV Tick by Tick original;
7. clique em **Preparar índice e localizar**;
8. confira o mapa de linhas;
9. clique em **Recortar e importar intervalo localizado**;
10. abra os candles na Biblioteca de microestrutura.

Nesse trecho, a validação anterior do projeto encontrou 10/10 candles completos com OHLC e quantidade coincidentes com a referência.

---

## Parte 12 — arquivos criados pelo programa

Por padrão:

~~~text
data\candle_lab.duckdb       banco local
data\indexes\               índices de linhas/bytes
data\slices\                pequenos recortes Tick
data\reports\               relatórios
~~~

O CSV grande original pode permanecer fora da pasta do Candle Lab.

---

## Problemas comuns

### O navegador abriu antes da aplicação

Aguarde alguns segundos e atualize a página.

### Python não encontrado

Instale Python 3.11 ou superior, marque **Add Python to PATH** e execute `iniciar.bat` novamente.

### Não consigo acertar o minuto no gráfico

Não tente insistir no clique. Use uma destas opções:

- aumente o zoom;
- arraste os marcadores INÍCIO/FIM;
- digite os horários nos campos;
- clique em **Zoom na seleção**.

### O horário digitado foi recusado

O horário precisa ser uma fronteira válida dos candles do timeframe importado.

### O índice demora na primeira vez

Isso é esperado para um CSV muito grande. Observe a barra de porcentagem exibida acima do resultado: ela informa o avanço real da leitura pelos bytes processados.

A leitura integral ocorre apenas para construir o índice. Depois ele é reutilizado e a interface informa **Índice reutilizado — nenhuma nova leitura integral foi necessária**.

### A Biblioteca de microestrutura está vazia

O gráfico diário pode existir sem dados Tick. A biblioteca só recebe microestrutura depois de **Recortar e importar intervalo localizado**.


### Erro envolvendo preço como 205.935

Nas exportações brasileiras do Profit, um valor como `205.935` para o WIN significa **205935 pontos**: o ponto é separador de milhar, não separador decimal.

A partir da v0.14.2, o perfil Profit interpreta esse formato corretamente antes de validar o tick. A regra não é aplicada indiscriminadamente a CSVs genéricos.
