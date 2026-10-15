from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.db import Base

class CarnePagamento(Base):
    __tablename__ = "carne_pagamento"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, nullable=False)
    recurring_invoice_id = Column(Text)
    documento_cliente = Column(Text, nullable=False)
    nome_cliente = Column(Text, nullable=False)
    valor_total = Column(Numeric(12, 2), nullable=False)
    valor_parcela = Column(Numeric(12, 2), nullable=False)
    total_parcelas = Column(Integer, nullable=False)
    frequencia = Column(Text, nullable=False)
    metodo_cobranca = Column(Text, nullable=False)
    dias_vencimento = Column(Integer, nullable=False)
    data_criacao = Column(DateTime, default=func.current_timestamp())
    status = Column(Text, nullable=False, default="CREATED")
    unidade = Column(Text, nullable=False)
    produto_id = Column(Integer, nullable=False)
    criado_por = Column(Text, nullable=False)
    uuid = Column(Text, nullable=False)
    desconto_boleto = Column(Numeric(12, 2))
    location_url = Column(Text)
    contrato_id = Column(Integer, ForeignKey("contratos.contrato_id"))
    tipo_odontograma_id = Column(Integer, ForeignKey("tipos_odontograma.id"))

    # Relacionamentos
    tipo_odontograma = relationship("TipoOdontograma", back_populates="carne_pagamentos")
    
    # Outros relacionamentos que possam existir