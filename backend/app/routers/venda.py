# app/routers/vendas.py

import logging
import uuid
import calendar
from typing import List, Optional, Any
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, model_validator

# Import database connector
from app.database.db import DatabaseConnection

# Import models/schemas
from app.models.pacientes import PacienteRead
from app.routers.dentista import DentistaRead
from app.routers.forma_pagamento import FormaPagamentoRead
from app.models.fatura_avulsa import FaturaAvulsaCreateRequest
from app.models.fatura_recorrente import FaturaRecorrenteCreateRequest
from app.database.db import get_db
from app.services.regras_vendas_service import RegrasVendasService
from app.services.venda_akimais_service import sync_venda_akimais_flags_conn
from .venda_regras import processar_regras_ortodontico, processar_regras_odc_combo, ajustar_split_carne_com_entrada
from app.middleware.auth_middleware import get_current_user
import httpx
import os

# Configure logger
logger = logging.getLogger(__name__)
# Example of setting a more detailed logging level if needed for development
# logging.basicConfig(level=logging.DEBUG)
# logger.setLevel(logging.DEBUG)

UNIDADES_GLOBAIS = {"todas unidades", "todas as unidades"}
DIAS_VENCIMENTO_CONTRATO_PERMITIDOS = {5, 10, 15}


def _get_user_value(current_user: Optional[Any], key: str) -> Optional[Any]:
    if not current_user:
        return None
    if isinstance(current_user, dict):
        return current_user.get(key)
    return getattr(current_user, key, None)


def _normalizar_unidade_real(unidade: Optional[str]) -> Optional[str]:
    unidade_normalizada = (unidade or "").strip()
    if not unidade_normalizada:
        return None
    if unidade_normalizada.lower() in UNIDADES_GLOBAIS:
        return None
    return unidade_normalizada


def resolver_unidade_venda(
    unidade_payload: Optional[str],
    current_user: Optional[Any] = None,
    conn: Optional[Any] = None,
    usuario_id: Optional[int] = None,
) -> str:
    unidade = _normalizar_unidade_real(unidade_payload)
    if unidade:
        return unidade

    unidade_usuario = _normalizar_unidade_real(_get_user_value(current_user, "unidade"))
    if unidade_usuario:
        return unidade_usuario

    if conn is not None and usuario_id:
        cursor = conn.cursor()
        cursor.execute("SELECT unidade FROM users WHERE id = %s", (usuario_id,))
        row = cursor.fetchone()
        unidade_usuario_banco = _normalizar_unidade_real(row[0] if row else None)
        if unidade_usuario_banco:
            return unidade_usuario_banco

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unidade da venda é obrigatória.",
    )


def resolver_forma_pagamento_id(
    cursor: Any,
    forma_pagamento_id: Optional[int],
    forma_pagamento_nome: Optional[str] = None,
) -> Optional[int]:
    if forma_pagamento_id is not None:
        cursor.execute("SELECT id FROM formas_pagamento WHERE id = %s", (forma_pagamento_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Forma de pagamento ID {forma_pagamento_id} não encontrada.",
            )
        return result[0]

    nome = (forma_pagamento_nome or "").strip()
    if not nome:
        return None

    cursor.execute("""
        SELECT id
        FROM formas_pagamento
        WHERE ativo = true
          AND (
              UPPER(nome) = UPPER(%s)
              OR (%s ILIKE '%%RECORRENTE%%' AND nome ILIKE '%%RECORRENTE%%')
              OR (%s ILIKE '%%CARN%%' AND nome ILIKE 'CARN%%')
          )
        ORDER BY CASE WHEN UPPER(nome) = UPPER(%s) THEN 0 ELSE 1 END, id
        LIMIT 1
    """, (nome, nome, nome, nome))
    result = cursor.fetchone()
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Forma de pagamento '{nome}' não encontrada.",
        )
    return result[0]


def resolver_dia_vencimento_contrato(contrato: Any) -> int:
    dia = getattr(contrato, "dia_vencimento", None)
    if dia is None:
        data_base = getattr(contrato, "data_vencimento_primeira_parcela", None)
        dia = data_base.day if data_base else None

    try:
        dia = int(dia)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dia de vencimento do contrato é obrigatório.",
        )

    if dia not in DIAS_VENCIMENTO_CONTRATO_PERMITIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dia de vencimento inválido para contrato. Permitidos: 5, 10 ou 15.",
        )

    return dia


def montar_data_vencimento(ano: int, mes: int, dia: int) -> date:
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia, ultimo_dia))


def calcular_datas_vencimento_contrato(dia_vencimento: int, qtd_parcelas: int) -> List[date]:
    hoje = date.today()
    primeiro_mes = hoje.month + 1
    primeiro_ano = hoje.year
    if primeiro_mes > 12:
        primeiro_mes = 1
        primeiro_ano += 1

    datas = []
    for i in range(qtd_parcelas):
        mes = primeiro_mes + i
        ano = primeiro_ano + ((mes - 1) // 12)
        mes = ((mes - 1) % 12) + 1
        datas.append(montar_data_vencimento(ano, mes, dia_vencimento))

    return datas


# --- Schemas Pydantic for VendaParcela ---

class VendaParcelaBase(BaseModel):
    numero_parcela: int
    valor_parcela: Decimal = Field(..., decimal_places=2)
    data_vencimento: date

    class Config:
        from_attributes = True

class VendaParcelaRead(VendaParcelaBase):
    id: int
    status_parcela: str
    data_pagamento: Optional[datetime] = None
    valor_pago: Optional[Decimal] = Field(None, decimal_places=2)
    documento_referencia: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# --- Schemas Pydantic for SolicitacaoDesconto ---

class SolicitacaoDescontoBase(BaseModel):
    valor_solicitado: Decimal = Field(..., ge=0, decimal_places=2)
    justificativa: Optional[str] = None

    class Config:
        from_attributes = True

class SolicitacaoDescontoCreate(SolicitacaoDescontoBase):
    # Used inside VendaCreate
    pass

class SolicitacaoDescontoRead(SolicitacaoDescontoBase):
    id: int
    venda_id: int
    unidade: str
    percentual_solicitado: Optional[Decimal] = Field(None, decimal_places=2)
    usuario_solicitante_id: int
    data_solicitacao: datetime
    status_aprovacao: str
    usuario_aprovador_id: Optional[int] = None
    data_aprovacao: Optional[datetime] = None
    observacao_aprovador: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# --- Schemas Pydantic for Venda ---

class VendaItemAvulsoCreate(BaseModel): # For sales without previous odonto
    produto_id: int
    quantidade: int = Field(..., gt=0)
    valor_unitario_registrado: Decimal = Field(..., gt=0, decimal_places=2) # Price at the time of sale
    observacao: Optional[str] = None

class VendaBase(BaseModel):
    paciente_id: int
    dentista_orcamentista_id: int
    unidade: str
    forma_pagamento_id: Optional[int] = None
    qtd_parcelas: int = Field(..., ge=1)
    odontograma_id: Optional[int] = None # Or itens_avulsos will be used
    dependente_id: Optional[int] = None  # ID do dependente quando a venda é para um dependente

    class Config:
        from_attributes = True

class VendaCreate(VendaBase):
    # Either odontograma_id or itens_avulsos must be provided
    itens_avulsos: Optional[List[VendaItemAvulsoCreate]] = None
    # Details for optional discount request
    valor_desconto_solicitado: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    justificativa_desconto: Optional[str] = None
    tipo_venda: Optional[str] = None
    valor_base_contrato: Optional[Decimal] = Field(None, decimal_places=2)
    valor_entrada: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    forma_pagamento_entrada_id: Optional[int] = None
    data_vencimento_primeira_parcela: date
    # Campo para pré-venda com entrada
    pre_venda_id: Optional[str] = None
    # Validator to ensure either odontograma_id or itens_avulsos (but not both) are provided
    @model_validator(mode='after')
    def check_source_items(self) -> 'VendaCreate':
        logger.debug(f"Running VendaCreate model validator for odontograma_id: {self.odontograma_id}, itens_avulsos: {bool(self.itens_avulsos)}")
        if self.odontograma_id is not None and self.itens_avulsos is not None:
            logger.warning("Validation failed: Both odontograma_id and itens_avulsos provided.")
            raise ValueError('Provide odontograma_id OR itens_avulsos, but not both.')
        if self.odontograma_id is None and not self.itens_avulsos:
            logger.warning("Validation failed: Neither odontograma_id nor itens_avulsos provided.")
            raise ValueError('You must provide odontograma_id OR a list of itens_avulsos.')
        if self.valor_desconto_solicitado is not None and self.valor_desconto_solicitado > 0 and not self.justificativa_desconto:
            logger.warning("Validation failed: Discount requested without justification.")
            raise ValueError('Justification is required when requesting extra discount.')
        logger.debug("VendaCreate model validation successful.")
        return self
    
# Schemas específicos para cada tipo de contrato
class ContratoOdontologicoCreate(BaseModel):
    paciente_id: int
    dentista_orcamentista_id: int
    unidade: str
    forma_pagamento_id: Optional[int] = None
    data_vencimento_primeira_parcela: date
    valor_base_contrato: Optional[Decimal] = Field(None, decimal_places=2)
    qtd_parcelas: Optional[int] = None
    valor_entrada: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    forma_pagamento_entrada_id: Optional[int] = None
    odontograma_id: Optional[int] = None  # Adicionar este campo
    dependente_id: Optional[int] = None  # ID do dependente quando a venda é para um dependente
    # Novos campos para regras de vendas
    dia_vencimento: Optional[int] = None
    forma_pagamento: Optional[str] = None
    valor_taxa_adesao: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    aplicar_desconto_avista: Optional[bool] = False
    percentual_desconto_avista: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)
    # Campo para pré-venda com entrada
    pre_venda_id: Optional[str] = None
    # Campo para identificar o usuário que está criando
    criado_por: Optional[int] = None
    
    @model_validator(mode='after')
    def check_entrada_fields(self) -> 'ContratoOdontologicoCreate':
        if self.valor_entrada is not None and self.valor_entrada > 0 and self.forma_pagamento_entrada_id is None:
            raise ValueError('Forma de pagamento da entrada é obrigatória quando há valor de entrada.')
        return self

class ContratoOrtodonticoCreate(BaseModel):
    paciente_id: int
    dentista_orcamentista_id: int
    unidade: str
    forma_pagamento_id: Optional[int] = None
    data_vencimento_primeira_parcela: date
    valor_base_contrato: Optional[Decimal] = Field(None, decimal_places=2)
    qtd_parcelas: Optional[int] = None
    valor_entrada: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    forma_pagamento_entrada_id: Optional[int] = None
    odontograma_id: Optional[int] = None
    dependente_id: Optional[int] = None  # ID do dependente quando a venda é para um dependente
    # Novos campos para regras de vendas
    dia_vencimento: Optional[int] = None
    forma_pagamento: Optional[str] = None
    valor_taxa_adesao: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    aplicar_desconto_avista: Optional[bool] = False
    percentual_desconto_avista: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)
    # Campo para pré-venda com entrada
    pre_venda_id: Optional[str] = None
    # Campo para identificar o usuário que está criando
    criado_por: Optional[int] = None

    @model_validator(mode='after')
    def check_entrada_fields(self) -> 'ContratoOrtodonticoCreate':
        if self.valor_entrada is not None and self.valor_entrada > 0 and self.forma_pagamento_entrada_id is None:
            raise ValueError('Forma de pagamento da entrada é obrigatória quando há valor de entrada.')
        return self

class ComboOrtoODCCreate(BaseModel):
    paciente_id: int
    dentista_orcamentista_id: int
    unidade: str
    forma_pagamento_id: Optional[int] = None
    data_vencimento_primeira_parcela: date
    valor_base_contrato: Optional[Decimal] = Field(None, decimal_places=2)
    qtd_parcelas: Optional[int] = None
    valor_entrada: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    forma_pagamento_entrada_id: Optional[int] = None
    odontograma_id: Optional[int] = None
    dependente_id: Optional[int] = None  # ID do dependente quando a venda é para um dependente
    # Novos campos para regras de vendas
    dia_vencimento: Optional[int] = None
    forma_pagamento: Optional[str] = None
    valor_taxa_adesao: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    aplicar_desconto_avista: Optional[bool] = False
    percentual_desconto_avista: Optional[Decimal] = Field(None, ge=0, le=100, decimal_places=2)
    # Campo para pré-venda com entrada
    pre_venda_id: Optional[str] = None
    # Campo para identificar o usuário que está criando
    criado_por: Optional[int] = None

    @model_validator(mode='after')
    def check_entrada_fields(self) -> 'ComboOrtoODCCreate':
        if self.valor_entrada is not None and self.valor_entrada > 0 and self.forma_pagamento_entrada_id is None:
            raise ValueError('Forma de pagamento da entrada é obrigatória quando há valor de entrada.')
        return self

