# app/users_sdk/company_utils.py

import logging
from ..database.db import DatabaseConnection
from .sdk_utils import get_token_and_seller_for_unidade
from .receiver_api import ReceiverAPI
from .exceptions import (
    BempaggoAPIError, BempaggoConnectionError, 
    BempaggoValidationError, BempaggoConfigurationError
)
import os
from datetime import datetime

logger = logging.getLogger(__name__)

def validate_company_data(data):
    """
    Valida os dados de uma empresa antes de enviar para a API.
    
    Args:
        data (dict): Dados da empresa.
        
    Returns:
        tuple: (is_valid, errors) - onde is_valid é um bool e errors é uma lista de erros.
    """
    logger.info(f"VALIDAÇÃO: Iniciando para empresa={data.get('businessName', '')}")
    errors = []
    
    # Verificar campos obrigatórios
    required_fields = [
        "businessName", "document", "businessEmail", "mcc", 
        "softDescriptor", "owner", "businessAddress", "businessPhone", "bankAccount"
    ]
    
    for field in required_fields:
        if field not in data or data[field] is None:
            errors.append(f"Campo obrigatório '{field}' não informado")
    
    # Validar campos do proprietário
    if "owner" in data and data["owner"]:
        owner_required = ["name", "document", "address", "phone", "birthdate", "email"]
        for field in owner_required:
            if field not in data["owner"] or data["owner"][field] is None:
                errors.append(f"Campo obrigatório 'owner.{field}' não informado")
        
        # Validar nome do proprietário
        if "name" in data["owner"] and data["owner"]["name"]:
            name_required = ["firstName", "lastName"]
            for field in name_required:
                if field not in data["owner"]["name"] or not data["owner"]["name"][field]:
                    errors.append(f"Campo obrigatório 'owner.name.{field}' não informado")
        
        # Validar endereço do proprietário
        if "address" in data["owner"] and data["owner"]["address"]:
            addr_required = ["street", "streetNumber", "neighborhood", "city", "state", "zipCode"]
            for field in addr_required:
                if field not in data["owner"]["address"] or not data["owner"]["address"][field]:
                    errors.append(f"Campo obrigatório 'owner.address.{field}' não informado")
        
        # Validar telefone do proprietário
        if "phone" in data["owner"] and data["owner"]["phone"]:
            phone_required = ["areaCode", "number"]
            for field in phone_required:
                if field not in data["owner"]["phone"] or not data["owner"]["phone"][field]:
                    errors.append(f"Campo obrigatório 'owner.phone.{field}' não informado")
        
        # Validar CPF do proprietário
        if "document" in data["owner"] and data["owner"]["document"]:
            if len(data["owner"]["document"]) != 11 or not data["owner"]["document"].isdigit():
                errors.append("Campo 'owner.document' deve ser um CPF válido com 11 dígitos numéricos")
    
    # Validar endereço da empresa
    if "businessAddress" in data and data["businessAddress"]:
        addr_required = ["street", "streetNumber", "neighborhood", "city", "state", "zipCode"]
        for field in addr_required:
            if field not in data["businessAddress"] or not data["businessAddress"][field]:
                errors.append(f"Campo obrigatório 'businessAddress.{field}' não informado")
    
    # Validar telefone da empresa
    if "businessPhone" in data and data["businessPhone"]:
        phone_required = ["areaCode", "number"]
        for field in phone_required:
            if field not in data["businessPhone"] or not data["businessPhone"][field]:
                errors.append(f"Campo obrigatório 'businessPhone.{field}' não informado")
    
    # Validar conta bancária
    if "bankAccount" in data and data["bankAccount"]:
        bank_required = ["bankCode", "bankBranch", "accountNumber", "accountCheckDigit", "accountType"]
        for field in bank_required:
            if field not in data["bankAccount"] or not data["bankAccount"][field]:
                errors.append(f"Campo obrigatório 'bankAccount.{field}' não informado")
        
        # Verificar se accountType é válido
        if "accountType" in data["bankAccount"] and data["bankAccount"]["accountType"] not in ["CHECKING", "SAVINGS"]:
            errors.append("Campo 'bankAccount.accountType' deve ser 'CHECKING' ou 'SAVINGS'")
    
    # Validar CNPJ
    if "document" in data and data["document"]:
        if len(data["document"]) != 14 or not data["document"].isdigit():
            errors.append("Campo 'document' deve ser um CNPJ válido com 14 dígitos numéricos")
    
    return (len(errors) == 0, errors)

