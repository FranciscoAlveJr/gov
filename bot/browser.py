from time import sleep
import random
import os
import tempfile
from playwright.sync_api import Page
from playwright.sync_api import sync_playwright
from playwright.sync_api import Request
from playwright.sync_api import TimeoutError
from playwright_stealth import Stealth
import logging

import base64

logger = logging.getLogger("BotINSS")

class LoginError(Exception):
    pass

def obter_caminho_chrome_local():
    """
    Busca o executável do Google Chrome na máquina do cliente, 
    independentemente de onde foi instalado.
    """
    caminhos_possiveis = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for caminho in caminhos_possiveis:
        if os.path.exists(caminho):
            return caminho
    raise Exception("Google Chrome não encontrado no sistema. É necessário instalá-lo para rodar o bot.")


_playwright_cm = None
_playwright_instance = None
_browser_context = None
_browser_page = None

def fechar_browser():
    global _playwright_cm, _playwright_instance, _browser_context, _browser_page
    try:
        if _browser_context:
            try:
                _browser_context.close()
            except: pass
        if _playwright_instance:
            try:
                _playwright_instance.stop()
            except: pass
    except Exception as e:
        logger.debug(f"Erro ao fechar navegador: {e}")
    finally:
        _playwright_cm = None
        _playwright_instance = None
        _browser_context = None
        _browser_page = None

def obter_pagina_persistente(headless=False):
    global _playwright_cm, _playwright_instance, _browser_context, _browser_page
    
    if _browser_page and not _browser_page.is_closed():
        return _browser_page, _browser_context

    import sys
    if getattr(sys, 'frozen', False):
        caminho_base = os.path.dirname(sys.executable)
    else:
        caminho_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    extensao_path = os.path.join(caminho_base, "extensions", "capsolver")

    args = [
        '--start-maximized',
        '--disable-blink-features=AutomationControlled'
    ]
    
    if os.path.exists(extensao_path):
        args.append(f"--disable-extensions-except={extensao_path}")
        args.append(f"--load-extension={extensao_path}")

    _playwright_cm = Stealth().use_sync(sync_playwright())
    _playwright_instance = _playwright_cm.__enter__()

    profile_dir = os.path.join(caminho_base, "data", "chrome_profile")
    os.makedirs(profile_dir, exist_ok=True)
    
    chrome_exe = obter_caminho_chrome_local()

    _browser_context = _playwright_instance.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        executable_path=chrome_exe,
        headless=headless,
        args=args,
        ignore_default_args=["--disable-extensions", "--disable-component-extensions-with-background-pages", "--enable-automation"],
    )
    _browser_page = _browser_context.pages[0] if _browser_context.pages else _browser_context.new_page()
    return _browser_page, _browser_context

def preparar_aba_novo_login(context, page: Page):
    """
    Mantém o browser/contexto abertos, mas cria uma aba nova para cada usuário.
    Isso reduz estado residual de captcha sem fechar a janela principal.
    """
    global _browser_page

    pagina_anterior = page
    nova_pagina = context.new_page()
    nova_pagina.bring_to_front()
    _browser_page = nova_pagina

    try:
        if pagina_anterior and not pagina_anterior.is_closed():
            pagina_anterior.close()
    except Exception as e:
        logger.debug(f"Não foi possível fechar aba anterior: {e}")

    return nova_pagina

def deslogar_se_necessario(page: Page):
    try:
        # Acessa a página base do login se não estiver nela
        if "meu.inss.gov.br" not in page.url:
            page.goto("https://meu.inss.gov.br/#/login", wait_until="networkidle")

        # Verifica botão de avatar do Gov.br ou INSS
        avatar_btn = page.locator('button#avatar-dropdown-trigger, button.btn-avatar').first
        if avatar_btn.is_visible(timeout=3000):
            logger.info("Usuário logado detectado. Realizando logout para a próxima conta...")
            avatar_btn.click()
            page.wait_for_timeout(1500)
            
            # Tentar achar pelo texto
            sair_btn = page.locator('button:has-text("Sair do Meu INSS")').first
            if not sair_btn.is_visible(timeout=2000):
                # Fallback: tentar pelo ícone especifico
                sair_btn = page.locator('button:has(i.fas.fa-power-off)').first
                
            if sair_btn.is_visible(timeout=3000):
                sair_btn.click()
                logger.info("Logout realizado com sucesso.")
                # Esperar cair na tela de login novamente
                page.wait_for_url("**/login**", timeout=15000)
                page.wait_for_timeout(2000)
        else:
            try:
                sair_btn = page.get_by_role('button').filter(has_text="Sair do Meu INSS").first
                if sair_btn.is_visible(timeout=2000):
                    logger.info("Usuário logado detectado (sem avatar). Realizando logout para a próxima conta...")
                    sair_btn.click()
                    logger.info("Logout realizado com sucesso.")
                    page.wait_for_url("**/login**", timeout=15000)
                    page.wait_for_timeout(2000)
            except TimeoutError:
                pass
    except Exception as e:
        logger.debug(f"Processo de verificação de logout concluído (Nenhum usuário estava logado): {e}")

