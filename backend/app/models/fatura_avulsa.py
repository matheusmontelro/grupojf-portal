"""Modelos para Fatura Avulsa Delta"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from decimal import Decimal

class FaturaAvulsaItem(BaseModel):
    """Item de uma fatura avulsa"""
    productId: int
    quantity: int = 1
    unitPriceInCents: int
    
class FaturaAvulsaSplit(BaseModel):
    """Split de pagamento para fatura avulsa"""
    sellerId: int
    percentage: float = Field(..., ge=0, le=100)
    cyclesToParticipate: int = 1
    absorbBalance: bool = False
    metadata: Optional[Dict] = None
    
class FaturaAvulsaPaymentMethod(BaseModel):
    """Método de pagamento aceito"""
    method: str  # CREDIT_CARD, PIX, BANK_SLIP
    cardSettings: Optional[Dict] = None  # Para cartão de crédito
    
class FaturaAvulsaCreateRequest(BaseModel):
    """Request para criar fatura avulsa"""
    # Dados do cliente
    customer_name: str
    customer_document: str
    customer_email: str
    customer_phone: Optional[str] = None
    customer_address: Optional[Dict] = None
    
    # Dados da fatura
    valor_total: Decimal
    payment_method: str  # CREDIT_CARD, PIX, BANK_SLIP
    installments: Optional[int] = 1  # Para cartão de crédito
    
    # Dados da venda
    venda_id: int
    odontograma_id: Optional[int] = None
    
    # URLs
    notification_url: Optional[str] = None
    success_url: Optional[str] = None
    
    # Splits (calculados dinamicamente)
    splits: Optional[List[FaturaAvulsaSplit]] = None
    
    # Novos campos para cálculo de splits dinâmicos
    criado_por: Optional[int] = None  # ID do usuário que está criando
    unidade: Optional[str] = None     # Unidade do usuário/clínica
    tipo_odontograma_id: Optional[int] = None  # Tipo do odontograma para cálculo de splits
    
class FaturaAvulsaResponse(BaseModel):
    """Response da criação de fatura avulsa"""
    id: int
    invoice_number: str
    status: str
    checkout_url: Optional[str] = None
    due_date: datetime
    amount_cents: int
    customer_id: int
    created_at: datetime
    
class FaturaAvulsaWebhookPayload(BaseModel):
    """Payload recebido no webhook"""
    event_type: str  # invoice.paid, invoice.canceled, etc
    invoice_id: int
    invoice_number: str
    status: str
    paid_at: Optional[datetime] = None
    amount_paid_cents: Optional[int] = None
    payment_method: Optional[str] = None