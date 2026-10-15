# app/models/carne.py
from datetime import datetime, date
from typing import List, Optional, Union
from pydantic import BaseModel, Field, validator
from decimal import Decimal

class RecurringItemCreate(BaseModel):
    product_id: int
    quantity: int = 1
    unit_price_in_cents: int
    max_billing_cycles: int

class PaymentMethodCreate(BaseModel):
    method: str = "BANK_SLIP"
    amount_off: Optional[int] = None

class SplitCreate(BaseModel):
    seller_id: int
    percentage: Decimal
    cycles_to_participate: int = 1
    absorb_balance: bool = False

class RecurringItem(BaseModel):
    product_id: int = Field(..., alias="productId", description="ID do produto na Bempaggo (deve ser criado previamente)")
    quantity: int
    unit_price_in_cents: int = Field(..., alias="unitPriceInCents", description="Valor unitário do item em centavos")
    max_billing_cycles: Optional[int] = Field(None, alias="maxBillingCycles", description="Número máximo de ciclos de cobrança. Nulo para infinito.")

class AcceptedPaymentMethod(BaseModel):
    method: str = Field(..., description="Método de pagamento (ex: BANK_SLIP, CREDIT_CARD)")
    amount_off: Optional[int] = Field(None, alias="amountOff", description="Valor de desconto em centavos para este método")

class SplitRule(BaseModel):
    seller_id: int = Field(..., alias="sellerId", description="ID do seller Bempaggo que receberá o split")
    percentage: Decimal
    cycles_to_participate: Optional[int] = Field(None, alias="cyclesToParticipate", description="Número de ciclos que este split participará")
    absorb_balance: Optional[bool] = Field(False, alias="absorbBalance", description="Se este split absorve o saldo restante")

class CarneCreateRequest(BaseModel):
    # Dados do Cliente (obrigatórios para Bempaggo se não existir customer_id)
    customer_id: Optional[int] = Field(None, alias="customerId", description="ID do cliente na Bempaggo (se já existir)")
    nome_cliente: str = Field(..., description="Nome do cliente")
    cpf_cnpj: str = Field(..., description="CPF ou CNPJ do cliente")
    
    # Detalhes do Carnê (obrigatórios para Bempaggo)
    days_until_due: int = Field(..., description="Dias até o primeiro vencimento (calculado pelo frontend)")
    dia_vencimento_escolhido: Optional[int] = Field(None, gt=0, le=31, description="Dia do mês escolhido para o vencimento (1-31), se informado, recalculará days_until_due em UTC.")
    billing_frequency: str = Field(..., alias="billingFrequency", description="Frequência de cobrança (ex: MONTHLY, WEEKLY)")
    collection_method: str = Field(..., alias="collectionMethod", description="Método de coleta (ex: BANK_SLIP, AUTOMATIC_CHARGE)")
    charges_by_booklet: int = Field(..., alias="chargesByBooklet", description="Número total de cobranças no carnê")
    recurring_item: RecurringItem = Field(..., alias="recurringItem", description="Item recorrente do carnê")
    accepted_payment_methods: List[AcceptedPaymentMethod] = Field(..., alias="acceptedPaymentMethods", description="Métodos de pagamento aceitos")
    splits: Optional[List[SplitRule]] = Field(None, description="Regras de split (opcional, pode vir da configuração do tipo de odontograma)")

    # Dados Adicionais (para nosso sistema e opcionalmente para Bempaggo)
    email: Optional[str] = None
    birthdate: Optional[date] = None # Mantido como date
    phone_country_code: Optional[str] = Field(None, alias="phoneCountryCode")
    phone_area_code: Optional[str] = Field(None, alias="phoneAreaCode")
    phone_number: Optional[str] = Field(None, alias="phoneNumber")
    street: Optional[str] = None
    street_number: Optional[str] = Field(None, alias="streetNumber")
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = Field(None, alias="zipCode")
    
    unidade: str = Field(..., description="Unidade que está criando o carnê")
    criado_por: str = Field(..., description="ID do usuário que criou o carnê") # Alterado para str se for UUID ou similar
    contrato_id: Optional[int] = Field(None, description="ID do contrato associado (opcional)")
    notification_url: Optional[str] = Field(None, alias="notificationUrl", description="URL de notificação para webhooks da Bempaggo (opcional, será gerada se não fornecida)")
    tipo_odontograma_id: Optional[int] = Field(None, description="ID do tipo de odontograma associado")
    dentista_id: Optional[int] = Field(None, description="ID do dentista associado (se aplicável para split)")
    odontograma_id: Optional[int] = Field(None, description="ID do odontograma associado")
    pre_venda_id: Optional[str] = Field(None, description="ID da pré-venda associada (se houver)")
    venda_id: Optional[int] = Field(None, description="ID da venda associada (se houver)")

    class Config:
        from_attributes = True # Antigo orm_mode
        populate_by_name = True # Permite usar tanto o nome do campo quanto o alias
        json_encoders = {
            Decimal: lambda v: float(v) # Serializar Decimal como float para JSON
        }

    @validator('billing_frequency')
    def billing_frequency_valid(cls, v):
        valid_frequencies = ["WEEKLY", "BIWEEKLY", "MONTHLY", "BIMONTHLY", "QUARTERLY", "SEMESTRAL", "YEARLY"]
        if v not in valid_frequencies:
            raise ValueError(f"Frequência inválida. Valores aceitos: {', '.join(valid_frequencies)}")
        return v
    
    @validator('collection_method')
    def collection_method_valid(cls, v):
        valid_methods = ["AUTOMATIC_CHARGE", "SEND_INVOICE"]
        if v not in valid_methods:
            raise ValueError(f"Método de cobrança inválido. Valores aceitos: {', '.join(valid_methods)}")
        return v

class CarneResponseItem(BaseModel):
    id: int
    recurring_invoice_id: Optional[str]
    everest_subscription_id: Optional[int] = None
    customer_id: int
    nome_cliente: str
    cpf_cnpj: str
    valor_total: Decimal
    valor_parcela: Decimal
    total_parcelas: int
    frequencia: str
    metodo_cobranca: str
    dias_vencimento: int
    data_criacao: datetime
    status: str
    unidade: str
    criado_por: str
    uuid: str
    location_url: Optional[str] = None
    tipo_odontograma: Optional[str] = None
    odontograma_id: Optional[int] = None

class CarneParcela(BaseModel):
    id: int
    carne_id: int
    numero_parcela: int
    valor_parcela: Decimal
    data_vencimento: date
    status: str
    data_pagamento: Optional[datetime] = None
    valor_pago: Optional[Decimal] = None
    codigo_barras: Optional[str] = None
    linha_digitavel: Optional[str] = None
    boleto_url: Optional[str] = None
    charge_id: Optional[str] = None
    created_at: datetime

class CarneSplit(BaseModel):
    id: int
    carne_id: int
    seller_id: int
    cargo_id: Optional[int] = None
    percentage: Decimal
    cycles_to_participate: int
    absorb_balance: bool
    created_at: datetime

class CarneDetalhado(CarneResponseItem):
    parcelas: List[CarneParcela]
    splits: List[CarneSplit]

class CarneUpdateStatus(BaseModel):
    status: str
    
    @validator('status')
    def status_valid(cls, v):
        valid_status = ["CREATED", "ACTIVE", "CANCELED", "COMPLETED", "ERROR"]
        if v not in valid_status:
            raise ValueError(f"Status inválido. Valores aceitos: {', '.join(valid_status)}")
        return v 
