import pandas as pd
from config import INPUT_DIR
from glob import glob
import os
import sys
import logging

logger = logging.getLogger("BotINSS")

def read_input_data(filepath=INPUT_DIR):
    """
    Lê a planilha de origem e retorna uma lista de dicionários.
    As colunas esperadas são:
    'CLIENTE', 'CPF', 'SENHA GOV', 'PROCESSO', 'TIPO DE PROCESSO', 
    'GRUPO DE PROCESSO', 'ESFERA', 'PARCEIRO', 'LÍDER', 
    'PETICIONANTE', 'CRIADOR', 'DATA DE INCLUSÃO'
    """
    try:
        # Procurar o arquivo excel na pasta input
        arquivos = glob(os.path.join(filepath, "*.xlsx"))
        file = arquivos[0] if arquivos else None

        if not file:
            logger.error("Nenhum arquivo Excel encontrado na pasta de input.")
            print("[ Aviso: O bot precisa de planilha da pasta 'input' para rodar. Coloque o arquivo lá e execute novamente. ]")
            input("\nPressione ENTER para sair...")
            import sys
            sys.exit(0)

        df = pd.read_excel(file)
        
        # Formatar a DATA DE INCLUSÃO para string dd/mm/yyyy (se houver a coluna)
        if 'DATA DE INCLUSÃO' in df.columns:
            # Converte para datetime de forma segura
            col_data = pd.to_datetime(df['DATA DE INCLUSÃO'], errors='coerce')
            # Formata apenas os valores não nulos (NaT)
            df['DATA DE INCLUSÃO'] = col_data.dt.strftime('%d/%m/%Y')

        # Preencher valores nulos (incluindo datas que falharam no parse) com string vazia
        df = df.fillna("")
        
        # Converter os dados para uma lista de dicionários (uma linha = um dit)
        records = df.to_dict(orient="records")
        return records
    except Exception as e:
        logger.exception(f"Erro ao ler planilha: {e}")
        return []