class VendaRead(VendaBase):
    id: int
    documento_venda: str
    data_venda: datetime
    valor_bruto_total: Decimal = Field(..., decimal_places=2)
    valor_desconto_regra: Decimal = Field(..., decimal_places=2)
    valor_desconto_solicitado: Decimal = Field(..., decimal_places=2)
    valor_desconto_aprovado: Decimal = Field(..., decimal_places=2)
    valor_liquido_total: Decimal = Field(..., decimal_places=2)
    usuario_venda_id: int
    status_venda: str
    data_cancelamento: Optional[datetime] = None
    usuario_cancelamento_id: Optional[int] = None
    motivo_cancelamento: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    parcelas: List[VendaParcelaRead] = []
    solicitacao_desconto: Optional[SolicitacaoDescontoRead] = None
    paciente: Optional[PacienteRead] = None
    dentista_orcamentista: Optional[DentistaRead] = None
    forma_pagamento: Optional[FormaPagamentoRead] = None

class VendaCancelUpdate(BaseModel):
    motivo_cancelamento: str = Field(..., min_length=5)

# --- Type alias for user authentication ---
User = Any  # Define User as Any type for compatibility with the current_user parameter

# --- FastAPI Router ---
router = APIRouter(
    prefix="/vendas",
    tags=["Vendas e Faturamento"]
)

# --- Helper Functions ---

def calcular_datas_vencimento(data_base: date, qtd_parcelas: int, primeiro_venc_dias: int = 0) -> List[date]:
    """Calculate the due dates for installments."""
    logger.debug(f"Calculating due dates: base_date={data_base}, installments_qty={qtd_parcelas}, first_due_days={primeiro_venc_dias}")
    datas = []
    # Primeira parcela (entrada) vence hoje (ou na data_base)
    vencimento_atual = data_base
    datas.append(vencimento_atual)
    
    # As parcelas restantes vencem a cada 30 dias
    for i in range(1, qtd_parcelas):  # Note que começamos de 1, pois já adicionamos a primeira parcela
        # Adicionar aproximadamente 30 dias para a próxima parcela
        mes = vencimento_atual.month + 1
        ano = vencimento_atual.year
        if mes > 12:
            mes = 1
            ano += 1
        # Try to keep the day, but adjust if the month doesn't have that day (e.g., day 31 in February)
        dia = vencimento_atual.day
        try:
            vencimento_atual = date(ano, mes, dia)
        except ValueError:
            # Day doesn't exist in the next month (e.g., Feb 31), go to the last day
            ultimo_dia = calendar.monthrange(ano, mes)[1]
            logger.debug(f"Adjusting due date for installment {i+1}: Day {dia} not in month {mes}/{ano}. Using last day: {ultimo_dia}")
            vencimento_atual = date(ano, mes, ultimo_dia)
        
        datas.append(vencimento_atual)
    
    logger.info(f"Calculated due dates: {datas}")
    return datas

