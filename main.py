import os
import time
import sqlite3
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import shutil

from input_reader import read_input_data
from bot.browser import login_e_extrair_tokens, fechar_browser, LoginError, PageDataError
from bot.api_client import APIClient
from bot.parser import analisar_historico_creditos
from bot.report_generator import gerar_relatorio_final
from bot.notifier import enviar_mensagem_telegram, enviar_documento_telegram
from bot.updater import check_and_update
from bot.logger_config import setup_logger

def formatar_data_para_api(data_obj: date) -> str:
    return data_obj.strftime("%d-%m-%Y")

def main():
    logger, caminho_log = setup_logger()
    
    import sys
    
    if getattr(sys, 'frozen', False):
        base_dir_app = os.path.dirname(sys.executable)
    else:
        base_dir_app = os.path.dirname(os.path.abspath(__file__))

    logger.info("========================================")
    logger.info(" INICIANDO ROTINA DE IMPLANTAÇÃO - INSS ")
    logger.info("========================================")
    
    # Verifica por atualizações (Fase 2)
    try:
        check_and_update()
    except Exception as e:
        logger.warning(f"Aviso de atualização falhou: {e}")
        
    start_time_obj = datetime.now()
    start_time_str = start_time_obj.strftime("%H:%Mh")
    
    usuario_pc = os.environ.get("USERNAME", "Desconhecido")
    enviar_mensagem_telegram(f"🚀 *Bot INSS Iniciado*\n\n🖥️ Cliente/PC: `{usuario_pc}`\n⏰ Horário: {start_time_str}")
    logger.info(f"Cliente/PC Identificado: {usuario_pc}")

    # Pastas de saída
    pasta_output = os.path.join(base_dir_app, "output")
    pasta_pdfs = os.path.join(pasta_output, "Pdfs")

    if os.path.exists(pasta_pdfs):
        try:
            shutil.rmtree(pasta_pdfs)
            logger.debug(f"Pasta de PDFs '{pasta_pdfs}' limpa no início da execução.")
        except Exception as e:
            logger.warning(f"Não foi possível limpar a pasta de PDFs no início: {e}")

    os.makedirs(pasta_pdfs)

    estatisticas = {
        "start_time": start_time_str,
        "end_time": "",
        "sucesso": 0,
        "implantacao_ou_pab": 0,
        "falha_extracao": 0,
        "senha_errada": 0,
        "sem_senha": 0
    }

    # Configurar Banco de Dados
    db_path = os.path.join(pasta_output, "temp_resultados.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resultados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            CONSULTA TEXT,
            CLIENTE TEXT,
            CPF TEXT,
            DATA TEXT,
            VALOR REAL,
            BANCO TEXT,
            PROCESSO TEXT,
            TIPO_DE_PROCESSO TEXT,
            GRUPO_DE_PROCESSO TEXT,
            ESFERA TEXT,
            PARCEIRO TEXT,
            LIDER TEXT,
            PETICIONANTE TEXT,
            DATA_DE_INCLUSAO TEXT,
            IMPLANTACAO TEXT,
            PAB TEXT
        )
    ''')
    conn.commit()

    # 1. Ler dados da entrada
    logger.info("Lendo planilha de entrada...")
    try:
        clientes = read_input_data()
        total_clientes = len(clientes)
    except Exception as e:
        logger.exception("Falha estrutural ao ler a planilha.")
        clientes = []
        total_clientes = 0
    
    # Recupera a quantidade de processados no banco de dados
    cursor.execute("SELECT COUNT(*) FROM resultados")
    qtd_processados = cursor.fetchone()[0]

    if qtd_processados > 0:
        logger.info(f"ATENÇÃO: Retomada inteligente iniciada! {qtd_processados} registros encontrados no DB.")
        # Atualiza a contagem das estatísticas para que o relatório feche a matemática
        cursor.execute("SELECT CONSULTA, COUNT(*) FROM resultados GROUP BY CONSULTA")
        for status, count in cursor.fetchall():
            if status == "Sucesso":
                estatisticas["sucesso"] = count
            elif status == "Senha Não Confere":
                estatisticas["senha_errada"] = count
            elif status == "Senha Não Fornecida":
                estatisticas["sem_senha"] = count
            elif status == "Falha na extração":
                estatisticas["falha_extracao"] = count
                
        # Atualiza a contagem dos PABs ou Implantações que foram sucesso
        cursor.execute("SELECT IMPLANTACAO, PAB FROM resultados WHERE CONSULTA = 'Sucesso'")
        for imp, pab in cursor.fetchall():
            if imp == "ALERTA DE IMPLANTAÇÃO" or pab == "ALERTA DE PAB":
                estatisticas["implantacao_ou_pab"] += 1
                
    logger.info(f"Total de registros: {total_clientes} | Restantes na fila: {max(0, total_clientes - qtd_processados)}")

    dados_finais = []

    # Datas de busca (5 anos atrás até 2 meses na frente)
    data_fim = start_time_obj
    data_inicio = start_time_obj - relativedelta(years=5)
    
    str_inicio = formatar_data_para_api(data_inicio)
    str_fim = formatar_data_para_api(data_fim)

    # 2. Processar cada cliente
    # O slice [qtd_processados:] pula os N primeiros registros já salvos no DB
    for idx, cliente in enumerate(clientes[qtd_processados:], start=qtd_processados + 1):
        nome_cliente = str(cliente.get("CLIENTE", f"Desconhecido_{idx}"))
        cpf = str(cliente.get("CPF", "")).strip().replace(".", "").replace("-", "")
        cpf = cpf.zfill(11)  # Garante que o CPF tenha 11 dígitos, preenchendo com zeros à esquerda
        senha = str(cliente.get("SENHA GOV", "")).strip()
        
        logger.info(f"--- [{idx}/{len(clientes)}] Processando: {nome_cliente} | CPF: {cpf} ---")

        # Preparar dicionário espelho da linha para ir pra planilha de resultado
        ## O dict 'cliente' já tem a maioria (CLIENTE, CPF, PROCESSO, TIPO DE PROCESSO, etc...)
        dado_saida = cliente.copy()
        
        dado_saida["CPF"] = cpf  # Sobrescreve o CPF formatado (apenas números, 11 dígitos)

        # Garante as colunas novas em branco, caso o python lance KeyError
        for col in ["CONSULTA", "DATA", "VALOR", "BANCO", "IMPLANTAÇÃO", "PAB"]:
            if col not in dado_saida:
                 if col == 'VALOR':
                     dado_saida[col] = 0.0
                 else:
                     dado_saida[col] = ""
                 

        # Tentativa de operação (Login -> API -> Avaliação)
        try:
            if not cpf or not senha or senha.lower() == "nan":
                raise ValueError("CPF ou senha ausente.")
            
            logger.info("  -> Iniciando login via Playwright...")
            
            # Aqui pode lançar `LoginError` ou retornar os tokens
            auth_dados = login_e_extrair_tokens(cpf, senha, headless=False) # Usando HEADLESS False pra rodar visível!
            
            if not auth_dados:
                logger.warning("  -> Falha genérica ou erro de senha.")
                dado_saida["CONSULTA"] = "Senha Não Confere"
                estatisticas["senha_errada"] += 1
                dados_finais.append(dado_saida)
                continue

            # API Client
            logger.info("  -> Conectando nas APIs do portal Meu INSS...")
            api = APIClient()
            api.configure_session(auth_dados)

            # PEGAR O JSON PARA AS REGRAS (Parser)
            dados_hiscre = api.get_historico_creditos(cpf, str_inicio, str_fim)
            resultado_regra = analisar_historico_creditos(dados_hiscre, data_consulta=start_time_obj.date())
            
            # Atualiza o dicionário com os resultados do parser
            dado_saida["IMPLANTAÇÃO"] = resultado_regra["IMPLANTAÇÃO"]
            dado_saida["PAB"] = resultado_regra["PAB"]

            
            if resultado_regra["IMPLANTAÇÃO"] == "ALERTA DE IMPLANTAÇÃO":
                dado_saida["DATA"] = resultado_regra["PREVISAO_PAGAMENTO"]
                dado_saida["VALOR"] = resultado_regra["VALOR_TOTAL"]
                dado_saida["BANCO"] = resultado_regra["BANCO"]

            logger.info(f"  -> Resultado obtido: {resultado_regra['IMPLANTAÇÃO']} | {resultado_regra['PAB']}")

            # SÓ BAIXA O PDF SE DEU CERTO A CONSULTA! (Como definido Sucesso)
            logger.info("  -> Efetuando o download do PDF de Extrato...")
            nome_seguro = "".join([c for c in nome_cliente if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            nome_pdf = f"{nome_seguro}.pdf"
            caminho_pdf = os.path.join(pasta_pdfs, nome_pdf)
            
            api.download_pdf_historico(cpf, str_inicio, str_fim, caminho_pdf)
            
            # Deu tudo certo!
            dado_saida["CONSULTA"] = "Sucesso"
            estatisticas["sucesso"] += 1
            if resultado_regra["IMPLANTAÇÃO"] == "ALERTA DE IMPLANTAÇÃO" or resultado_regra["PAB"] == "ALERTA DE PAB":
                estatisticas["implantacao_ou_pab"] += 1
            logger.info("  -> Extração do cliente finalizada com SUCESSO.")


        except PageDataError as pe:
            logger.error(f"  -> Erro na página (Dados cadastrais incompletos): {pe}")
            dado_saida["CONSULTA"] = "Falha na extração"
            estatisticas["falha_extracao"] += 1

        except LoginError as le:
            logger.error(f"  -> Erro de Login (Senha não confere): {le}")
            dado_saida["CONSULTA"] = "Senha Não Confere"
            estatisticas["senha_errada"] += 1

        except ValueError:
            logger.warning(f"  -> Senha não fornecida para {nome_cliente}")
            dado_saida["CONSULTA"] = "Senha Não Fornecida"
            estatisticas["sem_senha"] += 1
            dados_finais.append(dado_saida)

        except Exception as ex:
            logger.warning(f"  -> Detalhes de API/Hiscre não encontrados ou falhos para {cpf}: {ex}")
            # Como o login foi feito com sucesso, consideramos finalizado positivamente
            dado_saida["CONSULTA"] = "Sucesso"
            dado_saida["IMPLANTAÇÃO"] = "NÃO IMPLANTADO"
            estatisticas["sucesso"] += 1
            valor_numerico = 0.0

        finally:
            # Salva do banco de dados (seja sucesso ou falha)
            valor_bruto = dado_saida.get("VALOR", 0.0)
            try:
                valor_numerico = float(valor_bruto)
            except (ValueError, TypeError):
                valor_numerico = 0.0

            dado_saida["ESFERA"] = str(dado_saida["ESFERA"]).capitalize()
            if dado_saida["ESFERA"] == 'Administrative':
                dado_saida["ESFERA"] = 'Administrativa'

            cursor.execute('''
                INSERT INTO resultados (
                    CONSULTA, CLIENTE, CPF, DATA, VALOR, BANCO, PROCESSO,
                    TIPO_DE_PROCESSO, GRUPO_DE_PROCESSO, ESFERA, PARCEIRO,
                    LIDER, PETICIONANTE, DATA_DE_INCLUSAO, IMPLANTACAO, PAB
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(dado_saida.get("CONSULTA", "")),
                str(dado_saida.get("CLIENTE", "")),
                str(dado_saida.get("CPF", "")),
                str(dado_saida.get("DATA", "")),
                valor_numerico,
                str(dado_saida.get("BANCO", "")),
                str(dado_saida.get("PROCESSO", "")),
                str(dado_saida.get("TIPO DE PROCESSO", "")),
                str(dado_saida.get("GRUPO DE PROCESSO", "")),
                str(dado_saida.get("ESFERA", "")),
                str(dado_saida.get("PARCEIRO", "")),
                str(dado_saida.get("LÍDER", "")),
                str(dado_saida.get("PETICIONANTE", "")),
                str(dado_saida.get("DATA DE INCLUSÃO", "")),
                str(dado_saida.get("IMPLANTAÇÃO", "")),
                str(dado_saida.get("PAB", ""))
            ))
            conn.commit()
            
        # Pequena pausa entre requisições para evitar rate limit massivo
        time.sleep(1)

    # 3. Ler dados usando Pandas e Finalizar execução 
    logger.info("Processamento de CPFs concluído.")
    logger.info("Lendo dados do Banco SQLite e convertendo via Pandas para relatório final...")
    
    df_resultados = pd.read_sql_query("SELECT * FROM resultados", conn)
    conn.close()
    
    # Renomear colunas do BD para o padrão esperado pelo gerador de excel
    colunas_excel = {
        "TIPO_DE_PROCESSO": "TIPO DE PROCESSO",
        "GRUPO_DE_PROCESSO": "GRUPO DE PROCESSO",
        "LIDER": "LÍDER",
        "DATA_DE_INCLUSAO": "DATA DE INCLUSÃO",
        "IMPLANTACAO": "IMPLANTAÇÃO"
    }
    df_resultados.rename(columns=colunas_excel, inplace=True)
    df_resultados.drop(columns=["id"], inplace=True, errors="ignore")
    
    # Converte o dataframe de volta para uma lista de dicionários pro gerador_relatorio_final
    dados_finais = df_resultados.to_dict('records')

    logger.info("Gerando relatórios finais (Excel/Zip)...")
    end_time_str = datetime.now().strftime("%H:%Mh")
    estatisticas["end_time"] = end_time_str
    
    try:
        gerar_relatorio_final(dados_finais, estatisticas, pasta_pdfs, pasta_output)
        logger.info("Relatórios físicos gerados com sucesso na pasta output.")
    except Exception as ex:
        logger.critical(f"Erro Crítico ao gerar o relatório final em Excel/Zip: {ex}")
        
    # Deletando arquivo Database Temporário
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.debug(f"Banco de dados temporário '{db_path}' apagado.")
        except Exception as e:
            logger.warning(f"Não foi possível apagar o BD temporário: {e}")
    
    logger.info("Resumo da Operação:")
    logger.info(f"Sucesso: {estatisticas['sucesso']}")
    logger.info(f"Implantação ou PAB: {estatisticas['implantacao_ou_pab']}")
    logger.info(f"Falhas por Senha/Login: {estatisticas['senha_errada']}")
    logger.info(f"Falha de Extração Técnica: {estatisticas['falha_extracao']}")
    logger.info(f"Faltaram Senhas: {estatisticas['sem_senha']}")

    msg_fim = (
        f"<b>✅ Rotina Concluída</b>\n\n"
        f"🖥️ <b>Cliente/PC:</b> <i>{usuario_pc}</i>\n"
        f"⏱️ <b>Início:</b> {estatisticas['start_time']} | <b>Fim:</b> {estatisticas['end_time']}\n"
        f"📊 <b>Resumo da Operação:</b>\n"
        f"🟢 Sucessos: {estatisticas['sucesso']}\n"
        f"🟢 Implantação/PAB: {estatisticas['implantacao_ou_pab']}\n"
        f"🟡 Falhas Extração: {estatisticas['falha_extracao']}\n"
        f"⚪ Faltaram Senhas: {estatisticas['sem_senha']}"
    )
    
    # Envia o arquivo físico de log pro desenvolvedor monitorar!!
    logger.info("Enviando histórico de logs para o Telegram...")
    
    # Precisamos fechar os handlers de escrita para permitir leitura e envio do arquivo
    for handler in logger.handlers[:]:
        handler.flush()
        handler.close()
        
    enviar_documento_telegram(caminho_log, caption=msg_fim)
    
    # Fechar navegador no final
    fechar_browser()

    shutil.rmtree(pasta_pdfs)  # Limpa a pasta de PDFs baixados, pois já estão no relatório final

    # logger.info("Operação concluída.")

    print("\nOperação concluída com sucesso! Verifique a pasta 'output'.")
    print("\nPressione Enter para sair...")
    input()


if __name__ == "__main__":
    main()
