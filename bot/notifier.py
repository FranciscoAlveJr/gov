import requests
import json
import os
import logging

logger = logging.getLogger("BotINSS")
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv('data/.env')

# ==========================================
# CONFIGURAÇÕES DO TELEGRAM
# Você vai preencher esses dados no Passo 2!
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "SEU_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "SEU_CHAT_ID_AQUI")

def enviar_mensagem_telegram(mensagem):
    """
    Envia uma mensagem de texto para o chat configurado no Telegram.
    """
    if TELEGRAM_BOT_TOKEN == "SEU_TOKEN_AQUI" or TELEGRAM_CHAT_ID == "SEU_CHAT_ID_AQUI":
        logger.info("[Log] Telegram não configurado. Mensagem ignorada.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML" # Permite usar negrito (<b>), itálico (<i>), etc.
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == 200:
            logger.info("[Log] Notificação enviada ao Telegram com sucesso.")
            return True
        else:
            logger.info(f"[Log] Falha ao enviar para o Telegram: {response.text}")
            return False
    except Exception as e:
        logger.info(f"[Log] Erro de conexão com o Telegram: {e}")
        return False

def enviar_documento_telegram(caminho_arquivo, caption=""):
    """
    Envia um arquivo físico (.log, .zip, .pdf) para o Telegram.
    """
    if TELEGRAM_BOT_TOKEN == "SEU_TOKEN_AQUI" or TELEGRAM_CHAT_ID == "SEU_CHAT_ID_AQUI":
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption,
        "parse_mode": "HTML"
    }

    try:
        with open(caminho_arquivo, 'rb') as f:
            files = {'document': f}
            response = requests.post(url, data=data, files=files)
            if response.status_code == 200:
                logger.info(f"[Log] Arquivo {os.path.basename(caminho_arquivo)} enviado com sucesso.")
                return True
            else:
                logger.info(f"[Log] Falha ao enviar arquivo para o Telegram: {response.text}")
                return False
    except Exception as e:
        logger.info(f"[Log] Erro ao enviar documento para o Telegram: {e}")
        return False

def enviar_resumo_execucao(nome_cliente, estatisticas, arquivo_zip=None):
    """
    Formata as estatísticas em uma mensagem bonita e envia.
    """
    total = estatisticas.get('sucesso', 0) + estatisticas.get('falha_extracao', 0) + estatisticas.get('senha_errada', 0) + estatisticas.get('sem_senha', 0)
    
    msg = f"🤖 <b>RPA INSS - Execução Finalizada</b>\n\n"
    msg += f"👤 <b>Cliente/Máquina:</b> {nome_cliente}\n"
    msg += f"⏱️ <b>Início:</b> {estatisticas.get('start_time', 'N/A')}\n"
    msg += f"🏁 <b>Fim:</b> {estatisticas.get('end_time', 'N/A')}\n"
    msg += f"📊 <b>Total de Processos Lidos:</b> {total}\n\n"
    
    msg += f"✅ <b>Sucessos:</b> {estatisticas.get('sucesso', 0)}\n"
    msg += f"❌ <b>Falhas Extração:</b> {estatisticas.get('falha_extracao', 0)}\n"
    msg += f"🔑 <b>Senhas Erradas:</b> {estatisticas.get('senha_errada', 0)}\n"
    msg += f"📭 <b>Sem Senha:</b> {estatisticas.get('sem_senha', 0)}\n"
    
    enviar_mensagem_telegram(msg)
