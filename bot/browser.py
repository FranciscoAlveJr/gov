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

class BlockedUserError(Exception):
    pass

class PageDataError(Exception):
    pass

class TwoFactorAuthError(Exception):
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
    except Exception:
        logger.debug(f"Processo de verificação de logout concluído (Nenhum usuário estava logado)")

def _coletar_tokens_da_pagina(page: Page, context, cpf_str: str) -> dict:
    """
    Coleta os tokens de autenticação (bearer + miToken) a partir das requests
    já realizadas pela página, além dos cookies e user-agent.
    """
    bearer_token = None
    token = None

    for request in page.requests():
        if request.method == "OPTIONS":
            continue
        if "usuarioservices/info" in request.url:
            try:
                req_headers = request.headers
                if "authorization" in req_headers:
                    bearer_token = req_headers["authorization"].replace("Bearer ", "").strip()
                elif "Authorization" in req_headers:
                    bearer_token = req_headers["Authorization"].replace("Bearer ", "").strip()
                if request.response() and request.response().ok:
                    data = request.response().json()
                    token = data.get("miToken", "")
            except Exception as err:
                logger.debug(f"Erro ao ler JSON da API durante coleta de tokens: {err}")

    if not token:
        logger.info(f"[{cpf_str}] ATENÇÃO: Token não encontrado na intercepção.")

    cookies = context.cookies()
    auth_dict = {
        "cookies": cookies,
        "mitoken": token,
        "bearer": bearer_token,
        "user_agent": page.evaluate("navigator.userAgent")
    }
    return auth_dict


def _verificar_erros_pos_login(page: Page, cpf_str: str):
    """
    Verifica erros comuns após o envio das credenciais.
    Lança as exceções apropriadas se detectar bloqueio, senha errada, 2FA ou erro de página.
    """
    # Erro 502 / Servidor indisponível
    try:
        if (
            page.locator('text="502 Bad Gateway"').is_visible(timeout=2000)
            or page.locator('text="Bad Gateway"').is_visible(timeout=1000)
            or page.locator('text="Internal Server Error"').is_visible(timeout=1000)
            or page.locator('text="Erro interno"').is_visible(timeout=1000)
            or page.locator('text="Servidor indisponível"').is_visible(timeout=1000)
        ):
            raise TimeoutError("Erro 502/Interno detectado. Será feita nova tentativa.")
    except TimeoutError as te:
        if "502" in str(te) or "Interno" in str(te):
            raise

    # Erro 403 / Acesso negado
    try:
        if (
            page.locator('text="403 Forbidden"').is_visible(timeout=2000)
            or page.locator('text="Access Denied"').is_visible(timeout=1000)
            or page.locator('text="Acesso Negado"').is_visible(timeout=1000)
        ):
            raise TimeoutError("Erro 403/Acesso Negado detectado. Será feita nova tentativa.")
    except TimeoutError as te:
        if "403" in str(te) or "Acesso Negado" in str(te):
            raise

    # 2FA
    try:
        if page.locator('#twoFactorForm').is_visible(timeout=2000):
            raise TwoFactorAuthError("Autenticação de Dois Fatores exigida.")
    except TimeoutError:
        pass

    # Mensagem de aviso/erro no gov.br (.br-message.warning)
    try:
        page.wait_for_selector('.br-message.warning', timeout=3000)
        error_text = page.locator('.br-message.warning').inner_text()
        error_text_lower = error_text.lower()
        if "bloquead" in error_text_lower or "suspens" in error_text_lower:
            raise BlockedUserError(f"Usuário Bloqueado: {error_text}")
        elif any(kw in error_text_lower for kw in ["senha", "inválid", "incorret"]):
            raise LoginError(f"Erro no login: {error_text}")
        else:
            raise PageDataError(f"Erro na página gov: {error_text}")
    except TimeoutError:
        pass

    # Mensagem de erro div.message.error (INSS)
    try:
        error_msg = page.wait_for_selector('div.message.error', timeout=3000)
        if error_msg:
            texto_erro = error_msg.inner_text()
            texto_erro_lower = texto_erro.lower()
            if "bloquead" in texto_erro_lower or "suspens" in texto_erro_lower:
                raise BlockedUserError(f"Usuário Bloqueado: {texto_erro}")
            elif any(kw in texto_erro_lower for kw in ["senha", "inválid", "incorret"]):
                raise LoginError(f"Erro no login: {texto_erro}")
            else:
                raise PageDataError(f"Erro na página gov: {texto_erro}")
    except TimeoutError:
        pass


