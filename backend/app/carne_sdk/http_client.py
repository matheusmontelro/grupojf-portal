import requests

class HttpClientFactory:
    """
    Fábrica para criar clientes HTTP com configuração padrão.
    """

    @staticmethod
    def create(api_token):
        import logging
        logger = logging.getLogger(__name__)
        
        client = requests.Session()
        
        # Log para debug (mascara o token para segurança)
        if len(api_token) > 8:
            masked_token = f"{api_token[:4]}...{api_token[-4:]}"
        else:
            masked_token = "token vazio ou muito curto"
        logger.debug("Configurando cliente HTTP com token: %s", masked_token)
        
        # Configure cabeçalhos de autenticação
        client.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        return client