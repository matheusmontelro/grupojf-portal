from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from ..database.db import Base # Ajuste o caminho se sua Base estiver em outro lugar

class Dentista(Base):
    __tablename__ = "dentistas"

    id = Column(Integer, primary_key=True, index=True)
    # codigo_dentista pode ser gerado/controlado pela aplicação se necessário
    codigo_dentista = Column(String(10), unique=True, index=True, nullable=True)
    nome = Column(Text, nullable=False)
    funcao = Column(String(100))
    ativo = Column(Boolean, default=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relacionamentos inversos (o que um dentista "tem")
    odontogramas_criados = relationship("Odontograma", back_populates="dentista_orcamentista")
    vendas_realizadas = relationship("Venda", back_populates="dentista_orcamentista")
    
    # Relacionamento com User (usuário do sistema)
    usuario_sistema = relationship("User", back_populates="dentista_profissional")