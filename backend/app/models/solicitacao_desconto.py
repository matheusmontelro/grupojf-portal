# Discount request model.
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database.db import Base # Supondo que Base está em ../database/db.py

# Importar Pydantic para os Schemas
from pydantic import BaseModel, Field # Field para validações/descrições
from typing import Optional
from datetime import datetime
# Supondo que você tenha um schema Pydantic para Odontograma para o relacionamento
# Exemplo: from .odontograma import OdontogramaReadSimple # Ajuste o caminho conforme necessário

# ----- Modelo SQLAlchemy -----
class SolicitacaoDesconto(Base):
    __tablename__ = "solicitacoes_desconto"

    id = Column(Integer, primary_key=True, index=True)
    venda_id = Column(Integer, ForeignKey("vendas.id"), nullable=True, unique=True, index=True)
    unidade = Column(Text, nullable=False, index=True) # Adicionado index=True
    valor_solicitado = Column(Numeric(12, 2), nullable=False)
    percentual_solicitado = Column(Numeric(5, 2), nullable=True)
    justificativa = Column(Text, nullable=True)
    usuario_solicitante_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    data_solicitacao = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status_aprovacao = Column(String(50), default='Pendente', index=True) # Adicionado index=True
    usuario_aprovador_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    data_aprovacao = Column(DateTime(timezone=True), nullable=True)
    observacao_aprovador = Column(Text, nullable=True)
    
    # Nova coluna para vincular ao odontograma
    odontograma_id = Column(Integer, ForeignKey("odontogramas.id"), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relacionamentos
    # Relacionamentos
    venda = relationship("Venda", back_populates="solicitacao_desconto")
    # Adicionar relacionamento com User para solicitante e aprovador, se necessário
    usuario_solicitante = relationship("User", foreign_keys=[usuario_solicitante_id])
    usuario_aprovador = relationship("User", foreign_keys=[usuario_aprovador_id])
    
    # Novo relacionamento com Odontograma
    # O nome 'odontograma_solicitado' é usado para clareza
    odontograma = relationship("Odontograma") # Ajuste "Odontograma" e adicione back_populates no modelo Odontograma


# ----- Schemas Pydantic para SolicitacaoDesconto -----

# Schema base com campos comuns para criação e leitura
class SolicitacaoDescontoBase(BaseModel):
    venda_id: Optional[int] = Field(None, description="ID da venda associada à solicitação (pode ser nulo se vinculado apenas ao odontograma).")
    unidade: str = Field(..., description="Unidade de negócio que está realizando a solicitação.")
    valor_solicitado: float = Field(..., gt=0, description="Valor monetário do desconto solicitado.")
    percentual_solicitado: Optional[float] = Field(None, ge=0, le=100, description="Percentual de desconto solicitado (0 a 100).")
    justificativa: Optional[str] = Field(None, max_length=1000, description="Justificativa para a solicitação do desconto.")
    odontograma_id: Optional[int] = Field(None, description="ID opcional do odontograma específico para esta solicitação.")
    # usuario_solicitante_id será preenchido pelo backend com base no usuário autenticado

    class Config:
        from_attributes = True # Anteriormente orm_mode = True

# Schema para criar uma nova solicitação de desconto
class SolicitacaoDescontoCreate(SolicitacaoDescontoBase):
    # Se odontograma_id for obrigatório para um certo tipo de solicitação, pode ser definido aqui.
    # Por enquanto, segue a opcionalidade de SolicitacaoDescontoBase.
    pass

# Schema para payload de ações (aprovar/rejeitar)
class SolicitacaoDescontoAction(BaseModel):
    # status_aprovacao é definido pelo endpoint (aprovar/rejeitar)
    observacao_aprovador: Optional[str] = Field(None, max_length=1000, description="Observação do aprovador/rejeitador.")
    # usuario_aprovador_id será preenchido pelo backend

    class Config:
        from_attributes = True

# Schema para retornar dados da solicitação, incluindo campos gerados pelo sistema
class SolicitacaoDescontoRead(SolicitacaoDescontoBase):
    id: int
    usuario_solicitante_id: int # Mantido para consistência, mas poderia ser um objeto UserRead aninhado
    data_solicitacao: datetime
    status_aprovacao: str
    usuario_aprovador_id: Optional[int] = None # Poderia ser UserRead aninhado
    data_aprovacao: Optional[datetime] = None
    observacao_aprovador: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Para incluir dados aninhados do odontograma (se o backend os carregar):
    # odontograma: Optional[OdontogramaReadSimple] = None # Descomente e ajuste se necessário

    class Config:
        from_attributes = True
        # Removido orm_mode, from_attributes é o padrão para Pydantic v2+
