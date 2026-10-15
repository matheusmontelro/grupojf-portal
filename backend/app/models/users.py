# app/models/users.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, func, ForeignKey
from sqlalchemy.orm import relationship
from ..database.db import Base

# Classes Pydantic auxiliares para BemPaggo
class UserBankAccount(BaseModel):
    bank_code: str = Field(..., min_length=3, max_length=3)
    bank_branch: str = Field(..., min_length=1, max_length=9)
    bank_branch_digit: str = Field(..., min_length=1, max_length=2)
    account_number: str = Field(..., min_length=1, max_length=11)
    account_digit: str = Field(..., min_length=1, max_length=2)
    account_type: str = Field(..., description="CHECKING ou SAVINGS")

    @field_validator('account_type')
    def validate_account_type(cls, v):
        if v not in ['CHECKING', 'SAVINGS']:
            raise ValueError('account_type deve ser CHECKING ou SAVINGS')
        return v

class UserAddress(BaseModel):
    street: str = Field(..., min_length=1, max_length=150)
    street_number: str = Field(..., min_length=1, max_length=20)
    line_two: Optional[str] = Field(None, max_length=200)
    neighborhood: str = Field(..., min_length=1, max_length=150)
    city: str = Field(..., min_length=1, max_length=200)
    state: str = Field(..., min_length=2, max_length=2)
    zip_code: str = Field(..., min_length=8, max_length=9)

class UserPhone(BaseModel):
    country_code: str = Field("55")
    area_code: str = Field(...)
    number: str = Field(...)

class BempaggoInfo(BaseModel):
    cpf: str = Field(..., min_length=11, max_length=11)
    birthdate: date
    mcc: int  # Merchant Category Code
    soft_descriptor: str = Field(..., description="Nome que aparece na fatura")
    bank_account: UserBankAccount
    notification_url: Optional[str] = None

# Campos básicos comuns (nome, email, role, etc.)
class UserBase(BaseModel):
    nome: str
    email: EmailStr
    role: str
    unidade: str
    cargo_id: Optional[int] = None
    unidade_recuperacao: Optional[str] = None
    # Integracao Asaas (subconta PF / wallet PJ). A apiKey cifrada
    # (asaas_account_api_key_enc) nunca e exposta em leituras.
    asaas_wallet_id: Optional[str] = None
    asaas_account_id: Optional[str] = None
    asaas_integration_status: Optional[str] = None

# Para criar um usuário, precisamos também de 'senha'
class UserCreate(UserBase):
    senha: str = Field(..., min_length=15, max_length=128)
    # Campos de endereço
    street: Optional[str] = None
    street_number: Optional[str] = None
    line_two: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    
    # Campos de telefone
    phone_country_code: Optional[str] = "55"  # Default para Brasil
    phone_area_code: Optional[str] = None
    phone_number: Optional[str] = None
    
    # Campos pessoais adicionais
    cpf: Optional[str] = None
    birthdate: Optional[date] = None
    
    # Campos bancários
    bank_code: Optional[str] = None
    bank_branch: Optional[str] = None
    bank_branch_digit: Optional[str] = None
    account_number: Optional[str] = None
    account_digit: Optional[str] = None
    account_type: Optional[str] = "CHECKING"  # Default para conta corrente
    
    # Campos específicos BemPaggo
    mcc: Optional[int] = None
    soft_descriptor: Optional[str] = None
    bempaggo_notification_url: Optional[str] = None
    
    # Campo para indicar se deve integrar com BemPaggo
    integrate_with_bempaggo: bool = False

