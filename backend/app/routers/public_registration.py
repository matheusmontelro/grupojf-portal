# app/routers/public_registration.py

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import Optional
import logging
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator
import re

from ..database.db import DatabaseConnection
from ..routers.users import integrate_user_with_bempaggo
from ..security.passwords import hash_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["public"])

class PublicUserRegistration(BaseModel):
    # Dados básicos
    nome: str = Field(..., min_length=3, description="Nome completo")
    email: EmailStr
    senha: str = Field(..., min_length=15, max_length=128)
    cpf: str = Field(..., pattern="^[0-9]{11}$", description="CPF sem pontos ou traços")
    birthdate: str = Field(..., description="Data de nascimento no formato YYYY-MM-DD")
    
    # Unidade e cargo
    unidade: str = Field(..., description="Unidade de trabalho")
    cargo_nome: str = Field(default="Dentista", description="Nome do cargo")
    
    # Telefone
    phone_area_code: str = Field(..., pattern="^[0-9]{2}$", description="DDD")
    phone_number: str = Field(..., pattern="^[0-9]{8,9}$", description="Número do telefone")
    
    # Endereço
    zip_code: str = Field(..., pattern="^[0-9]{8}$", description="CEP sem traços")
    street: str = Field(..., min_length=3)
    street_number: str = Field(..., min_length=1, max_length=20)
    line_two: Optional[str] = Field(None, description="Complemento")
    neighborhood: str = Field(..., min_length=2)
    city: str = Field(..., min_length=2)
    state: str = Field(..., pattern="^[A-Z]{2}$", description="UF em maiúsculas")
    
    # Dados bancários
    bank_code: str = Field(..., pattern="^[0-9]{3}$", description="Código do banco")
    bank_branch: str = Field(..., pattern="^[0-9]{1,4}$", description="Agência")
    bank_branch_digit: str = Field(..., pattern="^[0-9]{1}$", description="Dígito da agência")
    account_number: str = Field(..., pattern="^[0-9]{1,11}$", description="Número da conta")
    account_digit: str = Field(..., pattern="^[0-9X]{1}$", description="Dígito da conta")
    account_type: str = Field(..., description="CHECKING ou SAVINGS")
    
    # Soft descriptor para BemPaggo
    soft_descriptor: str = Field(..., 
        pattern="^[A-Z0-9 ]{1,22}$", 
        description="Nome que aparecerá na fatura (apenas letras maiúsculas, números e espaços)"
    )
    
    @validator('account_type')
    def validate_account_type(cls, v):
        if v not in ['CHECKING', 'SAVINGS']:
            raise ValueError('Tipo de conta deve ser CHECKING ou SAVINGS')
        return v
    
    @validator('cpf')
    def validate_cpf(cls, v):
        # Remove caracteres não numéricos
        cpf = re.sub(r'\D', '', v)
        
        # Verifica se tem 11 dígitos
        if len(cpf) != 11:
            raise ValueError('CPF deve ter 11 dígitos')
        
        # Verifica se todos os dígitos são iguais
        if cpf == cpf[0] * len(cpf):
            raise ValueError('CPF inválido')
        
        # Validação dos dígitos verificadores
        for i in range(9, 11):
            value = sum((int(cpf[num]) * ((i+1) - num) for num in range(0, i)))
            digit = ((value * 10) % 11) % 10
            if digit != int(cpf[i]):
                raise ValueError('CPF inválido')
        
        return cpf
    
    @validator('soft_descriptor')
    def validate_soft_descriptor(cls, v):
        # Remove espaços extras
        v = ' '.join(v.split())
        
        # Verifica comprimento
        if len(v) > 22:
            raise ValueError('Nome na fatura deve ter no máximo 22 caracteres')
        
        return v


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def public_user_registration(
    registration_data: PublicUserRegistration,
    background_tasks: BackgroundTasks
):
    """
    Endpoint público para autocadastro de funcionários.
    Os usuários criados por esta rota precisam de aprovação do administrador.
    """
    
    logger.info(f"Iniciando autocadastro para: {registration_data.email}")
    
    # Hash da senha
    senha_hash = hash_password(registration_data.senha)
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se email já existe
        cursor.execute("SELECT id FROM users WHERE email = %s", (registration_data.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este e-mail já está cadastrado no sistema"
            )
        
        # Verificar se CPF já existe
        cursor.execute("SELECT id, nome FROM users WHERE cpf = %s", (registration_data.cpf,))
        existing_cpf = cursor.fetchone()
        if existing_cpf:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Este CPF já está cadastrado para o usuário: {existing_cpf[1]}"
            )
        
        # Buscar o cargo_id baseado no nome do cargo
        cursor.execute(
            "SELECT id FROM cargos WHERE nome = %s AND ativo = true",
            (registration_data.cargo_nome,)
        )
        cargo_result = cursor.fetchone()
        
        if not cargo_result:
            # Se não encontrar o cargo, usar Dentista como padrão
            cursor.execute(
                "SELECT id FROM cargos WHERE nome = 'Dentista' AND ativo = true"
            )
            cargo_result = cursor.fetchone()
        
        cargo_id = cargo_result[0] if cargo_result else None
        
        # Inserir o usuário com status pendente de aprovação
        insert_query = """
            INSERT INTO users (
                nome, email, senha, role, unidade, cargo_id,
                cpf, birthdate,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                phone_country_code, phone_area_code, phone_number,
                bank_code, bank_branch, bank_branch_digit, account_number, account_digit, account_type,
                mcc, soft_descriptor,
                integrate_with_bempaggo, bempaggo_integration_status,
                status_aprovacao, data_solicitacao,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                CURRENT_TIMESTAMP
            ) RETURNING id
        """
        
        cursor.execute(insert_query, (
            registration_data.nome,
            registration_data.email,
            senha_hash,
            registration_data.cargo_nome,
            registration_data.unidade,
            cargo_id,
            registration_data.cpf,
            registration_data.birthdate,
            registration_data.street,
            registration_data.street_number,
            registration_data.line_two,
            registration_data.neighborhood,
            registration_data.city,
            registration_data.state,
            registration_data.zip_code,
            '55',  # phone_country_code (Brasil)
            registration_data.phone_area_code,
            registration_data.phone_number,
            registration_data.bank_code,
            registration_data.bank_branch,
            registration_data.bank_branch_digit,
            registration_data.account_number,
            registration_data.account_digit,
            registration_data.account_type,
            8021,  # MCC para dentistas
            registration_data.soft_descriptor,
            False,  # integrate_with_bempaggo (será feito após aprovação)
            'aguardando_aprovacao',  # bempaggo_integration_status
            'pendente_aprovacao',  # status_aprovacao
            datetime.now()  # data_solicitacao
        ))
        
        new_user_id = cursor.fetchone()[0]
        conn.commit()
        
        logger.info(f"Usuário criado com ID: {new_user_id}, aguardando aprovação")
        
        return {
            "message": "Cadastro realizado com sucesso! Aguarde a aprovação do administrador.",
            "user_id": new_user_id,
            "email": registration_data.email,
            "status": "pendente_aprovacao"
        }


