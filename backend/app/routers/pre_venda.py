# backend/app/routers/pre_venda.py

import logging
import uuid
from datetime import datetime, timedelta, timezone
import pytz
from typing import Optional, List
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Import database and models
from ..database.db import get_db, DatabaseConnection
from ..models.pre_venda_entrada import PreVendaEntrada
# from ..models.fatura_avulsa import FaturaAvulsaCreateRequest  # Não usado para pré-vendas
from ..services.fatura_service import criar_fatura_avulsa_service

# Import existing schemas (removidos - não estão sendo usados)

logger = logging.getLogger(__name__)

# Função auxiliar para converter UTC para horário do Brasil
def converter_utc_para_brasil(timestamp_utc):
    """
    Converte timestamp UTC para timezone do Brasil (UTC-3)
    """
    if timestamp_utc is None:
        return None
    
    # Definir timezone do Brasil
    brasil_tz = pytz.timezone('America/Sao_Paulo')
    
    # Se o timestamp não tem timezone, assumir que é UTC
    if timestamp_utc.tzinfo is None:
        timestamp_utc = pytz.utc.localize(timestamp_utc)
    elif timestamp_utc.tzinfo != pytz.utc:
        # Se já tem timezone, converter para UTC primeiro
        timestamp_utc = timestamp_utc.astimezone(pytz.utc)
    
    # Converter para horário do Brasil
    timestamp_brasil = timestamp_utc.astimezone(brasil_tz)
    return timestamp_brasil

# Schemas
class PreVendaEntradaCreate(BaseModel):
    """Schema para criar uma pré-venda com entrada"""
    tipo_odontograma: str
    tipo_odontograma_id: Optional[int] = None  # ID do tipo de odontograma
    paciente_id: int
    dependente_id: Optional[int] = None
    dentista_id: int
    unidade: str
    valor_entrada: Decimal = Field(..., ge=0, decimal_places=2)  # Permitir valor 0 para entrada opcional
    forma_pagamento_id: int
    
    # Dados adicionais para criar a venda posteriormente
    valor_total: Decimal = Field(..., gt=0, decimal_places=2)
    numero_parcelas: int = Field(..., ge=1)
    odontograma_id: Optional[int] = None
    
    # Metadados opcionais
    metadata: Optional[dict] = None

class PreVendaEntradaResponse(BaseModel):
    """Resposta ao criar pré-venda"""
    pre_venda_id: str
    checkout_url: str
    valor: Decimal
    expires_at: datetime
    
class PreVendaEntradaStatus(BaseModel):
    """Status de uma pré-venda"""
    pre_venda_id: str
    status: str
    valor_pago: Optional[Decimal] = None
    checkout_id: Optional[str] = None
    created_at: datetime
    expires_at: datetime

class PagamentoEntradaPago(BaseModel):
    """Dados de um pagamento de entrada pago para listagem"""
    id: int
    pre_venda_id: str
    tipo_odontograma: str
    paciente_id: int
    paciente_nome: str
    paciente_cpf: str
    dependente_id: Optional[int] = None
    dentista_id: int
    dentista_nome: str
    vendedor_nome: Optional[str] = None
    unidade: str
    valor_solicitado: Decimal
    valor_pago: Decimal
    forma_pagamento_id: int
    forma_pagamento_nome: str
    checkout_id: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    metadata_json: Optional[dict] = None

class PagamentosEntradaPagosResponse(BaseModel):
    """Response para listagem de pagamentos de entrada pagos"""
    pagamentos: List[PagamentoEntradaPago]
    total: int
    page: int
    size: int
    total_pages: int

# Router
router = APIRouter(
    prefix="/pre-vendas",
    tags=["Pré-Vendas e Entradas"]
)

def validar_entrada_ortodontia(
    forma_pagamento_nome: str,
    valor_entrada: Decimal,
    valor_total: Decimal,
    tipo_odontograma: str
) -> bool:
    """Valida se o valor de entrada é permitido para contratos"""
    
    tipos_contratos = ['Contrato Ortodôntico', 'Combo Orto + ODC', 'Contrato Odontológico + Akimais']
    if tipo_odontograma not in tipos_contratos:
        # Para outros tipos, entrada deve ser maior que 0
        return valor_entrada > 0
    
    # Regras para todos os tipos de contrato
    if forma_pagamento_nome in ['PIX AVULSO DELTA', 'BOLETO AVULSO DELTA']:
        # Entrada opcional - pode ser 0 ou qualquer valor até o total
        return 0 <= valor_entrada <= valor_total
        
    elif forma_pagamento_nome in ['CARTÃO CRÉDITO AVULSO DELTA', 'CARTÃO RECORRENTE']:
        # Entrada flexível - qualquer valor até o total
        return 0 <= valor_entrada <= valor_total
        
    elif forma_pagamento_nome == 'CARNÊ':
        # Entrada fixa - deve ser o valor de 1 parcela (R$ 89,99)
        valor_parcela = Decimal('89.99')
        return abs(valor_entrada - valor_parcela) < Decimal('0.01')
        
    # Para outras formas de pagamento, entrada deve ser maior que 0
    return valor_entrada > 0

