# Boleto SDK HTTP client.
import requests


class HttpClientFactory:
    """
    Fábrica para criar clientes HTTP com configuração padrão.
    """

    @staticmethod
    def create(api_token):
        client = requests.Session()
        client.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        return client
