# app/users_sdk/sdk_utils.py

import os
import logging
from dotenv import load_dotenv
from .exceptions import BempaggoConfigurationError

logger = logging.getLogger(__name__)

# Carregando variáveis de ambiente
load_dotenv()

def get_token_and_seller_for_unidade(unidade: str, environment: str = "sandbox"):
    """
    Se environment="production", retorna tokens específicos por unidade.
    Se environment="sandbox", retorna o MESMO token para qualquer unidade.
    O seller_id pode ser o mesmo sempre, ou outro se você tiver IDs distintos.
    """

    # Token sandbox único para users_sdk
    API_TOKEN_SANDBOX = os.getenv("API_TOKEN_BEMPAGGO_SANDBOX_users", "")

    # Tokens de PRODUÇÃO para users_sdk
    API_TOKEN_NI1 = os.getenv("API_TOKEN_BEMPAGGO_NI1_users", "")
    API_TOKEN_SJM = os.getenv("API_TOKEN_BEMPAGGO_SJM_users", "")
    API_TOKEN_VILAR = os.getenv("API_TOKEN_BEMPAGGO_VILAR_users", "")
    API_TOKEN_BFR = os.getenv("API_TOKEN_BEMPAGGO_BFR_users", "")

    SELLER_ID = "1"  # Id fixo, ou outro se precisar

    # Se sandbox, sempre retorna o mesmo token
    if environment == "sandbox":
        if not API_TOKEN_SANDBOX:
            raise ValueError("Variável de ambiente API_TOKEN_BEMPAGGO_SANDBOX_users não está configurada.")
        return (API_TOKEN_SANDBOX, SELLER_ID)

    # Caso contrário, assume production:
    map_producao = {
        "Nova Iguaçu 1": API_TOKEN_NI1,
        "São João de Meriti": API_TOKEN_SJM,
        "Vilar dos Teles": API_TOKEN_VILAR,
        "Belford Roxo": API_TOKEN_BFR,
        "Todas as unidades": API_TOKEN_NI1,  # Usa o token de Nova Iguaçu 1 como padrão
    }

    if unidade not in map_producao:
        raise ValueError(f"Unidade '{unidade}' sem token configurado no environment de produção.")

    token = map_producao[unidade]
    if not token:
        raise ValueError(f"Token vazio p/ unidade '{unidade}' em produção.")

    return (token, SELLER_ID)

def validate_receiver_data(data):
    """
    Valida os dados de um recebedor antes de enviar para a API.
    
    Args:
        data (dict): Dados do recebedor.
        
    Returns:
        tuple: (is_valid, errors) - onde is_valid é um bool e errors é uma lista de erros.
    """
    logger.info(f"VALIDAÇÃO: Iniciando para bankAccount={data.get('bankAccount', {})}")
    errors = []
    
    # Verificar campos obrigatórios
    required_fields = [
        "name", "document", "address", "phone", "birthdate", "email", "mcc", 
        "softDescriptor", "bankAccount"
    ]
    
    for field in required_fields:
        if field not in data or data[field] is None:
            errors.append(f"Campo obrigatório '{field}' não informado")
    
    # Se tiver address, verificar campos obrigatórios
    if "address" in data and data["address"]:
        addr_required = ["street", "streetNumber", "neighborhood", "city", "state", "zipCode"]
        for field in addr_required:
            if field not in data["address"] or data["address"][field] is None or data["address"][field] == "":
                errors.append(f"Campo obrigatório 'address.{field}' não informado")
    
    # Se tiver phone, verificar campos obrigatórios
    if "phone" in data and data["phone"]:
        phone_required = ["areaCode", "number"]
        for field in phone_required:
            if field not in data["phone"] or data["phone"][field] is None or data["phone"][field] == "":
                errors.append(f"Campo obrigatório 'phone.{field}' não informado")
    
    # Em validate_receiver_data, para validação de bankAccount
    if "bankAccount" in data and data["bankAccount"]:
        # Log para diagnóstico - IMPORTANTE: vamos verificar ambos os campos possíveis
        if "bankCode" in data["bankAccount"]:
            logger.debug(f"[VALIDATION] bankCode: {data['bankAccount']['bankCode']!r}")
        elif "codeBank" in data["bankAccount"]:
            logger.debug(f"[VALIDATION] codeBank: {data['bankAccount']['codeBank']!r}")
        else:
            logger.debug("[VALIDATION] nem bankCode nem codeBank estão presentes no payload")
        
        # Verificar campos bancários obrigatórios - ALTERADO
        bank_required = {
            "bankCode": ["bankCode", "codeBank"],  # Verifica ambos os nomes possíveis
            "bankBranch": ["bankBranch"],
            "bankBranchCheckDigit": ["bankBranchCheckDigit"],
            "accountNumber": ["accountNumber"],
            "accountCheckDigit": ["accountCheckDigit"],
            "accountType": ["accountType"]
        }
        
        # Verificação de campos bancários, considerando nomes alternativos
        for required_field, field_variants in bank_required.items():
            field_present = False
            
            # Verificar cada possível variante do nome do campo
            for field_name in field_variants:
                if field_name in data["bankAccount"] and data["bankAccount"][field_name] is not None and data["bankAccount"][field_name] != "":
                    field_present = True
                    break
            
            if not field_present:
                errors.append(f"Campo obrigatório 'bankAccount.{required_field}' não informado")
        
        # Verificar se accountType é válido
        account_type_field = None
        if "accountType" in data["bankAccount"]:
            account_type_field = "accountType"
        
        if account_type_field and data["bankAccount"][account_type_field] not in ["CHECKING", "SAVINGS"]:
            errors.append("Campo 'bankAccount.accountType' deve ser 'CHECKING' ou 'SAVINGS'")
    
    # Validação de CPF
    if "document" in data and data["document"]:
        if len(data["document"]) != 11 or not data["document"].isdigit():
            errors.append("Campo 'document' deve ser um CPF válido com 11 dígitos numéricos")
    
    return (len(errors) == 0, errors)
