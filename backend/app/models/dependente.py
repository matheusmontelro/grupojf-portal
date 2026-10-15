# backend/app/models/dependente.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, func, ForeignKey
from sqlalchemy.orm import relationship
from ..database.db import Base

class Dependente(Base):
    __tablename__ = "dependentes"

    dependente_id = Column(Integer, primary_key=True, index=True)
    responsavel_paciente_id = Column(Integer, ForeignKey("pacientes.paciente_id"), nullable=False, index=True)
    nome_dependente = Column(String(255), nullable=False)
    data_nascimento_dependente = Column(Date, nullable=True)
    genero_dependente = Column(String(20), nullable=True)
    parentesco = Column(String(50), nullable=True)
    observacoes_dependente = Column(Text, nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    # Comentado temporariamente até que o modelo Paciente seja criado
    # responsavel = relationship("Paciente", back_populates="dependentes_vinculados", foreign_keys=[responsavel_paciente_id])
    
    # As relações com vendas e odontogramas são definidas via backref nos respectivos modelos