import pandas as pd
from config import INPUT_FILE

def read_input_data(filepath=INPUT_FILE):
    """
    Lê a planilha de origem e retorna uma lista de dicionários.
    As colunas esperadas são:
    'CLIENTE', 'CPF', 'SENHA GOV', 'PROCESSO', 'TIPO DE PROCESSO', 
    'GRUPO DE PROCESSO', 'ESFERA', 'PARCEIRO', 'LÍDER', 
    'PETICIONANTE', 'CRIADOR', 'DATA DE INCLUSÃO'
    """
    try:
        df = pd.read_excel(filepath)
        # Preencher valores nulos com string vazia para facilitar validações
        df = df.fillna("")
        
        # Converter os dados para uma lista de dicionários (uma linha = um dit)
        records = df.to_dict(orient="records")
        return records
    except Exception as e:
        print(f"Erro ao ler planilha: {e}")
        return []
