import os
from dotenv import load_dotenv

# Carrega o .env correto do diretório raiz do projeto
load_dotenv()

def get_token_for_unidade(unidade: str, environment: str = "production"):
    """
    Retorna o token Delta Recorrente apropriado baseado na unidade e ambiente.
    
    Args:
        unidade: Nome da unidade (ex: "Nova Iguaçu 1")
        environment: "sandbox" ou "production"
    
    Returns:
        str: Token de API correspondente
    """
    
    # Token sandbox único
    API_TOKEN_SANDBOX = os.getenv("API_TOKEN_DELTA_RECORRENTE_SANDBOX", "")
    
    # Tokens de PRODUÇÃO por unidade
    API_TOKEN_NI1 = os.getenv("API_TOKEN_DELTA_RECORRENTE_NI1", "")
    API_TOKEN_SJM = os.getenv("API_TOKEN_DELTA_RECORRENTE_SJM", "")
    API_TOKEN_VILAR = os.getenv("API_TOKEN_DELTA_RECORRENTE_VILAR", "")
    API_TOKEN_BFR = os.getenv("API_TOKEN_DELTA_RECORRENTE_BFR", "")
    
    # Se sandbox, sempre retorna o mesmo token
    if environment == "sandbox":
        if not API_TOKEN_SANDBOX:
            raise ValueError("Variável de ambiente API_TOKEN_DELTA_RECORRENTE_SANDBOX não está configurada.")
        return API_TOKEN_SANDBOX
    
    # Mapeamento para produção
    map_producao = {
        "Nova Iguaçu 1": API_TOKEN_NI1,
        "São João de Meriti": API_TOKEN_SJM,
        "Vilar dos Teles": API_TOKEN_VILAR,
        "Belford Roxo": API_TOKEN_BFR,
    }
    
    if unidade not in map_producao:
        raise ValueError(f"Unidade '{unidade}' sem token configurado no environment de produção.")
    
    token = map_producao[unidade]
    if not token:
        raise ValueError(f"Token vazio para unidade '{unidade}' em produção.")
    
    return token
