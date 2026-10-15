# app/carne_sdk/customer_manager.py

import logging
import requests
from typing import Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)

class CustomerManager:
    """
    Gerencia operações relacionadas a clientes na API da Bempaggo.
    """
    
    def __init__(self, base_url: str, api_token: str):
        """
        Inicializa o gerenciador de clientes.
        
        Args:
            base_url (str): URL base da API (sandbox ou production)
            api_token (str): Token de autenticação da API
        """
        self.base_url = base_url
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def check_customer_exists(self, document: str) -> Tuple[bool, Optional[int]]:
        """
        Verifica se um cliente já existe na Bempaggo pelo documento (CPF/CNPJ).
        
        Args:
            document (str): CPF ou CNPJ do cliente (apenas números)
            
        Returns:
            Tuple[bool, Optional[int]]: (True se o cliente existe, ID do cliente) ou (False, None)
        """
        url = f"{self.base_url}/customers/document/{document}"
        logger.info(f"Verificando se cliente com documento {document} existe")
        
        try:
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                customer_data = response.json()
                customer_id = customer_data.get("id")
                logger.info(f"Cliente encontrado com ID: {customer_id}")
                return True, customer_id
            elif response.status_code == 404:
                logger.info(f"Cliente com documento {document} não encontrado")
                return False, None
            else:
                logger.error(f"Erro ao verificar cliente: HTTP {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                response.raise_for_status()
                return False, None
                
        except Exception as e:
            logger.error(f"Erro ao verificar cliente: {str(e)}")
            raise
    
    def create_customer(self, customer_data: Dict[str, Any]) -> int:
        """
        Cria um novo cliente na Bempaggo.
        
        Args:
            customer_data (Dict[str, Any]): Dados do cliente conforme especificação da API
            
        Returns:
            int: ID do cliente criado
        """
        url = f"{self.base_url}/customers"
        logger.info(f"Criando cliente: {customer_data.get('name')}")
        
        try:
            response = requests.post(url, headers=self.headers, json=customer_data)
            response.raise_for_status()
            
            # A API retorna o ID no cabeçalho de localização
            location = response.headers.get("Location")
            if location:
                # Extrair o ID do Location (formato: "/api/v2/customers/{id}")
                customer_id = int(location.split("/")[-1])
                logger.info(f"Cliente criado com sucesso. ID: {customer_id}")
                return customer_id
            else:
                # Se não encontrar o location, fazer uma busca pelo documento
                document = customer_data.get("document")
                exists, customer_id = self.check_customer_exists(document)
                if exists and customer_id:
                    return customer_id
                else:
                    raise ValueError("Não foi possível obter o ID do cliente criado")
                
        except Exception as e:
            logger.error(f"Erro ao criar cliente: {str(e)}")
            raise
    
    def get_or_create_customer(self, document: str, customer_data: Dict[str, Any]) -> int:
        """
        Verifica se o cliente existe e o cria se necessário.
        
        Args:
            document (str): CPF ou CNPJ do cliente
            customer_data (Dict[str, Any]): Dados do cliente para criação
            
        Returns:
            int: ID do cliente (existente ou recém-criado)
        """
        exists, customer_id = self.check_customer_exists(document)
        
        if exists and customer_id:
            return customer_id
        else:
            return self.create_customer(customer_data)