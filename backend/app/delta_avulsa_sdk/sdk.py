"""SDK principal para integração com Delta - Fatura Avulsa"""
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid

from .environment import DeltaConfig
from .http_client import DeltaHttpClient
from .customer_manager import CustomerManager
from .split_manager import SplitManager

logger = logging.getLogger(__name__)

def _format_due_date(value: Optional[Any] = None) -> int:
    """Formata dueDate como epoch em milissegundos, conforme API da Delta."""
    if value is None:
        due_date = datetime.now(timezone.utc) + timedelta(days=1)
    elif isinstance(value, datetime):
        due_date = value
    elif isinstance(value, (int, float)):
        return int(value if value > 10_000_000_000 else value * 1000)
    elif isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            return int(value)
        try:
            due_date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Formato de dueDate inválido: {value}") from exc
    else:
        raise ValueError(f"Formato de dueDate inválido: {type(value).__name__}")

    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=timezone.utc)

    return int(due_date.astimezone(timezone.utc).timestamp() * 1000)

class DeltaAvulsaSDK:
    """SDK para criação e gerenciamento de faturas avulsas"""
    
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
                - productType: ONETIME para avulso
                - sellerId: ID do vendedor principal
                
        Returns:
            Dict com dados do produto criado
        """
        try:
            # Define tipo como ONETIME para fatura avulsa
            product_data['productType'] = 'ONETIME'
            
            response = self.http_client.post("/api/v2/products", json=product_data)
            product = response.json()
            
            logger.info(f"Produto criado. ID: {product.get('id')}")
            return product
            
        except Exception as e:
            logger.error(f"Erro ao criar produto: {e}")
            raise
            
    def create_invoice(self, invoice_data: Dict) -> Dict:
        """
        Cria uma fatura avulsa
        
        Args:
            invoice_data: Dados da fatura contendo:
                - customerId: ID do cliente
                - sellerId: ID do vendedor principal
                - invoiceNumber: Número único da fatura
                - dueDate: Data de vencimento (ISO 8601)
                - items: Lista de itens
                - acceptedPaymentMethods: Métodos aceitos
                - splits: Divisão de receita (opcional)
                - notificationUrl: URL para webhooks
                - successUrl: URL de sucesso
                
        Returns:
            Dict com dados da fatura criada e URL de checkout
        """
        try:
            # Gera número único se não fornecido
            if 'invoiceNumber' not in invoice_data:
                invoice_data['invoiceNumber'] = f"AV-{uuid.uuid4().hex[:8].upper()}"
                
            # Define data de vencimento padrão (hoje) se não fornecida
            invoice_data['dueDate'] = _format_due_date(invoice_data.get('dueDate'))
                
            # Valida seller_id e o remove do payload (não deve ir no body)
            seller_id = invoice_data.pop('sellerId', None)
            if not seller_id:
                raise ValueError("sellerId é obrigatório")
                
            # Log do payload final enviado para API
            logger.info(f"=== ENVIANDO PARA DELTA API ===")
            logger.info(f"Endpoint: /api/v2/sellers/{seller_id}/invoices")
            logger.info(f"Payload JSON: {json.dumps(invoice_data, indent=2)}")
            
            # Envia requisição
            endpoint = f"/api/v2/sellers/{seller_id}/invoices"
            response = self.http_client.post(endpoint, json=invoice_data)
            
            # Log da resposta
            logger.info(f"=== RESPOSTA DELTA API ===")
            logger.info(f"Status: {response.status_code}")
            logger.info(f"Headers: {dict(response.headers)}")
            logger.info(f"Body: {response.text}")
            
            # Verifica se há conteúdo na resposta
            if response.text:
                invoice = response.json()
            else:
                # Resposta vazia - criar estrutura básica
                # Tenta extrair ID do header content-id
                invoice_id = response.headers.get('content-id')
                if invoice_id:
                    try:
                        invoice_id = int(invoice_id)
                    except:
                        invoice_id = None
                        
                invoice = {
                    "id": invoice_id,
                    "invoiceNumber": invoice_data.get('invoiceNumber'),
                    "status": "CREATED",
                    "customerId": invoice_data.get('customerId'),
                    "sellerId": invoice_data.get('sellerId'),
                    "dueDate": invoice_data.get('dueDate'),
                    "totalAmountInCents": sum(item['unitPriceInCents'] * item.get('quantity', 1) 
                                             for item in invoice_data.get('items', []))
                }
            
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
                    # Procura pelo link de pagamento apropriado ao método
                    if 'pay-invoice' in link:
                        # Extrai URL entre < e >
                        start = link.find('<')
                        end = link.find('>')
                        if start != -1 and end != -1:
                            payment_api_url = link[start+1:end]
                            logger.info(f"Payment API URL extraída: {payment_api_url}")
                            
                            # Para qualquer método de pagamento, buscar URL de checkout na fatura
                            if '/invoices/' in payment_api_url:
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
                            if checkout_url:
                                break
                            
                # Se não conseguiu construir, usa a URL original
                if not checkout_url and payment_api_url:
                    checkout_url = payment_api_url
            else:
                logger.warning("Link header não encontrado na resposta")
                
            # Se houver Location header, pode ser a URL da API
            location_header = response.headers.get('location') or response.headers.get('Location')
            if location_header:
                logger.info(f"Location header: {location_header}")
                # Extrai ID da invoice do Location se necessário
                if not invoice.get('id') and location_header:
                    # Tenta extrair ID do path
                    parts = location_header.rstrip('/').split('/')
                    if parts and parts[-1].isdigit():
                        invoice['id'] = int(parts[-1])

                if not checkout_url and invoice.get('id'):
                    checkout_url = self.get_checkout_url_from_invoice(str(invoice['id']))
                    if checkout_url:
                        logger.info(f"Checkout URL obtida pelo Location header: {checkout_url}")
                    
            # Se não temos ID ainda, usar o invoice number
            if not invoice.get('id'):
                invoice['id'] = invoice_data.get('invoiceNumber')
                    
            result = {
                **invoice,
                'checkoutUrl': checkout_url,
                'apiUrl': location_header,
                'createdAt': datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Fatura avulsa criada. ID: {invoice.get('id')}")
            return result
            
        except Exception as e:
            logger.error(f"Erro ao criar fatura: {e}")
            raise
            
    def get_invoice(self, seller_id: int, invoice_id: int) -> Dict:
        """
        Busca uma fatura por ID
        
        Args:
            seller_id: ID do vendedor
            invoice_id: ID da fatura
            
        Returns:
            Dict com dados da fatura
        """
        try:
            endpoint = f"/api/v2/sellers/{seller_id}/invoices/{invoice_id}"
            response = self.http_client.get(endpoint)
            return response.json()
            
        except Exception as e:
            logger.error(f"Erro ao buscar fatura {invoice_id}: {e}")
            raise
            
    def cancel_invoice(self, seller_id: int, invoice_id: int) -> bool:
        """
        Cancela uma fatura
        
        Args:
            seller_id: ID do vendedor
            invoice_id: ID da fatura
            
        Returns:
            True se cancelada com sucesso
        """
        try:
            endpoint = f"/api/v2/sellers/{seller_id}/invoices/{invoice_id}/cancel"
            response = self.http_client.post(endpoint)
            
            logger.info(f"Fatura {invoice_id} cancelada com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao cancelar fatura {invoice_id}: {e}")
            return False
            
    def create_complete_invoice(self, 
                              customer_data: Dict,
                              amount_cents: int,
                              payment_method: str,
                              splits: Optional[List[Dict]] = None,
                              product_id: Optional[int] = None,
                              notification_url: Optional[str] = None,
                              success_url: Optional[str] = None,
                              seller_id: int = 1,
                              max_installments: int = 1) -> Dict:
        """
        Cria uma fatura completa (cliente + fatura)
        
        Args:
            customer_data: Dados do cliente
            amount_cents: Valor em centavos
            payment_method: Método de pagamento (CREDIT_CARD, PIX, BANK_SLIP)
            splits: Lista de splits (opcional)
            product_id: ID do produto (usa padrão se não fornecido)
            notification_url: URL para webhooks
            success_url: URL de sucesso
            seller_id: ID do vendedor principal
            
        Returns:
            Dict com fatura criada e URL de checkout
        """
        try:
            # Cria ou busca cliente
            customer = self.customer_manager.create_or_get_customer(customer_data)
            customer_id = customer.get('id')
            
            if not customer_id:
                raise ValueError("Não foi possível obter o ID do cliente criado")
            
            # Usa produto ID específico para fatura avulsa se não fornecido
            if not product_id:
                product_id = self.config.avulsa_product_id
                logger.info(f"🔍 Config - Unidade: {self.config.unidade}, Product ID (avulsa): {self.config.avulsa_product_id}, Product ID (recorrente): {self.config.recorrente_product_id}")

            # Monta payload da fatura
            # Data de vencimento para hoje + 1 dia em epoch milliseconds
            tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
            due_date = _format_due_date(tomorrow)

            logger.info(f"Due date epoch ms: {due_date}")

            # Log detalhado dos dados sendo enviados
            logger.info(f"=== CRIAÇÃO FATURA DELTA ===")
            logger.info(f"Payment Method: {payment_method}")
            logger.info(f"Amount in cents: {amount_cents} (type: {type(amount_cents)})")
            logger.info(f"Customer ID: {customer_id}")
            logger.info(f"Seller ID: {seller_id}")
            logger.info(f"Product ID: {product_id}")
            
            invoice_data = {
                "customerId": customer_id,
                "sellerId": seller_id,
                "invoiceNumber": f"AV-{uuid.uuid4().hex[:8].upper()}",
                "dueDate": due_date,
                "items": [{
                    "productId": product_id,
                    "quantity": 1,
                    "unitPriceInCents": amount_cents
                }],
                "acceptedPaymentMethods": []
            }
            
            # Configura método de pagamento aceito
            if payment_method == "CREDIT_CARD":
                invoice_data["acceptedPaymentMethods"].append({
                    "method": "CREDIT_CARD",
                    "cardSettings": {
                        "maxInstallments": max_installments,
                        "feePassThrough": False
                    }
                })
            elif payment_method == "PIX":
                invoice_data["acceptedPaymentMethods"].append({
                    "method": "PIX"
                })
            elif payment_method == "BANK_SLIP":
                invoice_data["acceptedPaymentMethods"].append({
                    "method": "BANK_SLIP"
                })
            
            # Adiciona URLs se fornecidas
            if notification_url:
                invoice_data["notificationUrl"] = notification_url
            if success_url:
                invoice_data["successUrl"] = success_url
                
            # Adiciona splits se fornecidos
            if splits:
                invoice_data["splits"] = splits
                
            # Log do payload completo
            logger.info(f"Invoice payload: {invoice_data}")
                
            # Cria fatura
            return self.create_invoice(invoice_data)
            
        except Exception as e:
            logger.error(f"Erro ao criar fatura completa: {e}")
            raise
