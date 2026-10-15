from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from ..database.db import Base
from sqlalchemy.orm import relationship  # Adicionado o import da função relationship

# Modelo SQLAlchemy para o banco de dados
class Cargo(Base):
    __tablename__ = "cargos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False, unique=True)
    codigo = Column(String(50), nullable=True, unique=True)
    descricao = Column(String, nullable=True)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    regras_split = relationship("RegraSplit", back_populates="cargo")
    participacoes_split = relationship("ParticipacaoCargoSplit", back_populates="cargo")

# Campos básicos comuns
class CargoBase(BaseModel):
    nome: str
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    ativo: bool = True

# Para criar um cargo
class CargoCreate(CargoBase):
    pass

# Para atualizar, todos os campos são opcionais
class CargoUpdate(BaseModel):
    nome: Optional[str] = None
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    ativo: Optional[bool] = None

# Modelo de leitura (retorno de GET)
class CargoRead(CargoBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True