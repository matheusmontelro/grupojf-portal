"""Configurações de ambiente para SDK Delta Avulsa"""
from enum import Enum
import os
from .sdk_utils import get_token_for_unidade, get_product_ids_for_unidade

class Environment(Enum):
    SANDBOX = "https://api-sandbox.deltapag.io"
    PRODUCTION = "https://api.deltapag.io"

class DeltaConfig:
    """Configuração para API Delta com suporte multi-unidade"""

    def __init__(self, api_key: str, environment: Environment = Environment.SANDBOX, unidade: str = None):
        self.api_key = api_key
        self.environment = environment
        self.base_url = environment.value
        self.unidade = unidade
        # Product IDs para diferentes tipos de fatura - usa função que detecta por unidade
        if unidade:
            self.avulsa_product_id, self.recorrente_product_id = get_product_ids_for_unidade(unidade)
        else:
            self.avulsa_product_id = int(os.getenv("DELTA_AVULSA_PRODUCT_ID", "34"))
            self.recorrente_product_id = int(os.getenv("DELTA_RECORRENTE_PRODUCT_ID", "35"))
        
    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
    @classmethod
    def from_env(cls, unidade: str = None):
        """
        Cria configuração a partir de variáveis de ambiente
        
        Args:
            unidade: Nome da unidade (obrigatório para produção)
        """
        env_name = os.getenv("ENVIRONMENT", "sandbox").lower()
        environment = Environment.PRODUCTION if env_name == "production" else Environment.SANDBOX
        
        # Se não passou unidade, tenta pegar do ambiente (fallback)
        if not unidade:
            unidade = os.getenv("DELTA_DEFAULT_UNIDADE", "Nova Iguaçu 1")
        
        # Obtém o token apropriado baseado na unidade e ambiente
        env_str = "production" if environment == Environment.PRODUCTION else "sandbox"
        api_key = get_token_for_unidade(unidade, env_str)
        
        return cls(api_key=api_key, environment=environment, unidade=unidade)