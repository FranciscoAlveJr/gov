# Manual de Uso - Robô Consulta INSS

Bem-vindo(a) ao **Robô Consulta INSS**! 
Este programa foi desenvolvido para facilitar e automatizar a forma como você consulta dados de clientes no sistema gov.br e no Meu INSS. Ele faz todo o trabalho manual e repetitivo por você, gerando relatórios organizados e baixando os arquivos necessários.

Abaixo, você encontrará um guia completo e simples de como utilizar o robô no seu dia a dia.

---

## 1. O que o Robô é capaz de fazer?

O robô age como um assistente virtual que realiza as seguintes tarefas de forma totalmente automática:

* **Acessa o portal gov.br:** Ele abre o navegador e preenche o CPF e a Senha do seu cliente.
* **Resolve as burocracias de acesso:** Ele consegue passar pelas telas iniciais para chegar diretamente ao portal do "Meu INSS".
* **Extrai informações valiosas:** Ele verifica os dados do histórico de créditos, buscando datas de previsão de pagamento, valores totais e bancos cadastrados referentes a implantações de benefícios.
* **Baixa documentos:** Ele faz o download automático dos relatórios de crédito (Extratos em PDF) e salva os arquivos com os nomes dos seus clientes.
* **Gera relatórios organizados:** Ao final do processo, ele cria uma planilha do Excel novinha, onde junta as informações que você passou com os resultados que ele encontrou (Valor, Banco, Status da Implantação, etc.).
* **Organiza tudo em um arquivo ZIP:** Ele compacta todos os PDFs e a planilha final em um único arquivo, pronto para você enviar para sua equipe ou armazenar.
* **Avisa sobre falhas:** Ele é capaz de dizer se a senha estava errada, se faltou algum dado ou se havia alguma inconsistência cadastral com o cliente lá no sistema do INSS.

---

## 2. Preparando os Arquivos (Onde colocar a planilha?)

Para que o robô saiba quais clientes pesquisar, ele precisa de uma lista. 

1. **Localize a pasta "**`input`**":** Dentro da pasta principal que você recebeu (onde estão os programas do robô), existe uma pasta chamada `input`.
2. **Coloque sua planilha lá:** Você deve colocar a sua planilha do Excel (com as colunas de "CLIENTE", "CPF", "SENHA GOV", etc.) **dentro** desta pasta `input`.
3. **Formato correto:** Não se preocupe com o robô se perder: contanto que seja a única planilha do Excel dentro da pasta `input`, ele a encontrará automaticamente.

> ⚠️ **Atenção:** Nunca esqueça de garantir que as senhas e os CPFs estão corretamente preenchidos na sua planilha antes de iniciar!

---

## 3. Como usar o Bot passo a passo

Utilizar o robô é muito fácil. Siga o passo a passo:

### Passo 1: Iniciar o programa
Vá até a pasta onde todos os arquivos estão e localize o arquivo principal chamado **`Bot_INSS.exe`** (ou um nome similar com o ícone de executável). Dê **dois cliques** sobre ele.

### Passo 2: O Terminal (A tela preta)
Uma janela preta (parecida com a tela do MS-DOS) vai se abrir. Não se assuste! Esse é o painel de comunicação do robô com você. É por ali que ele vai escrever tudo o que está fazendo no momento, como: *"Processando João da Silva"*, *"Login concluído"*, *"Baixando PDF"*, etc. 

### Passo 3: O Navegador automático
O robô abrirá o Google Chrome sozinho. Você verá as páginas do Gov.br e do Meu INSS sendo abertas e preenchidas como se houvesse um "fantasma" digitando. 
* **Regra de Ouro:** Quando o robô estiver trabalhando, **não clique na janela do navegador dele**, não minimize e não tente navegar junto com ele. Deixe as mãos fora do mouse e do teclado enquanto a janela estiver em primeiro plano, para não atrapalhar o processo.

### Passo 4: Fim da operação
Quando ele terminar de buscar toda a sua lista, ele avisará na tela preta. O navegador irá fechar sozinho. E a tela preta pedirá para você apertar **"ENTER"** para fechar. Sua pasta de relatórios estará pronta!

---

## 4. Onde encontrar o resultado do trabalho?

Sempre que o robô finaliza o seu trabalho, ele cria ou atualiza uma pasta chamada **`output`** (que significa "saída") no mesmo local onde o robô está instalado.

Dentro desta pasta, você encontrará:
* **Pasta `Pdfs`:** Onde estão armazenados todos os extratos em documento dos clientes que deram certo.
* **Arquivo ZIP:** Um "pacote" que contém tanto a sua planilha nova totalmente preenchida quanto os Pdfs para facilitar o envio ou o backup do dia.
* Você notará que na sua planilha final, aparecerão novas colunas detalhando o valor encontrado, o banco e se a pesquisa resultou em *"Sucesso"* ou *"Senha Não Confere"*.

---

## 5. Atualização Automática (É tudo sozinho!)

Seu robô está configurado para se manter sempre inteligente e na melhor versão possível.

* **Como funciona:** Toda vez que você abre o programa, nos primeiros segundos, ele verifica na internet se seu desenvolvedor liberou uma versão mais moderna do robô.
* **O que acontece:** Se houver uma atualização, o robô vai baixar a nova versão sozinho. O terminal (a tela preta) vai avisar que atualizou e, em seguida, ele informará que precisa ser fechado.
* **O que você deve fazer:** Basta seguir as instruções na tela preta: aperte a tecla **ENTER** para que a tela feche. E então é só você **abrir o programa novamente** clicando duas vezes nele, e a versão nova já estará funcionando perfeitamente!

---

## 6. Agendando para rodar sozinho

Se você não quiser abrir o programa manualmente todo dia e preferir que ele acorde e ligue sozinho na sua máquina, siga este passo a passo extra:

Junto com os arquivos do robô, você recebeu outro aplicativo chamado **`agendar.exe`** (ou `agendar`).

1. Garanta que a sua planilha com os clientes do dia já está lá dentro da pasta `input`.
2. Dê **dois cliques** no arquivo **`agendar.exe`**.
3. Ele fará uma rápida configuração no seu Windows.
4. Feito! O Windows foi programado para "acordar" o robô **automaticamente todos os dias às 08:30 da manhã**. 

Sempre que der 08:30 da manhã, a tela preta e o navegador vão se abrir sozinhos no seu computador e já começarão a pesquisar a planilha que estiver salva lá.

### Dicas Finais
* Deixe os arquivos e pastas sempre juntos. Nunca mova o `.exe` principal para fora da pasta dele, ou ele não saberá onde encontrar a sua planilha ou onde guardar os resultados. Se quiser criar um atalho na sua Área de Trabalho, clique com o botão direito nele e escolha "Criar atalho", e mova apenas o atalho.
* Caso falte energia ou o programa seja fechado agressivamente no meio de uma consulta, não se preocupe! O robô tem uma "memória inteligente": quando você abri-lo de novo, ele retomará de onde parou, não pesquisando os clientes que já tinham sido finalizados.
* Caso ocorra um erro, não é necessário mandar nenhum arquivo de log para o desenvolvedor. Basta avisar o ocorrido que ele irá analisar, remotamente, o que pode ter acontecido. Tendo resolvido o problema, ao abrir o bot novamente, ele fará a atualização automática (Como dito do item 5) e o problema corrigido. 