def calcular_valores_parcelas(valor_total: Decimal, qtd_parcelas: int) -> List[Decimal]:
    """Divide the total value into installments, handling cents."""
    logger.debug(f"Calculating installment values: total_value={valor_total}, installments_qty={qtd_parcelas}")
    if qtd_parcelas <= 0:
        logger.warning(f"Invalid quantity of installments ({qtd_parcelas}) for calculating values. Returning empty list.")
        return []
    valor_base_parcela = (valor_total / Decimal(qtd_parcelas)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    parcelas = [valor_base_parcela] * qtd_parcelas
    soma_atual = sum(parcelas)
    diferenca = valor_total - soma_atual
    
    logger.debug(f"Base installment value: {valor_base_parcela}, Sum of base installments: {soma_atual}, Difference: {diferenca}")
    # Distribute the difference in cents to the first installment
    if diferenca != Decimal(0):
        parcelas[0] += diferenca
        logger.debug(f"Distributed difference {diferenca} to the first installment. New value: {parcelas[0]}")
    logger.info(f"Calculated installment values: {parcelas}")
    return parcelas

# Helper function to convert database row to PacienteRead
def _row_to_paciente_read(row) -> PacienteRead:
    """Convert a database row to a PacienteRead model."""
    # logger.debug(f"Converting patient row to PacienteRead: {row}") # Can be too verbose
    return PacienteRead(
        paciente_id=row[0],
        nome_paciente=row[1],
        cpf_cnpj=row[2],
        email=row[3],
        data_nascimento=row[4],
        is_minor=row[5],
        responsavel_id=row[6],
        phone_country_code=row[7],
        phone_area_code=row[8],
        phone_number=row[9],
        street=row[10],
        street_number=row[11],
        neighborhood=row[12],
        city=row[13],
        state=row[14],
        zip_code=row[15],
        created_at=row[16],
        updated_at=row[17],
        unidade=row[18],
    )

def criar_fatura_automatica(venda_id: int, conn) -> Optional[dict]:
    """
    Cria uma fatura (avulsa ou recorrente) automaticamente baseado na forma de pagamento.
    
    Formas de pagamento suportadas:
    - PIX AVULSO DELTA, CARTÃO CRÉDITO AVULSO DELTA, BOLETO AVULSO DELTA → Fatura Avulsa
    - CARTÃO CRÉDITO RECORRENTE DELTA → Fatura Recorrente
    
    Args:
        venda_id: ID da venda criada
        conn: Conexão ativa do banco de dados
        
    Returns:
        Dict com dados da fatura criada ou None se não foi necessário criar
    """
    try:
        cursor = conn.cursor()
        
        # Buscar dados completos da venda incluindo forma de pagamento
        # Primeiro tentar pela forma de pagamento da venda, senão pela primeira parcela
        cursor.execute("""
            SELECT v.id, v.paciente_id, v.valor_liquido_total, v.unidade, v.odontograma_id,
                   v.usuario_venda_id, 
                   COALESCE(fp1.nome, fp2.nome) as forma_pagamento_nome, 
                   v.qtd_parcelas
            FROM vendas v
            LEFT JOIN formas_pagamento fp1 ON v.forma_pagamento_id = fp1.id
            LEFT JOIN venda_parcelas vp ON v.id = vp.venda_id AND vp.numero_parcela = 1
            LEFT JOIN formas_pagamento fp2 ON vp.forma_pagamento_id = fp2.id
            WHERE v.id = %s
        """, (venda_id,))
        
        venda_data = cursor.fetchone()
        if not venda_data:
            logger.error(f"Venda {venda_id} não encontrada para criar fatura avulsa")
            return None
            
        forma_pagamento_nome = venda_data[6]
        qtd_parcelas = venda_data[7]
        
        # Verificar se é uma forma de pagamento Delta
        formas_pagamento_avulsas = ["PIX AVULSO DELTA", "CARTÃO CRÉDITO AVULSO DELTA", "BOLETO AVULSO DELTA"]
        formas_pagamento_recorrentes = ["CARTÃO CRÉDITO RECORRENTE DELTA"]
        
        if forma_pagamento_nome in formas_pagamento_avulsas:
            logger.info(f"Venda {venda_id} é {forma_pagamento_nome}, criando fatura avulsa automaticamente")
            tipo_fatura = "avulsa"
        elif forma_pagamento_nome in formas_pagamento_recorrentes:
            logger.info(f"Venda {venda_id} é {forma_pagamento_nome}, criando fatura recorrente automaticamente")
            tipo_fatura = "recorrente"
        else:
            logger.info(f"Venda {venda_id} não é pagamento Delta ({forma_pagamento_nome}), não será criada fatura")
            return None
        
        # Buscar dados do paciente
        cursor.execute("""
            SELECT nome_paciente, cpf_cnpj, email, phone_country_code,
                   phone_area_code, phone_number, street, street_number, 
                   neighborhood, city, state, zip_code
            FROM pacientes
            WHERE paciente_id = %s
        """, (venda_data[1],))
        
        paciente_data = cursor.fetchone()
        if not paciente_data:
            logger.error(f"Paciente {venda_data[1]} não encontrado")
            return None
            
        # Montar dados para a API de fatura avulsa
        fatura_request = {
            "customer_name": paciente_data[0],
            "customer_document": paciente_data[1],
            "customer_email": paciente_data[2] or f"{paciente_data[1]}@cliente.com",
            "valor_total": float(venda_data[2]),  # valor_liquido_total
            "payment_method": forma_pagamento_nome,  # Usar o nome original da forma de pagamento
            "venda_id": venda_id,
            "odontograma_id": venda_data[4],
            "criado_por": venda_data[5],  # usuario_venda_id
            "unidade": venda_data[3],
            "installments": venda_data[7] or 1  # qtd_parcelas
        }
        
        # Adicionar telefone se disponível
        if paciente_data[5]:  # phone_number
            fatura_request["customer_phone"] = f"{paciente_data[3] or '55'}{paciente_data[4] or ''}{paciente_data[5]}"
            
        # Adicionar endereço se disponível
        if paciente_data[6]:  # street
            fatura_request["customer_address"] = {
                "street": paciente_data[6],
                "streetNumber": paciente_data[7] or "S/N",
                "neighborhood": paciente_data[8] or "Centro",
                "city": paciente_data[9] or "São Paulo",
                "state": paciente_data[10] or "SP",
                "zipCode": paciente_data[11] or "00000000"
            }
        
        # Fazer chamada síncrona para a API apropriada
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        
        if tipo_fatura == "avulsa":
            # Criar fatura avulsa
            with httpx.Client() as client:
                response = client.post(
                    f"{base_url}/fatura-avulsa/",
                    json=fatura_request,
                    timeout=30.0
                )
                
            if response.status_code == 201:
                fatura_data = response.json()
                logger.info(f"Fatura avulsa criada com sucesso para venda {venda_id}: {fatura_data.get('id')}")
                return fatura_data
            else:
                logger.error(f"Erro ao criar fatura avulsa para venda {venda_id}: {response.status_code} - {response.text}")
                return None
                
        elif tipo_fatura == "recorrente":
            # Preparar dados para fatura recorrente
            # Calcular valor mensal (valor total / quantidade de parcelas)
            valor_mensal = float(venda_data[2]) / qtd_parcelas if qtd_parcelas > 0 else float(venda_data[2])
            
            fatura_request["valor_mensal"] = valor_mensal
            fatura_request["total_parcelas"] = qtd_parcelas
            
            # Criar fatura recorrente
            with httpx.Client() as client:
                response = client.post(
                    f"{base_url}/fatura-recorrente/",
                    json=fatura_request,
                    timeout=30.0
                )
                
            if response.status_code == 200:
                fatura_data = response.json()
                logger.info(f"Fatura recorrente criada com sucesso para venda {venda_id}: {fatura_data.get('id')}")
                return fatura_data
            else:
                logger.error(f"Erro ao criar fatura recorrente para venda {venda_id}: {response.status_code} - {response.text}")
                return None
            
    except Exception as e:
        logger.error(f"Erro ao criar fatura avulsa automaticamente para venda {venda_id}: {str(e)}")
        return None

# --- Venda Endpoints ---

# Endpoint para Contrato Odontológico + Akimais
@router.post("/contrato-odontologico-akimais", response_model=VendaRead, status_code=status.HTTP_201_CREATED)
def create_contrato_odontologico_akimais(
    contrato: ContratoOdontologicoCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint específico para criação de venda do tipo 'Contrato Odontológico + Akimais'.
    """
    logger.info(f"Criando Contrato Odontológico + Akimais para paciente ID: {contrato.paciente_id}")
    
    TIPO_CONTRATO = 'Contrato Odontológico + Akimais'
    # Prioriza criado_por do payload, depois current_user, depois fallback para 1
    if contrato.criado_por:
        usuario_id = contrato.criado_por
    else:
        usuario_id = current_user.get('id', 1) if current_user else 1
    
    # Validar se o usuário tem cargo autorizado para fazer vendas
    from ..services.split_service import SplitService
    autorizado, mensagem_erro = SplitService.validar_cargo_autorizado_venda(usuario_id)
    
    if not autorizado:
        logger.warning(f"Tentativa de venda bloqueada: {mensagem_erro}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=mensagem_erro
        )
    
    # 1. Validar dados básicos
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Validar paciente
        cursor.execute("SELECT paciente_id FROM pacientes WHERE paciente_id = %s", (contrato.paciente_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Paciente ID {contrato.paciente_id} não encontrado.")
        
        # Validar dentista
        cursor.execute("SELECT id FROM dentistas WHERE id = %s", (contrato.dentista_orcamentista_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Dentista ID {contrato.dentista_orcamentista_id} não encontrado.")

        forma_pagamento_venda_id = resolver_forma_pagamento_id(
            cursor,
            contrato.forma_pagamento_id,
            contrato.forma_pagamento,
        )
        
        # Se tiver forma de pagamento da entrada, validar
        if contrato.forma_pagamento_entrada_id:
            cursor.execute("SELECT id FROM formas_pagamento WHERE id = %s", (contrato.forma_pagamento_entrada_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Forma de pagamento ID {contrato.forma_pagamento_entrada_id} não encontrada.")
        
        # Validar dependente se fornecido
        if hasattr(contrato, 'dependente_id') and contrato.dependente_id is not None:
            cursor.execute("""
                SELECT dependente_id, responsavel_paciente_id, ativo 
                FROM dependentes 
                WHERE dependente_id = %s
            """, (contrato.dependente_id,))
            db_dependente = cursor.fetchone()
            
            if not db_dependente:
                raise HTTPException(status_code=404, detail=f"Dependente ID {contrato.dependente_id} não encontrado.")
            
            if db_dependente[1] != contrato.paciente_id:
                raise HTTPException(status_code=400, detail=f"Dependente não pertence ao paciente responsável.")
            
            if not db_dependente[2]:  # ativo = False
                raise HTTPException(status_code=400, detail=f"Dependente está inativo.")
    
    # 2. Buscar configuração do contrato
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT valor_base, qtd_parcelas
            FROM tipos_odontograma
            WHERE nome = %s AND ativo = TRUE
        """, (TIPO_CONTRATO,))
        
        tipo_config = cursor.fetchone()
        if not tipo_config:
            raise HTTPException(status_code=404, detail=f"Configuração para tipo '{TIPO_CONTRATO}' não encontrada ou inativa.")
    
    # 3. Determinar valores do contrato
    valor_parcela = contrato.valor_base_contrato if contrato.valor_base_contrato is not None else Decimal(str(tipo_config[0]))
    qtd_parcelas = contrato.qtd_parcelas if contrato.qtd_parcelas is not None else tipo_config[1]
    
    if not valor_parcela or valor_parcela <= 0:
        raise HTTPException(status_code=400, detail="Valor da parcela deve ser maior que zero.")
    
    if not qtd_parcelas or qtd_parcelas <= 0:
        raise HTTPException(status_code=400, detail="Quantidade de parcelas deve ser maior que zero.")
    
    valor_bruto_total = valor_parcela * Decimal(qtd_parcelas)
    logger.info(f"Contrato Odontológico configurado: {qtd_parcelas} parcelas de R${valor_parcela} = R${valor_bruto_total}")
    
    # 4. Criar documento de venda e gerar datas de vencimento
    documento_venda = f"COA-{uuid.uuid4()}"
    
    dia_vencimento = resolver_dia_vencimento_contrato(contrato)
    datas_vencimento = calcular_datas_vencimento_contrato(dia_vencimento, qtd_parcelas)
    logger.info(
        f"Contrato Odontológico + Akimais: primeira parcela definida para {datas_vencimento[0]} "
        f"(dia escolhido: {dia_vencimento})"
    )
    
    # 5. Iniciar transação para criar a venda e parcelas
    try:
        with DatabaseConnection() as conn:
            conn.autocommit = False
            cursor = conn.cursor()
            now = datetime.now()
            unidade_venda = resolver_unidade_venda(contrato.unidade, current_user, conn, usuario_id)
            
            # 5.0 Buscar dependente_id do odontograma se houver
            dependente_id_venda = None
            if contrato.odontograma_id:
                cursor.execute("""
                    SELECT dependente_id 
                    FROM odontogramas 
                    WHERE id = %s
                """, (contrato.odontograma_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    dependente_id_venda = result[0]
                    logger.info(f"Odontograma ID {contrato.odontograma_id} pertence ao dependente ID {dependente_id_venda}")
            # Se não tiver dependente_id do odontograma, usar o do contrato se existir
            elif hasattr(contrato, 'dependente_id') and contrato.dependente_id:
                dependente_id_venda = contrato.dependente_id
            
            # 5.1 Inserir a venda
            # Definir campos de entrada se houver entrada configurada
            valor_entrada_venda = None
            tipo_cobranca_venda = None
            entrada_automatica_venda = False
            
            if contrato.valor_entrada and contrato.valor_entrada > 0:
                valor_entrada_venda = contrato.valor_entrada
                tipo_cobranca_venda = 'entrada'
                entrada_automatica_venda = True
                logger.info(f"Marcando venda ODC+Akimais com entrada: R$ {valor_entrada_venda}")
            
            cursor.execute("""
                INSERT INTO vendas (
                    documento_venda, paciente_id, dentista_orcamentista_id, odontograma_id, unidade,
                    forma_pagamento_id,
                    data_venda, valor_bruto_total, valor_desconto_regra, 
                    valor_desconto_solicitado, valor_desconto_aprovado, valor_liquido_total,
                    qtd_parcelas, usuario_venda_id, status_venda, tipo_venda, dependente_id,
                    valor_entrada, tipo_cobranca_inicial, entrada_automatica, pre_venda_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                documento_venda,
                contrato.paciente_id,
                contrato.dentista_orcamentista_id,
                contrato.odontograma_id,  # Agora está correto
                unidade_venda,
                forma_pagamento_venda_id,
                now,
                valor_bruto_total,
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                valor_bruto_total,
                qtd_parcelas,
                usuario_id,
                'Efetuada',
                TIPO_CONTRATO,
                dependente_id_venda,
                valor_entrada_venda,
                tipo_cobranca_venda,
                entrada_automatica_venda,
                contrato.pre_venda_id  # Usar pre_venda_id do contrato
            ))
            
            venda_id = cursor.fetchone()[0]
            logger.info(f"Venda de Contrato Odontológico + Akimais criada com ID: {venda_id}")

            sync_venda_akimais_flags_conn(
                conn=conn,
                venda_id=venda_id,
                pre_venda_id=contrato.pre_venda_id,
            )
            
            # 5.2 Criar parcelas
            valores_parcelas = [valor_parcela] * qtd_parcelas
            
            # Se tiver entrada, ajustar primeira parcela
            if contrato.valor_entrada and contrato.valor_entrada > 0:
                valores_parcelas[0] = contrato.valor_entrada
            
            for i in range(qtd_parcelas):
                doc_ref = f"{documento_venda}/{i+1:02}"
                
                cursor.execute("""
                    INSERT INTO venda_parcelas (
                        venda_id, numero_parcela, valor_parcela, data_vencimento,
                        status_parcela, documento_referencia, forma_pagamento_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    venda_id,
                    i + 1,
                    valores_parcelas[i],
                    datas_vencimento[i],
                    'Pendente',
                    doc_ref,
                    contrato.forma_pagamento_entrada_id if i == 0 and contrato.valor_entrada and contrato.valor_entrada > 0 else forma_pagamento_venda_id
                ))
            
            # 5.3 Commit e retorno
            conn.commit()
            logger.info(f"Contrato Odontológico + Akimais ID {venda_id} criado com sucesso")
            
            # Criar fatura avulsa automaticamente se for PIX AVULSO DELTA
            criar_fatura_automatica(venda_id, conn)
            
            # Retornar a venda criada
            return read_venda(venda_id)
    
    except Exception as e:
        logger.error(f"Erro ao criar Contrato Odontológico + Akimais: {str(e)}", exc_info=True)
        if 'conn' in locals() and conn and not conn.autocommit:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar contrato: {str(e)}")

# Endpoint para Contrato Ortodôntico
@router.post("/contrato-ortodontico", response_model=VendaRead, status_code=status.HTTP_201_CREATED)
def create_contrato_ortodontico(
    contrato: ContratoOrtodonticoCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint específico para criação de venda do tipo 'Contrato Ortodôntico'.
    """
    logger.info(f"Criando Contrato Ortodôntico para paciente ID: {contrato.paciente_id}")
    
    TIPO_CONTRATO = 'Contrato Ortodôntico'
    # Prioriza criado_por do payload, depois current_user, depois fallback para 1
    if contrato.criado_por:
        usuario_id = contrato.criado_por
    else:
        usuario_id = current_user.get('id', 1) if current_user else 1
    
    # Validar se o usuário tem cargo autorizado para fazer vendas
    from ..services.split_service import SplitService
    autorizado, mensagem_erro = SplitService.validar_cargo_autorizado_venda(usuario_id)
    
    if not autorizado:
        logger.warning(f"Tentativa de venda bloqueada: {mensagem_erro}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=mensagem_erro
        )
    
    # Verificar se há pré-venda com entrada paga
    entrada_paga_info = None
    if contrato.pre_venda_id:
        from ..routers.pre_venda import verificar_entrada_paga
        from ..database.db import SessionLocal
        
        db_session = SessionLocal()
        try:
            entrada_paga_info = verificar_entrada_paga(contrato.pre_venda_id, db_session)
            if not entrada_paga_info:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Entrada não foi paga para a pré-venda {contrato.pre_venda_id}"
                )
            
            if entrada_paga_info.status == 'pago':
                logger.info(f"Entrada paga confirmada: {entrada_paga_info.valor_pago}")
            else:
                logger.info(f"Entrada via boleto pendente permitida para pré-venda {contrato.pre_venda_id} - valor: {entrada_paga_info.valor_solicitado}")
        finally:
            db_session.close()
    
    # 1. Validar dados básicos
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Validar paciente
        cursor.execute("SELECT paciente_id FROM pacientes WHERE paciente_id = %s", (contrato.paciente_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Paciente ID {contrato.paciente_id} não encontrado.")
        
        # Validar dentista
        cursor.execute("SELECT id FROM dentistas WHERE id = %s", (contrato.dentista_orcamentista_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Dentista ID {contrato.dentista_orcamentista_id} não encontrado.")

        forma_pagamento_venda_id = resolver_forma_pagamento_id(
            cursor,
            contrato.forma_pagamento_id,
            contrato.forma_pagamento,
        )
        
        # Se tiver forma de pagamento da entrada, validar
        if contrato.forma_pagamento_entrada_id:
            cursor.execute("SELECT id FROM formas_pagamento WHERE id = %s", (contrato.forma_pagamento_entrada_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Forma de pagamento ID {contrato.forma_pagamento_entrada_id} não encontrada.")
    
    # 2. Buscar configuração do contrato - especificidades do ortodôntico
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT valor_base, qtd_parcelas
            FROM tipos_odontograma
            WHERE nome = %s AND ativo = TRUE
        """, (TIPO_CONTRATO,))
        
        tipo_config = cursor.fetchone()
        if not tipo_config:
            raise HTTPException(status_code=404, detail=f"Configuração para tipo '{TIPO_CONTRATO}' não encontrada ou inativa.")
    
    # 3. Determinar valores do contrato - ortodôntico tem valores específicos
    valor_parcela = contrato.valor_base_contrato if contrato.valor_base_contrato is not None else Decimal(str(tipo_config[0]))
    
    # Para contratos ortodônticos, a quantidade de parcelas padrão é 24, mas pode ser sobrescrita
    qtd_parcelas = contrato.qtd_parcelas if contrato.qtd_parcelas is not None else (tipo_config[1] or 24)
    
    if not valor_parcela or valor_parcela <= 0:
        raise HTTPException(status_code=400, detail="Valor da parcela deve ser maior que zero.")
    
    if not qtd_parcelas or qtd_parcelas <= 0:
        raise HTTPException(status_code=400, detail="Quantidade de parcelas deve ser maior que zero.")
    
    valor_bruto_total = valor_parcela * Decimal(qtd_parcelas)
    logger.info(f"Contrato Ortodôntico configurado: {qtd_parcelas} parcelas de R${valor_parcela} = R${valor_bruto_total}")
    
    # 4. Criar documento de venda e gerar datas de vencimento
    documento_venda = f"CORT-{uuid.uuid4()}"
    
    dia_vencimento = resolver_dia_vencimento_contrato(contrato)
    datas_vencimento = calcular_datas_vencimento_contrato(dia_vencimento, qtd_parcelas)
    logger.info(
        f"Contrato Ortodôntico: primeira parcela definida para {datas_vencimento[0]} "
        f"(dia escolhido: {dia_vencimento})"
    )
    
    # 5. Iniciar transação para criar a venda e parcelas
    try:
        with DatabaseConnection() as conn:
            conn.autocommit = False
            cursor = conn.cursor()
            now = datetime.now()
            unidade_venda = resolver_unidade_venda(contrato.unidade, current_user, conn, usuario_id)
            
            # 5.0 Buscar dependente_id do odontograma se houver
            dependente_id_venda = None
            if contrato.odontograma_id:
                cursor.execute("""
                    SELECT dependente_id 
                    FROM odontogramas 
                    WHERE id = %s
                """, (contrato.odontograma_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    dependente_id_venda = result[0]
                    logger.info(f"Odontograma ID {contrato.odontograma_id} pertence ao dependente ID {dependente_id_venda}")
            
            # 5.1 Inserir a venda - ortodôntico pode ter especificidades
            # Definir campos de entrada se houver entrada paga
            valor_entrada_venda = None
            tipo_cobranca_venda = None
            entrada_automatica_venda = False
            
            if entrada_paga_info:
                # Para boleto pendente, usar valor_solicitado; para pago, usar valor_pago
                if entrada_paga_info.status == 'pago' and entrada_paga_info.valor_pago:
                    valor_entrada_venda = entrada_paga_info.valor_pago
                else:
                    # Boleto pendente - usar valor solicitado
                    valor_entrada_venda = entrada_paga_info.valor_solicitado
                
                if valor_entrada_venda and valor_entrada_venda > 0:
                    tipo_cobranca_venda = 'entrada'
                    entrada_automatica_venda = True
                    logger.info(f"Marcando venda com entrada: R$ {valor_entrada_venda} (status: {entrada_paga_info.status})")
            
            cursor.execute("""
                INSERT INTO vendas (
                    documento_venda, paciente_id, dentista_orcamentista_id, odontograma_id, unidade,
                    forma_pagamento_id,
                    data_venda, valor_bruto_total, valor_desconto_regra, 
                    valor_desconto_solicitado, valor_desconto_aprovado, valor_liquido_total,
                    qtd_parcelas, usuario_venda_id, status_venda, tipo_venda, dependente_id,
                    valor_entrada, tipo_cobranca_inicial, entrada_automatica, pre_venda_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                documento_venda,
                contrato.paciente_id,
                contrato.dentista_orcamentista_id,
                contrato.odontograma_id,  # Usar o campo adicionado
                unidade_venda,
                forma_pagamento_venda_id,
                now,
                valor_bruto_total,
                Decimal("0.00"),  # Sem desconto para contratos
                Decimal("0.00"),
                Decimal("0.00"),
                valor_bruto_total,  # Valor líquido = bruto
                qtd_parcelas,
                usuario_id,
                'Efetuada',
                TIPO_CONTRATO,
                dependente_id_venda,
                valor_entrada_venda,
                tipo_cobranca_venda,
                entrada_automatica_venda,
                contrato.pre_venda_id  # Usar pre_venda_id do contrato
            ))
            
            venda_id = cursor.fetchone()[0]
            logger.info(f"Venda de Contrato Ortodôntico criada com ID: {venda_id}")

            sync_venda_akimais_flags_conn(
                conn=conn,
                venda_id=venda_id,
                pre_venda_id=contrato.pre_venda_id,
            )
            
            # 5.2 Criar parcelas
            # Se teve entrada paga via pré-venda, criar parcela 0
            if entrada_paga_info and valor_entrada_venda and valor_entrada_venda > 0:
                doc_ref_entrada = f"{documento_venda}/00"
                cursor.execute("""
                    INSERT INTO venda_parcelas (
                        venda_id, numero_parcela, valor_parcela, data_vencimento,
                        status_parcela, documento_referencia, forma_pagamento_id,
                        data_pagamento, valor_pago
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    venda_id,
                    0,  # Parcela 0 = entrada
                    valor_entrada_venda,
                    date.today(),  # Entrada vence/paga hoje
                    'Pago',
                    doc_ref_entrada,
                    entrada_paga_info.forma_pagamento_id,
                    datetime.now(),
                    valor_entrada_venda
                ))
                logger.info(f"Parcela 0 (entrada) criada como paga: R$ {valor_entrada_venda}")
            
            forma_pagamento_parcelas_id = forma_pagamento_venda_id
            if forma_pagamento_parcelas_id is None:
                cursor.execute("""
                    SELECT id FROM formas_pagamento
                    WHERE nome = 'CARNÊ' AND ativo = true
                    LIMIT 1
                """)
                result = cursor.fetchone()
                if result:
                    forma_pagamento_parcelas_id = result[0]
                    logger.info(f"Forma de pagamento CARNÊ encontrada com ID: {forma_pagamento_parcelas_id}")
                else:
                    logger.warning("Forma de pagamento CARNÊ não encontrada no banco de dados")
            
            # Criar parcelas normais (1 até N)
            valores_parcelas = [valor_parcela] * qtd_parcelas
            
            for i in range(qtd_parcelas):
                doc_ref = f"{documento_venda}/{i+1:02}"
                
                cursor.execute("""
                    INSERT INTO venda_parcelas (
                        venda_id, numero_parcela, valor_parcela, data_vencimento,
                        status_parcela, documento_referencia, forma_pagamento_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    venda_id,
                    i + 1,
                    valores_parcelas[i],
                    datas_vencimento[i],
                    'Pendente',
                    doc_ref,
                    forma_pagamento_parcelas_id
                ))
            
            # 5.3 Commit e retorno
            conn.commit()
            logger.info(f"Contrato Ortodôntico ID {venda_id} criado com sucesso")
            
            # Aplicar regras específicas do contrato ortodôntico
            if hasattr(contrato, 'forma_pagamento') and contrato.forma_pagamento:
                from sqlalchemy.orm import Session
                db_session = Session(bind=conn)
                try:
                    resultado_regras = processar_regras_ortodontico(
                        venda_id=venda_id,
                        forma_pagamento=contrato.forma_pagamento,
                        valor_total=valor_bruto_total,
                        qtd_parcelas=qtd_parcelas,
                        unidade=unidade_venda,
                        db=db_session,
                        conn=conn
                    )
                    
                    # Se criou entrada/taxa, ajustar split do carnê
                    if resultado_regras.get('entrada_criada'):
                        ajustar_split_carne_com_entrada(venda_id, True, db_session)
                        
                    logger.info(f"Regras aplicadas para venda {venda_id}: {resultado_regras}")
                except Exception as e:
                    logger.error(f"Erro ao aplicar regras ortodôntico: {e}")
                finally:
                    db_session.close()
            
            # Criar fatura avulsa automaticamente se for PIX AVULSO DELTA
            criar_fatura_automatica(venda_id, conn)
            
            # Retornar a venda criada
            return read_venda(venda_id)
    
    except Exception as e:
        logger.error(f"Erro ao criar Contrato Ortodôntico: {str(e)}", exc_info=True)
        if 'conn' in locals() and conn and not conn.autocommit:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar contrato: {str(e)}")

# Endpoint para Combo Orto + ODC
@router.post("/combo-orto-odc", response_model=VendaRead, status_code=status.HTTP_201_CREATED)
def create_combo_orto_odc(
    contrato: ComboOrtoODCCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint específico para criação de venda do tipo 'Combo Orto + ODC'.
    """
    logger.info(f"Criando Combo Orto + ODC para paciente ID: {contrato.paciente_id}")
    
    TIPO_CONTRATO = 'Combo Orto + ODC'
    # Prioriza criado_por do payload, depois current_user, depois fallback para 1
    if contrato.criado_por:
        usuario_id = contrato.criado_por
    else:
        usuario_id = current_user.get('id', 1) if current_user else 1
    
    # Validar se o usuário tem cargo autorizado para fazer vendas
    from ..services.split_service import SplitService
    autorizado, mensagem_erro = SplitService.validar_cargo_autorizado_venda(usuario_id)
    
    if not autorizado:
        logger.warning(f"Tentativa de venda bloqueada: {mensagem_erro}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=mensagem_erro
        )
    
    # 1. Validar dados básicos
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Validar paciente
        cursor.execute("SELECT paciente_id FROM pacientes WHERE paciente_id = %s", (contrato.paciente_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Paciente ID {contrato.paciente_id} não encontrado.")
        
        # Validar dentista
        cursor.execute("SELECT id FROM dentistas WHERE id = %s", (contrato.dentista_orcamentista_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Dentista ID {contrato.dentista_orcamentista_id} não encontrado.")

        forma_pagamento_venda_id = resolver_forma_pagamento_id(
            cursor,
            contrato.forma_pagamento_id,
            contrato.forma_pagamento,
        )
        
        # Se tiver forma de pagamento da entrada, validar
        if contrato.forma_pagamento_entrada_id:
            cursor.execute("SELECT id FROM formas_pagamento WHERE id = %s", (contrato.forma_pagamento_entrada_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Forma de pagamento ID {contrato.forma_pagamento_entrada_id} não encontrada.")
    
    # 2. Buscar configuração do combo
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT valor_base, qtd_parcelas
            FROM tipos_odontograma
            WHERE nome = %s AND ativo = TRUE
        """, (TIPO_CONTRATO,))
        
        tipo_config = cursor.fetchone()
        if not tipo_config:
            raise HTTPException(status_code=404, detail=f"Configuração para tipo '{TIPO_CONTRATO}' não encontrada ou inativa.")
    
    # 3. Determinar valores do contrato - combo tem valor maior que orto puro
    valor_parcela = contrato.valor_base_contrato if contrato.valor_base_contrato is not None else Decimal(str(tipo_config[0]))
    
    # Para combos, parcelas padrão é 36, mas pode ser sobrescrita
    qtd_parcelas = contrato.qtd_parcelas if contrato.qtd_parcelas is not None else (tipo_config[1] or 36)
    
    if not valor_parcela or valor_parcela <= 0:
        raise HTTPException(status_code=400, detail="Valor da parcela deve ser maior que zero.")
    
    if not qtd_parcelas or qtd_parcelas <= 0:
        raise HTTPException(status_code=400, detail="Quantidade de parcelas deve ser maior que zero.")
    
    valor_bruto_total = valor_parcela * Decimal(qtd_parcelas)
    logger.info(f"Combo Orto + ODC configurado: {qtd_parcelas} parcelas de R${valor_parcela} = R${valor_bruto_total}")
    
    # 4. Criar documento de venda e gerar datas de vencimento - combo usa prefixo diferente
    documento_venda = f"COMBO-{uuid.uuid4()}"
    
    dia_vencimento = resolver_dia_vencimento_contrato(contrato)
    datas_vencimento = calcular_datas_vencimento_contrato(dia_vencimento, qtd_parcelas)
    logger.info(
        f"Combo Orto + ODC: primeira parcela definida para {datas_vencimento[0]} "
        f"(dia escolhido: {dia_vencimento})"
    )
    
    # 5. Iniciar transação para criar a venda e parcelas
    try:
        with DatabaseConnection() as conn:
            conn.autocommit = False
            cursor = conn.cursor()
            now = datetime.now()
            unidade_venda = resolver_unidade_venda(contrato.unidade, current_user, conn, usuario_id)
            
            # 5.0 Buscar dependente_id do odontograma se houver
            dependente_id_venda = None
            if contrato.odontograma_id:
                cursor.execute("""
                    SELECT dependente_id 
                    FROM odontogramas 
                    WHERE id = %s
                """, (contrato.odontograma_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    dependente_id_venda = result[0]
                    logger.info(f"Odontograma ID {contrato.odontograma_id} pertence ao dependente ID {dependente_id_venda}")
            
            # 5.1 Inserir a venda - combo tem terminal específico para identificar na clínica
            # Definir campos de entrada se houver entrada configurada
            valor_entrada_venda = None
            tipo_cobranca_venda = None
            entrada_automatica_venda = False
            
            if contrato.valor_entrada and contrato.valor_entrada > 0:
                valor_entrada_venda = contrato.valor_entrada
                tipo_cobranca_venda = 'entrada'
                entrada_automatica_venda = True
                logger.info(f"Marcando venda Combo com entrada: R$ {valor_entrada_venda}")
            
            cursor.execute("""
                INSERT INTO vendas (
                    documento_venda, paciente_id, dentista_orcamentista_id, odontograma_id, unidade,
                    forma_pagamento_id,
                    data_venda, valor_bruto_total, valor_desconto_regra, 
                    valor_desconto_solicitado, valor_desconto_aprovado, valor_liquido_total,
                    qtd_parcelas, usuario_venda_id, status_venda, tipo_venda, terminal, dependente_id,
                    valor_entrada, tipo_cobranca_inicial, entrada_automatica, pre_venda_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                documento_venda,
                contrato.paciente_id,
                contrato.dentista_orcamentista_id,
                contrato.odontograma_id,
                unidade_venda,
                forma_pagamento_venda_id,
                now,
                valor_bruto_total,
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                valor_bruto_total,
                qtd_parcelas,
                usuario_id,
                'Efetuada',
                TIPO_CONTRATO,
                'COMBO',
                dependente_id_venda,
                valor_entrada_venda,
                tipo_cobranca_venda,
                entrada_automatica_venda,
                contrato.pre_venda_id  # Usar pre_venda_id do contrato
            ))
            
            venda_id = cursor.fetchone()[0]
            logger.info(f"Venda de Combo Orto + ODC criada com ID: {venda_id}")

            sync_venda_akimais_flags_conn(
                conn=conn,
                venda_id=venda_id,
                pre_venda_id=contrato.pre_venda_id,
            )
            
            # 5.2 Criar parcelas - todas com valor fixo para combo
            valores_parcelas = [valor_parcela] * qtd_parcelas
            
            # Se tiver entrada, ajustar primeira parcela
            if contrato.valor_entrada and contrato.valor_entrada > 0:
                valores_parcelas[0] = contrato.valor_entrada
            
            for i in range(qtd_parcelas):
                doc_ref = f"{documento_venda}/{i+1:02}"
                
                # Combo usa o status 'Ativa' em vez de 'Pendente'
                cursor.execute("""
                    INSERT INTO venda_parcelas (
                        venda_id, numero_parcela, valor_parcela, data_vencimento,
                        status_parcela, documento_referencia, forma_pagamento_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    venda_id,
                    i + 1,
                    valores_parcelas[i],
                    datas_vencimento[i],
                    'Ativa' if i == 0 else 'Pendente',  # Primeira parcela do combo já fica ativa
                    doc_ref,
                    contrato.forma_pagamento_entrada_id if i == 0 and contrato.valor_entrada and contrato.valor_entrada > 0 else forma_pagamento_venda_id
                ))
            
            # 5.3 Commit e retorno
            conn.commit()
            logger.info(f"Combo Orto + ODC ID {venda_id} criado com sucesso")
            
            # Aplicar regras específicas do Combo Orto + ODC
            if hasattr(contrato, 'forma_pagamento') and contrato.forma_pagamento:
                from sqlalchemy.orm import Session
                db_session = Session(bind=conn)
                try:
                    resultado_regras = processar_regras_odc_combo(
                        venda_id=venda_id,
                        forma_pagamento=contrato.forma_pagamento,
                        tipo_contrato='Combo Orto + ODC',
                        unidade=unidade_venda,
                        db=db_session,
                        conn=conn
                    )
                    
                    # Se criou taxa, ajustar split do carnê
                    if resultado_regras.get('taxa_criada'):
                        ajustar_split_carne_com_entrada(venda_id, True, db_session)
                        
                    logger.info(f"Regras aplicadas para venda {venda_id}: {resultado_regras}")
                except Exception as e:
                    logger.error(f"Erro ao aplicar regras ODC/Combo: {e}")
                finally:
                    db_session.close()
            
            # Criar fatura avulsa automaticamente se for PIX AVULSO DELTA
            criar_fatura_automatica(venda_id, conn)
            
            # Retornar a venda criada
            return read_venda(venda_id)
    
    except Exception as e:
        logger.error(f"Erro ao criar Combo Orto + ODC: {str(e)}", exc_info=True)
        if 'conn' in locals() and conn and not conn.autocommit:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar contrato: {str(e)}")

@router.post("/", response_model=VendaRead, status_code=status.HTTP_201_CREATED)
def create_venda(
    venda_in: VendaCreate,
    current_user: Optional[User] = None
):
    """
    Cria uma nova venda normal (não-contrato).
    Os contratos devem ser criados através de endpoints específicos para cada tipo.
    """
    logger.info(f"Verificando se a venda é elegível para criação pelo endpoint padrão")
    
    # Verificar se a venda é de um tipo de contrato (rejeitamos contratos neste endpoint)
    if venda_in.odontograma_id:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tipo
                FROM odontogramas
                WHERE id = %s
            """, (venda_in.odontograma_id,))
            
            odonto_data = cursor.fetchone()
            if odonto_data and odonto_data[0]:
                tipo_odontograma = odonto_data[0]
                
                # Validar produtos para tipos Particular e Ortodontia
                if tipo_odontograma in ['Particular', 'Ortodontia']:
                    from ..services.template_validation_service import TemplateValidationService
                    from ..database.db import get_db
                    
                    db = next(get_db())
                    try:
                        validation_service = TemplateValidationService()
                        validation_result = validation_service.validar_produtos_odontograma(
                            db=db,
                            odontograma_id=venda_in.odontograma_id,
                            tipo_odontograma=tipo_odontograma
                        )
                        
                        if not validation_result['valido']:
                            logger.error(f"Validação de produtos falhou: {validation_result['mensagem']}")
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=validation_result['mensagem']
                            )
                        
                        logger.info(f"Validação de produtos bem-sucedida para {tipo_odontograma}")
                    finally:
                        db.close()
                
                # Lista de tipos de contrato que têm endpoints específicos
                contract_types = ['Contrato Odontológico + Akimais', 'Contrato Ortodôntico', 'Combo Orto + ODC']
                
                if tipo_odontograma in contract_types:
                    # Converter o tipo para formato de URL (kebab-case)
                    tipo_url = tipo_odontograma.lower().replace(' ', '-').replace('+', '-plus')
                    
                    # Informar ao usuário qual endpoint usar
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Vendas do tipo '{tipo_odontograma}' devem ser criadas através do endpoint específico: /vendas/{tipo_url}"
                    )
    
    # Se chegou aqui, não é um contrato e podemos continuar
    logger.info(f"Attempting to create new sale. Payload: {venda_in.model_dump_json(indent=2)}")
    usuario_id = 1  # Default user ID if current_user is None
    if current_user and hasattr(current_user, 'id'):
        usuario_id = current_user.id
    unidade_venda = resolver_unidade_venda(venda_in.unidade, current_user)
    logger.info(f"Sale creation initiated by user ID: {usuario_id}")

    # 1. Validate FKs using DatabaseConnection
    logger.debug("Step 1: Validating Foreign Keys.")
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se a validação da forma de pagamento é necessária
        if venda_in.forma_pagamento_id is not None:
            logger.debug(f"Checking payment method ID: {venda_in.forma_pagamento_id}")
            cursor.execute("SELECT id FROM formas_pagamento WHERE id = %s", (venda_in.forma_pagamento_id,))
            db_fp = cursor.fetchone()
            if not db_fp:
                logger.error(f"Payment Method ID {venda_in.forma_pagamento_id} not found.")
                raise HTTPException(status_code=404, detail=f"Payment Method ID {venda_in.forma_pagamento_id} not found.")
            logger.debug(f"Payment Method ID {venda_in.forma_pagamento_id} found.")
        
        logger.debug(f"Checking patient ID: {venda_in.paciente_id}")
        cursor.execute("SELECT paciente_id FROM pacientes WHERE paciente_id = %s", (venda_in.paciente_id,))
        db_paciente = cursor.fetchone()
        if not db_paciente:
            logger.error(f"Patient ID {venda_in.paciente_id} not found.")
            raise HTTPException(status_code=404, detail=f"Patient ID {venda_in.paciente_id} not found.")
        logger.debug(f"Patient ID {venda_in.paciente_id} found.")
            
        logger.debug(f"Checking dentist ID: {venda_in.dentista_orcamentista_id}")
        cursor.execute("SELECT id FROM dentistas WHERE id = %s", (venda_in.dentista_orcamentista_id,))
        db_dentista = cursor.fetchone()
        if not db_dentista:
            logger.error(f"Dentist ID {venda_in.dentista_orcamentista_id} not found.")
            raise HTTPException(status_code=404, detail=f"Dentist ID {venda_in.dentista_orcamentista_id} not found.")
        logger.debug(f"Dentist ID {venda_in.dentista_orcamentista_id} found.")
        
        # Validar dependente se fornecido
        if hasattr(venda_in, 'dependente_id') and venda_in.dependente_id is not None:
            logger.debug(f"Checking dependent ID: {venda_in.dependente_id} for patient ID: {venda_in.paciente_id}")
            cursor.execute("""
                SELECT dependente_id, responsavel_paciente_id, ativo 
                FROM dependentes 
                WHERE dependente_id = %s
            """, (venda_in.dependente_id,))
            db_dependente = cursor.fetchone()
            
            if not db_dependente:
                logger.error(f"Dependent ID {venda_in.dependente_id} not found.")
                raise HTTPException(status_code=404, detail=f"Dependente ID {venda_in.dependente_id} não encontrado.")
            
            if db_dependente[1] != venda_in.paciente_id:
                logger.error(f"Dependent ID {venda_in.dependente_id} does not belong to patient ID {venda_in.paciente_id}.")
                raise HTTPException(status_code=400, detail=f"Dependente não pertence ao paciente responsável.")
            
            if not db_dependente[2]:  # ativo = False
                logger.error(f"Dependent ID {venda_in.dependente_id} is inactive.")
                raise HTTPException(status_code=400, detail=f"Dependente está inativo.")
            
            logger.debug(f"Dependent ID {venda_in.dependente_id} validated successfully.")

    # 2. Determine Items and Calculate Gross Value
    logger.debug("Step 2: Determining Items and Calculating Gross Value.")
    valor_bruto_total = Decimal("0.00")

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        if venda_in.odontograma_id:
            logger.info(f"Calculating gross value from odontogram ID: {venda_in.odontograma_id}")
            
            # Check if odontogram exists and get its type
            cursor.execute("""
                SELECT o.id, o.paciente_id
                FROM odontogramas o 
                WHERE o.id = %s
            """, (venda_in.odontograma_id,))
            db_odonto = cursor.fetchone()
            
            if not db_odonto:
                logger.error(f"Odontogram ID {venda_in.odontograma_id} not found.")
                raise HTTPException(status_code=404, detail=f"Odontogram ID {venda_in.odontograma_id} not found.")
            logger.debug(f"Odontogram ID {venda_in.odontograma_id} found.")
            
            # Validate if odonto belongs to the patient
            if db_odonto[1] != venda_in.paciente_id:
                logger.error(f"Odontogram {venda_in.odontograma_id} does not belong to patient {venda_in.paciente_id}.")
                raise HTTPException(status_code=400, detail="Odontogram does not belong to the specified patient.")
            
            # Get odontogram items to calculate regular value
            logger.debug(f"Fetching items for odontogram ID: {venda_in.odontograma_id}")
            cursor.execute("""
                SELECT valor_registrado 
                FROM odontograma_itens 
                WHERE odontograma_id = %s
            """, (venda_in.odontograma_id,))
            items = cursor.fetchall()
            logger.debug(f"Found {len(items)} items for odontogram {venda_in.odontograma_id}.")
            
            for item_idx, item in enumerate(items):
                valor_bruto_total += Decimal(str(item[0]))
                logger.debug(f"Odontogram item {item_idx+1} value: {item[0]}. Cumulative gross total: {valor_bruto_total}")
                    
        elif venda_in.itens_avulsos:
            logger.info(f"Calculating gross value from {len(venda_in.itens_avulsos)} 'itens_avulsos'.")
            for item_idx, item_avulso in enumerate(venda_in.itens_avulsos):
                logger.debug(f"Processing 'item_avulso' {item_idx+1}: Product ID {item_avulso.produto_id}, Qty {item_avulso.quantidade}, Unit Price {item_avulso.valor_unitario_registrado}")
                # Optionally validate product existence
                cursor.execute("SELECT id FROM produtos WHERE id = %s", (item_avulso.produto_id,))
                if not cursor.fetchone():
                    logger.error(f"Product ID {item_avulso.produto_id} for 'item_avulso' not found.")
                    raise HTTPException(status_code=404, detail=f"Product ID {item_avulso.produto_id} not found.")
                
                item_total = item_avulso.valor_unitario_registrado * item_avulso.quantidade
                valor_bruto_total += item_total
                logger.debug(f"'Item_avulso' {item_idx+1} total: {item_total}. Cumulative gross total: {valor_bruto_total}")

    if valor_bruto_total <= 0:
        logger.error(f"Calculated gross sale value is zero or negative: {valor_bruto_total}.")
        raise HTTPException(status_code=400, detail="Gross sale value cannot be zero or negative.")
    logger.info(f"Total Gross Value calculated: {valor_bruto_total}")

    # 3. Find Discount Rule
    logger.debug("Step 3: Finding Discount Rule.")
    valor_desconto_regra = Decimal("0.00")
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        logger.debug(f"Querying discount rule for payment method ID {venda_in.forma_pagamento_id} and {venda_in.qtd_parcelas} installments.")
        cursor.execute("""
            SELECT percentual_desconto 
            FROM regras_desconto 
            WHERE forma_pagamento_id = %s 
              AND ativo = TRUE 
              AND parcela_min <= %s 
              AND parcela_max >= %s
            LIMIT 1
        """, (venda_in.forma_pagamento_id, venda_in.qtd_parcelas, venda_in.qtd_parcelas))
        
        db_regra = cursor.fetchone()
        
        # 4. Calculate Rule Discount
        logger.debug("Step 4: Calculating Rule Discount.")
        if db_regra and Decimal(str(db_regra[0])) > 0:
            percentual_desconto = Decimal(str(db_regra[0]))
            logger.info(f"Discount rule found: {percentual_desconto}%")
            valor_desconto_regra = (valor_bruto_total * (percentual_desconto / Decimal(100))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            logger.info(f"Rule discount calculated: {valor_desconto_regra}")
        else:
            logger.info("No applicable discount rule found or discount is zero.")

    # 5. Calculate Approved Discount (Initially 0 if requested)
    logger.debug("Step 5: Setting initial Approved Discount.")
    valor_desconto_aprovado = Decimal("0.00") # This will be updated if a discount request is approved later

    # 6. Calculate Net Value
    logger.debug("Step 6: Calculating Net Value.")
    valor_liquido_total = valor_bruto_total - valor_desconto_regra - valor_desconto_aprovado
    if valor_liquido_total < 0: 
        logger.warning(f"Net value calculated as negative ({valor_liquido_total}). Setting to 0.00.")
        valor_liquido_total = Decimal("0.00")  # Don't allow negative value
    logger.info(f"Net Value calculated: {valor_liquido_total} (Gross: {valor_bruto_total}, Rule Discount: {valor_desconto_regra}, Approved Discount (initial): {valor_desconto_aprovado})")

    # 7. Generate Sale Document (using UUID for initial simplicity)
    documento_venda = f"V-{uuid.uuid4()}"
    logger.info(f"Generated Sale Document ID: {documento_venda}")

    # --- Start Transaction ---
    logger.info("Starting database transaction for sale creation.")
    try:
        with DatabaseConnection() as conn:
            now = datetime.now()
            
            cursor = conn.cursor()
            conn.autocommit = False  # Start a transaction
            logger.debug("Database autocommit disabled for transaction.")
            
            # 7.5 Buscar dependente_id do odontograma se houver
            dependente_id_venda = None
            if venda_in.odontograma_id:
                cursor.execute("""
                    SELECT dependente_id 
                    FROM odontogramas 
                    WHERE id = %s
                """, (venda_in.odontograma_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    dependente_id_venda = result[0]
                    logger.info(f"Odontograma ID {venda_in.odontograma_id} pertence ao dependente ID {dependente_id_venda}")
            # Se não tiver dependente_id do odontograma, usar o da venda se existir
            elif hasattr(venda_in, 'dependente_id') and venda_in.dependente_id:
                dependente_id_venda = venda_in.dependente_id
            
            # 8. Create Venda object
            logger.debug("Step 8: Creating Venda (Sale) record in database.")
            
            # Definir campos de entrada se houver entrada configurada
            valor_entrada_venda = None
            tipo_cobranca_venda = None
            entrada_automatica_venda = False
            
            if venda_in.valor_entrada and venda_in.valor_entrada > 0:
                valor_entrada_venda = venda_in.valor_entrada
                tipo_cobranca_venda = 'entrada'
                entrada_automatica_venda = True
                logger.info(f"Marcando venda normal com entrada: R$ {valor_entrada_venda}")
            
            # Regular insert without tipo_venda for non-contract types
            cursor.execute("""
                INSERT INTO vendas (
                    documento_venda, paciente_id, dentista_orcamentista_id, odontograma_id,
                    unidade, data_venda, valor_bruto_total, valor_desconto_regra, 
                    valor_desconto_solicitado, valor_desconto_aprovado, valor_liquido_total,
                    forma_pagamento_id, qtd_parcelas, usuario_venda_id, status_venda, dependente_id,
                    valor_entrada, tipo_cobranca_inicial, entrada_automatica, pre_venda_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                documento_venda, 
                venda_in.paciente_id,
                venda_in.dentista_orcamentista_id,
                venda_in.odontograma_id,
                unidade_venda,
                now,
                valor_bruto_total,
                valor_desconto_regra,
                venda_in.valor_desconto_solicitado or Decimal("0.00"),
                valor_desconto_aprovado,
                valor_liquido_total,
                venda_in.forma_pagamento_id,
                venda_in.qtd_parcelas,
                usuario_id,
                'Efetuada',
                dependente_id_venda,
                valor_entrada_venda,
                tipo_cobranca_venda,
                entrada_automatica_venda,
                venda_in.pre_venda_id  # Usar pre_venda_id da venda
            ))
            
            venda_id = cursor.fetchone()[0]
            logger.info(f"Venda record created successfully with ID: {venda_id}")

            sync_venda_akimais_flags_conn(
                conn=conn,
                venda_id=venda_id,
                pre_venda_id=venda_in.pre_venda_id,
            )
            
            # 9. Create Installments
            logger.debug(f"Step 9: Creating {venda_in.qtd_parcelas} installments for Venda ID: {venda_id}.")

            # Calcular parcelas normalmente para vendas não-contrato
            logger.info(f"Calculating installment values by dividing total: {valor_liquido_total} by {venda_in.qtd_parcelas}")
            valores_parcelas = calcular_valores_parcelas(valor_liquido_total, venda_in.qtd_parcelas)
                
            # Usar data de vencimento da primeira parcela como base
            datas_vencimento = calcular_datas_vencimento(venda_in.data_vencimento_primeira_parcela, venda_in.qtd_parcelas)

            # Se temos valor de entrada e forma de pagamento da entrada, usar para primeira parcela
            if venda_in.valor_entrada and venda_in.valor_entrada > 0 and venda_in.qtd_parcelas > 0:
                # A primeira parcela será o valor da entrada
                valores_parcelas[0] = venda_in.valor_entrada
                # Se fornecido forma_pagamento_entrada_id, salvar em campo adicional

            for i in range(venda_in.qtd_parcelas):
                num_parc = i + 1
                doc_ref = f"{documento_venda}/{num_parc:02}"  # Ex: V-UUID/01
                logger.debug(f"Creating installment {num_parc}/{venda_in.qtd_parcelas}: Value {valores_parcelas[i]}, Due Date {datas_vencimento[i]}, Doc Ref {doc_ref}")
                
                # Todas as parcelas são criadas como "Pendente" (inclusive a entrada)
                cursor.execute("""
                    INSERT INTO venda_parcelas (
                        venda_id, numero_parcela, valor_parcela, data_vencimento,
                        status_parcela, documento_referencia, forma_pagamento_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    venda_id,
                    num_parc,
                    valores_parcelas[i],
                    datas_vencimento[i],
                    'Pendente',  # Todas como "Pendente"
                    doc_ref,
                    # Use a forma de pagamento da entrada para a primeira parcela se aplicável,
                    # caso contrário use a forma de pagamento principal
                    venda_in.forma_pagamento_entrada_id if i == 0 and venda_in.valor_entrada and venda_in.valor_entrada > 0 and venda_in.forma_pagamento_entrada_id else venda_in.forma_pagamento_id
                ))
            
            logger.info(f"Successfully created {venda_in.qtd_parcelas} installments for Venda ID: {venda_id}.")
                
            # 10. Create Discount Request (if applicable)
            logger.debug("Step 10: Checking for and creating Discount Request if applicable.")
            if venda_in.valor_desconto_solicitado and venda_in.valor_desconto_solicitado > 0:
                logger.info(f"Creating discount request for Venda ID {venda_id}: Value {venda_in.valor_desconto_solicitado}, Justification '{venda_in.justificativa_desconto}'.")
                percentual_solicitado = None
                if valor_bruto_total > 0:
                    percentual_solicitado = (venda_in.valor_desconto_solicitado / valor_bruto_total * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    logger.debug(f"Calculated requested discount percentage: {percentual_solicitado}%")
                
                cursor.execute("""
                    INSERT INTO solicitacoes_desconto (
                        venda_id, unidade, valor_solicitado, percentual_solicitado,
                        justificativa, usuario_solicitante_id, status_aprovacao, data_solicitacao
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    venda_id,
                    unidade_venda,
                    venda_in.valor_desconto_solicitado,
                    percentual_solicitado,
                    venda_in.justificativa_desconto,
                    usuario_id,
                    'Pendente',
                    now
                ))
                solicitacao_id = cursor.fetchone()[0]
                logger.info(f"Discount request created successfully with ID: {solicitacao_id} for Venda ID: {venda_id}.")
            else:
                logger.info(f"No extra discount requested for Venda ID: {venda_id}.")
                
            # 11. Commit the Transaction
            logger.debug("Step 11: Committing the transaction.")
            conn.commit()
            logger.info(f"Transaction committed successfully for Venda ID: {venda_id}.")
            
            # 11.5 Criar fatura avulsa automaticamente se for PIX AVULSO DELTA
            criar_fatura_automatica(venda_id, conn)
            
            # 12. Return the created sale
            logger.debug(f"Step 12: Retrieving and returning the created sale details for Venda ID: {venda_id}.")
            return read_venda(venda_id) # Calls the read_venda function which has its own logging

    except Exception as e:
        logger.error(f"Exception during sale creation process for payload: {venda_in.model_dump_json()}. Rolling back transaction.")
        if 'conn' in locals() and conn and not conn.autocommit: # Check if conn was defined and transaction started
            conn.rollback()
            logger.info("Transaction rolled back due to error.")
        logger.error(f"Detailed error when creating sale: {e}", exc_info=True) # exc_info=True will log the traceback
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating sale: {str(e)}")

@router.get("/", response_model=List[VendaRead])
def read_vendas(
    skip: int = 0,
    limit: int = 100,
    paciente_id: Optional[int] = None,
    unidade: Optional[str] = None,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    status_venda: Optional[str] = None,
    dependente_id: Optional[int] = None,
    incluir_dependentes: Optional[bool] = None
):
    """
    Returns a list of sales with filters and pagination.
    """
    logger.info(f"Reading sales with parameters: skip={skip}, limit={limit}, paciente_id={paciente_id}, "
                f"unidade='{unidade}', data_inicio={data_inicio}, data_fim={data_fim}, status_venda='{status_venda}', "
                f"dependente_id={dependente_id}, incluir_dependentes={incluir_dependentes}")
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Build the base query
        query = """
            SELECT 
                v.id, v.documento_venda, v.paciente_id, v.dentista_orcamentista_id, 
                v.odontograma_id, v.unidade, v.data_venda, v.valor_bruto_total, 
                v.valor_desconto_regra, v.valor_desconto_solicitado, v.valor_desconto_aprovado, 
                v.valor_liquido_total, v.forma_pagamento_id, v.qtd_parcelas, 
                v.usuario_venda_id, v.status_venda, v.data_cancelamento, 
                v.usuario_cancelamento_id, v.motivo_cancelamento, v.created_at, v.updated_at,
                v.dependente_id
            FROM vendas v
        """
        
        # Apply filters
        where_clauses = []
        params = []
        
        if paciente_id is not None:
            logger.debug(f"Applying filter: paciente_id = {paciente_id}")
            where_clauses.append("v.paciente_id = %s")
            params.append(paciente_id)
            
        if unidade:
            logger.debug(f"Applying filter: unidade ILIKE '%{unidade}%'")
            where_clauses.append("v.unidade ILIKE %s")
            params.append(f"%{unidade}%")
            
        if data_inicio:
            logger.debug(f"Applying filter: data_venda >= {data_inicio}")
            where_clauses.append("v.data_venda >= %s")
            params.append(datetime.combine(data_inicio, datetime.min.time()))
            
        if data_fim:
            logger.debug(f"Applying filter: data_venda <= {data_fim}")
            where_clauses.append("v.data_venda <= %s")
            params.append(datetime.combine(data_fim, datetime.max.time()))
            
        if status_venda:
            logger.debug(f"Applying filter: status_venda = '{status_venda}'")
            where_clauses.append("v.status_venda = %s")
            params.append(status_venda)
        
        if dependente_id is not None:
            logger.debug(f"Applying filter: dependente_id = {dependente_id}")
            where_clauses.append("v.dependente_id = %s")
            params.append(dependente_id)
        
        if incluir_dependentes is False:
            logger.debug("Applying filter: only titular sales (dependente_id IS NULL)")
            where_clauses.append("v.dependente_id IS NULL")
        elif incluir_dependentes is True:
            logger.debug("Applying filter: only dependent sales (dependente_id IS NOT NULL)")
            where_clauses.append("v.dependente_id IS NOT NULL")
            
        # Add WHERE clause if any filters are applied
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            logger.debug(f"WHERE clause: {' AND '.join(where_clauses)}")
            
        # Add ORDER BY, OFFSET, and LIMIT
        query += " ORDER BY v.data_venda DESC OFFSET %s LIMIT %s"
        params.extend([skip, limit])
        logger.debug(f"Final query (params ommited for brevity): {query}")
        logger.debug(f"Query parameters: {params}")
        
        # Execute the main query
        cursor.execute(query, params)
        vendas_rows = cursor.fetchall()
        logger.info(f"Found {len(vendas_rows)} sales matching criteria.")
        
        # Prepare result list
        vendas_result = []
        
        # For each venda, load related data
        logger.debug(f"Fetching related data for {len(vendas_rows)} sales.")
        for idx, venda_row in enumerate(vendas_rows):
            venda_id = venda_row[0]
            logger.debug(f"Processing sale #{idx+1} (ID: {venda_id})")
            venda_dict = {
                "id": venda_id,
                "documento_venda": venda_row[1],
                "paciente_id": venda_row[2],
                "dentista_orcamentista_id": venda_row[3],
                "odontograma_id": venda_row[4],
                "unidade": venda_row[5],
                "data_venda": venda_row[6],
                "valor_bruto_total": venda_row[7],
                "valor_desconto_regra": venda_row[8],
                "valor_desconto_solicitado": venda_row[9],
                "valor_desconto_aprovado": venda_row[10],
                "valor_liquido_total": venda_row[11],
                "forma_pagamento_id": venda_row[12],
                "qtd_parcelas": venda_row[13],
                "usuario_venda_id": venda_row[14],
                "status_venda": venda_row[15],
                "data_cancelamento": venda_row[16],
                "usuario_cancelamento_id": venda_row[17],
                "motivo_cancelamento": venda_row[18],
                "created_at": venda_row[19],
                "updated_at": venda_row[20],
                "dependente_id": venda_row[21],
                "parcelas": [],
                "solicitacao_desconto": None,
                "paciente": None,
                "dentista_orcamentista": None,
                "forma_pagamento": None,
                "dependente": None
            }
            
            # Get parcelas
            logger.debug(f"Fetching installments for sale ID: {venda_id}")
            cursor.execute("""
                SELECT id, venda_id, numero_parcela, valor_parcela, data_vencimento,
                       status_parcela, data_pagamento, valor_pago, documento_referencia,
                       created_at, updated_at
                FROM venda_parcelas
                WHERE venda_id = %s
            """, (venda_id,))
            parcelas_rows = cursor.fetchall()
            logger.debug(f"Found {len(parcelas_rows)} installments for sale ID: {venda_id}")
            venda_dict["parcelas"] = [
                VendaParcelaRead(**{
                    "id": row[0], "venda_id": row[1], "numero_parcela": row[2], 
                    "valor_parcela": row[3], "data_vencimento": row[4], "status_parcela": row[5],
                    "data_pagamento": row[6], "valor_pago": row[7], "documento_referencia": row[8],
                    "created_at": row[9], "updated_at": row[10]
                }).model_dump() for row in parcelas_rows # Pydantic model for validation before assignment
            ]
            
            # Get solicitacao_desconto if any
            logger.debug(f"Fetching discount request for sale ID: {venda_id}")
            cursor.execute("""
                SELECT id, venda_id, unidade, valor_solicitado, percentual_solicitado,
                       justificativa, usuario_solicitante_id, status_aprovacao,
                       data_solicitacao, usuario_aprovador_id, data_aprovacao,
                       observacao_aprovador, created_at, updated_at
                FROM solicitacoes_desconto
                WHERE venda_id = %s
            """, (venda_id,))
            solicitacao_row = cursor.fetchone()
            if solicitacao_row:
                logger.debug(f"Discount request found for sale ID: {venda_id}")
                venda_dict["solicitacao_desconto"] = SolicitacaoDescontoRead(**{
                    "id": solicitacao_row[0], "venda_id": solicitacao_row[1], "unidade": solicitacao_row[2],
                    "valor_solicitado": solicitacao_row[3], "percentual_solicitado": solicitacao_row[4],
                    "justificativa": solicitacao_row[5], "usuario_solicitante_id": solicitacao_row[6],
                    "status_aprovacao": solicitacao_row[7], "data_solicitacao": solicitacao_row[8],
                    "usuario_aprovador_id": solicitacao_row[9], "data_aprovacao": solicitacao_row[10],
                    "observacao_aprovador": solicitacao_row[11], "created_at": solicitacao_row[12],
                    "updated_at": solicitacao_row[13]
                }).model_dump()
            else:
                logger.debug(f"No discount request found for sale ID: {venda_id}")
                
            # Get paciente data
            logger.debug(f"Fetching patient data (ID: {venda_dict['paciente_id']}) for sale ID: {venda_id}")
            cursor.execute("""
                SELECT paciente_id, nome_paciente, cpf_cnpj, email, data_nascimento,
                       is_minor, responsavel_id, phone_country_code, phone_area_code,
                       phone_number, street, street_number, neighborhood, city, state,
                       zip_code, created_at, updated_at, unidade
                FROM pacientes
                WHERE paciente_id = %s
            """, (venda_dict["paciente_id"],))
            paciente_row = cursor.fetchone()
            if paciente_row:
                venda_dict["paciente"] = _row_to_paciente_read(paciente_row).model_dump()
                logger.debug(f"Patient data fetched for sale ID: {venda_id}")
            else:
                logger.warning(f"Patient data not found for patient_id {venda_dict['paciente_id']} (Sale ID: {venda_id})")
                
            # Get dentist data
            logger.debug(f"Fetching dentist data (ID: {venda_dict['dentista_orcamentista_id']}) for sale ID: {venda_id}")
            cursor.execute("""
                SELECT id, nome, funcao, created_at, updated_at
                FROM dentistas
                WHERE id = %s
            """, (venda_dict["dentista_orcamentista_id"],))

            dentista_row = cursor.fetchone()
            if dentista_row:
                venda_dict["dentista_orcamentista"] = DentistaRead(**{
                    "id": dentista_row[0], "nome": dentista_row[1], "especialidade": dentista_row[2],
                    "created_at": dentista_row[3], "updated_at": dentista_row[4]
                }).model_dump()
                logger.debug(f"Dentist data fetched for sale ID: {venda_id}")
            else:
                logger.warning(f"Dentist data not found for dentista_id {venda_dict['dentista_orcamentista_id']} (Sale ID: {venda_id})")

            # Get payment method data
            logger.debug(f"Fetching payment method data (ID: {venda_dict['forma_pagamento_id']}) for sale ID: {venda_id}")
            cursor.execute("""
                SELECT id, nome, ativo, created_at, updated_at
                FROM formas_pagamento
                WHERE id = %s
            """, (venda_dict["forma_pagamento_id"],))
            pagamento_row = cursor.fetchone()
            if pagamento_row:
                venda_dict["forma_pagamento"] = FormaPagamentoRead(**{
                    "id": pagamento_row[0], "nome": pagamento_row[1], "ativo": pagamento_row[2],
                    "created_at": pagamento_row[3], "updated_at": pagamento_row[4]
                }).model_dump()
                logger.debug(f"Payment method data fetched for sale ID: {venda_id}")
            else:
                 logger.warning(f"Payment method data not found for forma_pagamento_id {venda_dict['forma_pagamento_id']} (Sale ID: {venda_id})")
            
            # Get dependente data if exists
            if venda_dict["dependente_id"]:
                logger.debug(f"Fetching dependent data (ID: {venda_dict['dependente_id']}) for sale ID: {venda_id}")
                cursor.execute("""
                    SELECT dependente_id, responsavel_paciente_id, nome_dependente, 
                           data_nascimento_dependente, genero_dependente, parentesco, 
                           observacoes_dependente, ativo, created_at, updated_at
                    FROM dependentes
                    WHERE dependente_id = %s
                """, (venda_dict["dependente_id"],))
                dependente_row = cursor.fetchone()
                if dependente_row:
                    venda_dict["dependente"] = {
                        "dependente_id": dependente_row[0],
                        "responsavel_paciente_id": dependente_row[1],
                        "nome_dependente": dependente_row[2],
                        "data_nascimento_dependente": dependente_row[3],
                        "genero_dependente": dependente_row[4],
                        "parentesco": dependente_row[5],
                        "observacoes_dependente": dependente_row[6],
                        "ativo": dependente_row[7],
                        "created_at": dependente_row[8],
                        "updated_at": dependente_row[9]
                    }
                    logger.debug(f"Dependent data fetched for sale ID: {venda_id}")
                else:
                    logger.warning(f"Dependent data not found for dependente_id {venda_dict['dependente_id']} (Sale ID: {venda_id})")
                
            # Add to result list
            vendas_result.append(VendaRead(**venda_dict)) # Validate with Pydantic model
            
        logger.info(f"Successfully prepared {len(vendas_result)} sales for response.")
        return vendas_result


@router.get("/{venda_id}", response_model=VendaRead)
def read_venda(venda_id: int):
    """
    Returns the complete details of a specific sale.
    """
    logger.info(f"Reading details for sale ID: {venda_id}")
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Get main venda data
        logger.debug(f"Fetching main data for sale ID: {venda_id}")
        cursor.execute("""
            SELECT 
                id, documento_venda, paciente_id, dentista_orcamentista_id, 
                odontograma_id, unidade, data_venda, valor_bruto_total, 
                valor_desconto_regra, valor_desconto_solicitado, valor_desconto_aprovado, 
                valor_liquido_total, forma_pagamento_id, qtd_parcelas, 
                usuario_venda_id, status_venda, data_cancelamento, 
                usuario_cancelamento_id, motivo_cancelamento, created_at, updated_at,
                dependente_id
            FROM vendas
            WHERE id = %s
        """, (venda_id,))
        
        venda_row = cursor.fetchone()
        if not venda_row:
            logger.error(f"Sale with ID {venda_id} not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
        logger.info(f"Main data found for sale ID: {venda_id}")
            
        venda_dict = {
            "id": venda_row[0],
            "documento_venda": venda_row[1],
            "paciente_id": venda_row[2],
            "dentista_orcamentista_id": venda_row[3],
            "odontograma_id": venda_row[4],
            "unidade": venda_row[5],
            "data_venda": venda_row[6],
            "valor_bruto_total": venda_row[7],
            "valor_desconto_regra": venda_row[8],
            "valor_desconto_solicitado": venda_row[9],
            "valor_desconto_aprovado": venda_row[10],
            "valor_liquido_total": venda_row[11],
            "forma_pagamento_id": venda_row[12],
            "qtd_parcelas": venda_row[13],
            "usuario_venda_id": venda_row[14],
            "status_venda": venda_row[15],
            "data_cancelamento": venda_row[16],
            "usuario_cancelamento_id": venda_row[17],
            "motivo_cancelamento": venda_row[18],
            "created_at": venda_row[19],
            "updated_at": venda_row[20],
            "dependente_id": venda_row[21],
            "parcelas": [],
            "solicitacao_desconto": None,
            "paciente": None,
            "dentista_orcamentista": None,
            "forma_pagamento": None,
            "dependente": None
        }
        
        # Get parcelas
        logger.debug(f"Fetching installments for sale ID: {venda_id}")
        cursor.execute("""
            SELECT installment.id, installment.venda_id,
                   installment.numero_parcela, installment.valor_parcela,
                   installment.data_vencimento,
                   CASE
                       WHEN resource.remote_status IN ('CONFIRMED', 'RECEIVED', 'RECEIVED_IN_CASH') THEN 'Pago'
                       WHEN resource.remote_status IN ('REFUNDED', 'PARTIALLY_REFUNDED', 'REFUND_REQUESTED', 'REFUND_IN_PROGRESS') THEN 'Estornado'
                       WHEN resource.remote_status IN ('CHARGEBACK_REQUESTED', 'CHARGEBACK_DISPUTE', 'AWAITING_CHARGEBACK_REVERSAL') THEN 'Disputa'
                       WHEN resource.remote_status IN ('CANCELLED', 'CANCELED') THEN 'Cancelada'
                       WHEN resource.remote_status = 'OVERDUE' THEN 'Vencido'
                       ELSE installment.status_parcela
                   END AS status_parcela,
                   CASE
                       WHEN resource.remote_status IN ('CONFIRMED', 'RECEIVED', 'RECEIVED_IN_CASH')
                       THEN COALESCE(installment.data_pagamento, payment_event.paid_at, resource.last_event_at)
                       ELSE installment.data_pagamento
                   END AS data_pagamento,
                   CASE
                       WHEN resource.remote_status IN ('CONFIRMED', 'RECEIVED', 'RECEIVED_IN_CASH')
                       THEN COALESCE(installment.valor_pago, installment.valor_parcela)
                       ELSE installment.valor_pago
                   END AS valor_pago,
                   installment.documento_referencia,
                   installment.created_at,
                   GREATEST(installment.updated_at, resource.updated_at) AS updated_at
            FROM venda_parcelas installment
            LEFT JOIN asaas_sale_integrations integration
              ON integration.venda_id = installment.venda_id
            LEFT JOIN asaas_sale_payment_links payment_link
              ON payment_link.integration_id = integration.id
             AND payment_link.venda_id = installment.venda_id
             AND payment_link.numero_parcela = installment.numero_parcela
            LEFT JOIN asaas_sale_resources resource
              ON resource.id = payment_link.resource_id
             AND resource.resource_type = 'payment'
            LEFT JOIN (
                SELECT webhook.resource_id,
                       MIN(
                           COALESCE(
                               NULLIF(webhook.technical_data #>> '{payment,paymentDate}', '')::timestamptz,
                               NULLIF(webhook.technical_data #>> '{payment,confirmedDate}', '')::timestamptz,
                               NULLIF(webhook.technical_data #>> '{payment,clientPaymentDate}', '')::timestamptz,
                               NULLIF(webhook.technical_data ->> 'dateCreated', '')::timestamptz
                           )
                       ) AS paid_at
                FROM asaas_sale_webhook_events webhook
                WHERE webhook.status = 'processado'
                  AND webhook.event_type IN (
                      'PAYMENT_CONFIRMED',
                      'PAYMENT_RECEIVED',
                      'PAYMENT_RECEIVED_IN_CASH'
                  )
                GROUP BY webhook.resource_id
            ) payment_event
              ON payment_event.resource_id = resource.id
            WHERE installment.venda_id = %s
            ORDER BY installment.numero_parcela
        """, (venda_id,))
        parcelas_rows = cursor.fetchall()
        logger.debug(f"Found {len(parcelas_rows)} installments for sale ID: {venda_id}")
        venda_dict["parcelas"] = [
            VendaParcelaRead(**{
                "id": row[0], "venda_id": row[1], "numero_parcela": row[2], 
                "valor_parcela": row[3], "data_vencimento": row[4], "status_parcela": row[5],
                "data_pagamento": row[6], "valor_pago": row[7], "documento_referencia": row[8],
                "created_at": row[9], "updated_at": row[10]
            }).model_dump() for row in parcelas_rows
        ]
        
        # Get solicitacao_desconto if any
        logger.debug(f"Fetching discount request for sale ID: {venda_id}")
        cursor.execute("""
            SELECT id, venda_id, unidade, valor_solicitado, percentual_solicitado,
                   justificativa, usuario_solicitante_id, status_aprovacao,
                   data_solicitacao, usuario_aprovador_id, data_aprovacao,
                   observacao_aprovador, created_at, updated_at
            FROM solicitacoes_desconto
            WHERE venda_id = %s
        """, (venda_id,))
        solicitacao_row = cursor.fetchone()
        if solicitacao_row:
            logger.debug(f"Discount request found for sale ID: {venda_id}")
            venda_dict["solicitacao_desconto"] = SolicitacaoDescontoRead(**{
                "id": solicitacao_row[0], "venda_id": solicitacao_row[1], "unidade": solicitacao_row[2],
                "valor_solicitado": solicitacao_row[3], "percentual_solicitado": solicitacao_row[4],
                "justificativa": solicitacao_row[5], "usuario_solicitante_id": solicitacao_row[6],
                "status_aprovacao": solicitacao_row[7], "data_solicitacao": solicitacao_row[8],
                "usuario_aprovador_id": solicitacao_row[9], "data_aprovacao": solicitacao_row[10],
                "observacao_aprovador": solicitacao_row[11], "created_at": solicitacao_row[12],
                "updated_at": solicitacao_row[13]
            }).model_dump()
        else:
            logger.debug(f"No discount request found for sale ID: {venda_id}")
            
        # Get paciente data
        logger.debug(f"Fetching patient data (ID: {venda_dict['paciente_id']}) for sale ID: {venda_id}")
        cursor.execute("""
            SELECT paciente_id, nome_paciente, cpf_cnpj, email, data_nascimento,
                   is_minor, responsavel_id, phone_country_code, phone_area_code,
                   phone_number, street, street_number, neighborhood, city, state,
                   zip_code, created_at, updated_at, unidade
            FROM pacientes
            WHERE paciente_id = %s
        """, (venda_dict["paciente_id"],))
        paciente_row = cursor.fetchone()
        if paciente_row:
            venda_dict["paciente"] = _row_to_paciente_read(paciente_row).model_dump()
            logger.debug(f"Patient data fetched for sale ID: {venda_id}")
        else:
            logger.warning(f"Patient data not found for patient_id {venda_dict['paciente_id']} (Sale ID: {venda_id})")
            
        # Get dentist data
        logger.debug(f"Fetching dentist data (ID: {venda_dict['dentista_orcamentista_id']}) for sale ID: {venda_id}")
        cursor.execute("""
            SELECT id, nome, funcao, created_at, updated_at
            FROM dentistas
            WHERE id = %s
        """, (venda_dict["dentista_orcamentista_id"],))

        dentista_row = cursor.fetchone()
        if dentista_row:
            venda_dict["dentista_orcamentista"] = DentistaRead(**{
                "id": dentista_row[0], "nome": dentista_row[1], "especialidade": dentista_row[2],
                "created_at": dentista_row[3], "updated_at": dentista_row[4]
            }).model_dump()
            logger.debug(f"Dentist data fetched for sale ID: {venda_id}")
        else:
            logger.warning(f"Dentist data not found for dentista_id {venda_dict['dentista_orcamentista_id']} (Sale ID: {venda_id})")
            
        # Get payment method data
        logger.debug(f"Fetching payment method data (ID: {venda_dict['forma_pagamento_id']}) for sale ID: {venda_id}")
        cursor.execute("""
            SELECT id, nome, ativo, created_at, updated_at
            FROM formas_pagamento
            WHERE id = %s
        """, (venda_dict["forma_pagamento_id"],))
        pagamento_row = cursor.fetchone()
        if pagamento_row:
            venda_dict["forma_pagamento"] = FormaPagamentoRead(**{
                "id": pagamento_row[0], "nome": pagamento_row[1], "ativo": pagamento_row[2],
                "created_at": pagamento_row[3], "updated_at": pagamento_row[4]
            }).model_dump()
            logger.debug(f"Payment method data fetched for sale ID: {venda_id}")
        else:
            logger.warning(f"Payment method data not found for forma_pagamento_id {venda_dict['forma_pagamento_id']} (Sale ID: {venda_id})")
        
        # Get dependente data if exists
        if venda_dict["dependente_id"]:
            logger.debug(f"Fetching dependent data (ID: {venda_dict['dependente_id']}) for sale ID: {venda_id}")
            cursor.execute("""
                SELECT dependente_id, responsavel_paciente_id, nome_dependente, 
                       data_nascimento_dependente, genero_dependente, parentesco, 
                       observacoes_dependente, ativo, created_at, updated_at
                FROM dependentes
                WHERE dependente_id = %s
            """, (venda_dict["dependente_id"],))
            dependente_row = cursor.fetchone()
            if dependente_row:
                venda_dict["dependente"] = {
                    "dependente_id": dependente_row[0],
                    "responsavel_paciente_id": dependente_row[1],
                    "nome_dependente": dependente_row[2],
                    "data_nascimento_dependente": dependente_row[3],
                    "genero_dependente": dependente_row[4],
                    "parentesco": dependente_row[5],
                    "observacoes_dependente": dependente_row[6],
                    "ativo": dependente_row[7],
                    "created_at": dependente_row[8],
                    "updated_at": dependente_row[9]
                }
                logger.debug(f"Dependent data fetched for sale ID: {venda_id}")
            else:
                logger.warning(f"Dependent data not found for dependente_id {venda_dict['dependente_id']} (Sale ID: {venda_id})")
            
        logger.info(f"Successfully prepared details for sale ID: {venda_id}.")
        return VendaRead(**venda_dict)


@router.put("/{venda_id}/cancelar", response_model=VendaRead)
def cancel_venda(
    venda_id: int,
    payload: VendaCancelUpdate, # Uses Pydantic model for the body
    current_user: Optional[User] = None
):
    """
    Cancel an existing sale. Updates the sale status and pending installments.
    """
    logger.info(f"Attempting to cancel sale ID: {venda_id}. Reason: '{payload.motivo_cancelamento}'")
    now = datetime.now()
    usuario_id = 1  # Default user ID if current_user is None
    if current_user and hasattr(current_user, 'id'):
        usuario_id = current_user.id
    logger.info(f"Sale cancellation initiated by user ID: {usuario_id} for Venda ID: {venda_id}")
    
    with DatabaseConnection() as conn:
        try:
            conn.autocommit = False  # Start a transaction
            logger.debug(f"Database autocommit disabled for transaction (Cancel Venda ID: {venda_id}).")
            cursor = conn.cursor()
            
            # Check if the sale exists
            logger.debug(f"Checking existence and status of sale ID: {venda_id}")
            cursor.execute("SELECT id, status_venda FROM vendas WHERE id = %s", (venda_id,))
            venda_row = cursor.fetchone()
            
            if not venda_row:
                logger.error(f"Sale ID {venda_id} not found for cancellation.")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
                
            if venda_row[1] == 'Cancelada':
                logger.warning(f"Sale ID {venda_id} is already cancelled. No action taken.")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sale is already cancelled.")
            logger.info(f"Sale ID {venda_id} found with status '{venda_row[1]}'. Proceeding with cancellation.")
                
            # Update venda status
            logger.debug(f"Updating status of sale ID: {venda_id} to 'Cancelada'.")
            cursor.execute("""
                UPDATE vendas
                SET status_venda = 'Cancelada',
                    data_cancelamento = %s,
                    usuario_cancelamento_id = %s,
                    motivo_cancelamento = %s,
                    updated_at = %s
                WHERE id = %s
            """, (now, usuario_id, payload.motivo_cancelamento, now, venda_id))
            logger.info(f"Sale ID: {venda_id} status updated to 'Cancelada'.")
            
            # Cancel associated pending installments
            logger.debug(f"Updating pending installments for sale ID: {venda_id} to 'Cancelada'.")
            cursor.execute("""
                UPDATE venda_parcelas
                SET status_parcela = 'Cancelada',
                    updated_at = %s
                WHERE venda_id = %s AND status_parcela = 'Pendente'
            """, (now, venda_id))
            updated_installments = cursor.rowcount
            logger.info(f"{updated_installments} pending installments for sale ID: {venda_id} updated to 'Cancelada'.")
            
            # Cancel pending discount request, if any
            logger.debug(f"Updating pending discount requests for sale ID: {venda_id} to 'Cancelado (Venda)'.")
            cursor.execute("""
                UPDATE solicitacoes_desconto
                SET status_aprovacao = 'Cancelado (Venda)',
                    data_aprovacao = %s, /* Using data_aprovacao for cancellation timestamp of request */
                    updated_at = %s
                WHERE venda_id = %s AND status_aprovacao = 'Pendente'
            """, (now, now, venda_id))
            updated_discount_requests = cursor.rowcount
            if updated_discount_requests > 0:
                logger.info(f"{updated_discount_requests} pending discount requests for sale ID: {venda_id} updated to 'Cancelado (Venda)'.")
            else:
                logger.info(f"No pending discount requests found to cancel for sale ID: {venda_id}.")
            
            # Commit the transaction
            logger.debug(f"Committing transaction for cancellation of sale ID: {venda_id}.")
            conn.commit()
            logger.info(f"Transaction committed successfully for cancellation of sale ID: {venda_id}.")
            
            # Return the updated sale using the get function
            logger.debug(f"Retrieving and returning the updated sale details for Venda ID: {venda_id} after cancellation.")
            return read_venda(venda_id) # This function already has logging
            
        except HTTPException as http_exc: # Re-raise HTTPExceptions to be handled by FastAPI
            logger.warning(f"HTTPException during cancellation of sale ID {venda_id}: {http_exc.detail}")
            if conn and not conn.autocommit: conn.rollback() # Rollback on known errors too if transaction was started
            raise http_exc
        except Exception as e:
            logger.error(f"Exception during cancellation of sale ID {venda_id}. Rolling back transaction.")
            if conn and not conn.autocommit: # Check if conn exists and transaction was started
                conn.rollback()
                logger.info(f"Transaction rolled back for sale ID: {venda_id} due to error.")
            logger.error(f"Error when cancelling sale {venda_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Error cancelling sale: {str(e)}"
            )
