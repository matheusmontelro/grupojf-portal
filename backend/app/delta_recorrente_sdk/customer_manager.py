"""Gerenciador de clientes para API Delta"""
import logging
from typing import Dict, Optional
from .http_client import DeltaHttpClient

logger = logging.getLogger(__name__)

class CustomerManager:
    """Gerencia criação e busca de clientes na API Delta"""
    
    def __init__(self, http_client: DeltaHttpClient):
        self.http_client = http_client
        
    def create_customer(self, customer_data: Dict) -> Dict:
        """
        Cria um novo cliente na API Delta
        
        Args:
            customer_data: Dados do cliente contendo:
                - name: Nome completo
                - document: CPF ou CNPJ
                - email: Email válido
                - phone: Objeto com countryCode, areaCode, number
                - address: Objeto com endereço completo
                
        Returns:
            Dict com dados do cliente criado
        """
        try:
            # Valida dados obrigatórios
            required_fields = ['name', 'document', 'email']
            for field in required_fields:
                if field not in customer_data:
                    raise ValueError(f"Campo obrigatório ausente: {field}")
                    
            # Formata documento (remove caracteres especiais)
            customer_data['document'] = ''.join(c for c in customer_data['document'] if c.isdigit())
            
            # Envia requisição
            response = self.http_client.post("/api/v2/customers", json=customer_data)
            
            # Verifica se a resposta tem conteúdo
            if response.text:
                customer = response.json()
                logger.info(f"Cliente criado com sucesso. ID: {customer.get('id')}")
                return customer
            else:
                # Se não há conteúdo na resposta, tenta extrair ID dos headers
                logger.info(f"Cliente criado, mas resposta vazia. Status: {response.status_code}")
                logger.info(f"Headers: {dict(response.headers)}")
                
                # O ID do cliente está no header 'content-id'
                customer_id = None
                content_id = response.headers.get('content-id')
                if content_id:
                    try:
                        customer_id = int(content_id)
                        logger.info(f"ID extraído do header content-id: {customer_id}")
                    except:
                        logger.error(f"Erro ao converter content-id para int: {content_id}")
                
                if not customer_id:
                    logger.error("Não foi possível extrair o ID do cliente dos headers")
                
                return {
                    "id": customer_id,
                    "name": customer_data.get('name'),
                    "document": customer_data.get('document'),
                    "email": customer_data.get('email')
                }
            
        except Exception as e:
            logger.error(f"Erro ao criar cliente: {e}")
            raise
            
    def get_customer(self, customer_id: int) -> Dict:
        """
        Busca cliente por ID
        
        Args:
            customer_id: ID do cliente na Delta
            
        Returns:
            Dict com dados do cliente
        """
        try:
            response = self.http_client.get(f"/api/v2/customers/{customer_id}")
            return response.json()
        except Exception as e:
            logger.error(f"Erro ao buscar cliente {customer_id}: {e}")
            raise
            
    def find_customer_by_document(self, document: str) -> Optional[Dict]:
        """
        Busca cliente por documento (CPF/CNPJ)
        
        Args:
            document: CPF ou CNPJ do cliente
            
        Returns:
            Dict com dados do cliente ou None se não encontrado
        """
        try:
            # Remove caracteres especiais do documento
            clean_document = ''.join(c for c in document if c.isdigit())
            
            # A API Delta não suporta busca por documento no endpoint GET /customers
            # Vamos sempre retornar None para forçar a criação de um novo cliente
            # TODO: Verificar com a Delta se existe endpoint de busca por documento
            logger.info(f"Busca por documento não implementada. Documento: {clean_document}")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar cliente por documento: {e}")
            return None
            
    def create_or_get_customer(self, customer_data: Dict) -> Dict:
        """
        Cria cliente ou retorna existente baseado no documento
        
        Args:
            customer_data: Dados do cliente
            
        Returns:
            Dict com dados do cliente (novo ou existente)
        """
        document = customer_data.get('document')
        if not document:
            raise ValueError("Documento é obrigatório")
            
        # Tenta encontrar cliente existente
        existing_customer = self.find_customer_by_document(document)
        if existing_customer:
            logger.info(f"Cliente já existe. ID: {existing_customer.get('id')}")
            return existing_customer
            
        # Cria novo cliente
        return self.create_customer(customer_data)