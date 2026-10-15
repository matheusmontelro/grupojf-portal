# Boleto SDK.

import logging
from .http_client import HttpClientFactory
from .link_parser import LinkParser
from .environment import Environment
import requests

logger = logging.getLogger(__name__)

class BoletoSDK:
    """
    SDK para integração com a API de boletos da DeltaPag/Bempaggo.
    """

    def __init__(self, api_token, seller_id, environment):
        """
        Inicializa a SDK com os parâmetros necessários.
        Args:
            api_token (str): Token de autenticação da API.
            seller_id (str): ID do vendedor.
            environment (str): 'sandbox' ou 'production'.
        """
        self.api_token = api_token
        self.seller_id = seller_id
        self.base_url = Environment.get_base_url(environment)
        self.http_client = HttpClientFactory.create(api_token)

    def create_boleto(self, boleto_data):
        """
        Cria um boleto e redireciona para verificar seu status.

        Args:
            boleto_data (dict): Dados do boleto.

        Returns:
            dict: Dados do boleto, incluindo a URL do PDF e mensagens da transação.
        """
        url = f"{self.base_url}/sellers/{self.seller_id}/orders/boleto"

        # LOGS de debug antes de mandar a requisição
        logger.info("[BoletoSDK] Enviando POST para: %s", url)
        logger.debug("[BoletoSDK] Payload enviado: %s", boleto_data)

        # Faz a requisição
        response = self.http_client.post(url, json=boleto_data)

        # LOGS da resposta recebida
        logger.debug("[BoletoSDK] Resposta HTTP status_code=%s", response.status_code)
        logger.debug("[BoletoSDK] Resposta texto=%s", response.text)

        # Se for 201, extraímos o "Location" e processamos
        if response.status_code == 201:
            location = response.headers.get("Location")
            logger.debug("[BoletoSDK] Location retornado no cabeçalho: %s", location)

            boleto_url = LinkParser._extract_boleto_url(response)
            logger.debug("[BoletoSDK] Boleto_url (Link header): %s", boleto_url)

            if not location:
                logger.error("[BoletoSDK] Cabeçalho 'Location' não encontrado na resposta. Resposta: %s", response.text)
                raise ValueError("Cabeçalho 'Location' não encontrado na resposta.")

            return self._process_location(location, boleto_url)

        # Se não for 201, gera exceção
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            # Logar a resposta da Bempaggo que causou erro
            logger.error("[BoletoSDK] Erro ao criar boleto: %s", http_err)
            logger.error("[BoletoSDK] Corpo da resposta: %s", response.text)
            raise  # re-raise para tratar em outro lugar

        return None

    def _process_location(self, location_url, boleto_url):
        """
        Faz o GET na URL de 'Location' e processa os dados retornados.

        Args:
            location_url (str): URL do cabeçalho 'Location'.
            boleto_url (str): URL pública do PDF do boleto (extraída do cabeçalho Link).

        Returns:
            dict: Dados do boleto, incluindo mensagens da transação, URL do PDF e charge_id.
        """
        logger.info("[BoletoSDK] Buscando dados em Location: %s", location_url)

        response = self.http_client.get(location_url)
        logger.debug("[BoletoSDK] Resposta GET Location status_code=%s", response.status_code)
        logger.debug("[BoletoSDK] Resposta GET Location texto=%s", response.text)

        response.raise_for_status()
        status_data = response.json()
        logger.debug("[BoletoSDK] JSON retornado no GET Location: %s", status_data)

        # Extrai o ID da cobrança
        charge_id = status_data.get("id")

        # Extrair informações da transação
        transactions = status_data.get("transactions", [])
        if transactions and isinstance(transactions, list):
            first_transaction = transactions[0]
            return_message = first_transaction.get("returnMessage", None)
            bar_code = first_transaction.get("barCode", None)
            digitable_line = first_transaction.get("digitableLine", None)
        else:
            return_message = None
            bar_code = None
            digitable_line = None

        status = status_data.get("status", "UNKNOWN")

        result_dict = {
            "status": status,
            "transaction_message": return_message,
            "bar_code": bar_code,
            "digitable_line": digitable_line,
            "charge_id": charge_id,
            "boleto_url": boleto_url,
        }

        logger.debug("[BoletoSDK] Dados finais do boleto: %s", result_dict)
        return result_dict