# Para atualizar, todos os campos são opcionais
class UserUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    senha: Optional[str] = Field(None, min_length=15, max_length=128)
    role: Optional[str] = None
    unidade: Optional[str] = None
    unidade_recuperacao: Optional[str] = None
    foto_path: Optional[str] = None

    # Campos de endereço
    street: Optional[str] = None
    street_number: Optional[str] = None
    line_two: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    
    # Campos de telefone
    phone_country_code: Optional[str] = None
    phone_area_code: Optional[str] = None
    phone_number: Optional[str] = None
    
    # Campos pessoais adicionais
    cpf: Optional[str] = None
    birthdate: Optional[date] = None
    cargo_id: Optional[int] = None
    
    # Campos bancários
    bank_code: Optional[str] = None
    bank_branch: Optional[str] = None
    bank_branch_digit: Optional[str] = None
    account_number: Optional[str] = None
    account_digit: Optional[str] = None
    account_type: Optional[str] = None
    
    # Campos específicos BemPaggo
    mcc: Optional[int] = None
    soft_descriptor: Optional[str] = None
    bempaggo_notification_url: Optional[str] = None
    bempaggo_receiver_id: Optional[str] = None
    bempaggo_integration_status: Optional[str] = None
    
    # Campo para indicar se deve integrar com BemPaggo
    integrate_with_bempaggo: Optional[bool] = None

# Modelo para tentar reintegração com BemPaggo
class BempaggoReintegration(BaseModel):
    user_id: int

# Modelo de leitura (retorno de GET)
class UserRead(UserBase):
    id: int
    created_at: datetime
    foto_path: Optional[str] = None
    
    # Dados de endereço
    street: Optional[str] = None
    street_number: Optional[str] = None
    line_two: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    
    # Dados de telefone
    phone_country_code: Optional[str] = None
    phone_area_code: Optional[str] = None
    phone_number: Optional[str] = None
    phone_verified_at: Optional[datetime] = None
    
    # Dados pessoais adicionais
    cpf: Optional[str] = None
    birthdate: Optional[date] = None
    
    # Dados BemPaggo
    bempaggo_receiver_id: Optional[str] = None
    bempaggo_integration_status: Optional[str] = None
    bempaggo_last_update: Optional[datetime] = None

    # Dados Asaas (apiKey cifrada nunca exposta em leituras)
    asaas_wallet_id: Optional[str] = None
    asaas_account_id: Optional[str] = None
    asaas_integration_status: Optional[str] = None
    asaas_account_updated_at: Optional[datetime] = None
    
    # Dados de aprovação
    status_aprovacao: Optional[str] = None
    data_solicitacao: Optional[datetime] = None
    usuario_aprovador_id: Optional[int] = None
    data_aprovacao: Optional[datetime] = None
    motivo_rejeicao: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            date: lambda v: v.isoformat() if v else None
        }

# Modelo para dados completos de BemPaggo
class UserReadWithBempaggo(UserRead):
    # Campos bancários (visível apenas para administradores)
    bank_code: Optional[str] = None
    bank_branch: Optional[str] = None
    bank_branch_digit: Optional[str] = None
    account_number: Optional[str] = None
    account_digit: Optional[str] = None
    account_type: Optional[str] = None
    
    # Campos específicos BemPaggo
    mcc: Optional[int] = None
    soft_descriptor: Optional[str] = None
    bempaggo_notification_url: Optional[str] = None

