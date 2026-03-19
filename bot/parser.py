import datetime
from dateutil.relativedelta import relativedelta

def analisar_historico_creditos(json_data: dict, data_consulta=None):
    """
    Analisa os dados em JSON retornados pela API hiscreServices/historicocreditos
    e aplica as regras de negócio para definir:
    - ALERTA DE IMPLANTAÇÃO ou NÃO IMPLANTADO
    - ALERTA DE PAB
    - E extrai as previsões de pagamento, saldo e banco caso implantado.
    """
    if data_consulta is None:
        data_consulta = datetime.date.today()
    
    resultado = {
        "IMPLANTAÇÃO": "NÃO IMPLANTADO",
        "PAB": "",
        "PREVISAO_PAGAMENTO": "",
        "VALOR_TOTAL": 0.0,
        "BANCO": ""
    }

    # Se não houver dados de crédito, retorna os padrões (Não Implantado)
    if not json_data or "creditosTO" not in json_data:
        return resultado

    creditos: list[dict] = json_data.get("creditosTO", [])
    
    # 1. Definir os meses de interesse para Implantação (Mês Atual e Próximo Mês)
    # Formato esperado: MM/YYYY
    mes_atual: str = data_consulta.strftime("%m/%Y")
    proximo_mes_date: datetime.date = data_consulta + relativedelta(months=1)
    prox_mes: str = proximo_mes_date.strftime("%m/%Y")
    
    meses_alvo = [mes_atual, prox_mes]
    
    tem_implantacao = False
    tem_pab = False
    
    # Estruturas para nos ajudar a somar os valores para uma mesma previsão de pagamento
    # Vamos agrupar pelo "dtInicioValidade" (Previsão de pagamento)
    valores_por_data: dict[str, float] = {}
    banco_por_data: dict[str, str] = {}

    for credito in creditos:
        # Extrair dados básicos do crédito
        dt_inicio_periodo = credito.get("dtInicioPeriodo", "")
        dt_fim_periodo = credito.get("dtFimPeriodo", "")
        dt_inicio_validade = credito.get("dtInicioValidade", "") # Nossa Data de Previsão
        dt_fim_validade = credito.get("dtFimValidade", "")
        dt_movimentacao = credito.get("dtMovimentacao", "")
        
        in_credito_pago = credito.get("inCreditoPago", False)
        valor_liquido = float(credito.get("valorLiquido", 0.0))
        
        # Recuperar o nome do Banco (No json: orgaoPagadorTO -> nmAAP)
        orgao: dict[str, str] = credito.get("orgaoPagadorTO", {})
        nm_banco: str = orgao.get("nmAAP", "")
        
        # --- VERIFICAÇÃO Regra 1: ALERTA DE IMPLANTAÇÃO ---
        # A regra diz "se aparecer em qualquer lugar do hiscre o mês atual ou o próximo"
        todas_datas_str = f"{dt_inicio_periodo} {dt_fim_periodo} {dt_inicio_validade} {dt_fim_validade} {dt_movimentacao}"
        for alvo in meses_alvo:
            if alvo in todas_datas_str:
                tem_implantacao = True
                
                # Vamos agrupar os valores desse crédito para a extração (Detalhe 1)
                if dt_inicio_validade not in valores_por_data:
                    valores_por_data[dt_inicio_validade] = 0.0
                
                valores_por_data[dt_inicio_validade] += valor_liquido
                banco_por_data[dt_inicio_validade] = nm_banco

        # --- VERIFICAÇÃO Regra 3: ALERTA DE PAB ---
        # Status "não pago/em branco" + "Data de Validade Fim" já ultrapassada.
        # no JSON: inCreditoPago == false e dtFimValidade < data_consulta
        if in_credito_pago is False and dt_fim_validade:
            try:
                data_fim_val_obj = datetime.datetime.strptime(dt_fim_validade, "%d/%m/%Y").date()
                if data_fim_val_obj < data_consulta:
                    tem_pab = True
            except ValueError:
                pass


    # Preenchendo os resultados finais após analisar todos os créditos
    if tem_implantacao:
        resultado["IMPLANTAÇÃO"] = "ALERTA DE IMPLANTAÇÃO"
        
        # "Somatório de todas as colunas de Valor Líquido que estiverem com a mesma data de 'Previsão de Pagamento'."
        # Se houver mais de uma data alvo encontrada, pegamos a de maior valor ou a mais recente.
        # Por simplicidade, vamos pegar a data de previsão que tem o maior montante a receber:
        if valores_por_data:
            melhor_data = max(valores_por_data, key=valores_por_data.get)
            resultado["PREVISAO_PAGAMENTO"] = melhor_data
            resultado["VALOR_TOTAL"] = valores_por_data[melhor_data]
            resultado["BANCO"] = banco_por_data[melhor_data]

    if tem_pab:
        resultado["PAB"] = "ALERTA DE PAB"

    return resultado