def login_e_extrair_tokens(cpf: str, senha: str, headless: bool = False):
    """
    Acessa o site do meu.inss.gov.br e realiza o login pelo gov.br usando CPF e senha.
    Trata três cenários distintos ao abrir o browser:

      Cenário A – Browser já logado na página do cliente:
        O avatar está visível assim que a página carrega. Coleta os tokens diretamente.

      Cenário B – Página principal do INSS, sessão ativa no gov.br:
        O botão 'Entrar com gov.br' está presente, mas ao clicar ele já redireciona
        para a área do cliente sem pedir CPF/senha novamente.

      Cenário C – Fluxo normal (sem sessão ativa):
        Redireciona para sso.acesso.gov.br e exige CPF + senha.

    Retorna um dicionário com cookies, mitoken, bearer e user_agent.
    """
    cpf_str = str(cpf).strip()
    senha_str = str(senha).strip()

    if not cpf_str or not senha_str:
        raise ValueError("CPF ou Senha vazio")

    while True:
        try:
            page, context = obter_pagina_persistente(headless=headless)

            # Abre aba limpa para o novo ciclo sem fechar o navegador
            page = preparar_aba_novo_login(context, page)

            # Desloga de contas anteriores
            deslogar_se_necessario(page)

            tentativas_login = 0
            while True:
                try:
                    logger.info(f"[{cpf_str}] Acessando portal Meu INSS...")
                    page.goto("https://meu.inss.gov.br/#/login", wait_until="domcontentloaded")

                    # --- Cenário A: já logado (avatar visível antes mesmo de clicar) ---
                    try:
                        avatar_btn = page.locator('button#avatar-dropdown-trigger, button.btn-avatar').first
                        avatar_btn.wait_for(state="visible", timeout=4000)
                        logger.info(f"[{cpf_str}] CENÁRIO A: Browser já logado na página do cliente. Coletando tokens...")
                        page.wait_for_load_state("networkidle", timeout=30000)
                        auth_dict = _coletar_tokens_da_pagina(page, context, cpf_str)
                        logger.info(f"[{cpf_str}] Login concluído (Cenário A). Token obtido: {'Sim' if auth_dict['mitoken'] else 'Não'}")
                        return auth_dict
                    except TimeoutError:
                        pass  # Avatar não visível ainda, continua para o próximo cenário

                    # --- Cenário B e C: há botão 'Entrar com gov.br' ---
                    btn_entrar = page.locator('button#main-content', has_text="Entrar com gov.br")
                    btn_entrar.wait_for(state="visible", timeout=10000)
                    btn_entrar.click()
                    logger.info(f"[{cpf_str}] Botão 'Entrar com gov.br' clicado. Aguardando resposta do site...")

                    # Espera para saber qual caminho o site vai tomar
                    # Pode ir para: (B) avatar do INSS  |  (C) campo CPF do gov.br
                    try:
                        page.wait_for_selector(
                            'button#avatar-dropdown-trigger, button.btn-avatar, input#accountId',
                            timeout=15000
                        )
                    except TimeoutError:
                        logger.warning(f"[{cpf_str}] Timeout esperando redirecionamento após clicar em Entrar.")
                        raise

                    # --- Cenário B: sessão gov.br ativa → avatar aparece sem pedir senha ---
                    avatar_pos_click = page.locator('button#avatar-dropdown-trigger, button.btn-avatar').first
                    if avatar_pos_click.is_visible(timeout=1000):
                        logger.info(f"[{cpf_str}] CENÁRIO B: Sessão gov.br ativa. Redirecionado diretamente para a área do cliente.")
                        page.wait_for_load_state("networkidle", timeout=30000)
                        auth_dict = _coletar_tokens_da_pagina(page, context, cpf_str)
                        logger.info(f"[{cpf_str}] Login concluído (Cenário B). Token obtido: {'Sim' if auth_dict['mitoken'] else 'Não'}")
                        return auth_dict

                    # --- Cenário C: fluxo normal, campo de CPF presente ---
                    logger.info(f"[{cpf_str}] CENÁRIO C: Fluxo normal. Preenchendo CPF no gov.br...")
                    cpf_locator = page.locator('input#accountId')
                    cpf_locator.wait_for(state="visible", timeout=5000)
                    cpf_locator.click()
                    sleep(random.uniform(0.3, 0.8))
                    for char in cpf_str:
                        cpf_locator.press_sequentially(char)
                        sleep(random.uniform(0.05, 0.25))

                    sleep(random.uniform(0.5, 1.5))
                    page.click('button#enter-account-id')

                    _verificar_erros_pos_login(page, cpf_str)

                    # Aguardar campo de senha
                    logger.info(f"[{cpf_str}] Aguardando campo de senha...")
                    page.wait_for_selector('input#password', timeout=60000)
                    sleep(random.uniform(1.5, 3.0))

                    logger.info(f"[{cpf_str}] Preenchendo senha...")
                    senha_locator = page.locator('input#password')
                    senha_locator.click()
                    sleep(random.uniform(0.3, 0.8))
                    for char in senha_str:
                        senha_locator.press_sequentially(char)
                        sleep(random.uniform(0.05, 0.25))

                    sleep(random.uniform(0.5, 1.5))

                    # Submete as credenciais
                    page.click('button#submit-button')
                    sleep(1)

                    # Verifica erros comuns pós-envio (502, 2FA, senha errada, bloqueio)
                    _verificar_erros_pos_login(page, cpf_str)

                    # Aguarda redirecionamento para o INSS
                    logger.info(f"[{cpf_str}] Aguardando autenticação e redirecionamento para o INSS...")
                    page.wait_for_url("**/meu.inss.gov.br/**", timeout=30000)
                    page.wait_for_load_state("networkidle", timeout=120000)

                    # Verifica tela de erro de cadastro
                    try:
                        logger.info(f"[{cpf_str}] Verificando ausência de tela de erro de cadastro...")
                        erro_cadastro = page.wait_for_selector(
                            'text="Dados cadastrais diferentes ou incompletos"', timeout=5000
                        )
                        if erro_cadastro:
                            logger.warning(f"[{cpf_str}] Tela de erro de Dados Cadastrais detectada.")
                            page.wait_for_timeout(2000)
                            raise PageDataError("Dados cadastrais diferentes ou incompletos.")
                    except TimeoutError:
                        pass  # Não apareceu, fluxo normal.

                    break  # Sai do loop interno, login Cenário C concluído

                except TimeoutError:
                    logger.warning(f"[{cpf_str}] Timeout durante o processo de login. Tentando novamente...")
                    tentativas_login += 1
                    if tentativas_login >= 3:
                        raise TimeoutError("Múltiplas tentativas de login falharam por timeout.")
                    page.wait_for_timeout(2000)
                    continue

            # Coleta tokens após fluxo completo (Cenário C)
            logger.info(f"[{cpf_str}] Coletando tokens após login completo (Cenário C)...")
            auth_dict = _coletar_tokens_da_pagina(page, context, cpf_str)
            logger.info(f"[{cpf_str}] Login concluído (Cenário C). Token obtido: {'Sim' if auth_dict['mitoken'] else 'Não'}")

            # 5. Faz o logoff do usuário
            try:
                page.wait_for_timeout(2500)  # Aguarda um pouco a estabilização pós-login
                deslogar_se_necessario(page)
            except Exception as e:
                logger.warning(f"Erro ao deslogar usuário: {e}")
            
            return auth_dict

        except TimeoutError as te:
            logger.warning(f"[{cpf_str}] Demora excessiva (Timeout) de rede ou do Gov.br: {te}")
            logger.warning(f"[{cpf_str}] Isso pode indicar que o site está lento ou que o captcha demorou demais.")
            logger.info("Esperando 1 minuto antes de tentar novamente...")
            page.wait_for_timeout(60000)
            continue