@router.get("/registration-info")
async def get_registration_info():
    """
    Retorna informações necessárias para o formulário de cadastro público.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Buscar unidades ativas
        unidades = [
            "Nova Iguaçu 1",
            "São João de Meriti", 
            "Vilar dos Teles",
            "Belford Roxo"
        ]
        
        # Buscar cargos ativos (exceto Master)
        cursor.execute("""
            SELECT nome FROM cargos 
            WHERE ativo = true 
            AND nome NOT IN ('Master', 'MASTER', 'master')
            ORDER BY nome
        """)
        cargos = [row[0] for row in cursor.fetchall()]
        
        # Lista de bancos comuns
        bancos = [
            {"code": "001", "name": "Banco do Brasil"},
            {"code": "033", "name": "Santander"},
            {"code": "104", "name": "Caixa Econômica Federal"},
            {"code": "237", "name": "Bradesco"},
            {"code": "341", "name": "Itaú"},
            {"code": "422", "name": "Safra"},
            {"code": "208", "name": "BTG Pactual"},
            {"code": "655", "name": "Votorantim"},
            {"code": "389", "name": "Mercantil do Brasil"},
            {"code": "070", "name": "BRB"},
            {"code": "260", "name": "Nubank"},
            {"code": "077", "name": "Inter"},
            {"code": "336", "name": "C6 Bank"},
            {"code": "290", "name": "PagBank"},
            {"code": "212", "name": "Original"},
            {"code": "323", "name": "Mercado Pago"},
            {"code": "197", "name": "Stone"},
            {"code": "335", "name": "Digio"}
        ]
        
        return {
            "unidades": unidades,
            "cargos": cargos if cargos else ["Dentista"],
            "bancos": bancos,
            "account_types": [
                {"value": "CHECKING", "label": "Conta Corrente"},
                {"value": "SAVINGS", "label": "Conta Poupança"}
            ]
        }