@router.get("/entrada/pendentes/{paciente_id}")
async def listar_pre_vendas_pendentes(
    paciente_id: int,
    tipo_odontograma: Optional[str] = None,
    odontograma_id: Optional[int] = None,
    incluir_pagas: Optional[bool] = False,
    db: Session = Depends(get_db)
):
    """
    Lista pré-vendas pendentes (e opcionalmente pagas) de um paciente
    """
    logger.info(f"Buscando pré-vendas - paciente: {paciente_id}, tipo: {tipo_odontograma}, odontograma: {odontograma_id}, incluir_pagas: {incluir_pagas}")
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Preparar filtro de status
            status_filter = "pve.status IN ('pendente', 'pago')" if incluir_pagas else "pve.status = 'pendente'"
            time_filter = "" if incluir_pagas else "AND pve.created_at > NOW() - INTERVAL '30 minutes'"

            if odontograma_id:
                # Buscar por odontograma específico
                query = f"""
                    SELECT
                        pve.pre_venda_id,
                        pve.tipo_odontograma,
                        pve.valor_solicitado,
                        pve.valor_pago,
                        pve.status,
                        pve.checkout_id,
                        pve.checkout_url,
                        pve.created_at,
                        pve.expires_at,
                        fp.nome as forma_pagamento,
                        pve.metadata_json
                    FROM pre_vendas_entradas pve
                    LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
                    WHERE pve.paciente_id = %s
                      AND pve.metadata_json->>'odontograma_id' = %s
                      AND {status_filter}
                      {time_filter}
                    ORDER BY pve.created_at DESC
                """
                cursor.execute(query, (paciente_id, str(odontograma_id)))
            elif tipo_odontograma:
                # Buscar por tipo
                query = f"""
                    SELECT
                        pve.pre_venda_id,
                        pve.tipo_odontograma,
                        pve.valor_solicitado,
                        pve.valor_pago,
                        pve.status,
                        pve.checkout_id,
                        pve.checkout_url,
                        pve.created_at,
                        pve.expires_at,
                        fp.nome as forma_pagamento,
                        pve.metadata_json
                    FROM pre_vendas_entradas pve
                    LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
                    WHERE pve.paciente_id = %s
                      AND pve.tipo_odontograma = %s
                      AND {status_filter}
                      {time_filter}
                    ORDER BY pve.created_at DESC
                """
                cursor.execute(query, (paciente_id, tipo_odontograma))
            else:
                # Buscar todas
                query = f"""
                    SELECT
                        pve.pre_venda_id,
                        pve.tipo_odontograma,
                        pve.valor_solicitado,
                        pve.valor_pago,
                        pve.status,
                        pve.checkout_id,
                        pve.checkout_url,
                        pve.created_at,
                        pve.expires_at,
                        fp.nome as forma_pagamento,
                        pve.metadata_json
                    FROM pre_vendas_entradas pve
                    LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
                    WHERE pve.paciente_id = %s
                      AND {status_filter}
                      {time_filter}
                    ORDER BY pve.created_at DESC
                """
                cursor.execute(query, (paciente_id,))
            
            pre_vendas = cursor.fetchall()
            
            resultado = []
            for pv in pre_vendas:
                from datetime import timezone
                tempo_restante = None
                if pv[8]:  # expires_at
                    tempo_restante = int((pv[8].replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds() / 60)
                
                resultado.append({
                    'pre_venda_id': pv[0],
                    'tipo_odontograma': pv[1],
                    'valor': float(pv[2]),
                    'valor_pago': float(pv[3]) if pv[3] else 0,
                    'status': pv[4],
                    'checkout_id': pv[5],
                    'checkout_url': pv[6],
                    'created_at': pv[7].isoformat() if pv[7] else None,
                    'expires_at': pv[8].isoformat() if pv[8] else None,
                    'forma_pagamento': pv[9],
                    'tempo_restante_minutos': tempo_restante,
                    'metadata': pv[10]
                })
            
            return {
                'pre_vendas_pendentes': resultado,
                'total': len(resultado)
            }
            
    except Exception as e:
        logger.error(f"Erro ao buscar pré-vendas pendentes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entrada/pagas", response_model=PagamentosEntradaPagosResponse)
async def listar_pagamentos_entrada_pagos(
    paciente_id: Optional[int] = None,
    unidade: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    dentista_id: Optional[int] = None,
    tipo_odontograma: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db)
):
    """
    Lista todos os pagamentos de entrada que foram pagos com filtros opcionais
    """
    logger.info(f"Listando pagamentos de entrada pagos - página: {page}, tamanho: {size}")
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Construir query base combinando pré-vendas de entrada e faturas recorrentes
            base_query = """
                (
                    -- Pagamentos de entrada tradicionais
                    SELECT 
                        pve.id,
                        pve.pre_venda_id,
                        pve.tipo_odontograma,
                        pve.paciente_id,
                        p.nome_paciente,
                        p.cpf_cnpj,
                        pve.dependente_id,
                        pve.dentista_id,
                        d.nome as dentista_nome,
                        pve.unidade,
                        pve.valor_solicitado,
                        pve.valor_pago,
                        pve.forma_pagamento_id,
                        fp.nome as forma_pagamento_nome,
                        pve.checkout_id,
                        pve.status,
                        pve.created_at,
                        pve.updated_at,
                        pve.metadata_json,
                        u.nome as vendedor_nome
                    FROM pre_vendas_entradas pve
                    INNER JOIN pacientes p ON pve.paciente_id = p.paciente_id
                    INNER JOIN dentistas d ON pve.dentista_id = d.id
                    LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
                    LEFT JOIN users u ON CAST(pve.metadata_json->>'usuario_id' AS INTEGER) = u.id
                    WHERE pve.status = 'pago'
                )
                UNION ALL
                (
                    -- Faturas recorrentes com primeira parcela paga
                    SELECT 
                        fr.id,
                        CONCAT('FR-', fr.subscription_id) as pre_venda_id,
                        COALESCE(o.tipo, 'Cartão Recorrente') as tipo_odontograma,
                        v.paciente_id,
                        p.nome_paciente,
                        p.cpf_cnpj,
                        v.dependente_id,
                        v.dentista_orcamentista_id as dentista_id,
                        d.nome as dentista_nome,
                        p.unidade,
                        fr.valor_mensal as valor_solicitado,
                        fr.valor_mensal as valor_pago,
                        v.forma_pagamento_id,
                        'CARTÃO CRÉDITO RECORRENTE DELTA' as forma_pagamento_nome,
                        fr.subscription_id::text as checkout_id,
                        'ativo' as status,
                        v.created_at,
                        fr.atualizado_em as updated_at,
                        jsonb_build_object(
                            'subscription_id', fr.subscription_id,
                            'valor_mensal', fr.valor_mensal,
                            'total_parcelas', fr.total_parcelas,
                            'parcelas_pagas', fr.parcelas_pagas,
                            'proxima_cobranca', fr.proxima_cobranca,
                            'venda_id', v.id
                        ) as metadata_json,
                        u.nome as vendedor_nome
                    FROM fatura_recorrente fr
                    INNER JOIN vendas v ON fr.venda_id = v.id
                    INNER JOIN pacientes p ON v.paciente_id = p.paciente_id
                    INNER JOIN dentistas d ON v.dentista_orcamentista_id = d.id
                    LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                    LEFT JOIN users u ON v.usuario_venda_id = u.id
                    WHERE fr.status = 'ACTIVE'
                )
            """
            
            # Query para contar total
            count_query = """
                SELECT COUNT(*) FROM (
                    (
                        SELECT pve.id
                        FROM pre_vendas_entradas pve
                        INNER JOIN pacientes p ON pve.paciente_id = p.paciente_id
                        INNER JOIN dentistas d ON pve.dentista_id = d.id
                        LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
                        LEFT JOIN users u ON CAST(pve.metadata_json->>'usuario_id' AS INTEGER) = u.id
                        WHERE pve.status = 'pago'
                    )
                    UNION ALL
                    (
                        SELECT fr.id
                        FROM fatura_recorrente fr
                        INNER JOIN vendas v ON fr.venda_id = v.id
                        INNER JOIN pacientes p ON v.paciente_id = p.paciente_id
                        INNER JOIN dentistas d ON v.dentista_orcamentista_id = d.id
                        LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                        LEFT JOIN users u ON v.usuario_venda_id = u.id
                        WHERE fr.status = 'ACTIVE'
                    )
                ) combined
            """
            
            # Preparar condições de filtro para ambas as partes da UNION
            entrada_conditions = []
            recorrente_conditions = []
            entrada_params = []
            recorrente_params = []
            
            # Aplicar filtros
            if paciente_id:
                entrada_conditions.append("pve.paciente_id = %s")
                recorrente_conditions.append("v.paciente_id = %s")
                entrada_params.append(paciente_id)
                recorrente_params.append(paciente_id)
            
            if unidade:
                entrada_conditions.append("pve.unidade ILIKE %s")
                recorrente_conditions.append("p.unidade ILIKE %s")
                entrada_params.append(f"%{unidade}%")
                recorrente_params.append(f"%{unidade}%")
            
            if data_inicio:
                entrada_conditions.append("pve.created_at >= %s")
                recorrente_conditions.append("v.created_at >= %s")
                entrada_params.append(f"{data_inicio} 00:00:00")
                recorrente_params.append(f"{data_inicio} 00:00:00")
            
            if data_fim:
                entrada_conditions.append("pve.created_at <= %s")
                recorrente_conditions.append("v.created_at <= %s")
                entrada_params.append(f"{data_fim} 23:59:59")
                recorrente_params.append(f"{data_fim} 23:59:59")
            
            if dentista_id:
                entrada_conditions.append("pve.dentista_id = %s")
                recorrente_conditions.append("v.dentista_orcamentista_id = %s")
                entrada_params.append(dentista_id)
                recorrente_params.append(dentista_id)
            
            if tipo_odontograma:
                entrada_conditions.append("pve.tipo_odontograma ILIKE %s")
                recorrente_conditions.append("COALESCE(o.tipo, 'Cartão Recorrente') ILIKE %s")
                entrada_params.append(f"%{tipo_odontograma}%")
                recorrente_params.append(f"%{tipo_odontograma}%")
            
            # Adicionar condições às queries
            if entrada_conditions or recorrente_conditions:
                # Modificar a query base para incluir filtros
                entrada_where = " AND " + " AND ".join(entrada_conditions) if entrada_conditions else ""
                recorrente_where = " AND " + " AND ".join(recorrente_conditions) if recorrente_conditions else ""
                
                base_query = base_query.replace(
                    "WHERE pve.status = 'pago'",
                    f"WHERE pve.status = 'pago'{entrada_where}"
                ).replace(
                    "WHERE fr.status = 'ACTIVE'",
                    f"WHERE fr.status = 'ACTIVE'{recorrente_where}"
                )
                
                count_query = count_query.replace(
                    "WHERE pve.status = 'pago'",
                    f"WHERE pve.status = 'pago'{entrada_where}"
                ).replace(
                    "WHERE fr.status = 'ACTIVE'",
                    f"WHERE fr.status = 'ACTIVE'{recorrente_where}"
                )
            
            count_params = entrada_params + recorrente_params
            query_params = entrada_params + recorrente_params

            # Executar query de contagem
            if count_params:
                cursor.execute(count_query, count_params)
            else:
                cursor.execute(count_query)
            total = cursor.fetchone()[0]
            
            # Calcular paginação
            total_pages = (total + size - 1) // size
            offset = (page - 1) * size
            
            # Adicionar ordenação e paginação (wrapeando a UNION em uma subquery)
            paginated_query = f"""
                SELECT * FROM ({base_query}) combined_results
                ORDER BY created_at DESC 
                LIMIT %s OFFSET %s
            """
            query_params.extend([size, offset])
            
            # Executar query principal
            if query_params:
                cursor.execute(paginated_query, query_params)
            else:
                cursor.execute(paginated_query)
            results = cursor.fetchall()
            
            # Converter resultados
            pagamentos = []
            for row in results:
                pagamento = PagamentoEntradaPago(
                    id=row[0],
                    pre_venda_id=row[1],
                    tipo_odontograma=row[2],
                    paciente_id=row[3],
                    paciente_nome=row[4],
                    paciente_cpf=row[5],
                    dependente_id=row[6],
                    dentista_id=row[7],
                    dentista_nome=row[8],
                    vendedor_nome=row[19] or "N/A",  # Vendedor da posição 19
                    unidade=row[9],
                    valor_solicitado=row[10],
                    valor_pago=row[11] or Decimal('0'),
                    forma_pagamento_id=row[12] or 0,
                    forma_pagamento_nome=row[13] or "N/A",
                    checkout_id=row[14],
                    status=row[15],
                    created_at=row[16],
                    updated_at=row[17],
                    metadata_json=row[18]
                )
                pagamentos.append(pagamento)
            
            return PagamentosEntradaPagosResponse(
                pagamentos=pagamentos,
                total=total,
                page=page,
                size=size,
                total_pages=total_pages
            )
            
    except Exception as e:
        logger.error(f"Erro ao listar pagamentos de entrada pagos: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar pagamentos: {str(e)}"
        )

