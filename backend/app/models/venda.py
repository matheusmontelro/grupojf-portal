# backend/app/models/venda.py
from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, DateTime, func, ForeignKey # Adicionado Text
from sqlalchemy.orm import relationship
from ..database.db import Base

class Venda(Base):
    __tablename__ = "vendas"

    id = Column(Integer, primary_key=True, index=True)
    documento_venda = Column(String(50), unique=True, nullable=False, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.paciente_id"), nullable=False, index=True)
    dentista_orcamentista_id = Column(Integer, ForeignKey("dentistas.id"), nullable=False, index=True)
    odontograma_id = Column(Integer, ForeignKey("odontogramas.id"), nullable=True, index=True)
    unidade = Column(Text, nullable=False, index=True)
    data_venda = Column(DateTime(timezone=True), server_default=func.now())
    valor_bruto_total = Column(Numeric(12, 2), nullable=False)
    valor_desconto_regra = Column(Numeric(12, 2), default=0.00)
    valor_desconto_solicitado = Column(Numeric(12, 2), default=0.00)
    valor_desconto_aprovado = Column(Numeric(12, 2), default=0.00)
    valor_liquido_total = Column(Numeric(12, 2), nullable=False)
    forma_pagamento_id = Column(Integer, ForeignKey("formas_pagamento.id"), nullable=True, index=True) # Presume que formas_pagamento.py será criado
    qtd_parcelas = Column(Integer, nullable=False, default=1)
    usuario_venda_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    terminal = Column(String(50), nullable=True) # Adicionado nullable=True como exemplo
    status_venda = Column(String(50), default='Efetuada', index=True)
    
    # --- NOVO CAMPO ---
    tipo_venda = Column(String(50), nullable=True, index=True) # Ex: "Particular", "Contrato", "Ortodontia"
    # Se o tipo "Contrato" ou "Ortodontia" exigir um link para a tabela de contratos:
    # contrato_id = Column(Integer, ForeignKey("contratos.contrato_id"), nullable=True, index=True)
    
    # Campo para vendas de dependentes
    dependente_id = Column(Integer, ForeignKey("dependentes.dependente_id"), nullable=True, index=True)

    data_cancelamento = Column(DateTime(timezone=True), nullable=True)
    usuario_cancelamento_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    motivo_cancelamento = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relacionamentos
    # paciente = relationship("Paciente", back_populates="vendas") # Se Paciente tiver 'vendas'
    dentista_orcamentista = relationship("Dentista", back_populates="vendas_realizadas")
    odontograma = relationship("Odontograma", back_populates="venda_associada")
    forma_pagamento = relationship("FormaPagamento", back_populates="vendas") # Presume que FormaPagamento terá 'vendas'
    # usuario_venda = relationship("User", foreign_keys=[usuario_venda_id]) # Ajustar conforme model User
    # usuario_cancelamento = relationship("User", foreign_keys=[usuario_cancelamento_id]) # Ajustar
    parcelas = relationship("VendaParcela", back_populates="venda", cascade="all, delete-orphan", order_by="VendaParcela.numero_parcela")
    solicitacao_desconto = relationship("SolicitacaoDesconto", back_populates="venda", uselist=False, cascade="all, delete-orphan") # Se SolicitacaoDesconto tiver 'venda'
    # Se adicionou contrato_id:
    # contrato_associado = relationship("Contrato") # Ajustar relacionamento se necessário
    
    # Relacionamento com dependente será definido apenas via FK por enquanto
    # dependente = relationship("Dependente", back_populates="vendas", foreign_keys=[dependente_id])

