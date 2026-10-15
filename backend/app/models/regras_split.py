from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, Numeric, Boolean, DateTime, ForeignKey, func, String, CheckConstraint
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from ..database.db import Base

# Enum para tipo de cálculo
class TipoCalculoEnum(str, PyEnum):
    PERCENTUAL = "percentual"
    VALOR_FIXO = "valor_fixo"

# Modelo SQLAlchemy para o banco de dados
class RegraSplit(Base):
    __tablename__ = "regras_split"

    id = Column(Integer, primary_key=True, index=True)
    tipo_odontograma_id = Column(Integer, ForeignKey("tipos_odontograma.id"), nullable=False)
    cargo_id = Column(Integer, ForeignKey("cargos.id"), nullable=False)
    percentual = Column(Numeric(5, 2), nullable=True)  # Agora pode ser nulo quando usar valor fixo
    ciclos_participacao = Column(Integer, nullable=False, default=1)
    absorve_saldo = Column(Boolean, default=False)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Novos campos para valor fixo
    tipo_calculo = Column(String(20), default=TipoCalculoEnum.PERCENTUAL, nullable=False)
    valor_fixo_brl = Column(Numeric(10, 2), nullable=True)
    
    # Campo unidade - NULL significa todas as unidades
    unidade = Column(String(100), nullable=True, index=True)

    # Atualize os relacionamentos para usar back_populates
    tipo_odontograma = relationship("TipoOdontograma", back_populates="regras_split")
    cargo = relationship("Cargo", back_populates="regras_split")
    
    # Constraint para garantir integridade
    __table_args__ = (
        CheckConstraint(
            "(tipo_calculo = 'percentual' AND percentual IS NOT NULL AND valor_fixo_brl IS NULL) OR "
            "(tipo_calculo = 'valor_fixo' AND valor_fixo_brl IS NOT NULL)",
            name="check_tipo_calculo_valores"
        ),
    )

# Classe base para Pydantic
class RegraSplitBase(BaseModel):
    tipo_odontograma_id: int
    cargo_id: int
    tipo_calculo: TipoCalculoEnum = TipoCalculoEnum.PERCENTUAL
    percentual: Optional[float] = Field(None, ge=0, le=100, description="Percentual de 0 a 100")
    valor_fixo_brl: Optional[Decimal] = Field(None, ge=0, description="Valor fixo em BRL")
    ciclos_participacao: int = Field(1, ge=1, description="Número de ciclos de participação")
    absorve_saldo: bool = False
    unidade: Optional[str] = Field(None, max_length=100, description="Unidade específica ou None para todas")

    @validator('percentual', 'valor_fixo_brl', pre=True)
    def validate_tipo_calculo(cls, v, values):
        # Simplificado - apenas valida se os campos obrigatórios estão presentes
        return v
    
    @validator('percentual')
    def validate_percentual_range(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Percentual deve estar entre 0 e 100')
        return v

# Para criar uma regra de split
class RegraSplitCreate(RegraSplitBase):
    pass

# Para atualizar uma regra de split
class RegraSplitUpdate(BaseModel):
    tipo_odontograma_id: Optional[int] = None
    cargo_id: Optional[int] = None
    tipo_calculo: Optional[TipoCalculoEnum] = None
    percentual: Optional[float] = Field(None, ge=0, le=100)
    valor_fixo_brl: Optional[Decimal] = Field(None, ge=0)
    ciclos_participacao: Optional[int] = Field(None, ge=1)
    absorve_saldo: Optional[bool] = None
    ativo: Optional[bool] = None
    unidade: Optional[str] = Field(None, max_length=100)

# Resposta com IDs
class RegraSplitRead(RegraSplitBase):
    id: int
    ativo: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Resposta com detalhes dos relacionamentos
class RegraSplitDetail(RegraSplitRead):
    tipo_odontograma_nome: Optional[str] = None
    cargo_nome: Optional[str] = None
    
    # Adicionar campo calculado para mostrar valor formatado
    @property
    def valor_display(self) -> str:
        if self.tipo_calculo == TipoCalculoEnum.PERCENTUAL:
            return f"{self.percentual}%"
        else:
            return f"R$ {self.valor_fixo_brl:,.2f}"