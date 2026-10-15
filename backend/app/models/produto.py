from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from ..database.db import Base

class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    codigo_interno = Column(String(50), unique=True, nullable=False, index=True)
    nome = Column(Text, nullable=False)
    tipo = Column(String(50))
    valor = Column(Numeric(10, 2), nullable=False)
    data_atualizacao_valor = Column(DateTime(timezone=True))
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relacionamento inverso
    itens_odontograma = relationship("OdontogramaItem", back_populates="produto")