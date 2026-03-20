import pandas as pd
from config import INPUT_DIR
from glob import glob
import os

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
            print("Nenhum arquivo Excel encontrado na pasta de input.")
            return []

        df = pd.read_excel(file)
        # Preencher valores nulos com string vazia para facilitar validações
        df = df.fillna("")
        
        # Converter os dados para uma lista de dicionários (uma linha = um dit)
        records = df.to_dict(orient="records")
        return records
    except Exception as e:
        print(f"Erro ao ler planilha: {e}")
        return []
