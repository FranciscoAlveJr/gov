# Bot Meu INSS - RPA de Extração de Dados

Robô de Automação de Processos (RPA) desenvolvido em Python para automatizar a consulta de dados de beneficiários do INSS através dos portais gov.br e Meu INSS.

## 📋 Visão Geral

Este projeto implementa um crawler web inteligente que automatiza o processo de extração de informações de histórico de créditos do INSS. O bot realiza login automático, navega pelos portais governamentais e extrai dados estruturados sobre implantações de benefícios, incluindo valores, datas de pagamento e dados bancários.

O sistema foi projetado para processar lotes de clientes de forma resiliente, com suporte a retomada inteligente em caso de falhas, retry automático para erros temporários e geração de relatórios em Excel e PDF.

---

## 🎯 Funcionalidades Principais

### Automação de Login e Autenticação
- **Acesso ao gov.br**: Preenche credenciais (CPF e senha) de forma segura e humanizada
- **Detecção de autenticação de dois fatores (2FA)**: Identifica quando a conta requer 2FA e aborta graciosamente
- **Tratamento de erros de login**: Classifica falhas (senha incorreta, usuário bloqueado, etc.)
- **Retry automático**: Implementa tentativas automáticas com backoff exponencial para erros transitórios (timeouts, erros 502)

### Extração de Dados
- **Histórico de Créditos**: Busca dados de beneficiários através da API do Meu INSS
- **Análise de Implantações**: Processa regras de negócio para identificar estatuto de implantação vs PAB
- **Download de Extratos**: Realiza o download automático de PDFs de extrato para clientes com implantações pendentes

### Processamento em Lote
- **Retomada Inteligente**: Rastreia progresso em SQLite e retoma de onde parou em caso de interrupção
- **Verificação de Duplicatas**: Detecta usuários já processados no banco e desconecta antes de reprocessar
- **Rate Limiting**: Implementa pausas entre requisições para evitar bloqueios

### Relatório e Exportação
- **Relatório Excel**: Gera planilhas com colunas estruturadas (CONSULTA, MOTIVO, AÇÃO, etc.)
- **Arquivos ZIP**: Compacta relatórios e PDFs para distribuição
- **Notificações Telegram**: Envia alertas e logs de erro via bot Telegram

### Tratamento de Erros
- **Classificação de Falhas**: Categoriza erros em tipos específicos (Falha Extração, Falha hiscre, Senha Não Confere, etc.)
- **Log Estruturado**: Registra classificação, código de erro e mensagens descritivas
- **Notificação imediata**: Envia arquivo de log ao Telegram quando exceções não tratadas ocorrem

---

## 🏗️ Arquitetura

### Módulos Principais

```
bot/
├── browser.py            # Automação Playwright (login, navegação)
├── api_client.py         # Cliente HTTP para APIs do Meu INSS
├── parser.py             # Análise de JSON e aplicação de regras de negócio
├── report_generator.py   # Geração de Excel e ZIP
├── notifier.py           # Integração com Telegram
├── logger_config.py      # Configuração centralizada de logging
└── updater.py            # Verificação e atualização automática

main.py                    # Orquestrador principal
input_reader.py            # Leitura de entrada (Excel)
tests/                     # Suite de testes com mocks
```

### Fluxo de Execução

```
1. Leitura da Planilha de Entrada
   └─> Lê Excel de input/ com CPFs e senhas

2. Verificação de Retomada
   └─> Consulta SQLite para CPFs já processados

3. Loop de Processamento (por cliente)
   ├─> Verificação de Duplicata no banco
   ├─> Login via Playwright
   │   ├─> Preenche CPF (humanizado)
   │   ├─> Aguarda tela de senha
   │   ├─> Preenche senha (humanizado)
   │   ├─> Detecta erros (2FA, bloqueio, datossuspeitos)
   │   ├─> Retry em erros 502 com reload
   │   └─> Intercepta tokens (Bearer token, miToken)
   ├─> Consulta API Meu INSS
   │   ├─> Histórico de Créditos (GET /hiscre)
   │   └─> Download PDF (GET /extrato)
   ├─> Análise de Regras
   │   ├─> Verifica implantação (data, valor, banco)
   │   ├─> Classifica como IMPLANTAÇÃO/PAB/NÃO_IMPLANTADO
   ├─> Classificação de Erro (se aplicável)
   │   ├─> 404 → Sucesso (sem dados)
   │   ├─> 401/403 → Sessão não autorizada
   │   ├─> 500/503 → Serviço indisponível
   └─> Salva em SQLite

4. Geração de Relatório
   ├─> Lê todos os registros do SQLite
   ├─> Aplica regras de coloração Excel (verde/vermelho)
   ├─> Gera planilha final
   ├─> Cria ZIP com PDFs
   └─> Envia resumo via Telegram
```

---

## 💻 Tecnologias Utilizadas

### Linguagem e Framework
- **Python 3.8+**: Linguagem principal
- **Playwright**: Automação de navegador (headless e GUI)
- **Playwright Stealth**: Bypass de detecção de automação

### Processamento de Dados
- **Pandas**: Manipulação de DataFrames Excel
- **SQLite3**: Banco de dados local para cache e retomada
- **OpenPyXL**: Geração de planilhas Excel com estilos

### Integração e Comunicação
- **Requests**: Cliente HTTP para APIs
- **python-dotenv**: Gerenciamento de variáveis de ambiente
- **Telegram Bot API**: Notificações em tempo real

