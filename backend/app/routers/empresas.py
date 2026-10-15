# app/routers/empresas.py

from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
import logging
from datetime import datetime

# Importando nossos modelos Pydantic
from ..models.empresa import (
    EmpresaCreate, EmpresaUpdate, EmpresaRead, BempaggoReintegration
)

# Import das funções de conexão com DB
from ..database.db import DatabaseConnection

# Import do SDK de usuários para integração com BemPaggo
from ..users_sdk.company_utils import integrate_company_with_bempaggo

# Criando logger para o módulo
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/empresas", tags=["empresas"])

@router.get("/", response_model=List[EmpresaRead])
def list_all_empresas(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    unidade: Optional[str] = None
):
    """
    Retorna todas as empresas, com opção de filtro por nome ou CNPJ.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Query base
        query = """
            SELECT 
                id, razao_social, nome_fantasia, cnpj, email, data_abertura, mcc, soft_descriptor,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
                owner_name, owner_cpf, owner_email, owner_birthdate,
                owner_street, owner_street_number, owner_line_two, owner_neighborhood, owner_city, 
                owner_state, owner_zip_code, owner_phone_country_code, owner_phone_area_code, 
                owner_phone_number, unidade, bempaggo_notification_url,
                bempaggo_receiver_id, bempaggo_integration_status, bempaggo_last_update,
                created_at, updated_at, integrate_with_bempaggo
            FROM empresas
        """
        
        # Adicionar filtros
        params = []
        where_clauses = []
        
        # Filtro por unidade se fornecido
        if unidade:
            where_clauses.append("unidade = %s")
            params.append(unidade)
        
        # Filtro de busca para nome, nome fantasia ou CNPJ
        if search:
            where_clauses.append("(razao_social ILIKE %s OR nome_fantasia ILIKE %s OR cnpj LIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        # Adicionar WHERE se necessário
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        # Adicionar ORDER BY, LIMIT e OFFSET
        query += " ORDER BY razao_social LIMIT %s OFFSET %s"
        params.extend([limit, skip])
        
        # Executar a query
        cursor.execute(query, params)
        rows = cursor.fetchall()
    
    # Converter para objetos EmpresaRead
    empresas = []
    for row in rows:
        empresas.append({
            "id": row[0],
            "razao_social": row[1],
            "nome_fantasia": row[2],
            "cnpj": row[3],
            "email": row[4],
            "data_abertura": row[5],
            "mcc": row[6],
            "soft_descriptor": row[7],
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
            "bank_code": row[18],
            "bank_branch": row[19],
            "bank_branch_digit": row[20],
            "account_number": row[21],
            "account_digit": row[22],
            "account_type": row[23],
            "owner_name": row[24],
            "owner_cpf": row[25],
            "owner_email": row[26],
            "owner_birthdate": row[27],
            "owner_street": row[28],
            "owner_street_number": row[29],
            "owner_line_two": row[30],
            "owner_neighborhood": row[31],
            "owner_city": row[32],
            "owner_state": row[33],
            "owner_zip_code": row[34],
            "owner_phone_country_code": row[35],
            "owner_phone_area_code": row[36],
            "owner_phone_number": row[37],
            "unidade": row[38],
            "bempaggo_notification_url": row[39],
            "bempaggo_receiver_id": row[40],
            "bempaggo_integration_status": row[41],
            "bempaggo_last_update": row[42],
            "created_at": row[43],
            "updated_at": row[44],
            "integrate_with_bempaggo": row[45] if len(row) > 45 else False
        })
    
    return empresas

@router.get("/{empresa_id}", response_model=EmpresaRead)
def get_empresa_by_id(empresa_id: int):
    """
    Retorna uma empresa pelo ID.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id, razao_social, nome_fantasia, cnpj, email, data_abertura, mcc, soft_descriptor,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
                owner_name, owner_cpf, owner_email, owner_birthdate,
                owner_street, owner_street_number, owner_line_two, owner_neighborhood, owner_city, 
                owner_state, owner_zip_code, owner_phone_country_code, owner_phone_area_code, 
                owner_phone_number, unidade, bempaggo_notification_url,
                bempaggo_receiver_id, bempaggo_integration_status, bempaggo_last_update,
                created_at, updated_at, integrate_with_bempaggo
            FROM empresas
            WHERE id = %s
        """, (empresa_id,))
        row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    
    return {
        "id": row[0],
        "razao_social": row[1],
        "nome_fantasia": row[2],
        "cnpj": row[3],
        "email": row[4],
        "data_abertura": row[5],
        "mcc": row[6],
        "soft_descriptor": row[7],
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
        "bank_code": row[18],
        "bank_branch": row[19],
        "bank_branch_digit": row[20],
        "account_number": row[21],
        "account_digit": row[22],
        "account_type": row[23],
        "owner_name": row[24],
        "owner_cpf": row[25],
        "owner_email": row[26],
        "owner_birthdate": row[27],
        "owner_street": row[28],
        "owner_street_number": row[29],
        "owner_line_two": row[30],
        "owner_neighborhood": row[31],
        "owner_city": row[32],
        "owner_state": row[33],
        "owner_zip_code": row[34],
        "owner_phone_country_code": row[35],
        "owner_phone_area_code": row[36],
        "owner_phone_number": row[37],
        "unidade": row[38],
        "bempaggo_notification_url": row[39],
        "bempaggo_receiver_id": row[40],
        "bempaggo_integration_status": row[41],
        "bempaggo_last_update": row[42],
        "created_at": row[43],
        "updated_at": row[44],
        "integrate_with_bempaggo": row[45] if len(row) > 45 else False
    }

@router.post("/", response_model=EmpresaRead, status_code=status.HTTP_201_CREATED)
def create_empresa(empresa_data: EmpresaCreate):
    """
    Cria uma nova empresa. Se o campo integrate_with_bempaggo for True,
    também cria um recebedor na BemPaggo.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se CNPJ já existe
        cursor.execute("SELECT id FROM empresas WHERE cnpj = %s", (empresa_data.cnpj,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="CNPJ já cadastrado.")

        # Construir a query dinâmica
        fields = ["razao_social", "cnpj", "unidade", "owner_name", "owner_cpf"]
        values = [empresa_data.razao_social, empresa_data.cnpj, 
                  empresa_data.unidade, empresa_data.owner_name, empresa_data.owner_cpf]
        
        # Adicionar campos opcionais
        if empresa_data.nome_fantasia:
            fields.append("nome_fantasia")
            values.append(empresa_data.nome_fantasia)
        if empresa_data.email:
            fields.append("email")
            values.append(empresa_data.email)
        if empresa_data.data_abertura:
            fields.append("data_abertura")
            values.append(empresa_data.data_abertura)
        if empresa_data.mcc:
            fields.append("mcc")
            values.append(empresa_data.mcc)
        if empresa_data.soft_descriptor:
            fields.append("soft_descriptor")
            values.append(empresa_data.soft_descriptor)
        
        # Endereço da empresa
        if empresa_data.street:
            fields.append("street")
            values.append(empresa_data.street)
        if empresa_data.street_number:
            fields.append("street_number")
            values.append(empresa_data.street_number)
        if empresa_data.line_two:
            fields.append("line_two")
            values.append(empresa_data.line_two)
        if empresa_data.neighborhood:
            fields.append("neighborhood")
            values.append(empresa_data.neighborhood)
        if empresa_data.city:
            fields.append("city")
            values.append(empresa_data.city)
        if empresa_data.state:
            fields.append("state")
            values.append(empresa_data.state)
        if empresa_data.zip_code:
            fields.append("zip_code")
            values.append(empresa_data.zip_code)
        
        # Telefone da empresa
        if empresa_data.phone_country_code:
            fields.append("phone_country_code")
            values.append(empresa_data.phone_country_code)
        if empresa_data.phone_area_code:
            fields.append("phone_area_code")
            values.append(empresa_data.phone_area_code)
        if empresa_data.phone_number:
            fields.append("phone_number")
            values.append(empresa_data.phone_number)
        
        # Dados bancários
        if empresa_data.bank_code:
            fields.append("bank_code")
            values.append(empresa_data.bank_code)
        if empresa_data.bank_branch:
            fields.append("bank_branch")
            values.append(empresa_data.bank_branch)
        if empresa_data.bank_branch_digit:
            fields.append("bank_branch_digit")
            values.append(empresa_data.bank_branch_digit)
        if empresa_data.account_number:
            fields.append("account_number")
            values.append(empresa_data.account_number)
        if empresa_data.account_digit:
            fields.append("account_digit")
            values.append(empresa_data.account_digit)
        if empresa_data.account_type:
            fields.append("account_type")
            values.append(empresa_data.account_type)
        
        # Dados do proprietário
        if empresa_data.owner_email:
            fields.append("owner_email")
            values.append(empresa_data.owner_email)
        if empresa_data.owner_birthdate:
            fields.append("owner_birthdate")
            values.append(empresa_data.owner_birthdate)
        
        # Endereço do proprietário
        if empresa_data.owner_street:
            fields.append("owner_street")
            values.append(empresa_data.owner_street)
        if empresa_data.owner_street_number:
            fields.append("owner_street_number")
            values.append(empresa_data.owner_street_number)
        if empresa_data.owner_line_two:
            fields.append("owner_line_two")
            values.append(empresa_data.owner_line_two)
        if empresa_data.owner_neighborhood:
            fields.append("owner_neighborhood")
            values.append(empresa_data.owner_neighborhood)
        if empresa_data.owner_city:
            fields.append("owner_city")
            values.append(empresa_data.owner_city)
        if empresa_data.owner_state:
            fields.append("owner_state")
            values.append(empresa_data.owner_state)
        if empresa_data.owner_zip_code:
            fields.append("owner_zip_code")
            values.append(empresa_data.owner_zip_code)
        
        # Telefone do proprietário
        if empresa_data.owner_phone_country_code:
            fields.append("owner_phone_country_code")
            values.append(empresa_data.owner_phone_country_code)
        if empresa_data.owner_phone_area_code:
            fields.append("owner_phone_area_code")
            values.append(empresa_data.owner_phone_area_code)
        if empresa_data.owner_phone_number:
            fields.append("owner_phone_number")
            values.append(empresa_data.owner_phone_number)
        
        # Dados de integração com BemPaggo
        if empresa_data.bempaggo_notification_url:
            fields.append("bempaggo_notification_url")
            values.append(empresa_data.bempaggo_notification_url)
        
        # Controle de integração
        fields.append("integrate_with_bempaggo")
        values.append(empresa_data.integrate_with_bempaggo)
        
        # Se vai integrar, adicionar status inicial
        if empresa_data.integrate_with_bempaggo:
            fields.append("bempaggo_integration_status")
            values.append("pendente")
            fields.append("bempaggo_last_update")
            values.append(datetime.now())
        
        # Construir a query
        placeholders = ", ".join(["%s"] * len(values))
        field_names = ", ".join(fields)
        
        query = f"""
            INSERT INTO empresas ({field_names})
            VALUES ({placeholders})
            RETURNING id
        """
        
        # Executar a query
        cursor.execute(query, values)
        empresa_id = cursor.fetchone()[0]
        conn.commit()
        
        # Se vai integrar com BemPaggo, fazer integração direta
        integration_result = None
        if empresa_data.integrate_with_bempaggo:
            integration_result = integrate_company_with_bempaggo(empresa_id)
            logger.info(f"Resultado da integração: {integration_result}")
        
        # Buscar a empresa completa para retornar
        cursor.execute("""
            SELECT 
                id, razao_social, nome_fantasia, cnpj, email, data_abertura, mcc, soft_descriptor,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
                owner_name, owner_cpf, owner_email, owner_birthdate,
                owner_street, owner_street_number, owner_line_two, owner_neighborhood, owner_city, 
                owner_state, owner_zip_code, owner_phone_country_code, owner_phone_area_code, 
                owner_phone_number, unidade, bempaggo_notification_url,
                bempaggo_receiver_id, bempaggo_integration_status, bempaggo_last_update,
                created_at, updated_at, integrate_with_bempaggo
            FROM empresas
            WHERE id = %s
        """, (empresa_id,))
        
        row = cursor.fetchone()
        
    # Retornar empresa criada
    return {
        "id": row[0],
        "razao_social": row[1],
        "nome_fantasia": row[2],
        "cnpj": row[3],
        "email": row[4],
        "data_abertura": row[5],
        "mcc": row[6],
        "soft_descriptor": row[7],
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
        "bank_code": row[18],
        "bank_branch": row[19],
        "bank_branch_digit": row[20],
        "account_number": row[21],
        "account_digit": row[22],
        "account_type": row[23],
        "owner_name": row[24],
        "owner_cpf": row[25],
        "owner_email": row[26],
        "owner_birthdate": row[27],
        "owner_street": row[28],
        "owner_street_number": row[29],
        "owner_line_two": row[30],
        "owner_neighborhood": row[31],
        "owner_city": row[32],
        "owner_state": row[33],
        "owner_zip_code": row[34],
        "owner_phone_country_code": row[35],
        "owner_phone_area_code": row[36],
        "owner_phone_number": row[37],
        "unidade": row[38],
        "bempaggo_notification_url": row[39],
        "bempaggo_receiver_id": row[40],
        "bempaggo_integration_status": row[41],
        "bempaggo_last_update": row[42],
        "created_at": row[43],
        "updated_at": row[44],
        "integrate_with_bempaggo": row[45] if len(row) > 45 else False
    }

@router.put("/{empresa_id}", response_model=EmpresaRead)
def update_empresa(empresa_id: int, empresa_data: EmpresaUpdate):
    """
    Atualiza dados de uma empresa.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se a empresa existe
        cursor.execute("""
            SELECT id, bempaggo_integration_status, bempaggo_receiver_id, cnpj
            FROM empresas 
            WHERE id = %s
        """, (empresa_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Empresa não encontrada.")
        
        _, current_status, current_receiver_id, current_cnpj = row
        
        # Preparar os campos para atualização
        updates = []
        values = []
        updated_fields = []
        
        # Dados básicos
        if empresa_data.razao_social is not None:
            updates.append("razao_social = %s")
            values.append(empresa_data.razao_social)
            updated_fields.append("razao_social")
        
        if empresa_data.nome_fantasia is not None:
            updates.append("nome_fantasia = %s")
            values.append(empresa_data.nome_fantasia)
            updated_fields.append("nome_fantasia")
        
        if empresa_data.cnpj is not None:
            updates.append("cnpj = %s")
            values.append(empresa_data.cnpj)
            updated_fields.append("cnpj")
        
        if empresa_data.email is not None:
            updates.append("email = %s")
            values.append(empresa_data.email)
            updated_fields.append("email")
        
        if empresa_data.data_abertura is not None:
            updates.append("data_abertura = %s")
            values.append(empresa_data.data_abertura)
            updated_fields.append("data_abertura")
        
        if empresa_data.mcc is not None:
            updates.append("mcc = %s")
            values.append(empresa_data.mcc)
            updated_fields.append("mcc")
        
        if empresa_data.soft_descriptor is not None:
            updates.append("soft_descriptor = %s")
            values.append(empresa_data.soft_descriptor)
            updated_fields.append("soft_descriptor")
        
        # Endereço da empresa
        if empresa_data.street is not None:
            updates.append("street = %s")
            values.append(empresa_data.street)
            updated_fields.append("street")
        
        if empresa_data.street_number is not None:
            updates.append("street_number = %s")
            values.append(empresa_data.street_number)
            updated_fields.append("street_number")
        
        if empresa_data.line_two is not None:
            updates.append("line_two = %s")
            values.append(empresa_data.line_two)
            updated_fields.append("line_two")
        
        if empresa_data.neighborhood is not None:
            updates.append("neighborhood = %s")
            values.append(empresa_data.neighborhood)
            updated_fields.append("neighborhood")
        
        if empresa_data.city is not None:
            updates.append("city = %s")
            values.append(empresa_data.city)
            updated_fields.append("city")
        
        if empresa_data.state is not None:
            updates.append("state = %s")
            values.append(empresa_data.state)
            updated_fields.append("state")
        
        if empresa_data.zip_code is not None:
            updates.append("zip_code = %s")
            values.append(empresa_data.zip_code)
            updated_fields.append("zip_code")
        
        # Telefone da empresa
        if empresa_data.phone_country_code is not None:
            updates.append("phone_country_code = %s")
            values.append(empresa_data.phone_country_code)
            updated_fields.append("phone_country_code")
        
        if empresa_data.phone_area_code is not None:
            updates.append("phone_area_code = %s")
            values.append(empresa_data.phone_area_code)
            updated_fields.append("phone_area_code")
        
        if empresa_data.phone_number is not None:
            updates.append("phone_number = %s")
            values.append(empresa_data.phone_number)
            updated_fields.append("phone_number")
        
        # Dados bancários
        if empresa_data.bank_code is not None:
            updates.append("bank_code = %s")
            values.append(empresa_data.bank_code)
            updated_fields.append("bank_code")
        
        if empresa_data.bank_branch is not None:
            updates.append("bank_branch = %s")
            values.append(empresa_data.bank_branch)
            updated_fields.append("bank_branch")
        
        if empresa_data.bank_branch_digit is not None:
            updates.append("bank_branch_digit = %s")
            values.append(empresa_data.bank_branch_digit)
            updated_fields.append("bank_branch_digit")
        
        if empresa_data.account_number is not None:
            updates.append("account_number = %s")
            values.append(empresa_data.account_number)
            updated_fields.append("account_number")
        
        if empresa_data.account_digit is not None:
            updates.append("account_digit = %s")
            values.append(empresa_data.account_digit)
            updated_fields.append("account_digit")
        
        if empresa_data.account_type is not None:
            updates.append("account_type = %s")
            values.append(empresa_data.account_type)
            updated_fields.append("account_type")
        
        # Dados do proprietário
        if empresa_data.owner_name is not None:
            updates.append("owner_name = %s")
            values.append(empresa_data.owner_name)
            updated_fields.append("owner_name")
        
        if empresa_data.owner_cpf is not None:
            updates.append("owner_cpf = %s")
            values.append(empresa_data.owner_cpf)
            updated_fields.append("owner_cpf")
        
        if empresa_data.owner_email is not None:
            updates.append("owner_email = %s")
            values.append(empresa_data.owner_email)
            updated_fields.append("owner_email")
        
        if empresa_data.owner_birthdate is not None:
            updates.append("owner_birthdate = %s")
            values.append(empresa_data.owner_birthdate)
            updated_fields.append("owner_birthdate")
        
        # Endereço do proprietário
        if empresa_data.owner_street is not None:
            updates.append("owner_street = %s")
            values.append(empresa_data.owner_street)
            updated_fields.append("owner_street")
        
        if empresa_data.owner_street_number is not None:
            updates.append("owner_street_number = %s")
            values.append(empresa_data.owner_street_number)
            updated_fields.append("owner_street_number")
        
        if empresa_data.owner_line_two is not None:
            updates.append("owner_line_two = %s")
            values.append(empresa_data.owner_line_two)
            updated_fields.append("owner_line_two")
        
        if empresa_data.owner_neighborhood is not None:
            updates.append("owner_neighborhood = %s")
            values.append(empresa_data.owner_neighborhood)
            updated_fields.append("owner_neighborhood")
        
        if empresa_data.owner_city is not None:
            updates.append("owner_city = %s")
            values.append(empresa_data.owner_city)
            updated_fields.append("owner_city")
        
        if empresa_data.owner_state is not None:
            updates.append("owner_state = %s")
            values.append(empresa_data.owner_state)
            updated_fields.append("owner_state")
        
        if empresa_data.owner_zip_code is not None:
            updates.append("owner_zip_code = %s")
            values.append(empresa_data.owner_zip_code)
            updated_fields.append("owner_zip_code")
        
        # Telefone do proprietário
        if empresa_data.owner_phone_country_code is not None:
            updates.append("owner_phone_country_code = %s")
            values.append(empresa_data.owner_phone_country_code)
            updated_fields.append("owner_phone_country_code")
        
        if empresa_data.owner_phone_area_code is not None:
            updates.append("owner_phone_area_code = %s")
            values.append(empresa_data.owner_phone_area_code)
            updated_fields.append("owner_phone_area_code")
        
        if empresa_data.owner_phone_number is not None:
            updates.append("owner_phone_number = %s")
            values.append(empresa_data.owner_phone_number)
            updated_fields.append("owner_phone_number")
        
        # Dados de integração com BemPaggo
        if empresa_data.bempaggo_notification_url is not None:
            updates.append("bempaggo_notification_url = %s")
            values.append(empresa_data.bempaggo_notification_url)
            updated_fields.append("bempaggo_notification_url")
        
        # Controle de integração
        if empresa_data.integrate_with_bempaggo is not None:
            updates.append("integrate_with_bempaggo = %s")
            values.append(empresa_data.integrate_with_bempaggo)
            updated_fields.append("integrate_with_bempaggo")
            
            # Se estiver mudando para True e não estiver já integrado, atualizar status
            if empresa_data.integrate_with_bempaggo and (current_status is None or current_status in ['erro_integracao', 'dados_incompletos']):
                updates.append("bempaggo_integration_status = %s")
                values.append('pendente')
                updates.append("bempaggo_last_update = %s")
                values.append(datetime.now())
        
        # Se não tiver nada para atualizar, retorna erro
        if not updates:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
        
        # Adicionar atualização do timestamp
        updates.append("updated_at = CURRENT_TIMESTAMP")
        
        # Construir a query de atualização
        update_query = f"""
            UPDATE empresas
            SET {", ".join(updates)}
            WHERE id = %s
            RETURNING 
                id, razao_social, nome_fantasia, cnpj, email, data_abertura, mcc, soft_descriptor,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
                owner_name, owner_cpf, owner_email, owner_birthdate,
                owner_street, owner_street_number, owner_line_two, owner_neighborhood, owner_city, 
                owner_state, owner_zip_code, owner_phone_country_code, owner_phone_area_code, 
                owner_phone_number, unidade, bempaggo_notification_url,
                bempaggo_receiver_id, bempaggo_integration_status, bempaggo_last_update,
                created_at, updated_at, integrate_with_bempaggo
        """
        
        # Adicionar ID no final dos valores para o WHERE
        values.append(empresa_id)
        
        # Executar a query
        cursor.execute(update_query, values)
        updated_row = cursor.fetchone()
        conn.commit()
        
        # Determinar se é necessário verificar/integrar com BemPaggo
        should_integrate = False
        
        # Campos críticos para integração BemPaggo
        bank_fields = ['bank_code', 'bank_branch', 'bank_branch_digit', 'account_number', 'account_digit', 'account_type']
        business_fields = ['razao_social', 'cnpj', 'email', 'data_abertura', 'mcc', 'soft_descriptor']
        owner_fields = ['owner_name', 'owner_cpf', 'owner_email', 'owner_birthdate']
        address_fields = ['street', 'street_number', 'neighborhood', 'city', 'state', 'zip_code']
        phone_fields = ['phone_area_code', 'phone_number']
        
        # Campos relevantes para BemPaggo
        bempaggo_fields = bank_fields + business_fields + owner_fields + address_fields + phone_fields
        
        # Caso 1: CNPJ modificado - sempre verificar
        if 'cnpj' in updated_fields:
            should_integrate = True
            logger.info(f"CNPJ atualizado, verificando integração para empresa {empresa_id}")
        
        # Caso 2: Sem ID de recebedor, com integração ativada
        elif empresa_data.integrate_with_bempaggo is True and not updated_row[40]:  # Sem receiver_id
            should_integrate = True
            logger.info(f"Integração ativada sem receiver_id, tentando integrar empresa {empresa_id}")
        
        # Caso 3: Status de erro + atualizou campos críticos
        elif (
            updated_row[41] in ['erro_integracao', 'dados_incompletos', 'erro_validacao', 'erro_processamento'] 
            and any(field in updated_fields for field in bempaggo_fields)
        ):
            should_integrate = True
            logger.info(f"Status de erro anterior + dados atualizados, tentando reintegrar empresa {empresa_id}")
        
        logger.info(f"[DEBUG] should_integrate={should_integrate}, empresa_id={empresa_id}, campos atualizados={updated_fields}")

        # Executar integração se necessário
        integration_result = None
        if should_integrate:
            logger.info(f"Iniciando integração BemPaggo após atualização para empresa {empresa_id}")
            integration_result = integrate_company_with_bempaggo(empresa_id)
            logger.info(f"Resultado da integração: {integration_result}")
    
    # Retornar a empresa atualizada
    return {
        "id": updated_row[0],
        "razao_social": updated_row[1],
        "nome_fantasia": updated_row[2],
        "cnpj": updated_row[3],
        "email": updated_row[4],
        "data_abertura": updated_row[5],
        "mcc": updated_row[6],
        "soft_descriptor": updated_row[7],
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
        "bank_code": updated_row[18],
        "bank_branch": updated_row[19],
        "bank_branch_digit": updated_row[20],
        "account_number": updated_row[21],
        "account_digit": updated_row[22],
        "account_type": updated_row[23],
        "owner_name": updated_row[24],
        "owner_cpf": updated_row[25],
        "owner_email": updated_row[26],
        "owner_birthdate": updated_row[27],
        "owner_street": updated_row[28],
        "owner_street_number": updated_row[29],
        "owner_line_two": updated_row[30],
        "owner_neighborhood": updated_row[31],
        "owner_city": updated_row[32],
        "owner_state": updated_row[33],
        "owner_zip_code": updated_row[34],
        "owner_phone_country_code": updated_row[35],
        "owner_phone_area_code": updated_row[36],
        "owner_phone_number": updated_row[37],
        "unidade": updated_row[38],
        "bempaggo_notification_url": updated_row[39],
        "bempaggo_receiver_id": updated_row[40],
        "bempaggo_integration_status": updated_row[41],
        "bempaggo_last_update": updated_row[42],
        "created_at": updated_row[43],
        "updated_at": updated_row[44],
        "integrate_with_bempaggo": updated_row[45] if len(updated_row) > 45 else False
    }

@router.post("/{empresa_id}/reintegrate", status_code=status.HTTP_202_ACCEPTED, response_model=BempaggoReintegration)
def reintegrate_company_with_bempaggo(empresa_id: int):
    """
    Tenta integrar novamente uma empresa com a BemPaggo.
    Útil quando houve falha anterior na integração.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM empresas WHERE id = %s", (empresa_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Empresa não encontrada.")
        
        # Atualizar status para pendente
        cursor.execute("""
            UPDATE empresas
            SET bempaggo_integration_status = 'pendente',
                bempaggo_last_update = CURRENT_TIMESTAMP,
                integrate_with_bempaggo = TRUE
            WHERE id = %s
        """, (empresa_id,))
        conn.commit()
    
    # Chamar integração diretamente
    result = integrate_company_with_bempaggo(empresa_id)
    
    return {
        "status": result.get("status", "unknown"),
        "message": result.get("message", ""),
        "receiver_id": str(result.get("receiver_id")) if result.get("receiver_id") is not None else None,
        "integration_status": result.get("integration_status")
    }

@router.delete("/{empresa_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_empresa(empresa_id: int):
    """
    Deleta a empresa pelo ID.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM empresas WHERE id = %s", (empresa_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Empresa não encontrada.")
        
        cursor.execute("DELETE FROM empresas WHERE id = %s", (empresa_id,))
        conn.commit()
    
    return None