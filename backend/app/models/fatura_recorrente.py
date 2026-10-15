"""Modelos para Fatura Recorrente Delta"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from decimal import Decimal

class FaturaRecorrenteItem(BaseModel):
    """Item de uma fatura recorrente"""
    productId: int
    quantity: int = 1
    unitPriceInCents: int
    
class FaturaRecorrenteSplit(BaseModel):
    """Split de pagamento para fatura recorrente"""
    sellerId: int
    percentage: float = Field(..., ge=0, le=100)
    cyclesToParticipate: Optional[int] = None  # None = todos os ciclos
    absorbBalance: bool = False
    metadata: Optional[Dict] = None
    
class FaturaRecorrenteCreateRequest(BaseModel):
    """Request para criar fatura recorrente (assinatura)"""
    # Dados do cliente
    customer_name: str
    customer_document: str
    customer_email: str
    customer_phone: Optional[str] = None
    customer_address: Optional[Dict] = None
    
    # Dados da assinatura
    valor_mensal: Decimal
    total_parcelas: int  # Total de ciclos/meses
    
    # Dados da venda
    venda_id: int
    odontograma_id: Optional[int] = None
    criado_por: Optional[int] = None  # ID do usuário que está criando
    unidade: Optional[str] = None  # Unidade para cálculo de splits
    
    # URLs
    notification_url: Optional[str] = None
    success_url: Optional[str] = None
    
    # Splits (calculados dinamicamente)
    splits: Optional[List[FaturaRecorrenteSplit]] = None
    
    # Para casos de entrada + parcelamento
    is_parcelamento: bool = False  # True quando é parte de entrada+parcelamento
    valor_entrada: Optional[Decimal] = None
    
class FaturaRecorrenteResponse(BaseModel):
    """Response da criação de fatura recorrente"""
    id: int
    subscription_id: str
    everest_subscription_id: Optional[str] = None
    status: str
    checkout_url: Optional[str] = None
    billing_cycle_start: datetime
    billing_frequency: str
    total_cycles: Optional[int] = None
    amount_cents_per_cycle: int
    customer_id: int
    created_at: datetime
    
class FaturaRecorrenteWebhookPayload(BaseModel):
    """Payload recebido no webhook"""
    event_type: str  # subscription.created, subscription.payment, subscription.canceled, etc
    subscription_id: int
    status: str
    cycle_number: Optional[int] = None
    paid_at: Optional[datetime] = None
    amount_paid_cents: Optional[int] = None
    next_billing_date: Optional[datetime] = None
    
class EntradaParcelamentoRequest(BaseModel):
    """Request para venda com entrada + parcelamento"""
    # Dados da entrada
    valor_entrada: Decimal
    forma_pagamento_entrada: str  # PIX_AVULSO_DELTA, BOLETO_AVULSO_DELTA, etc
    
    # Dados do parcelamento
    valor_parcelado: Decimal
    numero_parcelas: int
    
    # Sempre será cartão recorrente para o parcelamento
    forma_pagamento_parcelamento: str = "CARTÃO CRÉDITO RECORRENTE DELTA"