def integrate_company_with_bempaggo(company_id: int):
    """
    Integra uma empresa com a BemPaggo diretamente, verificando primeiro se o CNPJ já existe.
    """
    logger.info(f"Iniciando integração direta com BemPaggo para empresa {company_id}")
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Buscar dados da empresa
            cursor.execute("""
                SELECT 
                    id, razao_social, nome_fantasia, cnpj, email, data_abertura, mcc, soft_descriptor,
                    street, street_number, line_two, neighborhood, city, state, zip_code,
                    phone_country_code, phone_area_code, phone_number,
                    bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
                    owner_name, owner_cpf, owner_email, owner_birthdate,
                    owner_street, owner_street_number, owner_line_two, owner_neighborhood, owner_city, 
                    owner_state, owner_zip_code, owner_phone_country_code, owner_phone_area_code, 
                    owner_phone_number, unidade, bempaggo_notification_url
                FROM empresas
                WHERE id = %s
            """, (company_id,))
            
            company_data = cursor.fetchone()
            
            if not company_data:
                logger.error(f"Empresa ID {company_id} não encontrada")
                return {"status": "error", "message": "Empresa não encontrada"}
            
            # Extrair campos
            (id, razao_social, nome_fantasia, cnpj, email, data_abertura, mcc, soft_descriptor,
             street, street_number, line_two, neighborhood, city, state, zip_code,
             phone_country_code, phone_area_code, phone_number,
             bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
             owner_name, owner_cpf, owner_email, owner_birthdate,
             owner_street, owner_street_number, owner_line_two, owner_neighborhood, 
             owner_city, owner_state, owner_zip_code, owner_phone_country_code, 
             owner_phone_area_code, owner_phone_number, unidade, notification_url) = company_data
            
            # Verificar se CNPJ existe (requisito para busca)
            if not cnpj:
                cursor.execute("""
                    UPDATE empresas
                    SET bempaggo_integration_status = 'erro_sem_cnpj',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (company_id,))
                conn.commit()
                logger.warning(f"CNPJ não fornecido para integração: empresa {company_id}")
                return {"status": "error", "message": "CNPJ obrigatório para integração"}
            
            # Definir ambiente
            environment = "sandbox"
            if os.getenv("ENVIRONMENT", "development") == "production":
                environment = "production"
            
            # Inicializar API
            api_token, seller_id = get_token_and_seller_for_unidade(unidade, environment)
            api = ReceiverAPI(api_token, seller_id, environment)
            
            # Primeiro verificar se já existe um recebedor com este CNPJ
            existing_receiver = api.get_company_by_cnpj(cnpj)
            
            if existing_receiver and 'id' in existing_receiver:
                # Recebedor já existe! Apenas atualizar o banco com o ID
                receiver_id = existing_receiver['id']
                status_integracao = 'integrado_por_cnpj'
                
                cursor.execute("""
                    UPDATE empresas
                    SET bempaggo_receiver_id = %s,
                        bempaggo_integration_status = %s,
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (receiver_id, status_integracao, company_id))
                conn.commit()
                
                logger.info(f"Recebedor já existente vinculado à empresa ID {company_id}, receiver_id {receiver_id}")
                return {
                    "status": "success",
                    "message": "Recebedor existente vinculado com sucesso",
                    "receiver_id": receiver_id,
                    "integration_status": status_integracao
                }
            
            # Processamento do nome do proprietário
            owner_nome_partes = owner_name.split(" ", 1)
            owner_primeiro_nome = owner_nome_partes[0]
            owner_sobrenome = owner_nome_partes[1] if len(owner_nome_partes) > 1 else ""
            
            # Processamento de campos bancários
            bank_code_processado = str(bank_code).strip().zfill(3)[:3] if bank_code else None
            
            # Montagem do payload
            payload = {
                "businessName": razao_social,
                "openingDate": data_abertura.isoformat() if data_abertura else None,
                "document": cnpj,
                "businessEmail": email,
                "mcc": mcc,
                "softDescriptor": soft_descriptor,
                "owner": {
                    "name": {
                        "firstName": owner_primeiro_nome,
                        "lastName": owner_sobrenome
                    },
                    "address": {
                        "street": owner_street,
                        "streetNumber": owner_street_number,
                        "lineTwo": owner_line_two or "",
                        "neighborhood": owner_neighborhood,
                        "city": owner_city,
                        "state": owner_state,
                        "zipCode": owner_zip_code
                    },
                    "phone": {
                        "countryCode": owner_phone_country_code or "55",
                        "areaCode": owner_phone_area_code,
                        "number": owner_phone_number
                    },
                    "document": owner_cpf,
                    "birthdate": owner_birthdate.isoformat() if owner_birthdate else None,
                    "email": owner_email
                },
                "businessAddress": {
                    "street": street,
                    "streetNumber": street_number,
                    "lineTwo": line_two or "",
                    "neighborhood": neighborhood,
                    "city": city,
                    "state": state,
                    "zipCode": zip_code
                },
                "businessPhone": {
                    "countryCode": phone_country_code or "55",
                    "areaCode": phone_area_code,
                    "number": phone_number
                },
                "bankAccount": {
                    "bankCode": bank_code_processado,
                    "bankBranch": str(bank_branch),
                    "bankBranchCheckDigit": str(bank_branch_digit) if bank_branch_digit else "",
                    "accountNumber": str(account_number),
                    "accountCheckDigit": str(account_digit) if account_digit else "",
                    "accountType": account_type
                }
            }
            
            # Validar dados
            is_valid, validation_errors = validate_company_data(payload)
            if not is_valid:
                cursor.execute("""
                    UPDATE empresas
                    SET bempaggo_integration_status = 'dados_incompletos',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (company_id,))
                conn.commit()
                logger.warning(f"Dados inválidos para BemPaggo: {validation_errors}")
                return {"status": "error", "message": "Dados incompletos", "errors": validation_errors}
            
            # Criar novo recebedor
            try:
                response = api.create_company(payload)
                
                # Extrair ID do recebedor
                receiver_id = response.get('id')
                if not receiver_id:
                    cursor.execute("""
                        UPDATE empresas
                        SET bempaggo_integration_status = 'erro_id_nao_encontrado',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (company_id,))
                    conn.commit()
                    logger.error(f"ID não encontrado na resposta: {response}")
                    return {"status": "error", "message": "ID do recebedor não encontrado"}
                
                # Definir status com base na origem do ID
                status_integracao = 'integrado'
                if response.get('found_by_cnpj'):
                    status_integracao = 'integrado_por_cnpj'
                elif response.get('status') == 'id_pendente':
                    status_integracao = 'id_pendente'
                    
                # Atualizar empresa com ID do recebedor e status
                cursor.execute("""
                    UPDATE empresas
                    SET bempaggo_receiver_id = %s,
                        bempaggo_integration_status = %s,
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (receiver_id, status_integracao, company_id))
                conn.commit()
                
                logger.info(f"Integração com BemPaggo concluída para empresa ID {company_id}, receiver_id {receiver_id}")
                return {
                    "status": "success",
                    "message": "Recebedor criado com sucesso",
                    "receiver_id": str(receiver_id) if receiver_id else None,
                    "integration_status": status_integracao
                }
                
            except BempaggoValidationError as e:
                cursor.execute("""
                    UPDATE empresas
                    SET bempaggo_integration_status = 'erro_validacao',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (company_id,))
                conn.commit()
                
                logger.error(f"Erro de validação: {e.errors}")
                return {"status": "error", "message": "Erro de validação", "errors": e.errors}
                
            except Exception as e:
                cursor.execute("""
                    UPDATE empresas
                    SET bempaggo_integration_status = 'erro_integracao',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (company_id,))
                conn.commit()
                
                logger.error(f"Erro na integração: {str(e)}")
                return {"status": "error", "message": f"Erro na integração: {str(e)}"}
                
    except Exception as e:
        logger.error(f"Erro ao processar integração: {str(e)}", exc_info=True)
        
        # Atualizar status para erro
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE empresas
                    SET bempaggo_integration_status = 'erro_processamento',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (company_id,))
                conn.commit()
        except Exception as db_err:
            logger.error(f"Erro ao atualizar status no banco: {str(db_err)}")
            
        return {"status": "error", "message": f"Erro ao processar integração: {str(e)}"}