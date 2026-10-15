# backend/app/models/pre_venda_entrada.py
from sqlalchemy import Column, Integer, String, Numeric, DateTime, func, JSON, CheckConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from ..database.db import Base

class PreVendaEntrada(Base):
    __tablename__ = "pre_vendas_entradas"
    
    id = Column(Integer, primary_key=True, index=True)
    pre_venda_id = Column(String(100), unique=True, nullable=False)
    tipo_odontograma = Column(String(50), nullable=False)
    paciente_id = Column(Integer, nullable=False, index=True)
    dependente_id = Column(Integer, nullable=True)
    dentista_id = Column(Integer, nullable=False)
    unidade = Column(String(50), nullable=False)
    
    # Valores
    valor_solicitado = Column(Numeric(12, 2), nullable=False)
    valor_pago = Column(Numeric(12, 2), nullable=True)
    
    # Dados do checkout Delta
    checkout_id = Column(String(100), index=True)
    checkout_url = Column(String)
    forma_pagamento_id = Column(Integer)
    
    # Status
    status = Column(
        String(20), 
        default='pendente',
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(
        DateTime(timezone=True), 
        server_default=text("CURRENT_TIMESTAMP + INTERVAL '24 hours'")
    )
    
    # Metadata para dados adicionais
    metadata_json = Column(JSONB, default={})
    
    # Constraint para status válidos
    __table_args__ = (
        CheckConstraint(
            status.in_(['pendente', 'pago', 'cancelado', 'expirado']),
            name='check_pre_vendas_status'
        ),
    )