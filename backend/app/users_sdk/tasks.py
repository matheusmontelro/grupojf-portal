# app/users_sdk/tasks.py

import logging
import os
import json
from celery import shared_task
from ..database.db import DatabaseConnection
from .receiver_api import ReceiverAPI
from .sdk_utils import get_token_and_seller_for_unidade, validate_receiver_data
from .exceptions import (
    BempaggoAPIError, 
    BempaggoConnectionError, 
    BempaggoValidationError, 
    BempaggoConfigurationError
)
from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)

@shared_task(
    bind=True, 
    autoretry_for=(BempaggoConnectionError,),
    retry_kwargs={'max_retries': 3, 'countdown': 60}
)
def create_bempaggo_receiver(self, user_id):
    """
    Tarefa Celery para criar um recebedor na BemPaggo.
    """
    logger.info(f"Iniciando tarefa de criação de recebedor BemPaggo para usuário {user_id}")
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Buscar dados completos do usuário
            cursor.execute("""
                SELECT 
                    id, nome, email, role, unidade, cpf, birthdate, mcc, soft_descriptor,
                    street, street_number, line_two, neighborhood, city, state, zip_code,
                    phone_country_code, phone_area_code, phone_number,
                    bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type
                FROM users
                WHERE id = %s
            """, (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                logger.error(f"Usuário ID {user_id} não encontrado")
                return {"status": "error", "message": "Usuário não encontrado"}
            
            # Extrair campos
            (id, nome, email, role, unidade, cpf, birthdate, mcc, soft_descriptor,
             street, street_number, line_two, neighborhood, city, state, zip_code,
             phone_country_code, phone_area_code, phone_number,
             bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type) = user_data
            
            # Log e processamento dos dados do banco
            logger.debug(f"Dados do usuário {user_id}: bank_code={bank_code!r}, tipo={type(bank_code)}")
            
            # Processamento do nome
            nome_partes = nome.split(" ", 1)
            primeiro_nome = nome_partes[0]
            sobrenome = nome_partes[1] if len(nome_partes) > 1 else ""
            
            # Processamento seguro de campos bancários para garantir formato correto
            # Garantir que bank_code seja uma string de exatamente 3 caracteres
            bank_code_processado = None
            if bank_code is not None:
                # Converter para string, remover espaços e garantir 3 caracteres com leading zeros
                bank_code_processado = str(bank_code).strip().zfill(3)[:3]
                logger.debug(f"bank_code processado: {bank_code_processado!r}, comprimento: {len(bank_code_processado)}")
                
                # Verificar se o processamento resultou em um valor válido
                if not bank_code_processado or bank_code_processado == "000":
                    logger.warning(f"Valor de bank_code inválido após processamento: {bank_code_processado!r}")
            
            # Processamento de outros campos bancários
            bank_branch_processado = str(bank_branch).strip() if bank_branch else None
            bank_branch_digit_processado = str(bank_branch_digit).strip() if bank_branch_digit else None
            account_number_processado = str(account_number).strip() if account_number else None
            account_digit_processado = str(account_digit).strip() if account_digit else None
            
            # Montagem do payload com dados processados
            payload = {
                "name": {
                    "firstName": primeiro_nome,
                    "lastName": sobrenome
                },
                "document": cpf,
                "address": {
                    "street": street,
                    "streetNumber": street_number,
                    "lineTwo": line_two or "",
                    "neighborhood": neighborhood,
                    "city": city,
                    "state": state,
                    "zipCode": zip_code
                },
                "phone": {
                    "countryCode": phone_country_code or "55",
                    "areaCode": phone_area_code,
                    "number": phone_number
                },
                "birthdate": birthdate.isoformat() if birthdate else None,
                "email": email,
                "mcc": mcc,
                "softDescriptor": soft_descriptor,
                "bankAccount": {
                    "bankCode": bank_code_processado,
                    "bankBranch": bank_branch_processado,
                    "bankBranchCheckDigit": bank_branch_digit_processado,
                    "accountNumber": account_number_processado,
                    "accountCheckDigit": account_digit_processado,
                    "accountType": account_type
                }
            }
            
            # Log do payload antes da validação
            logger.debug(f"Payload preparado: bankAccount.bankCode={payload['bankAccount']['bankCode']!r}")
            
            # Validar dados
            is_valid, validation_errors = validate_receiver_data(payload)
            if not is_valid:
                logger.warning(f"Dados inválidos para BemPaggo: {validation_errors}")
                
                # Se o erro for específico para bankCode e temos um valor válido, devemos corrigir no banco
                codigo_banco_invalido = any(
                    "bankAccount.bankCode" in err or "bankAccount.bankCode" in str(err) 
                    for err in validation_errors
                )
                
                if codigo_banco_invalido and bank_code:
                    logger.info(f"Tentando corrigir bank_code no banco para {user_id}")
                    try:
                        # Atualizar o banco com o valor formatado
                        cursor.execute("""
                            UPDATE users 
                            SET bank_code = %s 
                            WHERE id = %s
                        """, (bank_code_processado, user_id))
                        conn.commit()
                        logger.info(f"bank_code atualizado para {bank_code_processado} no banco de dados")
                        
                        # Tentar novamente a validação após corrigir
                        is_valid, validation_errors = validate_receiver_data(payload)
                        if not is_valid:
                            logger.warning("Validação falhou mesmo após correção no banco")
                    except Exception as db_err:
                        logger.error(f"Erro ao atualizar bank_code no banco: {str(db_err)}")
                
                # Se ainda for inválido, atualizamos o status
                if not is_valid:
                    cursor.execute("""
                        UPDATE users
                        SET bempaggo_integration_status = 'dados_incompletos',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                    return {"status": "error", "message": "Dados incompletos", "errors": validation_errors}
            
            # Definir ambiente com base no status do sistema
            environment = "sandbox"
            if os.getenv("ENVIRONMENT", "development") == "production":
                environment = "production"
            
            try:
                # Inicializar API
                api_token, seller_id = get_token_and_seller_for_unidade(unidade, environment)
                api = ReceiverAPI(api_token, seller_id, environment)
                
                # Chamar API para criar recebedor
                response = api.create_receiver(payload)
                
                # Extrair ID do recebedor da resposta
                receiver_id = response.get('id')
                if not receiver_id:
                    raise BempaggoAPIError(
                        200, 
                        str(response), 
                        "ID do recebedor não encontrado na resposta"
                    )
                
                # Se o status indica ID pendente, registrar essa informação
                if response.get('status') == 'created_id_pending':
                    logger.warning(f"ID temporário usado para usuário {user_id}: {receiver_id}. Necessária verificação posterior.")
                
                # Atualizar usuário com ID do recebedor e status
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_receiver_id = %s,
                        bempaggo_integration_status = %s,
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    receiver_id, 
                    'integrado' if response.get('status') != 'created_id_pending' else 'id_pendente',
                    user_id
                ))
                conn.commit()
                
                logger.info(f"Integração com BemPaggo concluída para usuário ID {user_id}, receiver_id {receiver_id}")
                return {
                    "status": "success", 
                    "message": "Recebedor criado com sucesso", 
                    "receiver_id": receiver_id
                }
                
            except BempaggoValidationError as e:
                # Atualizar status para "erro_validacao"
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'erro_validacao',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                
                logger.error(f"Erro de validação na BemPaggo para usuário {user_id}: {e.errors}")
                return {"status": "error", "message": "Erro de validação", "errors": e.errors}
                
            except BempaggoConnectionError as e:
                # Nesse caso, não atualizar o status pois queremos que o retry funcione
                logger.error(f"Erro de conexão com BemPaggo para usuário {user_id}: {str(e)}")
                # Propagar para permitir o retry
                raise
                
            except BempaggoConfigurationError as e:
                # Atualizar status para "erro_configuracao"
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'erro_configuracao',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                
                logger.error(f"Erro de configuração BemPaggo para usuário {user_id}: {str(e)}")
                return {"status": "error", "message": str(e)}
                
            except BempaggoAPIError as e:
                # Atualizar status para "erro_api"
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'erro_api',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                
                logger.error(f"Erro da API BemPaggo para usuário {user_id}: {e.detail or e.response_body}")
                return {
                    "status": "error", 
                    "message": "Erro da API", 
                    "api_error": e.detail or e.response_body
                }
                
            except Exception as e:
                # Atualizar status para "erro_desconhecido"
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'erro_desconhecido',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                
                logger.error(f"Erro desconhecido para usuário {user_id}: {str(e)}", exc_info=True)
                return {"status": "error", "message": f"Erro desconhecido: {str(e)}"}
    
    except Exception as e:
        logger.error(f"Erro ao processar tarefa para usuário {user_id}: {str(e)}", exc_info=True)
        return {"status": "error", "message": f"Erro ao processar tarefa: {str(e)}"}


@shared_task(bind=True)
def update_bempaggo_receiver(self, user_id):
    """
    Tarefa Celery para atualizar um recebedor existente na BemPaggo.
    
    Args:
        user_id (int): ID do usuário a ter seus dados atualizados
        
    Returns:
        dict: Resultado da operação com status e mensagem
    """
    logger.info(f"Iniciando tarefa de atualização de recebedor BemPaggo para usuário {user_id}")
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Buscar dados completos do usuário - removida a coluna bempaggo_notification_url
            cursor.execute("""
                SELECT 
                    id, nome, email, role, unidade, cpf, birthdate, mcc, soft_descriptor,
                    street, street_number, line_two, neighborhood, city, state, zip_code,
                    phone_country_code, phone_area_code, phone_number,
                    bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
                    bempaggo_receiver_id
                FROM users
                WHERE id = %s
            """, (user_id,))
            
            user_data = cursor.fetchone()
            
            if not user_data:
                logger.error(f"Usuário ID {user_id} não encontrado")
                return {"status": "error", "message": "Usuário não encontrado"}
            
            # Extrair campos - removida a variável notification_url
            (id, nome, email, role, unidade, cpf, birthdate, mcc, soft_descriptor,
             street, street_number, line_two, neighborhood, city, state, zip_code,
             phone_country_code, phone_area_code, phone_number,
             bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
             receiver_id) = user_data
            
            # Verificar se tem ID de recebedor
            if not receiver_id:
                logger.error(f"Usuário ID {user_id} não possui ID de recebedor BemPaggo")
                return {"status": "error", "message": "Usuário não possui ID de recebedor"}
            
            # Log e processamento dos dados do banco
            logger.debug(f"Dados do usuário {user_id}: bank_code={bank_code!r}, tipo={type(bank_code)}")
            
            # Processamento do nome
            nome_partes = nome.split(" ", 1)
            primeiro_nome = nome_partes[0]
            sobrenome = nome_partes[1] if len(nome_partes) > 1 else ""
            
            # Processamento seguro de campos bancários para garantir formato correto
            # Garantir que bank_code seja uma string de exatamente 3 caracteres
            bank_code_processado = None
            if bank_code is not None:
                # Converter para string, remover espaços e garantir 3 caracteres com leading zeros
                bank_code_processado = str(bank_code).strip().zfill(3)[:3]
                logger.debug(f"bank_code processado: {bank_code_processado!r}, comprimento: {len(bank_code_processado)}")
                
                # Verificar se o processamento resultou em um valor válido
                if not bank_code_processado or bank_code_processado == "000":
                    logger.warning(f"Valor de bank_code inválido após processamento: {bank_code_processado!r}")
            
            # Processamento de outros campos bancários
            bank_branch_processado = str(bank_branch).strip() if bank_branch else None
            bank_branch_digit_processado = str(bank_branch_digit).strip() if bank_branch_digit else None
            account_number_processado = str(account_number).strip() if account_number else None
            account_digit_processado = str(account_digit).strip() if account_digit else None

            payload = {
                "name": {
                    "firstName": primeiro_nome,
                    "lastName": sobrenome
                },
                "document": cpf,
                "address": {
                    "street": street,
                    "streetNumber": street_number,
                    "lineTwo": line_two or "",
                    "neighborhood": neighborhood,
                    "city": city,
                    "state": state,
                    "zipCode": zip_code
                },
                "phone": {
                    "countryCode": phone_country_code or "55",
                    "areaCode": phone_area_code,
                    "number": phone_number
                },
                "birthdate": birthdate.isoformat() if birthdate else None,
                "email": email,
                "mcc": mcc,
                "softDescriptor": soft_descriptor,
                "bankAccount": {
                    "bankCode": bank_code_processado,
                    "bankBranch": bank_branch_processado,
                    "bankBranchCheckDigit": bank_branch_digit_processado,
                    "accountNumber": account_number_processado,
                    "accountCheckDigit": account_digit_processado,
                    "accountType": account_type
                }
            }
            
            # Log do payload antes da validação
            logger.debug(f"Payload preparado: bankAccount.bankCode={payload['bankAccount']['bankCode']!r}")
            
            # Validar dados
            is_valid, validation_errors = validate_receiver_data(payload)
            if not is_valid:
                logger.warning(f"Dados inválidos para BemPaggo: {validation_errors}")
                
                # Se o erro for específico para bankCode e temos um valor válido, devemos corrigir no banco
                codigo_banco_invalido = any(
                    "bankAccount.bankCode" in err or "bankAccount.bankCode" in str(err) 
                    for err in validation_errors
                )
                
                if codigo_banco_invalido and bank_code:
                    logger.info(f"Tentando corrigir bank_code no banco para {user_id}")
                    try:
                        # Atualizar o banco com o valor formatado
                        cursor.execute("""
                            UPDATE users 
                            SET bank_code = %s 
                            WHERE id = %s
                        """, (bank_code_processado, user_id))
                        conn.commit()
                        logger.info(f"bank_code atualizado para {bank_code_processado} no banco de dados")
                        
                        # Tentar novamente a validação após corrigir
                        is_valid, validation_errors = validate_receiver_data(payload)
                        if not is_valid:
                            logger.warning("Validação falhou mesmo após correção no banco")
                    except Exception as db_err:
                        logger.error(f"Erro ao atualizar bank_code no banco: {str(db_err)}")
                
                # Se ainda for inválido, atualizamos o status
                if not is_valid:
                    cursor.execute("""
                        UPDATE users
                        SET bempaggo_integration_status = 'dados_incompletos',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                    return {"status": "error", "message": "Dados incompletos", "errors": validation_errors}
            
            # Definir ambiente
            environment = "sandbox"
            if os.getenv("ENVIRONMENT", "development") == "production":
                environment = "production"
            
            try:
                # Inicializar API
                api_token, seller_id = get_token_and_seller_for_unidade(unidade, environment)
                api = ReceiverAPI(api_token, seller_id, environment)
                
                # Chamar API para atualizar recebedor
                response = api.update_receiver(receiver_id, payload)
                
                # Atualizar status do usuário
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'integrado',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                
                logger.info(f"Atualização na BemPaggo concluída para usuário ID {user_id}, receiver_id {receiver_id}")
                return {
                    "status": "success", 
                    "message": "Recebedor atualizado com sucesso"
                }
                
            except BempaggoValidationError as e:
                # Atualizar status para "erro_validacao"
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'erro_validacao',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                
                logger.error(f"Erro de validação na BemPaggo para usuário {user_id}: {e.errors}")
                return {"status": "error", "message": "Erro de validação", "errors": e.errors}
            
            except Exception as e:
                # Atualizar status para "erro_atualizacao"
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'erro_atualizacao',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                
                logger.error(f"Erro ao atualizar recebedor BemPaggo para usuário {user_id}: {str(e)}")
                return {"status": "error", "message": f"Erro ao atualizar recebedor: {str(e)}"}
    
    except Exception as e:
        logger.error(f"Erro ao processar tarefa de atualização para usuário {user_id}: {str(e)}", exc_info=True)
        return {"status": "error", "message": f"Erro ao processar tarefa: {str(e)}"}


def background_integrate_with_bempaggo(user_id: int):
    """
    Função bridge entre FastAPI BackgroundTasks e o Celery.
    """
    logger.info(f"Iniciando processo de integração com BemPaggo para usuário {user_id} via BackgroundTasks")
    
    try:
        # Dispara a tarefa Celery
        task = create_bempaggo_receiver.delay(user_id)
        logger.info(f"Tarefa Celery de integração com BemPaggo enfileirada para usuário {user_id}. Task ID: {task.id}")
    except Exception as e:
        logger.error(f"ERRO ao enfileirar tarefa Celery: {str(e)}")
        
        # Como fallback, vamos implementar a lógica diretamente aqui em vez de chamar a tarefa
        logger.info(f"Tentando implementar a lógica diretamente...")
        
        try:
            # Implementação direta do conteúdo de create_bempaggo_receiver, sem chamar a função
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Buscar dados completos do usuário
                cursor.execute("""
                    SELECT 
                        id, nome, email, role, unidade, cpf, birthdate, mcc, soft_descriptor,
                        street, street_number, line_two, neighborhood, city, state, zip_code,
                        phone_country_code, phone_area_code, phone_number,
                        bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type
                    FROM users
                    WHERE id = %s
                """, (user_id,))
                
                user_data = cursor.fetchone()
                
                if not user_data:
                    logger.error(f"Usuário ID {user_id} não encontrado")
                    return {"status": "error", "message": "Usuário não encontrado"}
                
                # Extrair campos
                # Processamento de outros campos bancários
                (id, nome, email, role, unidade, cpf, birthdate, mcc, soft_descriptor,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type) = user_data

                # Processamento do nome
                nome_partes = nome.split(" ", 1)
                primeiro_nome = nome_partes[0]
                sobrenome = nome_partes[1] if len(nome_partes) > 1 else ""
                
                # Processamento seguro de campos bancários para garantir formato correto
                # Garantir que bank_code seja uma string de exatamente 3 caracteres
                bank_code_processado = None
                if bank_code is not None:
                    logger.debug(f"PROCESSANDO: bank_code não é None")
                    # Converter para string, remover espaços e garantir 3 caracteres com leading zeros
                    bank_code_str = str(bank_code).strip()
                    logger.debug(f"APÓS STR: bank_code_str={bank_code_str!r}, VAZIO={bank_code_str == ''}")
                    if bank_code_str:  # Verifica se não é string vazia
                        bank_code_processado = bank_code_str.zfill(3)[:3]
                        logger.debug(f"APÓS ZFILL: bank_code_processado={bank_code_processado!r}")
                    else:
                        logger.debug("ALERTA: bank_code_str está vazio após strip()")
                        bank_code_processado = None
                else:
                    logger.debug("ALERTA: bank_code é None do banco de dados")
                    bank_code_processado = None
                
                # Montagem do payload com dados diretos do banco sem processamento desnecessário
                payload = {
                    "name": {
                        "firstName": primeiro_nome,
                        "lastName": sobrenome
                    },
                    "document": cpf,
                    "address": {
                        "street": street,
                        "streetNumber": street_number,
                        "lineTwo": line_two or "",
                        "neighborhood": neighborhood,
                        "city": city,
                        "state": state,
                        "zipCode": zip_code
                    },
                    "phone": {
                        "countryCode": phone_country_code or "55",
                        "areaCode": phone_area_code,
                        "number": phone_number
                    },
                    "birthdate": birthdate.isoformat() if birthdate else None,
                    "email": email,
                    "mcc": mcc,
                    "softDescriptor": soft_descriptor,
                    "bankAccount": {
                        "bankCode": str(bank_code),  # Usar o valor diretamente, apenas convertendo para string
                        "bankBranch": str(bank_branch),
                        "bankBranchCheckDigit": str(bank_branch_digit) if bank_branch_digit else "",
                        "accountNumber": str(account_number),
                        "accountCheckDigit": str(account_digit) if account_digit else "",
                        "accountType": account_type
                    }
                }

                logger.debug(f"Payload preparado: bankAccount.bankCode={payload['bankAccount']['bankCode']!r}")
                
                # Validar dados
                logger.debug(f"ANTES DA VALIDAÇÃO: payload['bankAccount']={payload['bankAccount']!r}")
                is_valid, validation_errors = validate_receiver_data(payload)
                logger.debug(f"APÓS VALIDAÇÃO: is_valid={is_valid}, errors={validation_errors!r}")
                
                if not is_valid:
                    logger.warning(f"Dados inválidos para BemPaggo: {validation_errors}")
                    
                    # Se o erro for específico para bankCode e temos um valor válido, devemos corrigir no banco
                    codigo_banco_invalido = any(
                        "bankAccount.bankCode" in err or "bankAccount.bankCode" in str(err) 
                        for err in validation_errors
                    )
                    
                    if codigo_banco_invalido and bank_code:
                        logger.info(f"Tentando corrigir bank_code no banco para {user_id}")
                        try:
                            # Atualizar o banco com o valor formatado
                            cursor.execute("""
                                UPDATE users 
                                SET bank_code = %s 
                                WHERE id = %s
                            """, (bank_code_processado, user_id))
                            conn.commit()
                            logger.info(f"bank_code atualizado para {bank_code_processado} no banco de dados")
                            
                            # Tentar novamente a validação após corrigir
                            is_valid, validation_errors = validate_receiver_data(payload)
                            if not is_valid:
                                logger.warning("Validação falhou mesmo após correção no banco")
                        except Exception as db_err:
                            logger.error(f"Erro ao atualizar bank_code no banco: {str(db_err)}")
                    
                    # Se ainda for inválido, atualizamos o status
                    if not is_valid:
                        cursor.execute("""
                            UPDATE users
                            SET bempaggo_integration_status = 'dados_incompletos',
                                bempaggo_last_update = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (user_id,))
                        conn.commit()
                        return {"status": "error", "message": "Dados incompletos", "errors": validation_errors}
                
                # Definir ambiente com base no status do sistema
                environment = "sandbox"
                if os.getenv("ENVIRONMENT", "development") == "production":
                    environment = "production"
                
                try:
                    # Inicializar API
                    api_token, seller_id = get_token_and_seller_for_unidade(unidade, environment)
                    api = ReceiverAPI(api_token, seller_id, environment)
                    
                    # Chamar API para criar recebedor
                    response = api.create_receiver(payload)
                    
                    # Log da resposta completa
                    logger.info(f"Resposta da API: {response}")
                    
                    # Extrair ID do recebedor da resposta
                    receiver_id = response.get('id')
                    if not receiver_id:
                        # Se a resposta não tem ID mas o código de status foi 201, 
                        # ainda assim consideramos como sucesso
                        if response.get('status') == 'success_inferred' or response.get('status') == 'success_despite_error':
                            receiver_id = response.get('id', 'generated_id')
                            logger.info(f"Usando ID gerado pelo sistema: {receiver_id}")
                        else:
                            logger.error(f"ID do recebedor não encontrado na resposta: {response}")
                            raise BempaggoAPIError(
                                200, 
                                str(response), 
                                "ID do recebedor não encontrado na resposta"
                            )
                    
                    # Atualizar usuário com ID do recebedor e status
                    cursor.execute("""
                        UPDATE users
                        SET bempaggo_receiver_id = %s,
                            bempaggo_integration_status = 'integrado',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (receiver_id, user_id))
                    conn.commit()
                    
                    logger.info(f"Integração com BemPaggo concluída para usuário ID {user_id}, receiver_id {receiver_id}")
                    return {
                        "status": "success", 
                        "message": "Recebedor criado com sucesso", 
                        "receiver_id": receiver_id
                    }
                    
                except BempaggoValidationError as e:
                    # Atualizar status para "erro_validacao"
                    cursor.execute("""
                        UPDATE users
                        SET bempaggo_integration_status = 'erro_validacao',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                    
                    logger.error(f"Erro de validação na BemPaggo para usuário {user_id}: {e.errors}")
                    return {"status": "error", "message": "Erro de validação", "errors": e.errors}
                    
                except BempaggoConnectionError as e:
                    # Nesse caso, atualizamos o status para erro de conexão
                    cursor.execute("""
                        UPDATE users
                        SET bempaggo_integration_status = 'erro_conexao',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                    
                    logger.error(f"Erro de conexão com BemPaggo para usuário {user_id}: {str(e)}")
                    return {"status": "error", "message": f"Erro de conexão: {str(e)}"}
                    
                except BempaggoConfigurationError as e:
                    # Atualizar status para "erro_configuracao"
                    cursor.execute("""
                        UPDATE users
                        SET bempaggo_integration_status = 'erro_configuracao',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                    
                    logger.error(f"Erro de configuração BemPaggo para usuário {user_id}: {str(e)}")
                    return {"status": "error", "message": str(e)}
                    
                except BempaggoAPIError as e:
                    # Atualizar status para "erro_api"
                    cursor.execute("""
                        UPDATE users
                        SET bempaggo_integration_status = 'erro_api',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                    
                    logger.error(f"Erro da API BemPaggo para usuário {user_id}: {e.detail or e.response_body}")
                    return {
                        "status": "error", 
                        "message": "Erro da API", 
                        "api_error": e.detail or e.response_body
                    }
                    
                except Exception as e:
                    # Atualizar status para "erro_desconhecido"
                    cursor.execute("""
                        UPDATE users
                        SET bempaggo_integration_status = 'erro_desconhecido',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                    
                    logger.error(f"Erro desconhecido para usuário {user_id}: {str(e)}", exc_info=True)
                    return {"status": "error", "message": f"Erro desconhecido: {str(e)}"}
        
        except Exception as inner_e:
            logger.error(f"Falha na implementação direta: {str(inner_e)}", exc_info=True)
            
            # Atualizar o status no banco para indicar o erro
            try:
                with DatabaseConnection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE users
                        SET bempaggo_integration_status = 'erro_enfileiramento',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
            except Exception as db_e:
                logger.error(f"Erro ao atualizar status no banco: {str(db_e)}")