def login_e_extrair_tokens(cpf: str, senha: str, headless: bool = False):
    """
    Acessa o site do meu.inss.gov.br, realiza o login pelo gov.br usando CPF e senha,
    e retorna informações de sessão.
    Mantém a janela do navegador aberta com a mesma sessão entre execuções.
    """
    cpf_str = str(cpf).strip()
    senha_str = str(senha).strip()

    if not cpf_str or not senha_str:
        raise ValueError("CPF ou Senha vazio")

    try:
        page, context = obter_pagina_persistente(headless=headless)
        
        # Desloga caso tenha sobrado login da iteração anterior
        deslogar_se_necessario(page)

        # Reabre aba limpa para o novo ciclo de captcha/login sem fechar o navegador
        page = preparar_aba_novo_login(context, page)
        
        logger.info(f"[{cpf_str}] Acessando portal Meu INSS...")
        page.goto("https://meu.inss.gov.br/#/login", wait_until="networkidle")

        # Aguardar o botão de "Entrar com gov.br" e clicar
        btn_entrar = page.locator('button#main-content', has_text="Entrar com gov.br")
        btn_entrar.wait_for(state="visible", timeout=10000)
        btn_entrar.click()

        # Aguardar redirecionamento para sso.acesso.gov.br
        logger.info(f"[{cpf_str}] Redirecionando para gov.br...")
        page.wait_for_selector('input#accountId')

        # Preencher CPF de forma mais lenta, aleatória e humana
        logger.info(f"[{cpf_str}] Preenchendo CPF...")
        cpf_locator = page.locator('input#accountId')
        cpf_locator.click()
        sleep(random.uniform(0.3, 0.8))
        for char in cpf_str:
            cpf_locator.press_sequentially(char)
            sleep(random.uniform(0.05, 0.25))
        
        sleep(random.uniform(0.5, 1.5))
        page.click('button#enter-account-id')

        # Aguardar campo de senha
        page.wait_for_selector('input#password', timeout=120000)
        sleep(random.uniform(1.5, 3.0))

        # Preencher Senha de forma mais lenta, aleatória e humana
        logger.info(f"[{cpf_str}] Preenchendo Senha...")
        senha_locator = page.locator('input#password')
        senha_locator.click()
        sleep(random.uniform(0.3, 0.8))
        for char in senha_str:
            senha_locator.press_sequentially(char)
            sleep(random.uniform(0.05, 0.25))
            
        sleep(random.uniform(0.5, 1.5))

        bearer_token = None
        token = None
        
        def intercept_response(responses: list[Request]):
            nonlocal bearer_token, token
            for request in responses:
                if request.method == "OPTIONS":
                    continue

                if "usuarioservices/info" in request.url:
                    try:
                        req_headers = request.headers
                        if "authorization" in req_headers:
                            bearer_token = req_headers["authorization"].replace("Bearer ", "").strip()
                        elif "Authorization" in req_headers:
                            bearer_token = req_headers["Authorization"].replace("Bearer ", "").strip()

                        if request.response().ok:
                            data = request.response().json()
                            token = data.get("miToken", "")
                    except Exception as err:
                        logger.info(f"Erro ao ler JSON da API: {err}")

        page.click('button#submit-button')

        try:
            page.wait_for_selector('.br-message.warning', timeout=5000)
            error_text = page.locator('.br-message.warning').inner_text()
            raise LoginError(f"Erro no login: {error_text}")        
        except TimeoutError:
            pass

        logger.info(f"[{cpf_str}] Aguardando autenticação e interceptando o tráfego do navegador...")
        
        try:
            error_msg = page.wait_for_selector('div.message.error', timeout=5000)
            if error_msg:
                texto_erro = error_msg.inner_text()
                raise LoginError(f"Erro no login: {texto_erro}")
        except TimeoutError:
            pass

        page.wait_for_url("**/meu.inss.gov.br/**", timeout=30000)
        page.wait_for_load_state("networkidle")

        try:
            logger.info(f"[{cpf_str}] Aguardando 5s para verificar ausência de tela de erro de cadastro...")
            erro_cadastro = page.wait_for_selector('text="Dados cadastrais diferentes ou incompletos"', timeout=5000)
            if erro_cadastro:
                logger.warning(f"[{cpf_str}] Foi detectada a tela de erro de Dados Cadastrais. Aguardando 2s para confirmação...")
                page.wait_for_timeout(2000)
                raise LoginError("Dados cadastrais diferentes ou incompletos.")
        except TimeoutError:
            # Não apareceu a tela de erro dentro dos 5 segundos, fluxo segue normal.
            pass

        logger.info(f"[{cpf_str}] Coletando token e ID da sessão interceptando o tráfego do navegador...")

        reqs = page.requests()

        intercept_response(reqs)
        
        if not token:
            logger.info(f"[{cpf_str}] ATENÇÃO: Token não encontrado na intercepção.")
        
        cookies = context.cookies()
        auth_dict = {
            "cookies": cookies,
            "mitoken": token,
            "bearer": bearer_token,
            "user_agent": page.evaluate("navigator.userAgent")
        }
        
        logger.info(f"[{cpf_str}] Login concluído, dados de sessão coletados. Token mitoken obtido: {'Sim' if token else 'Não'}")
        return auth_dict

    except Exception as e:
        logger.info(f"[{cpf_str}] Falha durante o processo: {e}")
        return False
        
