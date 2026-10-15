# app/routers/users.py

from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
import logging
import os
from datetime import datetime

# Importando nossos modelos Pydantic
from ..models.users import (
    UserCreate, UserUpdate, UserRead, UserReadWithBempaggo, BempaggoReintegration
)

# Import das funções de conexão com DB
from ..database.db import DatabaseConnection
from ..security.passwords import hash_password

# Import do SDK de usuários para integração com BemPaggo
from ..users_sdk.receiver_api import ReceiverAPI
from ..users_sdk.environment import Environment
from ..users_sdk.exceptions import (
    BempaggoIntegrationError, BempaggoValidationError, 
    BempaggoConnectionError, BempaggoConfigurationError
)

# Criando logger para o módulo
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

# Função para inicializar a API da BemPaggo
def get_receiver_api(unidade: str, environment: str = "sandbox"):
    from ..users_sdk.sdk_utils import get_token_and_seller_for_unidade
    
    try:
        api_token, seller_id = get_token_and_seller_for_unidade(unidade, environment)
        return ReceiverAPI(api_token, seller_id, environment)
    except Exception as e:
        logger.error(f"Erro ao inicializar ReceiverAPI: {str(e)}")
        return None

def integrate_user_with_bempaggo(user_id: int):
    """
    Integra um usuário com a BemPaggo diretamente, verificando primeiro se o CPF já existe.
    """
    logger.info(f"Iniciando integração direta com BemPaggo para usuário {user_id}")
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Buscar dados do usuário
            cursor.execute("""
                SELECT 
                    id, nome, email, role, unidade, cpf, birthdate, mcc, soft_descriptor,
                    street, street_number, line_two, neighborhood, city, state, zip_code,
                    phone_country_code, phone_area_code, phone_number,
                    bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
                    cargo_id
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
             bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
             cargo_id) = user_data
            
            # Verificar se CPF existe (requisito para busca)
            if not cpf:
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'erro_sem_cpf',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                logger.warning(f"CPF não fornecido para integração: usuário {user_id}")
                return {"status": "error", "message": "CPF obrigatório para integração"}
            
            # Definir ambiente
            environment = "sandbox"
            if os.getenv("ENVIRONMENT", "development") == "production":
                environment = "production"
            
            # Inicializar API
            from ..users_sdk.sdk_utils import get_token_and_seller_for_unidade
            api_token, seller_id = get_token_and_seller_for_unidade(unidade, environment)
            api = ReceiverAPI(api_token, seller_id, environment)
            
            # NOVO: Primeiro verificar se já existe um recebedor com este CPF
            existing_receiver = api.get_receiver_by_cpf(cpf)
            
            if existing_receiver and 'id' in existing_receiver:
                # Recebedor já existe! Apenas atualizar o banco com o ID
                receiver_id = existing_receiver['id']
                status_integracao = 'integrado_por_cpf'
                
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_receiver_id = %s,
                        bempaggo_integration_status = %s,
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (receiver_id, status_integracao, user_id))
                conn.commit()
                
                logger.info(f"Recebedor já existente vinculado ao usuário ID {user_id}, receiver_id {receiver_id}")
                return {
                    "status": "success",
                    "message": "Recebedor existente vinculado com sucesso",
                    "receiver_id": receiver_id,
                    "integration_status": status_integracao
                }
            
            # Se não encontrou recebedor existente, verificar campos obrigatórios para criação
            required_fields = [
                cpf, birthdate, mcc, soft_descriptor, bank_code, bank_branch,
                account_number, account_digit, account_type,
                street, street_number, neighborhood, city, state, zip_code,
                phone_area_code, phone_number
            ]
            
            if any(field is None for field in required_fields):
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'dados_incompletos',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                logger.warning(f"Dados incompletos para integração: usuário {user_id}")
                return {"status": "error", "message": "Dados incompletos para integração"}
            
            # Processamento do nome
            nome_partes = nome.split(" ", 1)
            primeiro_nome = nome_partes[0]
            sobrenome = nome_partes[1] if len(nome_partes) > 1 else ""
            
            # Processamento de campos bancários
            bank_code_processado = str(bank_code).strip().zfill(3)[:3] if bank_code else None
            
            # Montagem do payload
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
                    "bankBranch": str(bank_branch),
                    "bankBranchCheckDigit": str(bank_branch_digit) if bank_branch_digit else "",
                    "accountNumber": str(account_number),
                    "accountCheckDigit": str(account_digit) if account_digit else "",
                    "accountType": account_type
                }
            }
            
            # Criar novo recebedor somente se não existir
            try:
                response = api.create_receiver(payload)
                
                # Extrair ID do recebedor
                receiver_id = response.get('id')
                if not receiver_id:
                    cursor.execute("""
                        UPDATE users
                        SET bempaggo_integration_status = 'erro_id_nao_encontrado',
                            bempaggo_last_update = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                    logger.error(f"ID não encontrado na resposta: {response}")
                    return {"status": "error", "message": "ID do recebedor não encontrado"}
                
                # Definir status com base na origem do ID
                status_integracao = 'integrado'
                if response.get('found_by_cpf'):
                    status_integracao = 'integrado_por_cpf'
                elif response.get('status') == 'id_pendente':
                    status_integracao = 'id_pendente'
                    
                # Atualizar usuário com ID do recebedor e status
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_receiver_id = %s,
                        bempaggo_integration_status = %s,
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (receiver_id, status_integracao, user_id))
                conn.commit()
                
                logger.info(f"Integração com BemPaggo concluída para usuário ID {user_id}, receiver_id {receiver_id}")
                return {
                    "status": "success",
                    "message": "Recebedor criado com sucesso",
                    "receiver_id": receiver_id,
                    "integration_status": status_integracao
                }
                
            except BempaggoValidationError as e:
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'erro_validacao',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                
                logger.error(f"Erro de validação: {e.errors}")
                return {"status": "error", "message": "Erro de validação", "errors": e.errors}
                
            except Exception as e:
                cursor.execute("""
                    UPDATE users
                    SET bempaggo_integration_status = 'erro_integracao',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
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
                    UPDATE users
                    SET bempaggo_integration_status = 'erro_processamento',
                        bempaggo_last_update = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
        except Exception as db_err:
            logger.error(f"Erro ao atualizar status no banco: {str(db_err)}")
            
        return {"status": "error", "message": f"Erro ao processar integração: {str(e)}"}


@router.get("/", response_model=List[UserRead])
def list_all_users():
    """
    Retorna todos os usuários.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        # Expandimos a query para incluir os novos campos
        cursor.execute("""
            SELECT 
                id, nome, email, role, unidade, foto_path, created_at, cargo_id,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                cpf, birthdate, bempaggo_receiver_id, bempaggo_integration_status, bempaggo_last_update,
                status_aprovacao, data_solicitacao, usuario_aprovador_id, data_aprovacao, motivo_rejeicao
            FROM users 
            WHERE status_aprovacao = 'aprovado'
            ORDER BY id
        """)
        rows = cursor.fetchall()
    
    # Converter cada row em um dicionário compatível com UserRead
    users = []
    for row in rows:
        users.append({
            "id": row[0],
            "nome": row[1],
            "email": row[2],
            "role": row[3],
            "unidade": row[4],
            "foto_path": row[5],
            "created_at": row[6],
            "cargo_id": row[7],
            "street": row[8],
            "street_number": row[9],
            "line_two": row[10],
            "neighborhood": row[11],
            "city": row[12],
            "state": row[13],
            "zip_code": row[14],
            "phone_country_code": row[15],
            "phone_area_code": row[16],
            "phone_number": row[17],
            "cpf": row[18],
            "birthdate": row[19],
            "bempaggo_receiver_id": row[20],
            "bempaggo_integration_status": row[21],
            "bempaggo_last_update": row[22],
            "status_aprovacao": row[23],
            "data_solicitacao": row[24],
            "usuario_aprovador_id": row[25],
            "data_aprovacao": row[26],
            "motivo_rejeicao": row[27]
        })
    return users


@router.get("/pending", response_model=List[UserRead])
def list_pending_users():
    """
    Retorna todos os usuários pendentes de aprovação.
    Apenas administradores devem acessar esta rota.
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    id, nome, email, role, unidade, foto_path, created_at, cargo_id,
                    street, street_number, line_two, neighborhood, city, state, zip_code,
                    phone_country_code, phone_area_code, phone_number,
                    cpf, birthdate, bempaggo_receiver_id, bempaggo_integration_status, bempaggo_last_update,
                    status_aprovacao, data_solicitacao, usuario_aprovador_id, data_aprovacao, motivo_rejeicao
                FROM users 
                WHERE status_aprovacao = 'pendente_aprovacao'
                ORDER BY data_solicitacao DESC
            """)
            rows = cursor.fetchall()
        
        logger.info(f"Encontrados {len(rows)} usuários pendentes de aprovação")
        
        users = []
        for idx, row in enumerate(rows):
            try:
                user_dict = {
                    "id": row[0],
                    "nome": row[1],
                    "email": row[2],
                    "role": row[3],
                    "unidade": row[4],
                    "foto_path": row[5],
                    "created_at": row[6],
                    "cargo_id": row[7],
                    "street": row[8],
                    "street_number": row[9],
                    "line_two": row[10],
                    "neighborhood": row[11],
                    "city": row[12],
                    "state": row[13],
                    "zip_code": row[14],
                    "phone_country_code": row[15],
                    "phone_area_code": row[16],
                    "phone_number": row[17],
                    "cpf": row[18],
                    "birthdate": row[19],
                    "bempaggo_receiver_id": row[20],
                    "bempaggo_integration_status": row[21],
                    "bempaggo_last_update": row[22],
                    "status_aprovacao": row[23],
                    "data_solicitacao": row[24],
                    "usuario_aprovador_id": row[25],
                    "data_aprovacao": row[26],
                    "motivo_rejeicao": row[27]
                }
                users.append(user_dict)
            except Exception as e:
                logger.error(f"Erro ao processar usuário na linha {idx}: {row}")
                logger.error(f"Erro detalhado: {str(e)}")
                raise
        
        return users
    except Exception as e:
        logger.error(f"Erro ao listar usuários pendentes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar usuários pendentes: {str(e)}"
        )


