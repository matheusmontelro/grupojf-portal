# app/boleto_sdk/sdk_utils.py
import os
import re
from dotenv import load_dotenv

load_dotenv()  # caso ainda não tenha carregado

def get_token_and_seller_for_unidade(unidade: str, environment: str = "production"):
    """
    Se environment="production", retorna tokens específicos por unidade.
    Se environment="sandbox", retorna o MESMO token para qualquer unidade.
    O seller_id pode ser o mesmo sempre, ou outro se você tiver IDs distintos.
    """

    # Token sandbox único
    API_TOKEN_SANDBOX = os.getenv("API_TOKEN_BOLETO_SANDBOX", "")

    # Tokens de PRODUÇÃO
    API_TOKEN_NI1 = os.getenv("API_TOKEN_BOLETO_NI1", "")
    API_TOKEN_SJM = os.getenv("API_TOKEN_BOLETO_SJM", "")
    API_TOKEN_VILAR = os.getenv("API_TOKEN_BOLETO_VILAR", "")
    API_TOKEN_BFR = os.getenv("API_TOKEN_BOLETO_BFR", "")

    SELLER_ID = "1"  # Id fixo, ou outro se precisar

    # Se sandbox, sempre retorna o mesmo token
    if environment == "sandbox":
        if not API_TOKEN_SANDBOX:
            raise ValueError("Variável de ambiente API_TOKEN_BOLETO_SANDBOX não está configurada.")
        return (API_TOKEN_SANDBOX, SELLER_ID)

    # Caso contrário, assume production:
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
        raise ValueError(f"Token vazio p/ unidade '{unidade}' em produção.")

    return (token, SELLER_ID)
