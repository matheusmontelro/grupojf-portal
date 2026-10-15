from sqlalchemy import Column, Integer, String, Text, Boolean, Numeric, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from ..database.db import Base

class OdontogramaItem(Base):
    __tablename__ = "odontograma_itens"

    id = Column(Integer, primary_key=True, index=True)
    odontograma_id = Column(Integer, ForeignKey("odontogramas.id"), nullable=False, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False, index=True)
    dente_numero = Column(String(2))
    face_vestibular = Column(Boolean, default=False)
    face_lingual_palatina = Column(Boolean, default=False)
    face_mesial = Column(Boolean, default=False)
    face_distal = Column(Boolean, default=False)
    face_oclusal_incisal = Column(Boolean, default=False)
    valor_registrado = Column(Numeric(10, 2), nullable=False)
    observacao = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    odontograma = relationship("Odontograma", back_populates="itens")
    produto = relationship("Produto", back_populates="itens_odontograma")