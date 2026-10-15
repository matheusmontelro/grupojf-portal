# app/models/empresas.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.db import Base

class EmpresaBase(BaseModel):
    razao_social: str
    nome_fantasia: Optional[str] = None
    cnpj: str
    email: Optional[str] = None
    data_abertura: Optional[date] = None
    mcc: Optional[int] = None
    soft_descriptor: Optional[str] = None
    
    # Informações de endereço
    street: Optional[str] = None
    street_number: Optional[str] = None
    line_two: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    
    # Informações de telefone
    phone_country_code: Optional[str] = "55"
    phone_area_code: Optional[str] = None
    phone_number: Optional[str] = None
    
    # Informações bancárias
    bank_code: Optional[str] = None
    bank_branch: Optional[str] = None
    bank_branch_digit: Optional[str] = None
    account_number: Optional[str] = None
    account_digit: Optional[str] = None
    account_type: Optional[str] = None
    unidade: str
    # Informações do proprietário.
    owner_name: str
    owner_cpf: str
    owner_email: Optional[str] = None
    owner_birthdate: Optional[date] = None
    
    owner_street: Optional[str] = None
    owner_street_number: Optional[str] = None
    owner_line_two: Optional[str] = None
    owner_neighborhood: Optional[str] = None
    owner_city: Optional[str] = None
    owner_state: Optional[str] = None
    owner_zip_code: Optional[str] = None
    
    owner_phone_country_code: Optional[str] = "55"
    owner_phone_area_code: Optional[str] = None
    owner_phone_number: Optional[str] = None
    
    # Dados de integração com BemPaggo
    bempaggo_notification_url: Optional[str] = None
    integrate_with_bempaggo: Optional[bool] = False

class EmpresaCreate(EmpresaBase):
    pass

class EmpresaUpdate(BaseModel):
    razao_social: Optional[str] = None
    nome_fantasia: Optional[str] = None
    cnpj: Optional[str] = None
    email: Optional[str] = None
    data_abertura: Optional[date] = None
    mcc: Optional[int] = None
    soft_descriptor: Optional[str] = None
    
    # Informações de endereço
    street: Optional[str] = None
    street_number: Optional[str] = None
    line_two: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    
    # Informações de telefone
    phone_country_code: Optional[str] = None
    phone_area_code: Optional[str] = None
    phone_number: Optional[str] = None
    
    # Informações bancárias
    bank_code: Optional[str] = None
    bank_branch: Optional[str] = None
    bank_branch_digit: Optional[str] = None
    account_number: Optional[str] = None
    account_digit: Optional[str] = None
    account_type: Optional[str] = None
    
    # Informações do proprietário
    owner_name: Optional[str] = None
    owner_cpf: Optional[str] = None
    owner_email: Optional[str] = None
    owner_birthdate: Optional[date] = None
    
    owner_street: Optional[str] = None
    owner_street_number: Optional[str] = None
    owner_line_two: Optional[str] = None
    owner_neighborhood: Optional[str] = None
    owner_city: Optional[str] = None
    owner_state: Optional[str] = None
    owner_zip_code: Optional[str] = None
    
    owner_phone_country_code: Optional[str] = None
    owner_phone_area_code: Optional[str] = None
    owner_phone_number: Optional[str] = None
    
    # Dados de integração com BemPaggo
    bempaggo_notification_url: Optional[str] = None
    integrate_with_bempaggo: Optional[bool] = None

class EmpresaRead(EmpresaBase):
    id: int
    unidade: str
    bempaggo_receiver_id: Optional[str] = None
    bempaggo_integration_status: Optional[str] = None
    bempaggo_last_update: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class BempaggoReintegration(BaseModel):
    status: str
    message: str
    receiver_id: Optional[str] = None
    integration_status: Optional[str] = None

class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    razao_social = Column(Text, nullable=False)
    nome_fantasia = Column(Text)
    cnpj = Column(Text, nullable=False, unique=True)
    email = Column(Text)
    data_abertura = Column(Date)
    mcc = Column(Integer)
    soft_descriptor = Column(Text)
    street = Column(Text)
    street_number = Column(Text)
    line_two = Column(Text)
    neighborhood = Column(Text)
    city = Column(Text)
    state = Column(Text)
    zip_code = Column(Text)
    phone_country_code = Column(Text)
    phone_area_code = Column(Text)
    phone_number = Column(Text)
    bank_code = Column(Text)
    bank_branch = Column(Text)
    bank_branch_digit = Column(Text)
    account_number = Column(Text)
    account_digit = Column(Text)
    account_type = Column(Text)
    owner_name = Column(Text, nullable=False)
    owner_cpf = Column(Text, nullable=False)
    owner_email = Column(Text)
    owner_birthdate = Column(Date)
    owner_street = Column(Text)
    owner_street_number = Column(Text)
    owner_line_two = Column(Text)
    owner_neighborhood = Column(Text)
    owner_city = Column(Text)
    owner_state = Column(Text)
    owner_zip_code = Column(Text)
    owner_phone_country_code = Column(Text)
    owner_phone_area_code = Column(Text)
    owner_phone_number = Column(Text)
    bempaggo_receiver_id = Column(Text)
    bempaggo_integration_status = Column(Text)
    bempaggo_last_update = Column(DateTime)
    bempaggo_notification_url = Column(Text)
    unidade = Column(Text, nullable=False)
    integrate_with_bempaggo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relacionamentos
    regras_split = relationship("EmpresaRegrasSplit", back_populates="empresa")
    participacoes_split = relationship("ParticipacaoEmpresaSplit", back_populates="empresa")