from input_reader import read_input_data
from bot.browser import login_e_extrair_tokens
from bot.api_client import APIClient
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os

def main():
    print("Testando fluxo inicial de login e extração...")
    
    # Lendo planilha
    clientes = read_input_data()
    print(f"Total de registros encontrados: {len(clientes)}")

    if not clientes:
        print("Nenhum dado para processar.")
        return

    # Usando o primeiro cliente para teste manual
    primeiro_cliente = clientes[0]
    
    cliente_nome = primeiro_cliente.get("CLIENTE", "Desconhecido")
    cpf = primeiro_cliente.get("CPF", "")
    senha = primeiro_cliente.get("SENHA GOV", "")

    print("\n--- Testando Cliente ---")
    print(f"Nome: {cliente_nome}")
    print(f"CPF: {cpf}")
    print(f"Senha fornecida? {'Sim' if senha else 'Não'}")

    if not cpf or not senha:
        print("CPF ou Senha ausentes para este cliente. Teste interrompido.")
        return

    # 1. Realizar Login e Extração de Sessão
    print("\nIniciando navegador...")
    auth_dados = login_e_extrair_tokens(cpf, senha, headless=False)
    
    if auth_dados:
        print(f"\n=> SUCESSO na fase 1: Login pelo Playwright realizado e base da sessão extraída!")
        
        # 2. Configurar o Cliente de API 
        try:
            api = APIClient()
            api.configure_session(auth_dados)
            
            # Vamos gerar as datas (de 5 anos atrás para frente)
            hoje = datetime.now()
            ha_cinco_anos = hoje - relativedelta(years=5)
            
            # O sistema pede o formato DD-MM-YYYY
            # Vou estender a data fim pra frente para garantir que cobrimos o próximo mês de possível implantação
            fim_date = hoje

            str_inicio = ha_cinco_anos.strftime("%d-%m-%Y")
            str_fim = fim_date.strftime("%d-%m-%Y")
            
            # 3. Teste chamada JSON Hiscre
            print(f"\n[{cpf}] Testando requisição de Hiscre JSON ({str_inicio} até {str_fim})...")
            dados_hiscre = api.get_historico_creditos(cpf, str_inicio, str_fim)
            
            print(f"Sucesso na requisição Hiscre! JSON parcial retornado: {str(dados_hiscre)[:300]}...")
            
            # 4. Teste download PDF do extrato de benefício
            print("\nTestando Download do arquivo PDF de Extrato...")
            pdf_out_dir = os.path.join("output", "Pdfs")
            safename = str(cliente_nome).replace("/", "_").replace("\\", "_")
            pdf_file_path = os.path.join(pdf_out_dir, f"{safename} - {cpf}.pdf")
            
            arquivo_salvo = api.download_pdf_historico(cpf, str_inicio, str_fim, pdf_file_path)
            
            print(f"SUCESSO TOTAL! PDF escrito em: {arquivo_salvo}")
            
        except Exception as e:
            print(f"\n=> FALHA EXTRAÇÃO API: {e}")
            
    else:
        print(f"\n=> FALHA DE LOGIN: Não foi possível completar o login para {cliente_nome}")

if __name__ == "__main__":
    main()
