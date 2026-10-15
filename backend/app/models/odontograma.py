# backend/app/models/odontograma.py
from sqlalchemy import Column, Integer, Boolean, DateTime, func, ForeignKey, Text, String # Adicionado Text
from sqlalchemy.orm import relationship
from ..database.db import Base

class Odontograma(Base):
    __tablename__ = "odontogramas"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.paciente_id"), nullable=False, index=True)
    dentista_orcamentista_id = Column(Integer, ForeignKey("dentistas.id"), nullable=False, index=True)
    unidade = Column(Text, nullable=False, index=True)
    
    # Manter a coluna como está no banco de dados
    tipo = Column(String(50), nullable=True)  # Tipo de odontograma: Contrato, Particular, Ortodontia
    
    # Campo para odontogramas de dependentes
    dependente_id = Column(Integer, ForeignKey("dependentes.dependente_id"), nullable=True, index=True)
    
    data_criacao = Column(DateTime(timezone=True), server_default=func.now())
    usuario_criacao_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relacionamentos (mantidos como estavam)
    dentista_orcamentista = relationship("Dentista")
    itens = relationship("OdontogramaItem", back_populates="odontograma", cascade="all, delete-orphan")
    venda_associada = relationship("Venda", back_populates="odontograma")
    
    # Relacionamento com dependente será definido apenas via FK por enquanto
    # dependente = relationship("Dependente", backref="odontogramas", foreign_keys=[dependente_id])
    
    # Adicionar property para acessar 'tipo' como 'Tipo'
    @property
    def Tipo(self):
        return self.tipo
        
    @Tipo.setter
    def Tipo(self, value):
        self.tipo = value