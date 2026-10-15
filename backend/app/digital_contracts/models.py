# backend/app/digital_contracts/models.py
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator

from ..database.db import Base

# =============================================================================
# MODELO SQLALCHEMY
# =============================================================================

class DigitalContract(Base):
    """
    Modelo SQLAlchemy para contratos digitais
    """
    __tablename__ = "digital_contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    
    # Referências ao sistema existente
    paciente_id = Column(Integer, nullable=False, index=True)
    odontograma_id = Column(Integer, nullable=False, index=True)
    dependente_id = Column(Integer, nullable=True, index=True)  # ID do dependente quando o contrato é para um dependente
    valor_total = Column(Numeric(12, 2), nullable=False)
    
    # Status e controle
    status = Column(String(20), nullable=False, default='draft', index=True)
    access_token = Column(String(100), unique=True, nullable=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Dados capturados (JSON com selfie, assinatura, metadados)
    contract_data = Column(JSONB, nullable=True)
    
    # Tracking de timestamps
    sent_at = Column(DateTime, nullable=True)
    selfie_at = Column(DateTime, nullable=True)
    signed_at = Column(DateTime, nullable=True)
    
    # Timestamp de criação/atualização
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<DigitalContract(id={self.id}, uuid={self.uuid}, status={self.status})>"

# =============================================================================
# SCHEMAS PYDANTIC (REQUEST/RESPONSE)
# =============================================================================

class ContractCreateRequest(BaseModel):
    """
    Request para criar novo contrato
    """
    odontograma_id: int = Field(..., description="ID do odontograma")
    dependente_id: Optional[int] = Field(None, description="ID do dependente quando o contrato é para um dependente")
    forma_pagamento: Optional[str] = Field(None, description="Forma de pagamento selecionada")
    dia_vencimento: Optional[int] = Field(None, description="Dia de vencimento das parcelas")
    qtd_parcelas: Optional[int] = Field(None, description="Quantidade de parcelas")
    valor_total: Optional[float] = Field(None, description="Valor total com desconto aplicado")
    
    @validator('odontograma_id')
    def validate_odontograma_id(cls, v):
        if v <= 0:
            raise ValueError('ID do odontograma deve ser positivo')
        return v
    
    @validator('dependente_id')
    def validate_dependente_id(cls, v):
        if v is not None and v <= 0:
            raise ValueError('ID do dependente deve ser positivo')
        return v
    
    @validator('valor_total')
    def validate_valor_total(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Valor total deve ser positivo')
        return v

class ContractCreateResponse(BaseModel):
    """
    Response da criação de contrato
    """
    success: bool
    contract_link: str
    message: str
    contract_id: Optional[int] = None
    expires_at: Optional[datetime] = None

class ContractViewResponse(BaseModel):
    """
    Response para visualização do contrato pelo cliente
    """
    contract_id: int
    paciente_nome: str
    paciente_cpf: str
    endereco: str
    valor_total: float
    status: str
    contract_html: str
    expires_at: Optional[datetime] = None
    dependente_id: Optional[int] = None
    dependente_nome: Optional[str] = None

class SelfieUploadRequest(BaseModel):
    """
    Request para upload de selfie
    """
    selfie: str = Field(..., description="Selfie em base64")
    device_info: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('selfie')
    def validate_selfie(cls, v):
        if not v.startswith('data:image/'):
            raise ValueError('Selfie deve ser uma imagem válida em base64')
        return v

class SelfieUploadResponse(BaseModel):
    """
    Response do upload de selfie
    """
    success: bool
    message: str

class SignatureRequest(BaseModel):
    """
    Request para assinatura do contrato
    """
    signature: str = Field(..., description="Assinatura em base64")
    
    @validator('signature')
    def validate_signature(cls, v):
        if not v.startswith('data:image/'):
            raise ValueError('Assinatura deve ser uma imagem válida em base64')
        return v

class SignatureResponse(BaseModel):
    """
    Response da assinatura
    """
    success: bool
    message: str
    contract_completed: bool = True

class ContractStatusResponse(BaseModel):
    """
    Response com status do contrato
    """
    contract_id: int
    status: str
    paciente_nome: str
    valor_total: float
    created_at: datetime
    sent_at: Optional[datetime] = None
    selfie_at: Optional[datetime] = None
    signed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class ContractListResponse(BaseModel):
    """
    Response para listagem de contratos (admin)
    """
    contracts: list[ContractStatusResponse]
    total: int
    page: int
    per_page: int

# =============================================================================
# MODELOS AUXILIARES
# =============================================================================

class DeviceInfo(BaseModel):
    """
    Informações do dispositivo
    """
    user_agent: Optional[str] = None
    device_type: Optional[str] = None  # mobile, tablet, desktop
    os: Optional[str] = None
    browser: Optional[str] = None
    timestamp: Optional[str] = None

class ContractData(BaseModel):
    """
    Estrutura dos dados salvos no JSONB
    """
    selfie: Optional[str] = None
    selfie_timestamp: Optional[str] = None
    signature: Optional[str] = None
    signature_timestamp: Optional[str] = None
    device_info: Optional[DeviceInfo] = None
    completed: Optional[bool] = False
    
    class Config:
        extra = "allow"  # Permite campos extras

# =============================================================================
# VALIDADORES CUSTOMIZADOS
# =============================================================================

class ContractValidator:
    """
    Classe para validações específicas de contrato
    """
    
    @staticmethod
    def validate_contract_status(status: str) -> bool:
        """Valida se status é válido"""
        valid_statuses = ['draft', 'sent', 'opened', 'selfie_taken', 'signed', 'completed', 'expired', 'cancelled']
        return status in valid_statuses
    
    @staticmethod
    def validate_base64_image(data: str, max_size_mb: int = 5) -> bool:
        """Valida imagem base64"""
        if not data or not data.startswith('data:image/'):
            return False
        
        # Verificar tamanho aproximado
        estimated_size = len(data) * 0.75 / (1024 * 1024)
        return estimated_size <= max_size_mb
    
    @staticmethod
    def can_transition_status(current: str, new: str) -> bool:
        """Valida se transição de status é permitida"""
        transitions = {
            'draft': ['sent', 'cancelled'],
            'sent': ['opened', 'expired', 'cancelled'],
            'opened': ['selfie_taken', 'expired', 'cancelled'],
            'selfie_taken': ['signed', 'expired', 'cancelled'],
            'signed': ['completed'],
            'completed': [],
            'expired': [],
            'cancelled': []
        }
        
        return new in transitions.get(current, [])

# =============================================================================
# EXCEÇÕES CUSTOMIZADAS
# =============================================================================

class ContractError(Exception):
    """Exceção base para erros de contrato"""
    pass

class ContractNotFoundError(ContractError):
    """Contrato não encontrado"""
    pass

class ContractExpiredError(ContractError):
    """Contrato expirado"""
    pass

class InvalidTokenError(ContractError):
    """Token inválido"""
    pass

class InvalidStatusTransitionError(ContractError):
    """Transição de status inválida"""
    pass

class SelfieRequiredError(ContractError):
    """Selfie obrigatória"""
    pass