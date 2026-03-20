import os
import time
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from input_reader import read_input_data
from bot.browser import login_e_extrair_tokens, LoginError
from bot.api_client import APIClient
from bot.parser import analisar_historico_creditos
from bot.report_generator import gerar_relatorio_final

def formatar_data_para_api(data_obj: date) -> str:
    return data_obj.strftime("%d-%m-%Y")

def main():
    print("========================================")
    print(" INICIANDO ROTINA DE IMPLANTAÇÃO - INSS ")
    print("========================================")
    
    start_time_obj = datetime.now()
    start_time_str = start_time_obj.strftime("%H:%Mh")

    # Pastas de saída
    pasta_output = "output"
    pasta_pdfs = os.path.join(pasta_output, "Pdfs")
    os.makedirs(pasta_pdfs, exist_ok=True)

    estatisticas = {
        "start_time": start_time_str,
        "end_time": "",
        "sucesso": 0,
        "falha_extracao": 0,
        "senha_errada": 0,
        "sem_senha": 0
    }

    # 1. Ler dados da entrada
    print("Lendo planilha de entrada...")
    clientes = read_input_data()
    print(f"Total de registros a processar: {len(clientes)}")

    dados_finais = []

    # Datas de busca (5 anos atrás até 2 meses na frente)
    data_fim = start_time_obj
    data_inicio = start_time_obj - relativedelta(years=5)
    
    str_inicio = formatar_data_para_api(data_inicio)
    str_fim = formatar_data_para_api(data_fim)

    # 2. Processar cada cliente
    for idx, cliente in enumerate(clientes, 1):
        nome_cliente = str(cliente.get("CLIENTE", f"Desconhecido_{idx}"))
        cpf = str(cliente.get("CPF", "")).strip().replace(".", "").replace("-", "")
        senha = str(cliente.get("SENHA GOV", "")).strip()
        
        print(f"\n[{idx}/{len(clientes)}] Processando: {nome_cliente} | CPF: {cpf}")

        # Preparar dicionário espelho da linha para ir pra planilha de resultado
        ## O dict 'cliente' já tem a maioria (CLIENTE, CPF, PROCESSO, TIPO DE PROCESSO, etc...)
        dado_saida = cliente.copy()
        
        # Garante as colunas novas em branco, caso o python lance KeyError
        for col in ["CONSULTA", "DATA", "VALOR", "BANCO", "IMPLANTAÇÃO", "PAB"]:
            if col not in dado_saida:
                 if col == 'VALOR':
                     dado_saida[col] = 0.0
                 else:
                     dado_saida[col] = ""
                 
        if not cpf or not senha or senha.lower() == "nan":
            print("  -> Senha não fornecida.")
            dado_saida["CONSULTA"] = "Senha Não Fornecida"
            estatisticas["sem_senha"] += 1
            dados_finais.append(dado_saida)
            continue

        # Tentativa de operação (Login -> API -> Avaliação)
        try:
            print("  -> Iniciando login via Playwright...")
            
            # Aqui pode lançar `LoginError` ou retornar os tokens
            auth_dados = login_e_extrair_tokens(cpf, senha, headless=False) # Usando HEADLESS False pra rodar visível!
            
            if not auth_dados:
                print("  -> Falha genérica ou erro de senha.")
                dado_saida["CONSULTA"] = "Senha Não Confere"
                estatisticas["senha_errada"] += 1
                dados_finais.append(dado_saida)
                continue

            # API Client
            print("  -> Conectando nas APIs do portal Meu INSS...")
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

            print(f"  -> Resultado: {resultado_regra['IMPLANTAÇÃO']} | {resultado_regra['PAB']}")

            # SÓ BAIXA O PDF SE DEU CERTO A CONSULTA! (Como definido Sucesso)
            print("  -> Efetuando o download do PDF de Extrato...")
            nome_seguro = "".join([c for c in nome_cliente if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            nome_pdf = f"{nome_seguro}.pdf"
            caminho_pdf = os.path.join(pasta_pdfs, nome_pdf)
            
            api.download_pdf_historico(cpf, str_inicio, str_fim, caminho_pdf)
            
            # Deu tudo certo!
            dado_saida["CONSULTA"] = "Sucesso"
            estatisticas["sucesso"] += 1

        except LoginError as le:
            print(f"  -> Erro de Login (Senha não confere): {le}")
            dado_saida["CONSULTA"] = "Senha Não Confere"
            estatisticas["senha_errada"] += 1
            
        except Exception as ex:
            print(f"  -> Falha na extração de dados/API: {ex}")
            dado_saida["CONSULTA"] = "Falha na extração"
            estatisticas["falha_extracao"] += 1
            
        finally:
            dados_finais.append(dado_saida)
            
        # Pequena pausa entre requisições para evitar rate limit massivo
        time.sleep(1)

    # 3. Finalizar execução e gerar relatorios
    print("\nProcessamento concluído. Gerando relatórios...")
    end_time_str = datetime.now().strftime("%H:%Mh")
    estatisticas["end_time"] = end_time_str
    
    # try:
    gerar_relatorio_final(dados_finais, estatisticas, pasta_pdfs, pasta_output)
    # except Exception as ex:
    #     print(f"Erro Crítico ao gerar o relatório final em Excel/Zip: {ex}")
    
    print("\nResumo da Operação:")
    print(f"Sucesso: {estatisticas['sucesso']}")
    print(f"Falhas por Senha/Login: {estatisticas['senha_errada']}")
    print(f"Falha de Extração Técnica: {estatisticas['falha_extracao']}")
    print(f"Faltaram Senhas: {estatisticas['sem_senha']}")
    print("\nOperação concluída com sucesso! Verifique a pasta 'output'.")

if __name__ == "__main__":
    main()
