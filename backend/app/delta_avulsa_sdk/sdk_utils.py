import os
from dotenv import load_dotenv

load_dotenv()

def get_token_for_unidade(unidade: str, environment: str = "production"):
    """
    Retorna o token Delta Avulsa apropriado baseado na unidade e ambiente.

    Args:
        unidade: Nome da unidade (ex: "Nova Iguaçu 1")
        environment: "sandbox" ou "production"

    Returns:
        str: Token de API correspondente
    """

    # Token sandbox único
    API_TOKEN_SANDBOX = os.getenv("API_TOKEN_DELTA_AVULSA_SANDBOX", "")

    # Tokens de PRODUÇÃO por unidade
    API_TOKEN_NI1 = os.getenv("API_TOKEN_DELTA_AVULSA_NI1", "")
    API_TOKEN_SJM = os.getenv("API_TOKEN_DELTA_AVULSA_SJM", "")
    API_TOKEN_VILAR = os.getenv("API_TOKEN_DELTA_AVULSA_VILAR", "")
    API_TOKEN_BFR = os.getenv("API_TOKEN_DELTA_AVULSA_BFR", "")

    # Se sandbox, sempre retorna o mesmo token
    if environment == "sandbox":
        if not API_TOKEN_SANDBOX:
            raise ValueError("Variável de ambiente API_TOKEN_DELTA_AVULSA_SANDBOX não está configurada.")
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


def get_product_ids_for_unidade(unidade: str) -> tuple[int, int]:
    """
    Retorna os Product IDs (avulsa, recorrente) para uma unidade específica.

    Args:
        unidade: Nome da unidade (ex: "Belford Roxo")

    Returns:
        tuple: (avulsa_product_id, recorrente_product_id)
    """
    # Product IDs globais (padrão)
    default_avulsa = int(os.getenv("DELTA_AVULSA_PRODUCT_ID", "87"))
    default_recorrente = int(os.getenv("DELTA_RECORRENTE_PRODUCT_ID", "88"))

    # Product IDs específicos por unidade
    product_ids_map = {
        "Belford Roxo": (
            int(os.getenv("DELTA_AVULSA_PRODUCT_ID_BFR", default_avulsa)),
            int(os.getenv("DELTA_RECORRENTE_PRODUCT_ID_BFR", default_recorrente))
        ),
        "São João de Meriti": (
            int(os.getenv("DELTA_AVULSA_PRODUCT_ID_SJM", default_avulsa)),
            int(os.getenv("DELTA_RECORRENTE_PRODUCT_ID_SJM", default_recorrente))
        ),
        "Vilar dos Teles": (
            int(os.getenv("DELTA_AVULSA_PRODUCT_ID_VILAR", default_avulsa)),
            int(os.getenv("DELTA_RECORRENTE_PRODUCT_ID_VILAR", default_recorrente))
        ),
    }

    # Retorna IDs específicos da unidade ou os padrões
    return product_ids_map.get(unidade, (default_avulsa, default_recorrente))


def get_seller_ids_for_unidade(unidade: str) -> dict[str, int]:
    """
    Retorna os Seller IDs específicos para splits por unidade.

    Args:
        unidade: Nome da unidade (ex: "Belford Roxo")

    Returns:
        dict: Mapeamento de empresa -> seller_id
              Ex: {"partmed": 7, "akimais": 8}
    """
    # Mapeamento por unidade
    seller_ids_map = {
        "Belford Roxo": {
            "partmed": int(os.getenv("SELLER_ID_PARTMED_BFR", "7")),
            "akimais": int(os.getenv("SELLER_ID_AKIMAIS_BFR", "8"))
        },
        "São João de Meriti": {
            "partmed": int(os.getenv("SELLER_ID_PARTMED_SJM", "20")),
            "akimais": int(os.getenv("SELLER_ID_AKIMAIS_SJM", "21"))
        },
        "Vilar dos Teles": {
            "partmed": int(os.getenv("SELLER_ID_PARTMED_VILAR", "16")),
            "akimais": int(os.getenv("SELLER_ID_AKIMAIS_VILAR", "17"))
        },
        "Nova Iguaçu 1": {
            "partmed": int(os.getenv("SELLER_ID_PARTMED_NI1", "7")),
            "akimais": int(os.getenv("SELLER_ID_AKIMAIS_NI1", "8"))
        }
    }

    # Retorna IDs específicos da unidade ou valores padrão
    return seller_ids_map.get(unidade, {"partmed": 7, "akimais": 8})
