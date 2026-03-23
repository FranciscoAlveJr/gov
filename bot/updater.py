import os
import sys
import logging

logger = logging.getLogger("BotINSS")
import time
import requests
import subprocess
from bot.notifier import enviar_mensagem_telegram

# URL real do seu GitHub. O raw link para ler o arquivo de versão.
VERSION_URL = "https://raw.githubusercontent.com/FranciscoAlveJr/gov/main/data/version.txt"

# Link genérico para onde hospedaremos o .exe fixo no GitHub Releases (fase 3)
UPDATE_URL = "https://github.com/FranciscoAlveJr/gov/releases/latest/download/Bot_INSS.exe"

def check_and_update():
    """
    Verifica se existe uma nova versão no GitHub. 
    Se existir, baixa o novo .exe, cria um .bat para substituir o arquivo em uso e reinicia o bot.
    """
    # Se estiver rodando como .py normal (dev mode), não faz o update agressivo com .bat
    is_exe = getattr(sys, 'frozen', False)
    
    if is_exe:
        base_dir_app = os.path.dirname(sys.executable)
    else:
        base_dir_app = os.path.abspath(os.getcwd())

    # Para saber a versão atual, lemos o arquivo "version.txt" dentro da pasta "data"
    versao_local = "0.0.0"
    caminho_versao = os.path.join(base_dir_app, "data", "version.txt")
    if os.path.exists(caminho_versao):
        with open(caminho_versao, "r") as f:
            versao_local = f.read().strip()
    
    try:
        response = requests.get(VERSION_URL, timeout=10)
        
        if response.status_code == 200:
            versao_remota = response.text.strip()
            
            if versao_remota != versao_local:
                msg = f"🔄 *Atualização Encontrada!*\nVersão local: `{versao_local}`\nNova versão: `{versao_remota}`\n\n⬇️ Baixando atualização..."
                logger.info(msg)
                enviar_mensagem_telegram(msg)
                
                if not is_exe:
                    logger.info("\n[MODO DESENVOLVEDOR] Atualização ignorada, pois você está rodando o script .py diretamente. O update funciona no programa compilado (.exe).")
                    return
                
                # Baixa o novo arquivo .exe
                exe_req = requests.get(UPDATE_URL, stream=True)
                if exe_req.status_code == 200:
                    update_exe_path = os.path.join(base_dir_app, "update_novo.exe")
                    with open(update_exe_path, "wb") as f:
                        for chunk in exe_req.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    logger.info("Download concluído. Fechando para atualizar...")
                    enviar_mensagem_telegram("✅ Download finalizado. Reiniciando o bot com a nova versão.")
                    
                    # 1. Atualizar o arquivo version.txt localmente para a nova versão
                    with open(caminho_versao, "w") as f:
                        f.write(versao_remota)
                    
                    # Nome do executável atual (geralmente Bot_INSS.exe)
                    executavel_atual = sys.executable
                    nome_exe = os.path.basename(executavel_atual)
                    
                    # Vamos criar um script indestrutível com tentativas de substituição repetidas (loop :RETRY)
                    # Forçamos a morte do bot antigo se ele estiver grudado na RAM travando o arquivo
                    script_bat = f"""@echo off
title Atualizando Bot INSS...
echo Aguardando o bot fechar...
timeout /t 3 /nobreak > NUL

:: Força a morte do processo antigo (incluindo o bootloader do PyInstaller) para liberar o arquivo
taskkill /F /IM "{nome_exe}" /T > NUL 2>&1

:RETRY
echo Tentando substituir o arquivo...
move /y "{update_exe_path}" "{executavel_atual}"
IF ERRORLEVEL 1 (
    echo Arquivo ainda em uso pelo Windows. Tentando novamente em 2 segundos...
    timeout /t 2 /nobreak > NUL
    goto RETRY
)

echo ==============================================================
echo ATUALIZACAO CONCLUIDA! NOVA VERSAO INSTALADA.
echo POR FAVOR, ABRA O BOT INSS NOVAMENTE PARA UTILIZA-LO (OU AGUARDE O AGENDADOR DE TAREFAS).
echo ==============================================================
echo Pressione qualquer tecla para sair desta tela de atualizacao...
pause > NUL

(goto) 2>nul ^& del "%~f0"
"""
                    
                    # Cria o arquivo .bat de atualização
                    caminho_bat = os.path.join(base_dir_app, "atualizar_bot.bat")
                    with open(caminho_bat, "w", encoding="utf-8") as b:
                        b.write(script_bat)
                    
                    # Executa o .bat usando o comando nativo do Windows (os.startfile)
                    # Isso garante 100% que o processo nasce independente do Python e não morre no exit()
                    os.startfile(caminho_bat)
                    sys.exit(0)
                else:
                    logger.info("Erro ao tentar baixar o arquivo executável da atualização.")
                    enviar_mensagem_telegram("⚠️ *Erro na atualização*: Não foi possível baixar o novo arquivo do GitHub (Status != 200).")
            else:
                logger.info("✅ O bot já está na versão mais recente.")
        else:
            logger.info("Não foi possível verificar a versão (Status != 200).")
    except Exception as e:
        logger.info(f"Erro ao verificar atualizações: {e}")