@router.get("/{user_id}", response_model=UserRead)
def get_user_by_id(user_id: int):
    """
    Retorna um usuário pelo ID.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id, nome, email, role, unidade, foto_path, created_at, cargo_id,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                cpf, birthdate, bempaggo_receiver_id, bempaggo_integration_status, bempaggo_last_update
            FROM users
            WHERE id = %s
        """, (user_id,))
        row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    return {
        "id": row[0],
        "nome": row[1],
        "email": row[2],
        "role": row[3],
        "unidade": row[4],
        "foto_path": row[5],
        "created_at": row[6],
        "cargo_id": row[7],
        "street": row[8],
        "street_number": row[9],
        "line_two": row[10],
        "neighborhood": row[11],
        "city": row[12],
        "state": row[13],
        "zip_code": row[14],
        "phone_country_code": row[15],
        "phone_area_code": row[16],
        "phone_number": row[17],
        "cpf": row[18],
        "birthdate": row[19],
        "bempaggo_receiver_id": row[20],
        "bempaggo_integration_status": row[21],
        "bempaggo_last_update": row[22]
    }


@router.get("/{user_id}/complete", response_model=UserReadWithBempaggo)
def get_user_complete(user_id: int):
    """
    Retorna um usuário com todos os dados, incluindo informações financeiras.
    Esta rota deve ser protegida e acessível apenas por administradores.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id, nome, email, role, unidade, foto_path, created_at, cargo_id,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                cpf, birthdate, 
                bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
                mcc, soft_descriptor, bempaggo_notification_url,
                bempaggo_receiver_id, bempaggo_integration_status, bempaggo_last_update
            FROM users
            WHERE id = %s
        """, (user_id,))
        row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    return {
        "id": row[0],
        "nome": row[1],
        "email": row[2],
        "role": row[3],
        "unidade": row[4],
        "foto_path": row[5],
        "created_at": row[6],
        "cargo_id": row[7],
        "street": row[8],
        "street_number": row[9],
        "line_two": row[10],
        "neighborhood": row[11],
        "city": row[12],
        "state": row[13],
        "zip_code": row[14],
        "phone_country_code": row[15],
        "phone_area_code": row[16],
        "phone_number": row[17],
        "cpf": row[18],
        "birthdate": row[19],
        "bank_code": row[20],
        "bank_branch": row[21],
        "bank_branch_digit": row[22],
        "account_number": row[23],
        "account_digit": row[24],
        "account_type": row[25],
        "mcc": row[26],
        "soft_descriptor": row[27],
        "bempaggo_notification_url": row[28],
        "bempaggo_receiver_id": row[29],
        "bempaggo_integration_status": row[30],
        "bempaggo_last_update": row[31]
    }


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(user_data: UserCreate):
    """
    Cria um novo usuário. Se o campo integrate_with_bempaggo for True e o usuário tiver 
    todos os dados necessários, também cria um recebedor na BemPaggo.
    """
    # Hash de senha
    senha_hash = hash_password(user_data.senha)

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se email já existe
        cursor.execute("SELECT id FROM users WHERE email = %s", (user_data.email,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

        # Construir a query dinâmica com base nos campos fornecidos
        fields = ["nome", "email", "senha", "role", "unidade"]
        values = [user_data.nome, user_data.email, senha_hash, user_data.role, user_data.unidade]

        if user_data.unidade_recuperacao:
            fields.append("unidade_recuperacao")
            values.append(user_data.unidade_recuperacao)
        
        # Adicionar campos de endereço
        if user_data.street:
            fields.append("street")
            values.append(user_data.street)
        if user_data.street_number:
            fields.append("street_number")
            values.append(user_data.street_number)
        if user_data.line_two:
            fields.append("line_two")
            values.append(user_data.line_two)
        if user_data.neighborhood:
            fields.append("neighborhood")
            values.append(user_data.neighborhood)
        if user_data.city:
            fields.append("city")
            values.append(user_data.city)
        if user_data.state:
            fields.append("state")
            values.append(user_data.state)
        if user_data.zip_code:
            fields.append("zip_code")
            values.append(user_data.zip_code)
        
        # Adicionar campos de telefone
        if user_data.phone_country_code:
            fields.append("phone_country_code")
            values.append(user_data.phone_country_code)
        if user_data.phone_area_code:
            fields.append("phone_area_code")
            values.append(user_data.phone_area_code)
        if user_data.phone_number:
            fields.append("phone_number")
            values.append(user_data.phone_number)
        
        # Adicionar campos pessoais
        if user_data.cpf:
            fields.append("cpf")
            values.append(user_data.cpf)
        if user_data.birthdate:
            fields.append("birthdate")
            values.append(user_data.birthdate)
            
        # Adicionar campos bancários
        if user_data.bank_code:
            fields.append("bank_code")
            values.append(user_data.bank_code)
        if user_data.bank_branch:
            fields.append("bank_branch")
            values.append(user_data.bank_branch)
        if user_data.bank_branch_digit:
            fields.append("bank_branch_digit")
            values.append(user_data.bank_branch_digit)
        if user_data.account_number:
            fields.append("account_number")
            values.append(user_data.account_number)
        if user_data.account_digit:
            fields.append("account_digit")
            values.append(user_data.account_digit)
        if user_data.account_type:
            fields.append("account_type")
            values.append(user_data.account_type)

        if user_data.cargo_id:
            fields.append("cargo_id")
            values.append(user_data.cargo_id)
            
        # Adicionar campos BemPaggo
        if user_data.mcc:
            fields.append("mcc")
            values.append(user_data.mcc)
        if user_data.soft_descriptor:
            fields.append("soft_descriptor")
            values.append(user_data.soft_descriptor)
        if user_data.bempaggo_notification_url:
            fields.append("bempaggo_notification_url")
            values.append(user_data.bempaggo_notification_url)
            
        # Adicionar campo de integração
        fields.append("integrate_with_bempaggo")
        values.append(user_data.integrate_with_bempaggo)
        
        # Se vai integrar, adicionar status inicial
        if user_data.integrate_with_bempaggo:
            fields.append("bempaggo_integration_status")
            values.append("pendente")
            fields.append("bempaggo_last_update")
            values.append(datetime.now())
        
        # Construir a query
        placeholders = ", ".join(["%s"] * len(values))
        field_names = ", ".join(fields)
        
        query = f"""
            INSERT INTO users ({field_names})
            VALUES ({placeholders})
            RETURNING id, created_at
        """
        
        # Executar a query
        cursor.execute(query, values)
        new_id, created_at = cursor.fetchone()
        conn.commit()
        
        # Se vai integrar com BemPaggo, fazer integração direta
        integration_result = None
        if user_data.integrate_with_bempaggo:
            integration_result = integrate_user_with_bempaggo(new_id)
            logger.info(f"Resultado da integração: {integration_result}")
            
        # Buscar o usuário completo para retornar
        cursor.execute("""
            SELECT 
                id, nome, email, role, unidade, foto_path, created_at, cargo_id,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                cpf, birthdate, bempaggo_receiver_id, bempaggo_integration_status, bempaggo_last_update
            FROM users
            WHERE id = %s
        """, (new_id,))
        
        row = cursor.fetchone()
    
    # Retornar o usuário completo
    return {
        "id": row[0],
        "nome": row[1],
        "email": row[2],
        "role": row[3],
        "unidade": row[4],
        "foto_path": row[5],
        "created_at": row[6],
        "cargo_id": row[7],
        "street": row[8],
        "street_number": row[9],
        "line_two": row[10],
        "neighborhood": row[11],
        "city": row[12],
        "state": row[13],
        "zip_code": row[14],
        "phone_country_code": row[15],
        "phone_area_code": row[16],
        "phone_number": row[17],
        "cpf": row[18],
        "birthdate": row[19],
        "bempaggo_receiver_id": row[20],
        "bempaggo_integration_status": row[21],
        "bempaggo_last_update": row[22]
    }


@router.put("/{user_id}", response_model=UserRead)
def update_user(user_id: int, user_data: UserUpdate):
    """
    Atualiza dados de um usuário, com otimização da integração BemPaggo.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Primeiro, buscar o usuário para verificar existência e situação atual
        # Adicionando unidade atual na consulta para poder detectar mudanças
        cursor.execute("""
            SELECT id, integrate_with_bempaggo, bempaggo_integration_status, bempaggo_receiver_id, cpf, unidade
            FROM users 
            WHERE id = %s
        """, (user_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        
        _, current_integration, current_status, current_receiver_id, current_cpf, current_unit = row
        
        # Guardar os campos que estão sendo atualizados para decidir se é necessário reintegrar
        updated_fields = []
        
        # Preparar os campos para atualização
        updates = []
        values = []
        
        # Atualizar campos básicos
        if user_data.nome is not None:
            updates.append("nome = %s")
            values.append(user_data.nome)
            updated_fields.append("nome")
        
        if user_data.email is not None:
            updates.append("email = %s")
            values.append(user_data.email)
            updated_fields.append("email")
        
        if user_data.senha is not None:
            updates.append("senha = %s")
            values.append(hash_password(user_data.senha))
            updated_fields.append("senha")
        
        if user_data.role is not None:
            updates.append("role = %s")
            values.append(user_data.role)
            updated_fields.append("role")
        
        if user_data.unidade is not None:
            updates.append("unidade = %s")
            values.append(user_data.unidade)
            updated_fields.append("unidade")

        if user_data.unidade_recuperacao is not None:
            updates.append("unidade_recuperacao = %s")
            values.append(user_data.unidade_recuperacao or None)
            updated_fields.append("unidade_recuperacao")
        
        if user_data.foto_path is not None:
            updates.append("foto_path = %s")
            values.append(user_data.foto_path)
            updated_fields.append("foto_path")
            
        # Atualizar campos de endereço
        if user_data.street is not None:
            updates.append("street = %s")
            values.append(user_data.street)
            updated_fields.append("street")
        
        if user_data.street_number is not None:
            updates.append("street_number = %s")
            values.append(user_data.street_number)
            updated_fields.append("street_number")
        
        if user_data.line_two is not None:
            updates.append("line_two = %s")
            values.append(user_data.line_two)
            updated_fields.append("line_two")
        
        if user_data.neighborhood is not None:
            updates.append("neighborhood = %s")
            values.append(user_data.neighborhood)
            updated_fields.append("neighborhood")
        
        if user_data.city is not None:
            updates.append("city = %s")
            values.append(user_data.city)
            updated_fields.append("city")
        
        if user_data.state is not None:
            updates.append("state = %s")
            values.append(user_data.state)
            updated_fields.append("state")
        
        if user_data.zip_code is not None:
            updates.append("zip_code = %s")
            values.append(user_data.zip_code)
            updated_fields.append("zip_code")
            
        # Atualizar campos de telefone
        if user_data.phone_country_code is not None:
            updates.append("phone_country_code = %s")
            values.append(user_data.phone_country_code)
            updated_fields.append("phone_country_code")
        
        if user_data.phone_area_code is not None:
            updates.append("phone_area_code = %s")
            values.append(user_data.phone_area_code)
            updated_fields.append("phone_area_code")
        
        if user_data.phone_number is not None:
            updates.append("phone_number = %s")
            values.append(user_data.phone_number)
            updated_fields.append("phone_number")

        if any(
            field in updated_fields
            for field in ("phone_country_code", "phone_area_code", "phone_number")
        ):
            updates.append("phone_verified_at = NULL")
            
        # Atualizar campos pessoais
        new_cpf = None
        if user_data.cpf is not None:
            updates.append("cpf = %s")
            values.append(user_data.cpf)
            updated_fields.append("cpf")
            new_cpf = user_data.cpf
        
        if user_data.birthdate is not None:
            updates.append("birthdate = %s")
            values.append(user_data.birthdate)
            updated_fields.append("birthdate")
            
        # Atualizar campos bancários
        if user_data.bank_code is not None:
            updates.append("bank_code = %s")
            values.append(user_data.bank_code)
            updated_fields.append("bank_code")
        
        if user_data.bank_branch is not None:
            updates.append("bank_branch = %s")
            values.append(user_data.bank_branch)
            updated_fields.append("bank_branch")
        
        if user_data.bank_branch_digit is not None:
            updates.append("bank_branch_digit = %s")
            values.append(user_data.bank_branch_digit)
            updated_fields.append("bank_branch_digit")
        
        if user_data.account_number is not None:
            updates.append("account_number = %s")
            values.append(user_data.account_number)
            updated_fields.append("account_number")
        
        if user_data.account_digit is not None:
            updates.append("account_digit = %s")
            values.append(user_data.account_digit)
            updated_fields.append("account_digit")
        
        if user_data.account_type is not None:
            updates.append("account_type = %s")
            values.append(user_data.account_type)
            updated_fields.append("account_type")
            
        # Atualizar campos BemPaggo
        if user_data.mcc is not None:
            updates.append("mcc = %s")
            values.append(user_data.mcc)
            updated_fields.append("mcc")
        
        if user_data.soft_descriptor is not None:
            updates.append("soft_descriptor = %s")
            values.append(user_data.soft_descriptor)
            updated_fields.append("soft_descriptor")

        if user_data.cargo_id is not None:
            updates.append("cargo_id = %s")
            values.append(user_data.cargo_id)
            updated_fields.append("cargo_id")
        
        if user_data.bempaggo_notification_url is not None:
            updates.append("bempaggo_notification_url = %s")
            values.append(user_data.bempaggo_notification_url)
            updated_fields.append("bempaggo_notification_url")
        
        # Atualizar controle de integração
        if user_data.integrate_with_bempaggo is not None:
            updates.append("integrate_with_bempaggo = %s")
            values.append(user_data.integrate_with_bempaggo)
            updated_fields.append("integrate_with_bempaggo")
            
            # Se estiver mudando para True e não estiver já integrado, atualizar status
            if user_data.integrate_with_bempaggo and (not current_integration or current_status in ['erro_integracao', 'dados_incompletos']):
                updates.append("bempaggo_integration_status = %s")
                values.append('pendente')
                updates.append("bempaggo_last_update = %s")
                values.append(datetime.now())
        
        # Se não tiver nada para atualizar, retorna erro
        if not updates:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
        
        # Construir a query de atualização
        update_query = f"""
            UPDATE users
            SET {", ".join(updates)}
            WHERE id = %s
            RETURNING 
                id, nome, email, role, unidade, foto_path, created_at, cargo_id,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                cpf, birthdate, bempaggo_receiver_id, bempaggo_integration_status, bempaggo_last_update
        """
        
        # Adicionar ID no final dos valores para o WHERE
        values.append(user_id)
        
        # Executar a query
        cursor.execute(update_query, values)
        updated_row = cursor.fetchone()
        conn.commit()
        
        # Determinar se é necessário verificar/integrar com BemPaggo
        should_integrate = False
        
        # Listas de campos críticos para integração BemPaggo
        bank_fields = ['bank_code', 'bank_branch', 'bank_branch_digit', 'account_number', 'account_digit', 'account_type']
        personal_fields = ['cpf', 'birthdate', 'mcc', 'soft_descriptor']
        address_fields = ['street', 'street_number', 'neighborhood', 'city', 'state', 'zip_code']
        phone_fields = ['phone_area_code', 'phone_number']
        
        # Campos relevantes para BemPaggo
        bempaggo_fields = bank_fields + personal_fields + address_fields + phone_fields
        
        # NOVO: Detectar mudança de unidade
        changing_unit = 'unidade' in updated_fields and user_data.unidade != current_unit
        in_production = os.getenv("ENVIRONMENT", "development") == "production"
        
        # NOVO: Adicionar este caso específico 
        if changing_unit and in_production:
            should_integrate = True
            logger.info(f"Unidade alterada em ambiente de produção, revalidando integração para usuário {user_id}")
        
        # Caso 1: CPF modificado - sempre verificar
        elif 'cpf' in updated_fields and new_cpf:
            should_integrate = True
            logger.info(f"CPF atualizado, verificando integração para usuário {user_id}")
        
        # Caso 2: Sem ID de recebedor, com integração ativada
        elif user_data.integrate_with_bempaggo is True and not updated_row[20]:  # Sem receiver_id
            should_integrate = True
            logger.info(f"Integração ativada sem receiver_id, tentando integrar usuário {user_id}")
        
        # Caso 3: Status de erro + atualizou campos críticos
        elif (
            updated_row[21] in ['erro_integracao', 'dados_incompletos', 'erro_validacao', 'erro_processamento'] 
            and any(field in updated_fields for field in bempaggo_fields)
        ):
            should_integrate = True
            logger.info(f"Status de erro anterior + dados atualizados, tentando reintegrar usuário {user_id}")
        
        logger.info(f"[DEBUG] should_integrate={should_integrate}, user_id={user_id}, campos atualizados={updated_fields}")

        # Executar integração se necessário
        integration_result = None
        if should_integrate:
            logger.info(f"Iniciando integração BemPaggo após atualização para usuário {user_id}")
            integration_result = integrate_user_with_bempaggo(user_id)
            logger.info(f"Resultado da integração: {integration_result}")
    
    # Retornar o usuário atualizado
    return {
        "id": updated_row[0],
        "nome": updated_row[1],
        "email": updated_row[2],
        "role": updated_row[3],
        "unidade": updated_row[4],
        "foto_path": updated_row[5],
        "created_at": updated_row[6],
        "cargo_id": updated_row[7],
        "street": updated_row[8],
        "street_number": updated_row[9],
        "line_two": updated_row[10],
        "neighborhood": updated_row[11],
        "city": updated_row[12],
        "state": updated_row[13],
        "zip_code": updated_row[14],
        "phone_country_code": updated_row[15],
        "phone_area_code": updated_row[16],
        "phone_number": updated_row[17],
        "cpf": updated_row[18],
        "birthdate": updated_row[19],
        "bempaggo_receiver_id": updated_row[20],
        "bempaggo_integration_status": updated_row[21],
        "bempaggo_last_update": updated_row[22]
    }


@router.post("/{user_id}/approve", status_code=status.HTTP_200_OK)
def approve_user(user_id: int, current_user_id: int):
    """
    Aprova um usuário pendente e inicia a integração com BemPaggo.
    """
    logger.info(f"Aprovando usuário {user_id} pelo admin {current_user_id}")
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se o usuário existe e está pendente
        cursor.execute("""
            SELECT status_aprovacao 
            FROM users 
            WHERE id = %s
        """, (user_id,))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        
        if result[0] != 'pendente_aprovacao':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Usuário não está pendente de aprovação. Status atual: {result[0]}"
            )
        
        # Aprovar o usuário
        cursor.execute("""
            UPDATE users 
            SET status_aprovacao = 'aprovado',
                usuario_aprovador_id = %s,
                data_aprovacao = CURRENT_TIMESTAMP,
                integrate_with_bempaggo = true,
                bempaggo_integration_status = 'pendente'
            WHERE id = %s
        """, (current_user_id, user_id))
        
        conn.commit()
        
        # Iniciar integração com BemPaggo
        integration_result = integrate_user_with_bempaggo(user_id)
        
        return {
            "message": "Usuário aprovado com sucesso",
            "user_id": user_id,
            "integration_result": integration_result
        }


@router.post("/{user_id}/reject", status_code=status.HTTP_200_OK)
def reject_user(user_id: int, current_user_id: int, motivo: Optional[str] = None):
    """
    Rejeita um usuário pendente.
    """
    logger.info(f"Rejeitando usuário {user_id} pelo admin {current_user_id}")
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se o usuário existe e está pendente
        cursor.execute("""
            SELECT status_aprovacao 
            FROM users 
            WHERE id = %s
        """, (user_id,))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        
        if result[0] != 'pendente_aprovacao':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Usuário não está pendente de aprovação. Status atual: {result[0]}"
            )
        
        # Rejeitar o usuário
        cursor.execute("""
            UPDATE users 
            SET status_aprovacao = 'rejeitado',
                usuario_aprovador_id = %s,
                data_aprovacao = CURRENT_TIMESTAMP,
                motivo_rejeicao = %s
            WHERE id = %s
        """, (current_user_id, motivo, user_id))
        
        conn.commit()
        
        return {
            "message": "Usuário rejeitado",
            "user_id": user_id,
            "motivo": motivo
        }


@router.post("/{user_id}/reintegrate", status_code=status.HTTP_202_ACCEPTED)
def reintegrate_with_bempaggo(user_id: int):
    """
    Tenta integrar novamente um usuário com a BemPaggo.
    Útil quando houve falha anterior na integração.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        
        # Atualizar status para pendente
        cursor.execute("""
            UPDATE users
            SET bempaggo_integration_status = 'pendente',
                bempaggo_last_update = CURRENT_TIMESTAMP,
                integrate_with_bempaggo = TRUE
            WHERE id = %s
        """, (user_id,))
        conn.commit()
    
    # Chamar integração diretamente
    result = integrate_user_with_bempaggo(user_id)
    
    return {
        "message": f"Solicitação de reintegração para usuário {user_id} processada.",
        "status": result.get("status", "unknown"),
        "details": result.get("message", "")
    }


@router.delete("/{user_id}")
def delete_user(user_id: int):
    """
    Deleta o usuário pelo ID.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        
        # Exemplo: se quiser evitar deletar o último admin etc., trate aqui
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    
    return {"message": f"Usuário {user_id} excluído com sucesso."}
