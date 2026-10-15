"""SDK principal para integração com Delta - Fatura Recorrente"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from decimal import Decimal
import uuid
from urllib.parse import urlparse

from .environment import DeltaConfig
from .http_client import DeltaHttpClient
from .customer_manager import CustomerManager
from .split_manager import SplitManager

logger = logging.getLogger(__name__)

class DeltaRecorrenteSDK:
    """SDK para criação e gerenciamento de faturas recorrentes (cartão de crédito)"""
    
    def __init__(self, config: DeltaConfig):
        self.config = config
        self.http_client = DeltaHttpClient(
            base_url=config.base_url,
            headers=config.headers
        )
        self.customer_manager = CustomerManager(self.http_client)
        self.split_manager = SplitManager()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.http_client.client.close()
        
    def get_checkout_url_from_invoice(self, invoice_id: str) -> Optional[str]:
        """
        Busca a URL de checkout da fatura via GET na fatura
        
        Args:
            invoice_id: ID da fatura
            
        Returns:
            URL de checkout da fatura
        """
        try:
            # Buscar dados da fatura
            endpoint = f"/api/v2/invoices/{invoice_id}"
            response = self.http_client.get(endpoint)
            
            if response.status_code == 200:
                invoice_data = response.json()
                # Buscar campo paymentUrl na resposta
                payment_url = invoice_data.get('paymentUrl')
                if payment_url:
                    logger.info(f"Payment URL encontrada na fatura: {payment_url}")
                    return payment_url
                else:
                    logger.warning(f"Campo paymentUrl não encontrado na fatura {invoice_id}")
                    
            logger.warning(f"Não foi possível obter dados da fatura {invoice_id}. Status: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar fatura {invoice_id}: {e}")
            return None
        
    def create_product(self, product_data: Dict) -> Dict:
        """
        Cria um produto na API Delta
        
        Args:
            product_data: Dados do produto contendo:
                - name: Nome do produto
                - description: Descrição
                - productType: RECURRING para recorrente
                - value: Valor em centavos
                - interval: MONTHLY, WEEKLY, etc
                - maxCharges: Número máximo de cobranças
                - affiliateId: ID do afiliado
                - themeId: ID do tema
                - methods: Lista de métodos de pagamento
                - maxInstallments: Número máximo de parcelas
                
        Returns:
            Dict com dados do produto criado
        """
        try:
            # Define tipo como RECURRING para fatura recorrente
            product_data['productType'] = 'RECURRING'
            
            response = self.http_client.post("/api/v2/products", json=product_data)
            
            # Se resposta vazia, extrai ID do Location
            if response.status_code == 201:
                product = {}
                if response.text:
                    product = response.json()
                else:
                    # Extrai ID do header Location
                    location = response.headers.get('Location') or response.headers.get('location')
                    if location:
                        parts = location.rstrip('/').split('/')
                        if parts and parts[-1].isdigit():
                            product['id'] = int(parts[-1])
                
                logger.info(f"Produto recorrente criado. ID: {product.get('id')}")
                return product
            else:
                raise Exception(f"Erro ao criar produto: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Erro ao criar produto: {e}")
            raise
            
    def get_or_create_default_product(self, seller_id: int = 1) -> int:
        """
        Obtém ou cria um produto padrão para faturas recorrentes
        
        Returns:
            ID do produto
        """
        try:
            # Por enquanto, vamos criar um novo produto sempre
            # TODO: Implementar cache de produtos
            product_data = {
                "name": f"Assinatura Odontológica",
                "description": "Assinatura mensal para tratamento odontológico",
                "productType": "RECURRING",
                "value": 10000,  # R$ 100,00 padrão
                "interval": "MONTHLY",
                "maxCharges": 12,
                "affiliateId": seller_id,
                "themeId": 1,
                "methods": ["CREDIT_CARD"],
                "maxInstallments": 1
            }
            
            product = self.create_product(product_data)
            return product.get('id', 1)  # Fallback para ID 1
            
        except Exception as e:
            logger.error(f"Erro ao obter/criar produto padrão: {e}")
            # Retorna ID 1 como fallback
            return 1
            
    def create_recurring_invoice(self, invoice_data: Dict) -> Dict:
        """
        Cria uma fatura recorrente (assinatura)
        
        Args:
            invoice_data: Dados da fatura contendo:
                - customerId: ID do cliente
                - sellerId: ID do vendedor principal
                - billingCycleStartDate: Data início (timestamp ms)
                - billingFrequency: DAILY, WEEKLY, MONTHLY, YEARLY
                - collectionMethod: AUTOMATIC_CHARGE para cartão
                - daysUntilDue: Dias até vencimento
                - recurringItems: Lista de itens recorrentes
                - splits: Divisão de receita (opcional)
                - notificationUrl: URL para webhooks
                - successUrl: URL de sucesso
                - totalCycles: Total de ciclos (opcional)
                
        Returns:
            Dict com dados da assinatura criada e URL de checkout
        """
        try:
            # Define método de cobrança como automático para cartão
            invoice_data['collectionMethod'] = 'AUTOMATIC_CHARGE'
            
            # Define frequência padrão como mensal
            if 'billingFrequency' not in invoice_data:
                invoice_data['billingFrequency'] = 'MONTHLY'
                
            # Define data de início como hoje se não fornecida
            if 'billingCycleStartDate' not in invoice_data:
                invoice_data['billingCycleStartDate'] = int(datetime.now(timezone.utc).timestamp() * 1000)
                
            # Para cartão, vencimento é imediato (0 dias)
            invoice_data['daysUntilDue'] = 0
            
            # Valida seller_id e o remove do payload (não deve ir no body)
            seller_id = invoice_data.pop('sellerId', None)
            if not seller_id:
                raise ValueError("sellerId é obrigatório")
                
            # Remove campos que não devem ir no payload
            invoice_data.pop('totalCycles', None)  # totalCycles não existe no nível raiz
                
            # Envia requisição
            endpoint = f"/api/v2/sellers/{seller_id}/recurring-invoices"
            response = self.http_client.post(endpoint, json=invoice_data)
            
            # Log detalhado dos headers para debug
            logger.info(f"Response headers: {dict(response.headers)}")
            
            # Extrai URL de checkout do header Link
            checkout_url = None
            payment_api_url = None
            link_header = response.headers.get('link') or response.headers.get('Link')
            
            if link_header:
                logger.info(f"Link header encontrado: {link_header}")
                # Parse do header Link para encontrar URL de pagamento
                # Pode haver múltiplos links separados por vírgula
                links = link_header.split(', ')
                for link in links:
                    # Procura pelo link de pagamento com cartão de crédito
                    if 'pay-invoice-credit-card' in link:
                        # Extrai URL entre < e >
                        start = link.find('<')
                        end = link.find('>')
                        if start != -1 and end != -1:
                            payment_api_url = link[start+1:end]
                            logger.info(f"Payment API URL extraída: {payment_api_url}")
                            # Para checkout de cartão, construir URL de checkout diretamente
                            # A URL de API não é para o usuário final
                            if '/credit-card/pay' in payment_api_url:
                                # Extrair ID da invoice da URL
                                parts = payment_api_url.split('/')
                                for i, part in enumerate(parts):
                                    if part == 'invoices' and i+1 < len(parts):
                                        invoice_id = parts[i+1]
                                        # Buscar URL de checkout real na fatura
                                        checkout_url = self.get_checkout_url_from_invoice(invoice_id)
                                        if checkout_url:
                                            logger.info(f"Checkout URL obtida da fatura: {checkout_url}")
                                        else:
                                            logger.warning(f"Não foi possível obter checkout URL da fatura {invoice_id}")
                                            # Fallback para URL da API
                                            checkout_url = payment_api_url
                                        break
                            if not checkout_url:
                                checkout_url = payment_api_url
                            break
            else:
                logger.warning("Link header não encontrado na resposta")
                
            # Se não houver body JSON (201 pode retornar vazio), usa os headers
            try:
                invoice = response.json() if response.text else {}
            except:
                invoice = {}
                
            # Se houver Location header, pode ser a URL da API
            location_header = response.headers.get('location') or response.headers.get('Location')
            if location_header:
                logger.info(f"Location header: {location_header}")
                # Extrai ID da invoice do Location se necessário
                if not invoice.get('id'):
                    # Tenta extrair ID do path
                    parts = location_header.rstrip('/').split('/')
                    if parts and parts[-1].isdigit():
                        invoice['id'] = int(parts[-1])
                    
            result = {
                **invoice,
                'checkoutUrl': checkout_url,
                'apiUrl': location_header
            }
            
            logger.info(f"Fatura recorrente criada. ID: {invoice.get('id')}")
            return result
            
        except Exception as e:
            logger.error(f"Erro ao criar fatura recorrente: {e}")
            raise
            
    def get_recurring_invoice(self, seller_id: int, invoice_id: int) -> Dict:
        """
        Busca uma fatura recorrente por ID
        
        Args:
            seller_id: ID do vendedor
            invoice_id: ID da fatura recorrente
            
        Returns:
            Dict com dados da fatura recorrente
        """
        try:
            endpoint = f"/api/v2/sellers/{seller_id}/recurring-invoices/{invoice_id}"
            response = self.http_client.get(endpoint)
            return response.json()
            
        except Exception as e:
            logger.error(f"Erro ao buscar fatura recorrente {invoice_id}: {e}")
            raise

    def get_recurring_invoice_invoices(self, recurring_invoice_id: int) -> List[Dict]:
        """
        Lista as cobranças/invoices geradas por uma fatura recorrente.
        """
        try:
            endpoint = f"/api/v2/recurring-invoices/{recurring_invoice_id}/invoices"
            response = self.http_client.get(endpoint)
            data = response.json()

            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("content") or data.get("items") or data.get("data") or []

            return []

        except Exception as e:
            logger.error(
                "Erro ao listar invoices da fatura recorrente %s: %s",
                recurring_invoice_id,
                e,
            )
            raise
            
    def cancel_recurring_invoice(self, seller_id: int, invoice_id: int) -> bool:
        """
        Cancela uma assinatura
        
        Args:
            seller_id: ID do vendedor
            invoice_id: ID da fatura recorrente
            
        Returns:
            True se cancelada com sucesso
        """
        try:
            endpoint = f"/api/v2/sellers/{seller_id}/recurring-invoices/{invoice_id}/cancel"
            response = self.http_client.post(endpoint)
            
            logger.info(f"Assinatura {invoice_id} cancelada com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao cancelar assinatura {invoice_id}: {e}")
            return False
            
    def create_complete_subscription(self, 
                                   customer_data: Dict,
                                   amount_cents: int,
                                   total_cycles: int,
                                   splits: Optional[List[Dict]] = None,
                                   product_id: Optional[int] = None,
                                   notification_url: Optional[str] = None,
                                   success_url: Optional[str] = None,
                                   seller_id: int = 1,
                                   billing_frequency: str = "MONTHLY") -> Dict:
        """
        Cria uma assinatura completa (cliente + fatura recorrente)
        
        Args:
            customer_data: Dados do cliente
            amount_cents: Valor mensal em centavos
            total_cycles: Número total de ciclos/parcelas
            splits: Lista de splits (opcional)
            product_id: ID do produto (usa padrão se não fornecido)
            notification_url: URL para webhooks
            success_url: URL de sucesso
            seller_id: ID do vendedor principal
            billing_frequency: Frequência de cobrança
            
        Returns:
            Dict com assinatura criada e URL de checkout
        """
        try:
            # Cria ou busca cliente
            customer = self.customer_manager.create_or_get_customer(customer_data)
            customer_id = customer['id']
            
            # Usa produto ID específico para fatura recorrente se não fornecido
            if not product_id:
                logger.info("Product ID não fornecido, usando produto recorrente configurado...")
                product_id = self.config.recorrente_product_id
                
            # Monta payload da fatura recorrente
            invoice_data = {
                "customerId": customer_id,
                "sellerId": seller_id,  # Adiciona sellerId temporariamente (será removido em create_recurring_invoice)
                "billingCycleStartDate": int(datetime.now(timezone.utc).timestamp() * 1000),
                "billingFrequency": billing_frequency,
                "collectionMethod": "AUTOMATIC_CHARGE",
                "daysUntilDue": 0,  # Cartão cobra no vencimento
                "recurringItems": [{
                    "productId": product_id,
                    "quantity": 1,
                    "unitPriceInCents": amount_cents,
                    "maxBillingCycles": total_cycles  # Campo obrigatório
                }],
                "acceptedPaymentMethods": [{
                    "method": "CREDIT_CARD",  # Por padrão, cartão de crédito
                    "cardSettings": {
                        "maxInstallments": 1,
                        "feePassThrough": False
                    }
                }]
            }
                
            # Adiciona URLs se fornecidas
            if notification_url:
                invoice_data["notificationUrl"] = notification_url
            if success_url:
                invoice_data["successUrl"] = success_url
                
            # Adiciona splits se fornecidos
            if splits:
                # Garantir que sellerId seja inteiro e pelo menos um tenha absorbBalance=true
                processed_splits = []
                has_absorb_balance = False
                
                for split in splits:
                    # Converter sellerId para inteiro
                    split_copy = split.copy()
                    split_copy['sellerId'] = int(split_copy['sellerId'])
                    
                    # Verificar se tem absorbBalance
                    if split_copy.get('absorbBalance', False):
                        has_absorb_balance = True
                    
                    # Garantir que cyclesToParticipate esteja no formato correto
                    # Se veio cycles_to_participate, converter para cyclesToParticipate
                    if 'cycles_to_participate' in split_copy and 'cyclesToParticipate' not in split_copy:
                        split_copy['cyclesToParticipate'] = split_copy.pop('cycles_to_participate')
                    
                    processed_splits.append(split_copy)
                
                # Se nenhum split tem absorbBalance=true, definir o último
                if not has_absorb_balance and processed_splits:
                    processed_splits[-1]['absorbBalance'] = True
                    logger.info("Definindo último split como absorbBalance=true")
                
                invoice_data["splits"] = processed_splits
                
            # Log do payload completo para debug
            logger.info(f"Payload da fatura recorrente: {invoice_data}")
                
            # Cria assinatura
            result = self.create_recurring_invoice(invoice_data)
            
            # Adiciona customer_id ao resultado
            result['customerId'] = customer_id
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao criar assinatura completa: {e}")
            raise
