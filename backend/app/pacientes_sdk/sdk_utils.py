# app/patients_sdk/sdk_utils.py

import os
import logging
from dotenv import load_dotenv
from .exceptions import DeltaConfigurationError

logger = logging.getLogger(__name__)

# Carregando variáveis de ambiente
load_dotenv()

def get_token_and_seller_for_unidade(unidade: str, environment: str = "sandbox"):
    """
    Se environment="production", retorna tokens específicos por unidade.
    Se environment="sandbox", retorna o MESMO token para qualquer unidade.
    O seller_id pode ser o mesmo sempre, ou outro se você tiver IDs distintos.
    """

    # Token sandbox único para patients_sdk
    API_TOKEN_SANDBOX = os.getenv("API_TOKEN_BEMPAGGO_SANDBOX_patients", "")

    # Tokens de PRODUÇÃO para patients_sdk
    API_TOKEN_NI1 = os.getenv("API_TOKEN_BEMPAGGO_NI1_patients", "")
    API_TOKEN_SJM = os.getenv("API_TOKEN_BEMPAGGO_SJM_patients", "")
    API_TOKEN_VILAR = os.getenv("API_TOKEN_BEMPAGGO_VILAR_patients", "")
    API_TOKEN_BFR = os.getenv("API_TOKEN_BEMPAGGO_BFR_patients", "")

    SELLER_ID = "1"  # Id fixo, ou outro se precisar

    # Se sandbox, sempre retorna o mesmo token
    if environment == "sandbox":
        if not API_TOKEN_SANDBOX:
            raise ValueError("Variável de ambiente API_TOKEN_BEMPAGGO_SANDBOX_patients não está configurada.")
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

def validate_patient_data(data):
    """
    Valida os dados de um paciente antes de enviar para a API Delta.
    
    Args:
        data (dict): Dados do paciente.
        
    Returns:
        tuple: (is_valid, errors) - onde is_valid é um bool e errors é uma lista de erros.
    """
    logger.info("VALIDAÇÃO: Iniciando dados de paciente")
    errors = []
    
    # Verificar campos obrigatórios
    required_fields = [
        "name", "document"
    ]
    
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == "":
            errors.append(f"Campo obrigatório '{field}' não informado")
    
    # Se tiver address (opcional para patients_sdk), verificar campos obrigatórios do address
    if "address" in data and data["address"]:
        addr_required = ["street", "streetNumber", "neighborhood", "city", "state", "zipCode"]
        for field in addr_required:
            if field not in data["address"] or data["address"][field] is None or data["address"][field] == "":
                errors.append(f"Campo obrigatório 'address.{field}' não informado")
    
    # Se tiver phone (opcional para patients_sdk), verificar campos obrigatórios do phone
    if "phone" in data and data["phone"]:
        phone_required = ["countryCode", "areaCode", "number"]
        for field in phone_required:
            if field not in data["phone"] or data["phone"][field] is None or data["phone"][field] == "":
                errors.append(f"Campo obrigatório 'phone.{field}' não informado")
    
    # Validação de CPF/CNPJ
    if "document" in data and data["document"]:
        # Remover caracteres não numéricos
        document = ''.join(filter(lambda x: x.isdigit(), str(data["document"])))
        
        # Verificar se é um CPF (11 dígitos) ou CNPJ (14 dígitos)
        if len(document) != 11 and len(document) != 14:
            errors.append("Campo 'document' deve ser um CPF (11 dígitos) ou CNPJ (14 dígitos)")
    
    return (len(errors) == 0, errors)

def transform_to_delta_format(paciente_data):
    """
    Transforma os dados do paciente do formato interno para o formato da API Delta.
    
    Args:
        paciente_data (dict): Dados do paciente no formato interno.
        
    Returns:
        dict: Dados formatados para a API Delta.
    """
    # Montagem do payload para a API Delta
    delta_payload = {
        "name": paciente_data.get("nome_paciente", ""),
        "document": ''.join(filter(lambda x: x.isdigit(), str(paciente_data.get("cpf_cnpj", "")))),
        "email": paciente_data.get("email")
    }
    
    # Adicionar data de nascimento se disponível
    if paciente_data.get("data_nascimento"):
        # Converter para ISO format string com timezone
        birthdate = paciente_data.get("data_nascimento")
        if hasattr(birthdate, 'isoformat'):
            delta_payload["birthdate"] = f"{birthdate.isoformat()}T00:00:00.000Z"
        else:
            delta_payload["birthdate"] = f"{birthdate}T00:00:00.000Z"
    
    # Adicionar telefone se disponível
    if paciente_data.get("phone_area_code") and paciente_data.get("phone_number"):
        delta_payload["phone"] = {
            "countryCode": int(paciente_data.get("phone_country_code") or "55"),
            "areaCode": int(paciente_data.get("phone_area_code")),
            "number": int(paciente_data.get("phone_number").replace("-", "").replace(" ", ""))
        }
    
    # Adicionar endereço se disponível
    if (paciente_data.get("street") and paciente_data.get("city") and 
        paciente_data.get("state") and paciente_data.get("zip_code")):
        delta_payload["address"] = {
            "street": paciente_data.get("street", ""),
            "streetNumber": paciente_data.get("street_number", ""),
            "lineTwo": paciente_data.get("line_two", "") or "",
            "neighborhood": paciente_data.get("neighborhood", ""),
            "city": paciente_data.get("city", ""),
            "state": paciente_data.get("state", ""),
            "zipCode": paciente_data.get("zip_code", "").replace("-", "").replace(".", "")
        }
    
    return delta_payload

def transform_from_delta_format(delta_data):
    """
    Transforma os dados do paciente do formato da API Delta para o formato interno.
    
    Args:
        delta_data (dict): Dados do paciente no formato da API Delta.
        
    Returns:
        dict: Dados formatados para o modelo interno.
    """
    # Dados básicos
    internal_data = {
        "nome_paciente": delta_data.get("name", ""),
        "cpf_cnpj": delta_data.get("document", ""),
        "email": delta_data.get("email")
    }
    
    # Data de nascimento
    if delta_data.get("birthdate"):
        # Normalizar a data para formato YYYY-MM-DD
        birthdate = delta_data.get("birthdate", "").split("T")[0]
        internal_data["data_nascimento"] = birthdate
    
    # Telefone
    if delta_data.get("phone"):
        phone_data = delta_data.get("phone", {})
        internal_data["phone_country_code"] = str(phone_data.get("countryCode", "55"))
        internal_data["phone_area_code"] = str(phone_data.get("areaCode", ""))
        internal_data["phone_number"] = str(phone_data.get("number", ""))
    
    # Endereço
    if delta_data.get("address"):
        address_data = delta_data.get("address", {})
        internal_data["street"] = address_data.get("street", "")
        internal_data["street_number"] = address_data.get("streetNumber", "")
        internal_data["line_two"] = address_data.get("lineTwo", "")
        internal_data["neighborhood"] = address_data.get("neighborhood", "")
        internal_data["city"] = address_data.get("city", "")
        internal_data["state"] = address_data.get("state", "")
        internal_data["zip_code"] = address_data.get("zipCode", "")
    
    return internal_data
