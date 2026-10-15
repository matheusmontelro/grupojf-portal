from sqlalchemy import Column, Integer, Numeric, Boolean, DateTime, ForeignKey, UniqueConstraint, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.db import Base
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

class EmpresaRegrasSplit(Base):
    __tablename__ = "empresa_regras_split"

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    tipo_odontograma_id = Column(Integer, ForeignKey("tipos_odontograma.id"), nullable=False)
    percentual = Column(Numeric(5, 2), nullable=False)
    ciclos_participacao = Column(Integer, nullable=False, default=1)
    absorve_saldo = Column(Boolean, default=False)
    ativo = Column(Boolean, default=True)
    unidade = Column(String(100), nullable=True, index=True)
    tipo_calculo = Column(String(20), nullable=False, default='percentual')
    valor_fixo_brl = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Adicione estas relações
    tipo_odontograma = relationship("TipoOdontograma", back_populates="empresa_regras_split")
    empresa = relationship("Empresa", back_populates="regras_split")

    # Garantir que não haja duplicidade de regras para mesma empresa e tipo de odontograma
    __table_args__ = (
        UniqueConstraint("empresa_id", "tipo_odontograma_id", name="unique_empresa_regra_split"),
    )

class EmpresaRegrasSplitBase(BaseModel):
    empresa_id: int
    tipo_odontograma_id: int
    percentual: Decimal = Field(..., ge=0, le=100)
    ciclos_participacao: int = 1
    absorve_saldo: bool = False
    ativo: bool = True
    unidade: Optional[str] = Field(None, max_length=100)
    tipo_calculo: str = Field(default='percentual', pattern='^(percentual|valor_fixo)$')
    valor_fixo_brl: Optional[Decimal] = Field(None, ge=0)

class EmpresaRegrasSplitCreate(EmpresaRegrasSplitBase):
    pass

class EmpresaRegrasSplitUpdate(BaseModel):
    percentual: Optional[Decimal] = Field(None, ge=0, le=100)
    ciclos_participacao: Optional[int] = None
    absorve_saldo: Optional[bool] = None
    ativo: Optional[bool] = None
    unidade: Optional[str] = Field(None, max_length=100)
    tipo_calculo: Optional[str] = Field(None, pattern='^(percentual|valor_fixo)$')
    valor_fixo_brl: Optional[Decimal] = Field(None, ge=0)

class EmpresaRegrasSplitRead(EmpresaRegrasSplitBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class EmpresaRegrasSplitDetail(EmpresaRegrasSplitRead):
    empresa_nome: Optional[str] = None
    tipo_odontograma_nome: Optional[str] = None

    class Config:
        orm_mode = True