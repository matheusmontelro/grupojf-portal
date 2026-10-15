# app/users_sdk/http_client.py

import requests
import logging

logger = logging.getLogger(__name__)

class HttpClientFactory:
    """
    Fábrica para criar clientes HTTP com configuração padrão.
    """

    @staticmethod
    def create(api_token):
        """
        Cria e configura um cliente HTTP com o token de autenticação.
        
        Args:
            api_token (str): Token de API da BemPaggo.
            
        Returns:
            requests.Session: Sessão HTTP configurada com os headers necessários.
        """
        client = requests.Session()
        client.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        return client