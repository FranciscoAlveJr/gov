# INSS Implantação Bot — Plano de Implementação (Python/Playwright)

## Resumo

Bot Python que lê uma planilha `.xlsx` local com credenciais de clientes, faz login no `meu.inss.gov.br` via Playwright para capturar tokens de autenticação, depois usa `requests` diretamente nas APIs do INSS para buscar histórico de créditos (`hiscreServices`) e baixar PDFs, aplica as regras de negócio (ALERTA IMPLANTAÇÃO / NÃO IMPLANTADO / ALERTA PAB), gera Excel com abas Resumo + Consulta com formatação de cores, e empacota tudo em `.zip`. Agendamento via Windows Task Scheduler.

---

## Estrutura de Pastas

```
gov/
├── main.py                  # Entry point (run manual + chamado pelo scheduler)
├── config.py                # Constantes, caminhos, datas de referência
├── requirements.txt
├── .env                     # INPUT_PATH, API_BASE, ANTICAPTCHA_KEY (opcional)
├── bot/
│   ├── __init__.py
│   ├── browser.py           # Playwright: login → captura mitoken + oracle_id
│   ├── api_client.py        # requests: hiscreServices JSON + download PDF binário
│   └── captcha.py           # hCaptcha solver (stub, ativa via .env se necessário)
├── parser/
│   ├── __init__.py
│   └── hiscre_parser.py     # Regras 1-3: implantação, PAB, extração de detalhes
├── reports/
│   ├── __init__.py
│   ├── excel_builder.py     # openpyxl: abas Resumo + Consulta, fontes verde/vermelha
│   └── zip_builder.py       # Compactar pasta PDFs + Excel gerado
├── db/
│   ├── __init__.py
│   └── cache.py             # SQLite: cache de CPFs já consultados no dia
├── input/                   # Planilha de entrada fica aqui
└── output/                  # PDFs baixados + zips gerados
```

---

## Fase 1 — Estrutura base e config

1. Criar estrutura de pastas e arquivos `__init__.py`
2. `config.py`: `INPUT_PATH`, `OUTPUT_DIR`, `API_BASE_URL`, cálculo de data início (5 anos atrás), meses de referência para regra 1 (mês atual `03/2026` + próximo `04/2026`)
3. `.env`: variáveis `INPUT_PATH`, `ANTICAPTCHA_KEY` (opcional)
4. `requirements.txt`: `playwright`, `requests`, `pandas`, `openpyxl`, `pdfplumber`, `python-dotenv`, `fake-useragent`

---

## Fase 2 — Leitura da planilha de entrada

5. Ler `.xlsx` com pandas → lista de dicts com colunas: `CLIENTE, CPF, LOGIN, SENHA, PROCESSO, TIPO DE PROCESSO, GRUPO DE PROCESSO, ESFERA, PARCEIRO, LÍDER, PETICIONANTE, DATA DE INCLUSÃO`
6. Validação antecipada: se `SENHA` vazia/ausente → resultado imediato `"Senha Não Fornecida"` (pula login completamente)

> **Verificar colunas reais** abrindo `docs/modelo planilha de origem.xlsx` antes de implementar esta fase.

---

## Fase 3 — Autenticação (Playwright + hCaptcha)

7. `browser.py` — estratégia em camadas:
   - **Tentativa 1:** POST direto na API de login INSS (sem browser) — verificar se retorna token sem exigir captcha
   - **Tentativa 2 (fallback):** Playwright com Chromium, intercepta XHR da endpoint `/usuarioservices/info/{CPF}` → extrai `mitoken` do JSON de resposta
   - Interceptar também a chamada ao Oracle Infinity → extrair `oracle_id` (endpoint `/dc.oracleinfinity.io/v4/account/.../client/id` ou elemento do DOM)
   - Retornar dict com headers: `{ Authorization: "Bearer {mitoken}", oracle-id: "...", Cookie: "..." }`
   - Se login retornar mensagem "senha não confere" → lançar `PasswordError` (resultado = `"Senha Não Confere"`)

8. `captcha.py`: stub desativado por padrão; se `ANTICAPTCHA_KEY` presente no `.env`, integra com anti-captcha.com API para resolver hCaptcha antes do submit

---

## Fase 4 — Cliente API (requests)

9. `api_client.py`:
   - `get_hiscre(cpf, data_inicio, data_fim, headers) → dict`
     - GET `{API_BASE}/hiscreServices/historicocreditos/{cpf}/{DD-MM-YYYY}/{DD-MM-YYYY}`
   - `download_pdf(cpf, data_inicio, data_fim, headers, dest_path) → None`
     - GET `{API_BASE}/hiscreServices/historicocreditosPdf/{cpf}/{DD-MM-YYYY}/{DD-MM-YYYY}` → salva binário
   - Tratamento de erros: `401` → relogar e tentar novamente; `5xx` → resultado `"Falha na extração"`
   - Formato de data nas URLs: `DD-MM-YYYY`

---

## Fase 5 — Parser / Regras de negócio

10. `hiscre_parser.py` — função `analyze(hiscre_data, ref_date) → ParseResult`:

    - **Regra 1 (ALERTA DE IMPLANTAÇÃO):** qualquer item do hiscre com mês/ano == mês atual **ou** mês/ano == próximo mês → `ALERTA DE IMPLANTAÇÃO`
    - **Regra 2 (NÃO IMPLANTADO):** ausência das datas acima → `NÃO IMPLANTADO`
    - **Regra 3 (ALERTA DE PAB):** `status` em branco ou "não pago" **E** `data_validade_fim` < `ref_date` → `ALERTA DE PAB`

    Para **ALERTA DE IMPLANTAÇÃO**, extrair os **Detalhes**:
    - **DATA (Previsão de pagamento):** valor numérico após `"CMG – CARTAO MAGNETICO"` (formato `R$ X.XXX,00`)
    - **VALOR (Total da implantação):** somatório de todas as colunas `Valor Líquido` com mesma `DATA` da previsão de pagamento
    - **BANCO:** todo o texto da linha após a palavra `"banco"`

