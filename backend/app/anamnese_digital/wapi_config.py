"""Configuracao das instancias W-API para cada unidade do GrupoJF."""

import os

# URL base da API W-API
WAPI_BASE_URL = os.getenv("WAPI_BASE_URL", "https://api.w-api.app/v1")

# Mapeamento de unidades para suas respectivas instâncias W-API
WAPI_INSTANCES = {
    "Nova Iguaçu 1": {
        "instance_id": os.getenv("WAPI_NI1_INSTANCE_ID", ""),
        "token": os.getenv("WAPI_NI1_TOKEN", ""),
        "nome_exibicao": "Nova Iguaçu"
    },
    "São João de Meriti": {
        "instance_id": os.getenv("WAPI_SJM_INSTANCE_ID", ""),
        "token": os.getenv("WAPI_SJM_TOKEN", ""),
        "nome_exibicao": "São João de Meriti"
    },
    "Belford Roxo": {
        "instance_id": os.getenv("WAPI_BFR_INSTANCE_ID", ""),
        "token": os.getenv("WAPI_BFR_TOKEN", ""),
        "nome_exibicao": "Belford Roxo"
    },
    "Vilar dos Teles": {
        "instance_id": os.getenv("WAPI_VILAR_INSTANCE_ID", ""),
        "token": os.getenv("WAPI_VILAR_TOKEN", ""),
        "nome_exibicao": "Vilar dos Teles"
    }
}

# Unidade padrão para fallback
DEFAULT_UNIT = "Nova Iguaçu 1"

def get_wapi_config(unidade: str = None):
    """
    Retorna a configuração W-API para a unidade especificada.
    Se a unidade não for encontrada ou for "Todas unidades", usa a unidade padrão.
    
    Args:
        unidade: Nome da unidade
        
    Returns:
        Dict com instance_id, token e nome_exibicao
    """
    if not unidade or unidade == "Todas unidades" or unidade not in WAPI_INSTANCES:
        return WAPI_INSTANCES[DEFAULT_UNIT]
    
    return WAPI_INSTANCES[unidade]
