from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB # Específico para PostgreSQL
from sqlalchemy.orm import relationship
from ..database.db import Base

class FormaPagamento(Base):
    __tablename__ = "formas_pagamento"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False, index=True)
    # Armazena uma lista de strings de categorias
    categorias = Column(JSONB, nullable=True)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relacionamentos inversos
    regras_desconto = relationship("RegraDesconto", back_populates="forma_pagamento")
    vendas = relationship("Venda", back_populates="forma_pagamento")