---

## Fase 6 — Geração de relatórios

11. `excel_builder.py` (openpyxl):

    - **Nome do arquivo:** `"Implantação DD.MM.YYYY.xlsx"` → se já existe no dia → `"Implantação DD.MM.YYYY V2.xlsx"` → `V3`... `V4`...
    - **Aba 1 — "Resumo"** (primeira aba):
      ```
      Data: XX/XX/XXXX
      Horário início: 00:00h
      Horário fim: 00:00h
      1 – Sucesso: XX
      2 – Falha na extração: XX
      3 – Senha Não Confere: XX
      4 – Senha Não Fornecida: XX
      5 – Pdfs na pasta: XX  ← contagem real dos arquivos na pasta
      ```
      Linhas 1 e 5: fonte **verde** se "Pdfs na pasta" == "Sucesso"; **vermelha** se forem diferentes.

    - **Aba 2 — "Consulta":** colunas `CONSULTA, CLIENTE, CPF, DATA, VALOR, BANCO, PROCESSO, TIPO DE PROCESSO, GRUPO DE PROCESSO, ESFERA, PARCEIRO, LÍDER, PETICIONANTE, DATA DE INCLUSÃO, IMPLANTAÇÃO, PAB`
      - `CONSULTA`: `"Sucesso"` / `"Falha na extração"` / `"Senha Não Confere"` / `"Senha Não Fornecida"`
      - `IMPLANTAÇÃO`: `"ALERTA DE IMPLANTAÇÃO"` / `"NÃO IMPLANTADO"` / vazio (falhas)
      - `PAB`: `"ALERTA DE PAB"` / vazio
      - **Detalhe 3:** `DATA DE INCLUSÃO` > 60 dias da data da consulta → linha inteira com fonte **vermelha**
      - **Detalhe 4:** `IMPLANTAÇÃO == "ALERTA DE IMPLANTAÇÃO"` → linha inteira com fonte **verde** (prioridade sobre vermelho)
      - **Detalhe 2:** quando `NÃO IMPLANTADO` e/ou `ALERTA DE PAB`, não colhe DATA/VALOR/BANCO — apenas reproduz dados da planilha de origem e preenche IMPLANTAÇÃO e PAB

12. `zip_builder.py`: empacota pasta `PDFs/` + arquivo Excel em `"Implantação DD.MM.YYYY.zip"`

---

## Fase 7 — Cache SQLite

13. `db/cache.py`:
    - Tabela: `consultas(cpf TEXT, data_inicio TEXT, data_fim TEXT, resultado_json TEXT, timestamp TEXT)`
    - `is_cached(cpf, data_inicio, data_fim) → bool` — verifica se já processado no mesmo dia
    - `save(cpf, data_inicio, data_fim, resultado_json)` — persiste resultado
    - Antes de processar cada cliente, verificar cache para evitar reprocessamento

---

## Fase 8 — Orquestrador principal

14. `main.py`:
    - `argparse`: flag `--manual` para run imediato
    - Registrar horário de início
    - Ler planilha de entrada
    - Para cada cliente:
      1. Checar cache → se encontrado, usar resultado cacheado
      2. Validar senha presente → se não, registrar `"Senha Não Fornecida"`
      3. Fazer login via `browser.py` → capturar headers de auth
      4. Se `PasswordError` → registrar `"Senha Não Confere"`
      5. Chamar `api_client.get_hiscre()` → se falhar, registrar `"Falha na extração"`
      6. Chamar `api_client.download_pdf()` → salvar em `output/PDFs/{CLIENTE}.pdf`
      7. Chamar `hiscre_parser.analyze()` → obter resultado
      8. Acumular em lista de resultados
    - Registrar horário de fim
    - Chamar `excel_builder.build(resultados, horario_inicio, horario_fim)`
    - Chamar `zip_builder.pack(output_dir, excel_path)`
    - Salvar no cache SQLite

---

## Fase 9 — Agendamento

15. `task_scheduler_setup.bat`: cria tarefa no Windows Task Scheduler que executa `python main.py` às `02:00` diariamente. Caminho do Python e do projeto configuráveis via variáveis no início do arquivo.

---

## Decisões registradas

| Decisão | Escolha |
|---|---|
| hCaptcha | Investigar bypass via API direta primeiro; Playwright como fallback; anticaptcha configurável via `.env` |
| Planilha de entrada | `.xlsx` local, caminho configurável em `.env` |
| SQLite | Cache de consultas realizadas no dia (evitar reprocessamento) |
| Agendamento | Windows Task Scheduler (externo ao Python) |
| Prioridade de cor | Linha verde (ALERTA IMPLANTAÇÃO) tem prioridade sobre linha vermelha (> 60 dias) |

---

## Pontos de atenção

- A estrutura exata do JSON retornado por `hiscreServices/historicocreditos` ainda precisa ser validada contra a API real — o parser será construído com base nas regras e ajustado quando os dados reais forem inspecionados.
- Confirmar colunas reais da planilha de entrada abrindo `docs/modelo planilha de origem.xlsx` antes de implementar a Fase 2.
- O fluxo de reutilização de sessão autenticada entre múltiplos clientes deve ser avaliado: se um mesmo operador processa N clientes, talvez um único login baste (a depender de como a API autentica — por CPF do operador ou do beneficiário).