@router.get("/entrada/{pre_venda_id}/comprovante-html", response_class=HTMLResponse)
async def gerar_comprovante_html(
    pre_venda_id: str,
    db: Session = Depends(get_db)
):
    """
    Gera um comprovante HTML profissional para impressão/download
    """
    logger.info(f"Gerando comprovante HTML para pré-venda: {pre_venda_id}")
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Buscar dados completos do pagamento (entrada tradicional ou fatura recorrente)
            if pre_venda_id.startswith('FR-'):
                # Fatura recorrente
                subscription_id = pre_venda_id.replace('FR-', '')
                cursor.execute("""
                    SELECT 
                        fr.id,
                        %s as pre_venda_id,
                        COALESCE(o.tipo, 'Cartão Recorrente') as tipo_odontograma,
                        v.paciente_id,
                        p.nome_paciente,
                        p.cpf_cnpj,
                        p.phone_area_code,
                        p.phone_number,
                        p.street,
                        p.street_number,
                        p.neighborhood,
                        p.city,
                        p.state,
                        v.dependente_id,
                        v.dentista_orcamentista_id as dentista_id,
                        d.nome as dentista_nome,
                        p.unidade,
                        fr.valor_mensal as valor_solicitado,
                        fr.valor_mensal as valor_pago,
                        v.forma_pagamento_id,
                        'CARTÃO CRÉDITO RECORRENTE DELTA' as forma_pagamento_nome,
                        fr.subscription_id::text as checkout_id,
                        'ativo' as status,
                        v.created_at,
                        fr.atualizado_em as updated_at,
                        jsonb_build_object(
                            'subscription_id', fr.subscription_id,
                            'valor_mensal', fr.valor_mensal,
                            'total_parcelas', fr.total_parcelas,
                            'parcelas_pagas', fr.parcelas_pagas,
                            'proxima_cobranca', fr.proxima_cobranca,
                            'venda_id', v.id
                        ) as metadata_json
                    FROM fatura_recorrente fr
                    INNER JOIN vendas v ON fr.venda_id = v.id
                    INNER JOIN pacientes p ON v.paciente_id = p.paciente_id
                    INNER JOIN dentistas d ON v.dentista_orcamentista_id = d.id
                    LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                    WHERE fr.subscription_id = %s AND fr.status = 'ACTIVE'
                """, (pre_venda_id, subscription_id))
            else:
                # Pré-venda tradicional
                cursor.execute("""
                    SELECT 
                        pve.id,
                        pve.pre_venda_id,
                        pve.tipo_odontograma,
                        pve.paciente_id,
                        p.nome_paciente,
                        p.cpf_cnpj,
                        p.phone_area_code,
                        p.phone_number,
                        p.street,
                        p.street_number,
                        p.neighborhood,
                        p.city,
                        p.state,
                        pve.dependente_id,
                        pve.dentista_id,
                        d.nome as dentista_nome,
                        pve.unidade,
                        pve.valor_solicitado,
                        pve.valor_pago,
                        pve.forma_pagamento_id,
                        fp.nome as forma_pagamento_nome,
                        pve.checkout_id,
                        pve.status,
                        pve.created_at,
                        pve.updated_at,
                        pve.metadata_json
                    FROM pre_vendas_entradas pve
                    INNER JOIN pacientes p ON pve.paciente_id = p.paciente_id
                    INNER JOIN dentistas d ON pve.dentista_id = d.id
                    LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
                    WHERE pve.pre_venda_id = %s AND pve.status = 'pago'
                """, (pre_venda_id,))
            
            result = cursor.fetchone()
            
            if not result:
                tipo_busca = "Fatura recorrente" if pre_venda_id.startswith('FR-') else "Pagamento de entrada"
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"{tipo_busca} não encontrado ou não está ativo"
                )
            
            # Extrair dados
            (id_, pre_venda_id, tipo_odontograma, paciente_id, paciente_nome, 
             paciente_cpf, phone_area, phone_number, street, street_number,
             neighborhood, city, state, dependente_id, dentista_id, dentista_nome,
             unidade, valor_solicitado, valor_pago, forma_pagamento_id,
             forma_pagamento_nome, checkout_id, status, created_at, updated_at,
             metadata_json) = result
            
            # Buscar dados do dependente se houver
            dependente_nome = None
            if dependente_id:
                cursor.execute("""
                    SELECT nome_dependente FROM dependentes WHERE dependente_id = %s
                """, (dependente_id,))
                dep_result = cursor.fetchone()
                if dep_result:
                    dependente_nome = dep_result[0]
            
            # Formatar dados para o template
            telefone = ""
            if phone_area and phone_number:
                telefone = f"({phone_area}) {phone_number}"
            
            endereco = ""
            if street:
                endereco_parts = [street]
                if street_number:
                    endereco_parts.append(f"nº {street_number}")
                if neighborhood:
                    endereco_parts.append(neighborhood)
                if city and state:
                    endereco_parts.append(f"{city} - {state}")
                endereco = ", ".join(endereco_parts)
            
            # Formatar valor
            valor_formatado = f"R$ {valor_pago:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            
            # Formatar data - CORRIGIDO: converter UTC para Brasil
            created_at_brasil = converter_utc_para_brasil(created_at)
            data_pagamento = created_at_brasil.strftime("%d/%m/%Y às %H:%M")
            
            # Data de emissão também em horário do Brasil
            agora_brasil = converter_utc_para_brasil(datetime.now(pytz.utc))
            data_emissao = agora_brasil.strftime("%d/%m/%Y às %H:%M")
            
            # Extrair dados do plano de tratamento dos metadados
            valor_total_tratamento = ""
            num_parcelas = ""
            dia_vencimento = ""
            
            if metadata_json:
                if 'valor_total' in metadata_json:
                    valor_total = float(metadata_json['valor_total'])
                    valor_total_tratamento = f"R$ {valor_total:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                
                if 'numero_parcelas' in metadata_json:
                    num_parcelas = f"{metadata_json['numero_parcelas']}x"
                
                if 'dia_vencimento' in metadata_json:
                    dia_vencimento = f"Dia {metadata_json['dia_vencimento']} de cada mês"
            
            # Buscar dados do usuário que fez a venda
            vendedor_nome = ""
            if metadata_json and 'usuario_id' in metadata_json:
                try:
                    usuario_id = int(metadata_json['usuario_id'])
                    cursor.execute("""
                        SELECT nome FROM users WHERE id = %s
                    """, (usuario_id,))
                    usuario_result = cursor.fetchone()
                    if usuario_result:
                        vendedor_nome = usuario_result[0]
                except (ValueError, TypeError):
                    pass
            
            # Template HTML do comprovante (estilo bobina)
            html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Comprovante (Bobina) - Grupo JF</title>
  <style>
    :root {{
      --bobina-width: 90mm; 
      --min-height: 150mm;
      --scale: 0.5;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ height: 100%; }}

    body {{
      font: 12px/1.35 "Courier New", monospace;
      color: #000;
      background: #f2f2f2;
      padding: 12mm;
    }}

    @media screen {{
      .sheet {{
        width: 210mm;
        min-height: 297mm;
        margin: 0 auto;
        background: #fff;
        box-shadow: 0 0 0 1px rgba(0,0,0,.06), 0 12px 24px rgba(0,0,0,.08);
        display: flex;
        justify-content: flex-start;
        align-items: flex-start;
        padding: 10mm;
      }}
    }}

    .receipt {{
      width: var(--bobina-width);
      min-height: var(--min-height);
      background: #fff;
      border: 1px solid #000;
      padding: 6mm 5mm;
      transform: scale(var(--scale));
      transform-origin: top left;
    }}

    .h-center {{ text-align: center; }}
    .block {{ margin-top: 3mm; }}
    .small {{ font-size: 10px; }}
    .h1 {{ font-weight: 700; font-size: 12px; letter-spacing: .5px; text-transform: uppercase; }}
    .h2 {{ font-weight: 700; font-size: 11px; text-transform: uppercase; }}
    .price {{ font-size: 16px; font-weight: 700; }}

    .sep {{ margin: 2mm 0; border-top: 1px dashed #000; }}

    .kv {{ display: flex; justify-content: space-between; gap: 3mm; }}
    .kv + .kv {{ margin-top: 1mm; }}

    .code {{ font-family: inherit; }}

    @page {{ size: A4 portrait; margin: 10mm; }}

    @media print {{
      body {{ background: #fff; padding: 0; }}
      .sheet {{ width: auto; min-height: auto; box-shadow: none; padding: 0; margin: 0; display: flex; justify-content: flex-start; align-items: flex-start; }}
      .no-print {{ display: none !important; }}
      .receipt {{ border: 0; }}
    }}

    .height-150 {{ min-height: 150mm; }}
    .height-200 {{ min-height: 200mm; }}
    .width-80 {{ width: 80mm; }}
    .width-100 {{ width: 100mm; }}
  </style>
</head>
<body>
  <div class="sheet">
    <article class="receipt height-150" role="document" aria-label="Comprovante estilo bobina">
      <header class="h-center">
        <div style="margin-bottom: 2mm;">
          <img src="/static/Logo-Odontocompany.png" alt="OdontoCompany" style="height: 8mm; filter: grayscale(100%);" />
        </div>
        <div class="h2">{'COMPROVANTE DE ASSINATURA RECORRENTE' if pre_venda_id.startswith('FR-') else 'COMPROVANTE DE ENTRADA'}</div>
        <div class="small">Emitido em {data_emissao}</div>
      </header>

      <div class="sep"></div>

      <section class="block">
        <div class="h2">Titular</div>
        <div class="kv"><span>Nome</span><span>{paciente_nome}</span></div>
        <div class="kv"><span>CPF</span><span>{paciente_cpf}</span></div>
        {f'<div class="kv"><span>Telefone</span><span>{telefone}</span></div>' if telefone else ''}
        {f'<div class="kv"><span>Endereço</span><span>{endereco}</span></div>' if endereco else ''}
      </section>

      {f'''
      <div class="sep"></div>

      <section class="block">
        <div class="h2">Dependente</div>
        <div class="kv"><span>Nome</span><span>{dependente_nome}</span></div>
        <div class="kv"><span>Responsável</span><span>{paciente_nome}</span></div>
      </section>
      ''' if dependente_nome else ''}

      <div class="sep"></div>

      <section class="block">
        <div class="h2">Pagamento</div>
        <div class="kv"><span>Status</span><span>{'ASSINATURA ATIVA' if pre_venda_id.startswith('FR-') else 'PAGO'}</span></div>
        <div class="kv"><span>Valor{'Mensal' if pre_venda_id.startswith('FR-') else ''}</span><span class="price">{valor_formatado}</span></div>
        <div class="kv"><span>Método</span><span>{forma_pagamento_nome or 'N/A'}</span></div>
        <div class="kv"><span>Data</span><span>{data_pagamento}</span></div>
        <div class="kv"><span>ID Transação</span><span class="code">{pre_venda_id}</span></div>
        {f'<div class="kv"><span>ID Checkout</span><span>{checkout_id}</span></div>' if checkout_id else ''}
      </section>

      {f'''
      <div class="sep"></div>
      
      <section class="block">
        <div class="h2">Assinatura Recorrente</div>
        <div class="kv"><span>ID Assinatura</span><span>{pre_venda_id.replace("FR-", "")}</span></div>
        <div class="kv"><span>Status</span><span>ATIVA</span></div>
        <div class="kv"><span>Cobrança</span><span>Automática Mensal</span></div>
      </section>
      ''' if pre_venda_id.startswith('FR-') else ''}

      <div class="sep"></div>

      <section class="block">
        <div class="h2">Tratamento</div>
        <div class="kv"><span>Tipo</span><span>{tipo_odontograma}</span></div>
        <div class="kv"><span>Unidade</span><span>{unidade}</span></div>
        <div class="kv"><span>Dentista</span><span>{dentista_nome}</span></div>
        {f'<div class="kv"><span>Valor do Tratamento</span><span>{valor_total_tratamento}</span></div>' if valor_total_tratamento else ''}
        {f'<div class="kv"><span>Parcelas</span><span>{num_parcelas}</span></div>' if num_parcelas else ''}
        {f'<div class="kv"><span>Vencimento</span><span>{dia_vencimento}</span></div>' if dia_vencimento else ''}
        {f'<div class="kv"><span>Vendedor(a)</span><span>{vendedor_nome}</span></div>' if vendedor_nome else ''}
      </section>

      <div class="sep"></div>

      <section class="block">
        <div class="h2">Detalhes</div>
        <div class="kv"><span>Nº Documento</span><span>#{id_}</span></div>
        <div class="kv"><span>Criação</span><span>{created_at_brasil.strftime('%d/%m/%Y às %H:%M')}</span></div>
        {f'<div class="kv"><span>Atualização</span><span>{converter_utc_para_brasil(updated_at).strftime("%d/%m/%Y às %H:%M")}</span></div>' if updated_at else ''}
      </section>

      <div class="sep"></div>

      <footer class="h-center small block">
        <div><strong>Este comprovante é válido como prova de pagamento da entrada.</strong></div>
        <div class="small">Documento gerado automaticamente em {data_emissao}</div>
      </footer>
    </article>
  </div>

  <div class="no-print h-center" style="text-align:center;margin-top:12px;">
    <button onclick="window.print()" style="padding:8px 14px;border:1px solid #000;background:#fff;cursor:pointer;">Imprimir / Salvar PDF</button>
    <div class="small" style="margin-top:6px;">Comprovante otimizado para impressão em bobina (80/90/100mm).</div>
  </div>
</body>
</html>"""
            
            return HTMLResponse(content=html_content)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar comprovante HTML: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar comprovante: {str(e)}"
        )

@router.get("/entrada/{pre_venda_id}/dados-completos")
async def obter_dados_completos_pagamento(
    pre_venda_id: str,
    db: Session = Depends(get_db)
):
    """
    Retorna dados completos de um pagamento de entrada para uso no frontend
    """
    logger.info(f"Buscando dados completos para pré-venda: {pre_venda_id}")
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Buscar todos os dados necessários (entrada tradicional ou fatura recorrente)
            if pre_venda_id.startswith('FR-'):
                # Fatura recorrente
                subscription_id = pre_venda_id.replace('FR-', '')
                cursor.execute("""
                    SELECT 
                        fr.id,
                        %s as pre_venda_id,
                        COALESCE(o.tipo, 'Cartão Recorrente') as tipo_odontograma,
                        v.paciente_id,
                        p.nome_paciente,
                        p.cpf_cnpj,
                        p.email,
                        p.phone_country_code,
                        p.phone_area_code,
                        p.phone_number,
                        p.street,
                        p.street_number,
                        p.neighborhood,
                        p.city,
                        p.state,
                        p.zip_code,
                        v.dependente_id,
                        dep.nome_dependente as dependente_nome,
                        v.dentista_orcamentista_id as dentista_id,
                        d.nome as dentista_nome,
                        p.unidade,
                        fr.valor_mensal as valor_solicitado,
                        fr.valor_mensal as valor_pago,
                        v.forma_pagamento_id,
                        'CARTÃO CRÉDITO RECORRENTE DELTA' as forma_pagamento_nome,
                        fr.subscription_id::text as checkout_id,
                        fr.checkout_url,
                        'ativo' as status,
                        v.created_at,
                        fr.atualizado_em as updated_at,
                        fr.proxima_cobranca::timestamp as expires_at,
                        jsonb_build_object(
                            'subscription_id', fr.subscription_id,
                            'valor_mensal', fr.valor_mensal,
                            'total_parcelas', fr.total_parcelas,
                            'parcelas_pagas', fr.parcelas_pagas,
                            'proxima_cobranca', fr.proxima_cobranca,
                            'venda_id', v.id
                        ) as metadata_json
                    FROM fatura_recorrente fr
                    INNER JOIN vendas v ON fr.venda_id = v.id
                    INNER JOIN pacientes p ON v.paciente_id = p.paciente_id
                    INNER JOIN dentistas d ON v.dentista_orcamentista_id = d.id
                    LEFT JOIN dependentes dep ON v.dependente_id = dep.dependente_id
                    LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                    WHERE fr.subscription_id = %s AND fr.status = 'ACTIVE'
                """, (pre_venda_id, subscription_id))
            else:
                # Pré-venda tradicional
                cursor.execute("""
                    SELECT 
                        pve.id,
                        pve.pre_venda_id,
                        pve.tipo_odontograma,
                        pve.paciente_id,
                        p.nome_paciente,
                        p.cpf_cnpj,
                        p.email,
                        p.phone_country_code,
                        p.phone_area_code,
                        p.phone_number,
                        p.street,
                        p.street_number,
                        p.neighborhood,
                        p.city,
                        p.state,
                        p.zip_code,
                        pve.dependente_id,
                        dep.nome_dependente as dependente_nome,
                        pve.dentista_id,
                        d.nome as dentista_nome,
                        pve.unidade,
                        pve.valor_solicitado,
                        pve.valor_pago,
                        pve.forma_pagamento_id,
                        fp.nome as forma_pagamento_nome,
                        pve.checkout_id,
                        pve.checkout_url,
                        pve.status,
                        pve.created_at,
                        pve.updated_at,
                        pve.expires_at,
                        pve.metadata_json
                    FROM pre_vendas_entradas pve
                    INNER JOIN pacientes p ON pve.paciente_id = p.paciente_id
                    INNER JOIN dentistas d ON pve.dentista_id = d.id
                    LEFT JOIN dependentes dep ON pve.dependente_id = dep.dependente_id
                    LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
                    WHERE pve.pre_venda_id = %s
                """, (pre_venda_id,))
            
            result = cursor.fetchone()
            
            if not result:
                tipo_busca = "Fatura recorrente" if pre_venda_id.startswith('FR-') else "Pagamento de entrada"
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"{tipo_busca} não encontrado"
                )
            
            # Montar resposta com todos os dados
            dados = {
                "id": result[0],
                "pre_venda_id": result[1],
                "tipo_odontograma": result[2],
                "paciente": {
                    "id": result[3],
                    "nome": result[4],
                    "cpf": result[5],
                    "email": result[6],
                    "telefone": {
                        "country_code": result[7] or "55",
                        "area_code": result[8],
                        "number": result[9],
                        "formatted": f"({result[8]}) {result[9]}" if result[8] and result[9] else None
                    },
                    "endereco": {
                        "street": result[10],
                        "number": result[11],
                        "neighborhood": result[12],
                        "city": result[13],
                        "state": result[14],
                        "zip_code": result[15],
                        "formatted": None
                    }
                },
                "dependente": {
                    "id": result[16],
                    "nome": result[17]
                } if result[16] else None,
                "dentista": {
                    "id": result[18],
                    "nome": result[19]
                },
                "unidade": result[20],
                "valores": {
                    "solicitado": float(result[21]) if result[21] else 0,
                    "pago": float(result[22]) if result[22] else 0,
                    "formatado_solicitado": f"R$ {result[21]:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.') if result[21] else "R$ 0,00",
                    "formatado_pago": f"R$ {result[22]:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.') if result[22] else "R$ 0,00"
                },
                "pagamento": {
                    "forma_pagamento_id": result[23],
                    "forma_pagamento_nome": result[24],
                    "checkout_id": result[25],
                    "checkout_url": result[26],
                    "status": result[27]
                },
                "timestamps": {
                    "created_at": result[28].isoformat() if result[28] else None,
                    "updated_at": result[29].isoformat() if result[29] else None,
                    "expires_at": result[30].isoformat() if result[30] else None,
                    "formatted_created": converter_utc_para_brasil(result[28]).strftime("%d/%m/%Y às %H:%M") if result[28] else None,
                    "formatted_updated": converter_utc_para_brasil(result[29]).strftime("%d/%m/%Y às %H:%M") if result[29] else None,
                    "formatted_expires": converter_utc_para_brasil(result[30]).strftime("%d/%m/%Y às %H:%M") if result[30] else None
                },
                "metadata": result[31] or {}
            }
            
            # Formatar endereço completo
            endereco_parts = []
            if result[10]:  # street
                endereco_parts.append(result[10])
                if result[11]:  # street_number
                    endereco_parts.append(f"nº {result[11]}")
                if result[12]:  # neighborhood
                    endereco_parts.append(result[12])
                if result[13] and result[14]:  # city and state
                    endereco_parts.append(f"{result[13]} - {result[14]}")
                if result[15]:  # zip_code
                    endereco_parts.append(f"CEP: {result[15]}")
                
                dados["paciente"]["endereco"]["formatted"] = ", ".join(endereco_parts)
            
            # Extrair informações adicionais dos metadados
            if dados["metadata"]:
                metadata = dados["metadata"]
                
                # Informações do tratamento
                dados["tratamento"] = {
                    "valor_total": metadata.get("valor_total"),
                    "numero_parcelas": metadata.get("numero_parcelas"),
                    "odontograma_id": metadata.get("odontograma_id"),
                    "dia_vencimento": metadata.get("dia_vencimento"),
                    "forma_pagamento_parcelas": metadata.get("forma_pagamento_parcelas"),
                    "usuario_id": metadata.get("usuario_id")
                }
                
                # Formatar valor total se disponível
                if metadata.get("valor_total"):
                    try:
                        valor_total = float(metadata["valor_total"])
                        dados["tratamento"]["valor_total_formatado"] = f"R$ {valor_total:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                        dados["tratamento"]["parcelas_formatadas"] = f"{metadata.get('numero_parcelas', 1)}x"
                        dados["tratamento"]["vencimento_formatado"] = f"Dia {metadata.get('dia_vencimento', 'N/A')} de cada mês"
                    except (ValueError, TypeError):
                        pass
            
            # Buscar dados do usuário que fez a venda
            dados["vendedor"] = None
            if dados["metadata"] and dados["metadata"].get("usuario_id"):
                try:
                    usuario_id = int(dados["metadata"]["usuario_id"])
                    cursor.execute("""
                        SELECT nome, email FROM users WHERE id = %s
                    """, (usuario_id,))
                    usuario_result = cursor.fetchone()
                    if usuario_result:
                        dados["vendedor"] = {
                            "id": usuario_id,
                            "nome": usuario_result[0],
                            "email": usuario_result[1]
                        }
                except (ValueError, TypeError):
                    pass
            
            return dados
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar dados completos: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar dados: {str(e)}"
        )

@router.post("/entrada", response_model=PreVendaEntradaResponse)
async def criar_pre_venda_entrada(
    data: PreVendaEntradaCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Cria uma pré-venda com entrada e retorna URL de checkout.
    
    Este endpoint:
    1. Valida os dados da entrada
    2. Cria registro temporário de pré-venda
    3. Gera fatura avulsa Delta para a entrada (se valor > 0)
    4. Retorna URL de checkout ou confirmação para entrada = 0
    """
    logger.info(f"Criando pré-venda com entrada - dados recebidos: {data.model_dump()}")
    logger.info(f"Criando pré-venda com entrada para paciente {data.paciente_id}")
    
    # Extrair usuário do contexto de autenticação
    user_data = getattr(request.state, 'user', None)
    usuario_email = None
    usuario_id = None
    
    if user_data:
        # O token JWT tem o email no campo 'sub'
        usuario_email = user_data.get('sub')
        logger.info(f"Usuário autenticado (email): {usuario_email}")
        
        # Buscar ID do usuário pelo email
        if usuario_email:
            try:
                with DatabaseConnection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE email = %s", (usuario_email,))
                    result = cursor.fetchone()
                    if result:
                        usuario_id = result[0]
                        logger.info(f"ID do usuário encontrado: {usuario_id}")
            except Exception as e:
                logger.error(f"Erro ao buscar ID do usuário: {str(e)}")
    
    # Validar se o usuário tem cargo autorizado para fazer vendas
    if usuario_id:
        from ..services.split_service import SplitService
        autorizado, mensagem_erro = SplitService.validar_cargo_autorizado_venda(usuario_id)
        
        if not autorizado:
            logger.warning(f"Tentativa de venda bloqueada: {mensagem_erro}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=mensagem_erro
            )
    
    try:
        # Gerar ID único para a pré-venda
        pre_venda_id = f"PV-{uuid.uuid4()}"
        
        # Buscar dados do paciente para o checkout
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # NOVA VALIDAÇÃO: Verificar se já existe pré-venda pendente
            # para o mesmo paciente/odontograma específico
            if data.odontograma_id:
                # Se tem odontograma_id, verifica por ele (mais específico)
                cursor.execute("""
                    SELECT pre_venda_id, created_at, valor_solicitado, forma_pagamento_id
                    FROM pre_vendas_entradas
                    WHERE paciente_id = %s 
                      AND metadata_json->>'odontograma_id' = %s
                      AND status = 'pendente'
                      AND created_at > NOW() - INTERVAL '30 minutes'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (data.paciente_id, str(data.odontograma_id)))
            else:
                # Se não tem odontograma_id, verifica por tipo (para casos como Taxa de Adesão)
                cursor.execute("""
                    SELECT pre_venda_id, created_at, valor_solicitado, forma_pagamento_id
                    FROM pre_vendas_entradas
                    WHERE paciente_id = %s 
                      AND tipo_odontograma = %s
                      AND status = 'pendente'
                      AND created_at > NOW() - INTERVAL '30 minutes'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (data.paciente_id, data.tipo_odontograma))
            
            pre_venda_existente = cursor.fetchone()
            if pre_venda_existente:
                # Buscar nome da forma de pagamento e checkout_url
                cursor.execute("""
                    SELECT fp.nome, pve.checkout_url
                    FROM pre_vendas_entradas pve
                    LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
                    WHERE pve.pre_venda_id = %s
                """, (pre_venda_existente[0],))
                dados_adicionais = cursor.fetchone()
                fp_nome = dados_adicionais[0] if dados_adicionais and dados_adicionais[0] else "N/A"
                checkout_url = dados_adicionais[1] if dados_adicionais and dados_adicionais[1] else None
                
                tempo_decorrido = datetime.now(timezone.utc) - pre_venda_existente[1].replace(tzinfo=timezone.utc)
                minutos = int(tempo_decorrido.total_seconds() / 60)
                tempo_restante = 30 - minutos
                
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": f"Já existe uma pré-venda pendente criada há {minutos} minutos",
                        "pre_venda_id": pre_venda_existente[0],
                        "valor": float(pre_venda_existente[2]),
                        "forma_pagamento": fp_nome,
                        "minutos_decorridos": minutos,
                        "tempo_restante": tempo_restante,
                        "checkout_url": checkout_url,
                        "sugestao": "Complete o pagamento da pré-venda existente ou aguarde mais alguns minutos"
                    }
                )
            
            # Buscar paciente
            cursor.execute("""
                SELECT nome_paciente, cpf_cnpj, email, phone_country_code,
                       phone_area_code, phone_number, street, street_number,
                       neighborhood, city, state, zip_code
                FROM pacientes
                WHERE paciente_id = %s
            """, (data.paciente_id,))
            
            paciente_data = cursor.fetchone()
            if not paciente_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Paciente {data.paciente_id} não encontrado"
                )
            
            # Buscar forma de pagamento apenas se ID > 0
            if data.forma_pagamento_id > 0:
                cursor.execute("""
                    SELECT nome FROM formas_pagamento WHERE id = %s AND ativo = true
                """, (data.forma_pagamento_id,))
            else:
                # Sem forma de pagamento (sem entrada)
                cursor.execute("SELECT NULL")
            
            forma_pagamento = cursor.fetchone()
            # Se forma_pagamento_id é 0, significa sem entrada
            if data.forma_pagamento_id == 0:
                forma_pagamento = (None,)  # Tupla vazia para manter compatibilidade
            elif not forma_pagamento:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Forma de pagamento {data.forma_pagamento_id} não encontrada"
                )
        
        # Validar entrada para ortodontia
        forma_pagamento_nome = forma_pagamento[0] if forma_pagamento and forma_pagamento[0] else 'SEM_ENTRADA'
        
        # Se forma_pagamento_id = 0, significa que é sem entrada
        if data.forma_pagamento_id == 0:
            # Buscar forma de pagamento das parcelas nos metadados
            if data.metadata and 'forma_pagamento_parcelas' in data.metadata:
                fp_parcelas = data.metadata['forma_pagamento_parcelas']
                
                # Implementar matriz de regras conforme especificação:
                # SIM = entrada obrigatória, NÃO = entrada opcional (pode ser sem entrada)
                
                # Particular e Ortodontia: SIM para CARNÊ e CARTÃO RECORRENTE, NÃO para PIX/BOLETO/CARTÃO AVULSO
                if data.tipo_odontograma in ['Particular', 'Ortodontia']:
                    if fp_parcelas in ['CARNÊ', 'CARTÃO CRÉDITO RECORRENTE DELTA']:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Entrada é obrigatória para {data.tipo_odontograma} com {fp_parcelas}"
                        )
                    # Para PIX/BOLETO/CARTÃO AVULSO = entrada opcional, pode ser sem entrada
                
                # Contrato Ortodôntico: SIM apenas para CARNÊ, NÃO para todas as outras
                elif data.tipo_odontograma == 'Contrato Ortodôntico':
                    if fp_parcelas == 'CARNÊ':
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Entrada é obrigatória para Contrato Ortodôntico com CARNÊ"
                        )
                    # Para outras formas = entrada opcional, pode ser sem entrada
                
                # ODC + Akimais, Combo, Taxa de Adesão: NÃO para todas as formas = sempre opcional
                # Permite entrada sem pagamento para todos estes tipos
                
            else:
                # Se não há metadados de forma de pagamento, aplicar regra restritiva
                tipos_permitidos = ['Contrato Ortodôntico', 'Combo Orto + ODC', 'Contrato Odontológico + Akimais', 'Taxa de Adesão']
                if data.tipo_odontograma not in tipos_permitidos:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Entrada sem pagamento só é permitida para {', '.join(tipos_permitidos)}"
                    )
        else:
            # Validar valor da entrada baseado na forma de pagamento
            tipos_contratos = ['Contrato Ortodôntico', 'Combo Orto + ODC', 'Contrato Odontológico + Akimais']
            if data.tipo_odontograma in tipos_contratos:
                if not validar_entrada_ortodontia(
                    forma_pagamento_nome,
                    data.valor_entrada,
                    data.valor_total,
                    data.tipo_odontograma
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Valor de entrada inválido para a forma de pagamento selecionada"
                    )
        
        # Criar registro de pré-venda
        # Garantir que metadata sempre tenha as informações necessárias
        metadata_completo = data.metadata.copy() if data.metadata else {}
        metadata_completo.update({
            'valor_total': str(data.valor_total),
            'numero_parcelas': data.numero_parcelas,
            'odontograma_id': data.odontograma_id,
            'usuario_id': str(usuario_id) if usuario_id else None
        })
        
        pre_venda = PreVendaEntrada(
            pre_venda_id=pre_venda_id,
            tipo_odontograma=data.tipo_odontograma,
            paciente_id=data.paciente_id,
            dependente_id=data.dependente_id,
            dentista_id=data.dentista_id,
            unidade=data.unidade,
            valor_solicitado=data.valor_entrada,
            forma_pagamento_id=data.forma_pagamento_id,
            status='pendente',
            metadata_json=metadata_completo
        )
        
        db.add(pre_venda)
        db.commit()
        db.refresh(pre_venda)
        
        # Se valor da entrada é 0, não criar checkout
        if data.valor_entrada == 0:
            logger.info(f"Pré-venda {pre_venda_id} criada sem entrada (valor = 0)")
            
            # Marcar como pago automaticamente
            pre_venda.status = 'pago'
            pre_venda.valor_pago = Decimal('0.00')
            pre_venda.checkout_url = 'SEM_CHECKOUT'
            db.commit()
            
            return PreVendaEntradaResponse(
                pre_venda_id=pre_venda_id,
                checkout_url='SEM_CHECKOUT',  # Frontend deve tratar este caso
                valor=Decimal('0.00'),
                expires_at=pre_venda.expires_at
            )
        
        # Montar dados para checkout Delta (sem usar FaturaAvulsaCreateRequest)
        customer_phone = None
        if paciente_data[5]:  # phone_number
            customer_phone = f"{paciente_data[3] or '55'}{paciente_data[4] or ''}{paciente_data[5]}"
        
        # Criar um objeto simples com os dados necessários
        fatura_request = {
            'customer_name': paciente_data[0],
            'customer_document': paciente_data[1],
            'customer_email': paciente_data[2] or f"{paciente_data[1]}@cliente.com",
            'customer_phone': customer_phone,
            'valor_total': float(data.valor_entrada),
            'payment_method': forma_pagamento[0] if forma_pagamento and forma_pagamento[0] else 'PIX AVULSO DELTA',  # Default para sem entrada
            'metadata': {
                "tipo_pagamento": "entrada_venda",
                "pre_venda_id": pre_venda_id,
                "tipo_odontograma": data.tipo_odontograma
            },
            'unidade': data.unidade,
            'criado_por': usuario_id if usuario_id else 1,  # Usar ID do usuário autenticado
            'odontograma_id': data.odontograma_id,
            'dentista_id': data.dentista_id,  # Adicionar dentista_id
            'tipo_odontograma_id': data.tipo_odontograma_id  # ID vindo do frontend
        }
        
        # Adicionar endereço se disponível
        if paciente_data[6]:  # street
            fatura_request['customer_address'] = {
                "street": paciente_data[6],
                "streetNumber": paciente_data[7] or "S/N",
                "neighborhood": paciente_data[8] or "Centro",
                "city": paciente_data[9] or "São Paulo",
                "state": paciente_data[10] or "SP",
                "zipCode": paciente_data[11] or "00000000"
            }
        
        # Criar checkout para entrada
        logger.info(f"Criando checkout Delta para entrada {pre_venda_id}")
        
        # Converter para objeto simples para o serviço
        class SimpleRequest:
            def __init__(self, data):
                for key, value in data.items():
                    setattr(self, key, value)
                    
        request_obj = SimpleRequest(fatura_request)
        try:
            fatura_response = await criar_fatura_avulsa_service(request_obj, db)
        except Exception as checkout_error:
            pre_venda.status = 'cancelado'
            pre_venda.updated_at = datetime.now(timezone.utc)
            metadata = dict(pre_venda.metadata_json or {})
            metadata['erro_checkout'] = str(checkout_error)[:500]
            pre_venda.metadata_json = metadata
            db.commit()
            raise
        
        if not fatura_response.get('checkout_url'):
            # Se falhou, marcar pré-venda como cancelada
            pre_venda.status = 'cancelado'
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao gerar checkout para entrada"
            )
        
        # Atualizar pré-venda com dados do checkout
        pre_venda.checkout_url = fatura_response['checkout_url']
        pre_venda.checkout_id = fatura_response.get('checkout_id')
        db.commit()
        
        logger.info(f"Pré-venda {pre_venda_id} criada com sucesso")
        
        return PreVendaEntradaResponse(
            pre_venda_id=pre_venda_id,
            checkout_url=fatura_response['checkout_url'],
            valor=data.valor_entrada,
            expires_at=pre_venda.expires_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar pré-venda: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar pré-venda: {str(e)}"
        )

