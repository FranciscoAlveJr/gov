from time import sleep
import random
import os
import tempfile
from playwright.sync_api import sync_playwright
from playwright.sync_api import Request
from playwright.sync_api import TimeoutError
from playwright_stealth import Stealth

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

def login_e_extrair_tokens(cpf, senha, headless=False):
    """
    Acessa o site do meu.inss.gov.br, realiza o login pelo gov.br usando CPF e senha,
    e retorna informações de sessão (que serão úteis mais para frente).
    Por enquanto, o objetivo principal é apenas provar que o bot navega e loga.
    """
    cpf_str = str(cpf).strip()
    senha_str = str(senha).strip()

    if not cpf_str or not senha_str:
        raise ValueError("CPF ou Senha vazio")

    # Configuração do caminho da extensão
    # A extensão DEVE estar "descompactada", ou seja, ser uma pasta contendo o "manifest.json" e os arquivos da extensão.
    import sys
    if getattr(sys, 'frozen', False):
        caminho_base = os.path.dirname(sys.executable)
    else:
        caminho_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    extensao_path = os.path.join(caminho_base, "extensions", "captcha_solver")

    # Inicializar Playwright
    args = [
        '--start-maximized',
        '--disable-blink-features=AutomationControlled'
    ]
    
    # Se a pasta da extensão existir, adiciona aos argumentos
    if os.path.exists(extensao_path):
        args.append(f"--disable-extensions-except={extensao_path}")
        args.append(f"--load-extension={extensao_path}")

    with Stealth().use_sync(sync_playwright()) as p:
        # Extensões no Playwright Chrome exigem o "Persistent Context", e a janela não pode estar Headless de início
        # (se quiser rodar "focado no fundo", pode usar screen frame buffer ou o headless mode "--headless=new")
        temp_dir = tempfile.mkdtemp()
        chrome_exe = obter_caminho_chrome_local()
        
        context = p.chromium.launch_persistent_context(
            executable_path=chrome_exe,
            user_data_dir=temp_dir,
            headless=False, # <-- Extensões precisam de headless=False ou args.append('--headless=new') para funcionar bem
            args=args,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            no_viewport=True,
        )
        
        # Como o launch_persistent_context já devolve um "context", e ele tem 1 página padrão criada
        page = context.pages[0] if context.pages else context.new_page()
        client = context.new_cdp_session(page)
        
        # Aplicando máscaras de detecção antibot do stealth

        try:
            print(f"[{cpf_str}] Acessando portal Meu INSS...")
            page.goto("https://meu.inss.gov.br/#/login", wait_until="networkidle")

            # Aguardar o botão de "Entrar com gov.br" e clicar
            # O botão tem o texto Entrar com gov.br
            btn_entrar = page.locator('button#main-content', has_text="Entrar com gov.br")
            btn_entrar.wait_for(state="visible", timeout=10000)
            btn_entrar.click()

            # Aguardar redirecionamento para sso.acesso.gov.br
            print(f"[{cpf_str}] Redirecionando para gov.br...")
            page.wait_for_selector('input#accountId')

            # Preencher CPF de forma mais lenta, aleatória e humana
            print(f"[{cpf_str}] Preenchendo CPF...")
            cpf_locator = page.locator('input#accountId')
            cpf_locator.click()
            sleep(random.uniform(0.3, 0.8))
            for char in cpf_str:
                cpf_locator.press_sequentially(char)
                sleep(random.uniform(0.05, 0.25))
            
            sleep(random.uniform(0.5, 1.5))
            page.click('button#enter-account-id')

            # Aguardar campo de senha
            page.wait_for_selector('input#password')
            sleep(random.uniform(1.5, 3.0)) # Pausa aleatória para transição de tela

            # Preencher Senha de forma mais lenta, aleatória e humana
            print(f"[{cpf_str}] Preenchendo Senha...")
            senha_locator = page.locator('input#password')
            senha_locator.click()
            sleep(random.uniform(0.3, 0.8))
            for char in senha_str:
                senha_locator.press_sequentially(char)
                sleep(random.uniform(0.05, 0.25))
                
            sleep(random.uniform(0.5, 1.5))

            # ======== MUDANÇA ENTRA AQUI ========
            bearer_token = None
            token = None
            
            def intercept_response(responses: list[Request]):
                nonlocal bearer_token, token
                # Evita falhas se a requisição for do tipo OPTIONS (pré-voo do navegador)
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
                            print(f"Erro ao ler JSON da API: {err}")

            # Registramos o escutador ANTES de clicar em 'Entrar'
            # page.on("response", intercept_response)
            # ====================================

            page.click('button#submit-button')

            try:
                page.wait_for_selector('.br-message.warning', timeout=5000)
                error_text = page.locator('.br-message.warning').inner_text()
                raise LoginError(f"Erro no login: {error_text}")        
            except TimeoutError:
                # Se deu timeout procurando mensagem de erro, significa que provavelmente o login avançou
                pass

            # Aguardar o login concluir e voltar para a página do INSS
            print(f"[{cpf_str}] Aguardando autenticação e interceptando o tráfego do navegador...")
            
            # Aqui pode aparecer tela de confirmar autorização (dependendo da conta) ou erro de senha.
            # Verificando se apareceu mensagem de erro longo após o submit
            try:
                error_msg = page.wait_for_selector('div.message.error', timeout=5000)
                if error_msg:
                    texto_erro = error_msg.inner_text()
                    raise LoginError(f"Erro no login: {texto_erro}")
            except TimeoutError:
                # Se deu timeout procurando erro, significa que provavelmente o login avançou
                pass

            # Aguardamos algum elemento da home do INSS (por exemplo a header ou o texto 'Extratos')
            # ou simplesmente esperamos network idle
            page.wait_for_url("**/meu.inss.gov.br/**", timeout=30000)
            page.wait_for_load_state("networkidle")
            
            # Não precisamos mais navegar para o extrato se a intenção era só pegar o token!
            # Mas se quiser, pode deixar o page.goto pra lá

            print(f"[{cpf_str}] Coletando token e ID da sessão interceptando o tráfego do navegador...")

            reqs = page.requests()

            intercept_response(reqs)
            
            if not token:
                print(f"[{cpf_str}] ATENÇÃO: Token não encontrado na intercepção.")
            
            # Precisamos extrair todos os cookies de sessão
            cookies = context.cookies()
            auth_dict = {
                "cookies": cookies,
                "mitoken": token,        # O token retornado pela API "mitoken"
                "bearer": bearer_token,  # O Token capturado dos Headers do Governo
                "user_agent": page.evaluate("navigator.userAgent")
            }
            
            print(f"[{cpf_str}] Login concluído, dados de sessão coletados. Token mitoken obtido: {'Sim' if token else 'Não'}")
            return auth_dict

        except Exception as e:
            print(f"[{cpf_str}] Falha durante o processo: {e}")
            return False
        finally:
            if 'context' in locals():
                context.close()
