# app/carne_sdk/sdk.py (Atualizado)
import logging
from .http_client import HttpClientFactory
from .environment import Environment
import requests
from urllib.parse import urljoin, urlparse, urlunparse

logger = logging.getLogger(__name__)

class CarneSDK:
    """
    SDK para integração com a API de carnês da DeltaPag/Bempaggo.
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

    def _normalize_location_url(self, location_url):
        """
        Normaliza o Location retornado pela Bempaggo antes do GET.
        A API pode retornar URL absoluta em http mesmo quando a criação foi feita
        via https; seguir esse Location como veio causa falha na porta 80.
        """
        normalized_url = urljoin(f"{self.base_url.rstrip('/')}/", location_url)
        parsed_location = urlparse(normalized_url)
        parsed_base = urlparse(self.base_url)

        if parsed_location.scheme == "http" and parsed_location.netloc == parsed_base.netloc:
            normalized_url = urlunparse(parsed_location._replace(scheme="https"))

        return normalized_url

    def create_booklet(self, customer_id, days_until_due, billing_frequency, 
                       collection_method, charges_by_booklet, recurring_item, 
                       accepted_payment_methods, order_reference=None, 
                       notification_url=None, splits=None):
        """
        Cria um carnê de pagamento.

        Args:
            customer_id (int): ID do cliente que está sendo faturado.
            days_until_due (int): Número de dias até a fatura vencer.
            billing_frequency (str): Frequência de cobrança (WEEKLY, BIWEEKLY, MONTHLY, etc.).
            collection_method (str): Método de cobrança (AUTOMATIC_CHARGE ou SEND_INVOICE).
            charges_by_booklet (int): Quantidade de cobranças no carnê.
            recurring_item (dict): Dados do item recorrente.
            accepted_payment_methods (list): Lista de métodos de pagamento aceitos.
            order_reference (str, optional): Referência do pedido externa.
            notification_url (str, optional): URL para receber webhooks.
            splits (list, optional): Regras de divisão de receita entre os sellers.

        Returns:
            dict: Dados do carnê criado.
        """
        url = f"{self.base_url}/sellers/{self.seller_id}/booklet"

        # Prepara o payload
        payload = {
            "customerId": customer_id,
            "daysUntilDue": days_until_due,
            "billingFrequency": billing_frequency,
            "collectionMethod": collection_method,
            "chargesByBooklet": str(charges_by_booklet),
            "recurringItem": recurring_item,
            "acceptedPaymentMethods": accepted_payment_methods
        }

        # Adicionar campos opcionais se fornecidos
        if order_reference:
            payload["orderReference"] = order_reference
            
        if notification_url:
            payload["notificationUrl"] = notification_url
            
        if splits:
            payload["splits"] = splits

        # LOGS de debug antes de mandar a requisição
        logger.info("[CarneSDK] Enviando POST para: %s", url)
        logger.debug("[CarneSDK] Payload enviado: %s", payload)

        # Faz a requisição
        response = self.http_client.post(url, json=payload)

        # LOGS da resposta recebida
        logger.debug("[CarneSDK] Resposta HTTP status_code=%s", response.status_code)
        logger.debug("[CarneSDK] Resposta cabeçalhos=%s", response.headers)
        logger.debug("[CarneSDK] Resposta texto=%s", response.text)

        # Se for 201, extraímos o "Location" e processamos
        if response.status_code == 201:
            location = response.headers.get("Location")
            logger.debug("[CarneSDK] Location retornado no cabeçalho: %s", location)

            if not location:
                logger.error("[CarneSDK] Cabeçalho 'Location' não encontrado na resposta.")
                raise ValueError("Cabeçalho 'Location' não encontrado na resposta.")

            return self._process_location(location)

        # Se não for 201, gera exceção
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            # Logar a resposta da Bempaggo que causou erro
            logger.error("[CarneSDK] Erro ao criar carnê: %s", http_err)
            logger.error("[CarneSDK] Corpo da resposta: %s", response.text)
            raise  # re-raise para tratar em outro lugar

        return None

    def generate_booklet_boletos(self, recurring_invoice_id):
        """
        Gera todos os boletos para um carnê de pagamento.
        
        Args:
            recurring_invoice_id (int): ID do carnê/fatura recorrente.
            
        Returns:
            list: Lista de boletos gerados.
        """
        url = f"{self.base_url}/recurring-invoices/{recurring_invoice_id}/boleto/generate-bulk"
        
        logger.info("[CarneSDK] Gerando boletos para: %s", url)
        
        response = self.http_client.post(url)
        
        logger.debug("[CarneSDK] Resposta HTTP status_code=%s", response.status_code)
        logger.debug("[CarneSDK] Resposta cabeçalhos=%s", response.headers)
        logger.debug("[CarneSDK] Resposta texto=%s", response.text)
        
        # Verificar se a resposta está vazia
        if not response.text:
            logger.error("[CarneSDK] Resposta vazia da API de geração de boletos")
            raise ValueError("API retornou resposta vazia ao gerar boletos")
        
        # Tentar fazer parse do JSON
        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError as e:
            logger.error("[CarneSDK] Erro ao decodificar JSON da resposta: %s", e)
            logger.error("[CarneSDK] Conteúdo da resposta: %s", response.text[:500])  # Primeiros 500 chars
            raise ValueError(f"Resposta inválida da API: {response.text[:200]}...")
    
        if response_data and isinstance(response_data, list) and len(response_data) > 0:
            primeiro_boleto = response_data[0]
            logger.info("[CarneSDK] Valor do primeiro boleto: %s", 
                    primeiro_boleto.get("boleto", {}).get("amount"))
        
        response.raise_for_status()
        return response_data

    def get_charge(self, charge_id):
        """
        Busca uma cobrança individual na Bempaggo/Delta pelo charge_id.
        """
        url = f"{self.base_url}/charges/{charge_id}"

        logger.info("[CarneSDK] Buscando charge: %s", url)

        response = self.http_client.get(url, timeout=30)
        logger.debug("[CarneSDK] Resposta GET charge status_code=%s", response.status_code)

        response.raise_for_status()
        return response.json()

    def get_recurring_invoice_invoices(self, recurring_invoice_id):
        """
        Lista as invoices/cobranças de um carnê/fatura recorrente.
        """
        url = f"{self.base_url}/recurring-invoices/{recurring_invoice_id}/invoices"

        logger.info("[CarneSDK] Buscando invoices do carnê: %s", url)

        response = self.http_client.get(url, timeout=30)
        logger.debug("[CarneSDK] Resposta GET invoices status_code=%s", response.status_code)

        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("content") or data.get("items") or data.get("data") or []
        return []

    def _process_location(self, location_url):
        """
        Faz o GET na URL de 'Location' e processa os dados retornados.

        Args:
            location_url (str): URL do cabeçalho 'Location'.

        Returns:
            dict: Dados do carnê criado.
        """
        location_url = self._normalize_location_url(location_url)
        logger.info("[CarneSDK] Buscando dados em Location: %s", location_url)

        response = self.http_client.get(location_url)
        logger.debug("[CarneSDK] Resposta GET Location status_code=%s", response.status_code)
        logger.debug("[CarneSDK] Resposta GET Location texto=%s", response.text)

        response.raise_for_status()
        carne_data = response.json()
        logger.debug("[CarneSDK] JSON retornado no GET Location: %s", carne_data)

        return carne_data
    
    def get_booklet_html(self, recurring_invoice_id):
        """
        Obtém a visualização HTML do carnê completo.
        
        Args:
            recurring_invoice_id (int): ID do carnê/fatura recorrente.
            
        Returns:
            str: HTML do carnê para visualização/impressão.
        """
        url = f"{self.base_url}/recurring-invoices/{recurring_invoice_id}/booklet"
        
        logger.info("[CarneSDK] Obtendo HTML do carnê: %s", url)
        
        response = self.http_client.get(url)
        logger.debug("[CarneSDK] Resposta HTTP status_code=%s", response.status_code)
        
        response.raise_for_status()
        return response.text  # Retorna o HTML diretamente