@router.get("/entrada/{pre_venda_id}/status", response_model=PreVendaEntradaStatus)
async def verificar_status_pre_venda(
    pre_venda_id: str,
    db: Session = Depends(get_db)
):
    """
    Verifica o status de uma pré-venda.
    
    Útil para o frontend verificar se o pagamento foi confirmado.
    """
    pre_venda = db.query(PreVendaEntrada).filter(
        PreVendaEntrada.pre_venda_id == pre_venda_id
    ).first()
    
    if not pre_venda:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pré-venda não encontrada"
        )
    
    # Verificar se expirou
    now = datetime.now(timezone.utc)
    if pre_venda.expires_at < now and pre_venda.status == 'pendente':
        pre_venda.status = 'expirado'
        db.commit()
    
    return PreVendaEntradaStatus(
        pre_venda_id=pre_venda.pre_venda_id,
        status=pre_venda.status,
        valor_pago=pre_venda.valor_pago,
        checkout_id=pre_venda.checkout_id,
        created_at=pre_venda.created_at,
        expires_at=pre_venda.expires_at
    )

@router.post("/entrada/{pre_venda_id}/confirmar-pagamento")
async def confirmar_pagamento_entrada(
    pre_venda_id: str,
    valor_pago: Decimal,
    checkout_id: str,
    db: Session = Depends(get_db)
):
    """
    Confirma o pagamento de uma entrada (chamado pelo webhook).
    
    Este endpoint deve ser protegido e chamado apenas pelo sistema.
    """
    logger.info(f"Confirmando pagamento da pré-venda {pre_venda_id}")
    
    pre_venda = db.query(PreVendaEntrada).filter(
        PreVendaEntrada.pre_venda_id == pre_venda_id
    ).first()
    
    if not pre_venda:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pré-venda não encontrada"
        )
    
    if pre_venda.status != 'pendente':
        logger.warning(f"Tentativa de confirmar pré-venda {pre_venda_id} com status {pre_venda.status}")
        return {"message": "Pré-venda já processada"}
    
    # Atualizar status
    pre_venda.status = 'pago'
    pre_venda.valor_pago = valor_pago
    pre_venda.checkout_id = checkout_id
    pre_venda.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    
    logger.info(f"Pré-venda {pre_venda_id} confirmada como paga")
    
    return {"message": "Pagamento confirmado com sucesso"}

