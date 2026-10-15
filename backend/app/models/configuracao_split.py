from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.database.db import Base

# -------------------- SQLAlchemy Models --------------------

class ParticipacaoEmpresaSplit(Base):
    __tablename__ = "participacao_empresa_split"

    id = Column(Integer, primary_key=True, index=True)
    tipo_odontograma_id = Column(Integer, ForeignKey("tipos_odontograma.id"), nullable=False)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False)
    ativo = Column(Boolean, default=True)
    ordem_prioridade = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relações
    tipo_odontograma = relationship("TipoOdontograma", back_populates="participacoes_empresas")
    empresa = relationship("Empresa", back_populates="participacoes_split")

    # Constraint
    __table_args__ = (
        UniqueConstraint('tipo_odontograma_id', 'empresa_id', name='unique_empresa_tipo_odontograma'),
    )


class ParticipacaoCargoSplit(Base):
    __tablename__ = "participacao_cargo_split"

    id = Column(Integer, primary_key=True, index=True)
    tipo_odontograma_id = Column(Integer, ForeignKey("tipos_odontograma.id"), nullable=False)
    cargo_id = Column(Integer, ForeignKey("cargos.id"), nullable=False)
    ativo = Column(Boolean, default=True)
    ordem_prioridade = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relações
    tipo_odontograma = relationship("TipoOdontograma", back_populates="participacoes_cargos")
    cargo = relationship("Cargo", back_populates="participacoes_split")

    # Constraint
    __table_args__ = (
        UniqueConstraint('tipo_odontograma_id', 'cargo_id', name='unique_cargo_tipo_odontograma'),
    )


class ConfigLimiteSplit(Base):
    __tablename__ = "config_limite_split"

    id = Column(Integer, primary_key=True, index=True)
    tipo_odontograma_id = Column(Integer, ForeignKey("tipos_odontograma.id"), nullable=False, unique=True)
    max_empresas = Column(Integer, default=1)
    max_cargos = Column(Integer, default=20)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relações
    tipo_odontograma = relationship("TipoOdontograma", back_populates="config_limite")

    # Constraint já aplicado com unique=True no tipo_odontograma_id


# -------------------- Pydantic Schemas --------------------

# -- ParticipacaoEmpresaSplit --

class ParticipacaoEmpresaSplitBase(BaseModel):
    tipo_odontograma_id: int
    empresa_id: int
    ativo: bool = True
    ordem_prioridade: int = 1

class ParticipacaoEmpresaSplitCreate(ParticipacaoEmpresaSplitBase):
    pass

class ParticipacaoEmpresaSplitUpdate(BaseModel):
    ativo: Optional[bool] = None
    ordem_prioridade: Optional[int] = None

class ParticipacaoEmpresaSplitRead(ParticipacaoEmpresaSplitBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# Com informações de relacionamento
class ParticipacaoEmpresaSplitDetail(ParticipacaoEmpresaSplitRead):
    tipo_odontograma_nome: Optional[str] = None
    empresa_nome: Optional[str] = None

    class Config:
        orm_mode = True


# -- ParticipacaoCargoSplit --

class ParticipacaoCargoSplitBase(BaseModel):
    tipo_odontograma_id: int
    cargo_id: int
    ativo: bool = True
    ordem_prioridade: int = 1

class ParticipacaoCargoSplitCreate(ParticipacaoCargoSplitBase):
    pass

class ParticipacaoCargoSplitUpdate(BaseModel):
    ativo: Optional[bool] = None
    ordem_prioridade: Optional[int] = None

class ParticipacaoCargoSplitRead(ParticipacaoCargoSplitBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# Com informações de relacionamento
class ParticipacaoCargoSplitDetail(ParticipacaoCargoSplitRead):
    tipo_odontograma_nome: Optional[str] = None
    cargo_nome: Optional[str] = None

    class Config:
        orm_mode = True


# -- ConfigLimiteSplit --

class ConfigLimiteSplitBase(BaseModel):
    tipo_odontograma_id: int
    max_empresas: int = Field(1, ge=0)
    max_cargos: int = Field(20, ge=0)

class ConfigLimiteSplitCreate(ConfigLimiteSplitBase):
    pass

class ConfigLimiteSplitUpdate(BaseModel):
    max_empresas: Optional[int] = Field(None, ge=0)
    max_cargos: Optional[int] = Field(None, ge=0)

class ConfigLimiteSplitRead(ConfigLimiteSplitBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class ConfigLimiteSplitDetail(ConfigLimiteSplitRead):
    tipo_odontograma_nome: Optional[str] = None

    class Config:
        orm_mode = True