### Desenvolvimento e Utilitários
- **logging**: Logging estruturado e rotativo
- **dateutil**: Manipulação de datas
- **zipfile**: Compressão de arquivos
- **tempfile**: Gerenciamento de arquivos temporários

---

## 📋 Requisitos de Entrada

O bot espera um arquivo Excel na pasta `input/` com as seguintes colunas:

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| CLIENTE | String | ✅ | Nome do cliente |
| CPF | String | ✅ | CPF com ou sem formatação |
| SENHA GOV | String | ✅ | Senha do gov.br |
| PROCESSO | String | ❌ | Número do processo |
| TIPO DE PROCESSO | String | ❌ | Classificação |
| GRUPO DE PROCESSO | String | ❌ | Agrupamento |
| ESFERA | String | ❌ | Administrativa/Judiciária |
| PARCEIRO | String | ❌ | Nome do parceiro |
| LÍDER | String | ❌ | Responsável |
| PETICIONANTE | String | ❌ | Solicitante |
| DATA DE INCLUSÃO | Date | ❌ | Data de registro |

---

## 📤 Formato de Saída

### Planilha Final (output/Implantação DD.MM.YYYY.xlsx)

Colunas:
- **CONSULTA**: Status (Sucesso, Falha no hiscre, Senha Não Confere, etc.)
- **MOTIVO**: Razão específica do erro (ex: "Sessão não autorizada")
- **AÇÃO**: Ação recomendada (ex: "Conferir o cliente manualmente")
- **[Dados do cliente + resultados da API]**
- **IMPLANTAÇÃO**: Status (ALERTA DE IMPLANTAÇÃO, Não Implantado, etc.)
- **PAB**: Status do PAB
- **DATA**: Data de previsão de pagamento
- **VALOR**: Valor total do crédito
- **BANCO**: Código/nome do banco

### Arquivo ZIP (output/Implantação DD.MM.YYYY.zip)

```
Implantação DD.MM.YYYY.zip
├── Implantação DD.MM.YYYY.xlsx
└── PDFs/
    ├── Cliente1.pdf
    ├── Cliente2.pdf
    └── ...
```

---

## 🛠️ Setup e Instalação

### Para Desenvolvedores

1. Clone o repositório:
   ```bash
   git clone https://github.com/FranciscoAlveJr/Bot-Meu-INSS.git
   cd Bot-Meu-INSS
   ```

2. Crie um ambiente virtual:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```

3. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure variáveis de ambiente (`.env`):
   ```env
   TELEGRAM_BOT_TOKEN=seu_token_aqui
   TELEGRAM_CHAT_ID=seu_chat_id_aqui
   ```

5. Execute:
   ```bash
   python main.py
   ```

### Para Usuários Finais

Faça download do executável `Bot_INSS.exe` da seção de Releases. Coloque sua planilha na pasta `input/` e execute o .exe.

---

## 🔍 Tratamento de Erros

O bot classifica exceções em categorias específicas:

| Classificação | HTTP | Descrição | Ação |
|---|---|---|---|
| Sucesso | 200 | Dados extraídos com sucesso | Nenhuma |
| Sucesso (Dados Ausentes) | 404 | Sem histórico de créditos | Marca como "Não Implantado" |
| Falha no hiscre | 401/403/500/503 | Erro na API | Conferir cliente manualmente |
| Falha na extração | - | Erro genérico de parsing | Verificar dados cadastrais |
| Exige 2 Fatores | - | Autenticação 2FA ativada | Desativar com cliente |
| Senha Não Confere | - | Credencial inválida | Revisar credencial |
| Usuário Bloqueado | - | Conta suspensa/bloqueada | Regularizar no Gov.br |
| Senha Não Fornecida | - | Campo vazio ou NaN | Solicitar ao cliente |

---

## 📊 Estatísticas Geradas

Ao final da execução, o bot gera um resumo com:
- Total de sucessos
- Total de implantações/PAB encontrados
- Total de não implantados
- Falhas de extração (técnicas e hiscre)
- Falhas de autenticação (senha, 2FA, bloqueio)
- Senhas não fornecidas

---

## 📝 Logging

Logs são salvos em `output/logs/` com rotina diária. Cada execução gera um arquivo `.log` contendo:
- Timestamp de cada evento
- CPF processado
- Status e classificação
- Erros e exceções completos

Em caso de exceção genérica, o arquivo de log é enviado automaticamente via Telegram para diagnóstico remoto.

---

## 🧪 Testes

Para executar a suite de testes com mocks (sem fazer chamadas reais à API):

```bash
python tests/main_test.py
```

Os testes simulam:
- Login bem-sucedido
- Resposta de API mockada
- Geração de relatório
- Sem aguardas de rede

---

## 📄 Licença

Este projeto é fornecido como ferramenta interna. Consulte o arquivo LICENSE para detalhes.

---

## 👥 Suporte e Contribuições

Para relatar bugs ou solicitar funcionalidades, abra uma Issue. Para contribuir com código, envie um Pull Request.

---

## ⚠️ Notas Importantes

- **Dados Sensíveis**: Este bot lida com CPFs e senhas. Armazene credenciais com segurança e nunca compartilhe arquivos com dados sensíveis.
- **Conformidade**: Confirme a conformidade legal antes de usar em produção (LGPD, termos de serviço gov.br).
- **Rate Limiting**: O bot implementa pausas entre requisições (1s) para não sobrecarregar os servidores.
- **Autossuficiente**: A retomada inteligente permite que o bot seja pausado e retomado sem perda de progresso. 