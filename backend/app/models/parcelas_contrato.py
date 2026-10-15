from sqlalchemy import Column, Integer, String, Text, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
# Removendo a relação com Contrato que está causando o erro
# from sqlalchemy.orm import relationship 
from app.database.db import Base

class ParcelaContrato(Base):
    __tablename__ = "parcelas_contrato"

    parcela_id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.contrato_id", ondelete="CASCADE"), nullable=True)
    numero_parcela = Column(Integer, nullable=False)
    valor_parcela = Column(Numeric(12, 2), nullable=False)
    data_vencimento = Column(Date, nullable=False)
    status = Column(String(20), default="Pendente")
    data_pagamento = Column(DateTime, nullable=True)
    valor_pago = Column(Numeric(12, 2), nullable=True)
    metodo_pagamento = Column(String(50), nullable=True)
    documento_ref = Column(String(70), nullable=True)
    observacao = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Removendo a relação com Contrato que não existe
    # contrato = relationship("Contrato", back_populates="parcelas")

    def __repr__(self):
        return f"<ParcelaContrato(id={self.parcela_id}, contrato_id={self.contrato_id}, parcela={self.numero_parcela})>"