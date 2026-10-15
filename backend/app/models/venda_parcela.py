# Sale installment model.
from pydantic import BaseModel, Field, validator  
from typing import Optional, Union
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, DateTime, Date, func, ForeignKey
from sqlalchemy.orm import relationship
from ..database.db import Base

# Schemas Pydantic
class VendaParcelaBase(BaseModel):
    venda_id: int
    numero_parcela: int
    valor_parcela: float
    data_vencimento: date
    status_parcela: str = "Pendente"
    documento_referencia: Optional[str] = None

    class Config:
        from_attributes = True

class VendaParcelaCreate(VendaParcelaBase):
    pass

class VendaParcelaPagamentoUpdate(BaseModel):
    data_pagamento: Union[datetime, date]
    valor_pago: float
    status_parcela: str = "Pago"

    class Config:
        from_attributes = True

class PagamentoInicialCreate(BaseModel):
    venda_id: int
    parcela_id: int
    valor_pago: float
    data_pagamento: Union[datetime, date] = Field(default_factory=datetime.now)
    
    class Config:
        from_attributes = True
        
    @validator('valor_pago')
    def validar_valor_pago(cls, v):
        if v <= 0:
            raise ValueError('O valor do pagamento deve ser maior que zero')
        return v

class VendaParcelaRead(VendaParcelaBase):
    id: int
    data_pagamento: Optional[Union[datetime, date]] = None
    valor_pago: Optional[float] = None
    created_at: datetime
    updated_at: datetime

class VendaParcela(Base):
    __tablename__ = "venda_parcelas"

    id = Column(Integer, primary_key=True, index=True)
    venda_id = Column(Integer, ForeignKey("vendas.id"), nullable=False, index=True)
    numero_parcela = Column(Integer, nullable=False)
    valor_parcela = Column(Numeric(12, 2), nullable=False)
    data_vencimento = Column(Date, nullable=False)
    status_parcela = Column(String(50), default='Pendente', index=True)
    documento_referencia = Column(String(50), nullable=True)
    data_pagamento = Column(DateTime(timezone=True), nullable=True)
    valor_pago = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relacionamento com Venda
    venda = relationship("Venda", back_populates="parcelas")