# Modelo SQLAlchemy para o banco de dados
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    senha = Column(String, nullable=False)
    role = Column(String, nullable=False)
    unidade = Column(String, nullable=False)
    foto_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Campos de endereço
    street = Column(String(150), nullable=True)
    street_number = Column(String(20), nullable=True)
    line_two = Column(String(200), nullable=True)
    neighborhood = Column(String(150), nullable=True)
    city = Column(String(200), nullable=True)
    state = Column(String(2), nullable=True)
    zip_code = Column(String(9), nullable=True)
    
    # Campos de telefone
    phone_country_code = Column(String(5), nullable=True)
    phone_area_code = Column(String(5), nullable=True)
    phone_number = Column(String(20), nullable=True)
    phone_verified_at = Column(DateTime(timezone=True), nullable=True)
    unidade_recuperacao = Column(String(100), nullable=True)
    auth_version = Column(Integer, nullable=False, default=0)
    
    # Campos pessoais adicionais
    cpf = Column(String(11), nullable=True)
    birthdate = Column(Date, nullable=True)
    
    # Campos bancários
    bank_code = Column(String(3), nullable=True)
    bank_branch = Column(String(9), nullable=True)
    bank_branch_digit = Column(String(2), nullable=True)
    account_number = Column(String(11), nullable=True)
    account_digit = Column(String(2), nullable=True)
    account_type = Column(String(20), nullable=True)
    
    # Campos específicos BemPaggo
    mcc = Column(Integer, nullable=True)
    soft_descriptor = Column(String(100), nullable=True)
    bempaggo_receiver_id = Column(String(50), nullable=True)
    bempaggo_integration_status = Column(String(50), nullable=True)
    bempaggo_notification_url = Column(String(255), nullable=True)
    bempaggo_last_update = Column(DateTime, nullable=True)

    # Campos Asaas (splits PF/empresas). asaas_account_api_key_enc guarda a
    # apiKey de subconta CIFRADA via Fernet (ASAAS_ACCOUNT_API_KEY_SECRET);
    # nunca logar nem expor em leituras.
    asaas_wallet_id = Column(String(64), nullable=True)
    asaas_account_id = Column(String(64), nullable=True)
    asaas_integration_status = Column(String(50), nullable=True)
    asaas_account_api_key_enc = Column("asaas_account_api_key_enc", String, nullable=True)
    asaas_account_updated_at = Column(DateTime(timezone=True), nullable=True)

    cargo_id = Column(Integer, ForeignKey("cargos.id"), nullable=True)
    # adicionar o relacionamento com a tabela cargos
    cargo = relationship("Cargo")
    
    # Flag para indicar se deveria ser integrado com BemPaggo
    integrate_with_bempaggo = Column(Boolean, default=False)
    
    # Campos de aprovação
    status_aprovacao = Column(String(20), default='aprovado')
    data_solicitacao = Column(DateTime, nullable=True)
    usuario_aprovador_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    data_aprovacao = Column(DateTime, nullable=True)
    motivo_rejeicao = Column(String, nullable=True)
    
    # Relacionamentos com SolicitacaoDesconto
    solicitacoes_criadas = relationship(
        "SolicitacaoDesconto",
        foreign_keys="SolicitacaoDesconto.usuario_solicitante_id",
        back_populates="usuario_solicitante"
    )
    solicitacoes_aprovadas = relationship(
        "SolicitacaoDesconto",
        foreign_keys="SolicitacaoDesconto.usuario_aprovador_id",
        back_populates="usuario_aprovador"
    )
    
    # Relacionamento com Dentista (perfil profissional)
    dentista_profissional = relationship("Dentista", back_populates="usuario_sistema")
    
    # Método helper para verificar se o usuário tem todos os dados
    # necessários para integração com BemPaggo
    def has_complete_bempaggo_data(self):
        required_fields = [
            self.cpf, self.birthdate, self.mcc, self.soft_descriptor,
            self.bank_code, self.bank_branch, self.bank_branch_digit,
            self.account_number, self.account_digit, self.account_type,
            self.street, self.street_number, self.neighborhood,
            self.city, self.state, self.zip_code,
            self.phone_country_code, self.phone_area_code, self.phone_number,
            self.email
        ]
        return all(field is not None for field in required_fields)
    
    # Método para extrair os dados para envio à API BemPaggo
    def get_bempaggo_payload(self):
        if not self.has_complete_bempaggo_data():
            return None
            
        return {
            "name": self.nome,
            "document": self.cpf,
            "address": {
                "street": self.street,
                "streetNumber": self.street_number,
                "lineTwo": self.line_two or "",
                "neighborhood": self.neighborhood,
                "city": self.city,
                "state": self.state,
                "zipCode": self.zip_code
            },
            "phone": {
                "countryCode": self.phone_country_code,
                "areaCode": self.phone_area_code,
                "number": self.phone_number
            },
            "birthdate": self.birthdate.isoformat() if self.birthdate else None,
            "email": self.email,
            "mcc": self.mcc,
            "softDescriptor": self.soft_descriptor,
            "bankAccount": {
                "codeBank": self.bank_code,
                "bankBranch": self.bank_branch,
                "bankBranchCheckDigit": self.bank_branch_digit,
                "accountNumber": self.account_number,
                "accountCheckDigit": self.account_digit,
                "accountType": self.account_type
            },
            "notificationUrl": self.bempaggo_notification_url
        }
