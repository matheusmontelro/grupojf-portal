from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.db import Base

class TipoOdontograma(Base):
    __tablename__ = "tipos_odontograma"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(80), unique=True, nullable=False)
    descricao = Column(Text, nullable=True)
    valor_base = Column(Numeric(10, 2), nullable=True)
    qtd_parcelas = Column(Integer, nullable=True)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())

    # Adicionando as relações bidirecionais necessárias
    participacoes_empresas = relationship(
        "ParticipacaoEmpresaSplit", 
        back_populates="tipo_odontograma",
        cascade="all, delete-orphan"
    )
    
    participacoes_cargos = relationship(
        "ParticipacaoCargoSplit", 
        back_populates="tipo_odontograma",
        cascade="all, delete-orphan"
    )
    
    config_limite = relationship(
        "ConfigLimiteSplit", 
        back_populates="tipo_odontograma", 
        uselist=False,  # One-to-one relationship
        cascade="all, delete-orphan"
    )
    
    # Se estas relações existirem no seu modelo, também adicione:
    regras_split = relationship(
        "RegraSplit", 
        back_populates="tipo_odontograma",
        cascade="all, delete-orphan"
    )
    
    empresa_regras_split = relationship(
        "EmpresaRegrasSplit", 
        back_populates="tipo_odontograma",
        cascade="all, delete-orphan"
    )
    
    carne_pagamentos = relationship(
        "CarnePagamento", 
        back_populates="tipo_odontograma"
    )

    def __repr__(self):
        return f"<TipoOdontograma(id={self.id}, nome='{self.nome}')>"