from curl_cffi import requests
import os
import logging
from bot.browser import LoginError

logger = logging.getLogger("BotINSS")

class APIClient:
    def __init__(self):
        self.session = requests.Session(impersonate="chrome120")
        self.base_url = "https://vip-pmeuinss-api.inss.gov.br/apis"
        self.oracle_id = "" # Pode ser atualizado se obtido no intercept

    def configure_session(self, auth_dict: dict):
        # Adicionar o user-agent e headers necessários de Fetch
        headers = {
            "User-Agent": auth_dict.get("user_agent", ""),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Referer": "https://meu.inss.gov.br/",
            "Origin": "https://meu.inss.gov.br"
        }
        self.session.headers.update(headers)
        
        # Injetar o Bearer do governo base (se encontrado)
        if auth_dict.get("bearer"):
            self.session.headers.update({"Authorization": f"Bearer {auth_dict['bearer']}"})
            
        # Opcionalmente, injetar o mitoken em header próprio se for usado em alguma rota específica pelo INSS
        if auth_dict.get("mitoken"):
            self.session.headers.update({"mitoken": auth_dict['mitoken']})
        
        # Formatar os cookies para o session
        cookies_list = auth_dict.get("cookies", [])
        for cookie in cookies_list:
            self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

    def get_historico_creditos(self, cpf: str, data_inicio: str, data_fim: str) -> dict:
        url = f"{self.base_url}/hiscreServices/historicocreditos/{cpf}/{data_inicio}/{data_fim}"
        
        logger.info(f"[{cpf}] Chamando JSON do Hiscre: {url}")
        res = self.session.get(url)
        
        if res.status_code == 401:
            logger.error(f"[{cpf}] Sessão expirou ou não autorizada para ler Hiscre.")
            raise LoginError("Sessão expirou ou não autorizada para ler Hiscre.")
            
        res.raise_for_status()
        return res.json()

    def download_pdf_historico(self, cpf: str, data_inicio: str, data_fim: str, output_path: str) -> str:
        url = f"{self.base_url}/hiscreServices/historicocreditosPdf/{cpf}/{data_inicio}/{data_fim}"
        
        logger.info(f"[{cpf}] Chamando PDF do Hiscre: {url}")
        res = self.session.get(url)
        
        if res.status_code == 401:
            logger.error(f"[{cpf}] Sessão expirou ou não autorizada para download de PDF.")
            raise LoginError("Sessão expirou ou não autorizada para download de PDF.")
            
        res.raise_for_status()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(res.content)
                    
        return output_path