@router.delete("/entrada/{pre_venda_id}")
async def cancelar_pre_venda(
    pre_venda_id: str,
    motivo: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Cancela uma pré-venda (se ainda não foi paga).
    """
    pre_venda = db.query(PreVendaEntrada).filter(
        PreVendaEntrada.pre_venda_id == pre_venda_id
    ).first()
    
    if not pre_venda:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pré-venda não encontrada"
        )
    
    if pre_venda.status == 'pago':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível cancelar uma pré-venda já paga"
        )
    
    pre_venda.status = 'cancelado'
    if motivo:
        pre_venda.metadata_json = pre_venda.metadata_json or {}
        pre_venda.metadata_json['motivo_cancelamento'] = motivo
    
    db.commit()
    
    return {"message": "Pré-venda cancelada com sucesso"}

# Função auxiliar para verificar entrada paga
def verificar_entrada_paga(pre_venda_id: str, db: Session) -> Optional[PreVendaEntrada]:
    """
    Verifica se uma entrada foi paga e retorna os dados.
    
    Usado pelos endpoints de criação de venda.
    
    IMPORTANTE: Para pagamentos via boleto, aceita status 'pendente' pois 
    a compensação pode levar até 2 dias úteis.
    """
    if not pre_venda_id:
        return None
        
    # Primeiro buscar a pré-venda
    pre_venda = db.query(PreVendaEntrada).filter(
        PreVendaEntrada.pre_venda_id == pre_venda_id
    ).first()
    
    if not pre_venda:
        logger.warning(f"Pré-venda {pre_venda_id} não encontrada")
        return None
    
    # Se está paga, retornar
    if pre_venda.status == 'pago':
        return pre_venda
    
    # Se está pendente, verificar se é boleto
    if pre_venda.status == 'pendente':
        # Buscar a forma de pagamento
        if pre_venda.forma_pagamento_id:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT nome FROM formas_pagamento WHERE id = %s",
                    (pre_venda.forma_pagamento_id,)
                )
                result = cursor.fetchone()
                
                if result and 'BOLETO' in result[0]:
                    logger.info(f"Pré-venda {pre_venda_id} com boleto pendente - permitindo prosseguir")
                    return pre_venda
    
    logger.warning(f"Pré-venda {pre_venda_id} não está em status válido para prosseguir")
    return None
