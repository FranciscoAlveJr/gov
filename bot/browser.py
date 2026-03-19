import time
from playwright.sync_api import sync_playwright
from playwright.sync_api import Request

class LoginError(Exception):
    pass

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

    # Inicializar Playwright
    args = [
        '--start-maximized',
        '--disable-blink-features=AutomationControlled'
        ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=args)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            no_viewport=True,
        )
        page = context.new_page()

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

            # Preencher CPF
            print(f"[{cpf_str}] Preenchendo CPF...")
            page.fill('input#accountId', cpf_str)
            page.click('button#enter-account-id')

            # Aguardar campo de senha
            page.wait_for_selector('input#password')
            time.sleep(1) # Pequena pausa para evitar bloqueio / comportar-se mais como humano

            # Preencher Senha
            print(f"[{cpf_str}] Preenchendo Senha...")
            page.fill('input#password', senha_str)

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

            # Aguardar o login concluir e voltar para a página do INSS
            print(f"[{cpf_str}] Aguardando autenticação e interceptando o tráfego do navegador...")
            
            # Aqui pode aparecer tela de confirmar autorização (dependendo da conta) ou erro de senha.
            # Verificando se apareceu mensagem de erro longo após o submit
            try:
                error_msg = page.wait_for_selector('div.message.error', timeout=5000)
                if error_msg:
                    texto_erro = error_msg.inner_text()
                    raise LoginError(f"Erro no login: {texto_erro}")
            except Exception as e:
                if isinstance(e, LoginError):
                    raise e
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
            browser.close()
