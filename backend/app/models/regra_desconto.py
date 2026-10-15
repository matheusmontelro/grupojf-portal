from sqlalchemy import Column, Integer, Numeric, Boolean, DateTime, func, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from ..database.db import Base

class RegraDesconto(Base):
    __tablename__ = "regras_desconto"

    id = Column(Integer, primary_key=True, index=True)
    forma_pagamento_id = Column(Integer, ForeignKey("formas_pagamento.id"), nullable=False, index=True)
    parcela_min = Column(Integer, nullable=False, default=1)
    parcela_max = Column(Integer, nullable=False, default=1)
    percentual_desconto = Column(Numeric(5, 2), nullable=False, default=0.00)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Check constraint para garantir min <= max
    __table_args__ = (CheckConstraint('parcela_min <= parcela_max', name='chk_parcela_min_max'),)

    # Relacionamento
    forma_pagamento = relationship("FormaPagamento", back_populates="regras_desconto")