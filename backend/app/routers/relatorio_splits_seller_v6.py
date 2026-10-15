# backend/app/routers/relatorio_splits_seller_v6.py

from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import logging
import csv
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from app.database.db import DatabaseConnection
from app.middleware.auth_middleware import get_current_user
from pydantic import BaseModel

# Configurar logging
logger = logging.getLogger(__name__)

# Criar router
router = APIRouter(
    prefix="/relatorio-splits-v6",
    tags=["Relatório de Splits V6"],
    responses={404: {"description": "Not found"}}
)

# Modelos de resposta
class BeneficiarioSplit(BaseModel):
    seller_id: str
    tipo: str  # 'usuario' ou 'empresa'
    id_beneficiario: Optional[int]  # ID do usuário ou empresa
    nome_beneficiario: str
    cpf_cnpj: Optional[str]
    percentage: float
    valor_calculado: float
    status_pagamento: Optional[str]  # 'pago', 'pendente', etc
    eh_usuario_venda: bool = False  # Indica se é o usuário que fez a venda
    
class SplitDetalhado(BaseModel):
    tipo_split: str  # 'pre_venda', 'venda', 'carne', 'fatura_avulsa', 'fatura_recorrente'
    id_referencia: str  # ID da pré-venda, carnê, fatura, etc
    data_criacao: date
    valor_base: float  # Valor sobre o qual o split é calculado
    status_geral: str  # Status do pagamento principal
    data_pagamento: Optional[date]
    beneficiarios: List[BeneficiarioSplit]
    
# Modelos adicionais para a nova página
class VendaResumo(BaseModel):
    venda_id: int
    documento_venda: str
    data_venda: date
    paciente_nome: str
    valor_bruto: float
    valor_liquido: float
    usuario_venda_nome: str
    total_splits: int
    valor_total_splits: float
    tipos_split: List[str]

class RankingUsuario(BaseModel):
    usuario_id: int
    usuario_nome: str
    usuario_email: str
    receiver_id: Optional[str]
    total_recebido: float
    quantidade_splits: int
    vendas_participadas: int
    tipos_split_recebidos: List[str]
    percentual_medio: float

class EstatisticasSplits(BaseModel):
    total_vendas_com_splits: int
    valor_total_splits: float
    ticket_medio_splits: float
    beneficiarios_unicos: int
    splits_por_tipo: Dict[str, Dict[str, float]]

class OpcoesFiltros(BaseModel):
    usuarios: List[Dict[str, Any]]
    unidades: List[str]
    tipos_split: List[str]
    status_vendas: List[str]

class VendasPaginado(BaseModel):
    vendas: List[VendaResumo]
    total: int
    page: int
    per_page: int
    total_pages: int

class VendaComTodosSplits(BaseModel):
    venda_id: int
    documento_venda: str
    data_venda: date
    paciente_nome: str
    paciente_cpf: str
    odontograma_tipo: Optional[str]
    valor_bruto: float
    valor_liquido: float
    unidade: str
    status_venda: str
    usuario_venda: Dict[str, Any]
    splits_detalhados: List[SplitDetalhado]
    resumo_splits: Dict[str, Any]

def obter_beneficiario_por_seller_id_com_contexto_venda(cursor, seller_id: str, venda_id: int = None, pre_venda_id: str = None) -> Dict[str, Any]:
    """
    Busca o beneficiário considerando o contexto da venda.
    Prioriza o usuário que fez a venda/pré-venda quando há múltiplos com mesmo receiver_id.
    """
    # Primeiro, identificar quem fez a venda/pré-venda
    usuario_venda_receiver = None
    usuario_venda_id = None
    
    if venda_id:
        cursor.execute("""
            SELECT 
                u.id,
                u.bempaggo_receiver_id
            FROM vendas v
            JOIN users u ON v.usuario_venda_id = u.id
            WHERE v.id = %s
        """, (venda_id,))
        
        result = cursor.fetchone()
        if result:
            usuario_venda_id = result[0]
            usuario_venda_receiver = result[1]
    
    # Se temos pré-venda, verificar também quem criou a pré-venda
    if pre_venda_id and not usuario_venda_receiver:
        # Verificar se existe alguma venda associada à pré-venda
        cursor.execute("""
            SELECT 
                v.usuario_venda_id,
                u.bempaggo_receiver_id
            FROM vendas v
            JOIN users u ON v.usuario_venda_id = u.id
            WHERE v.pre_venda_id = %s
            LIMIT 1
        """, (pre_venda_id,))
        
        result = cursor.fetchone()
        if result:
            usuario_venda_id = result[0]
            usuario_venda_receiver = result[1]
    
    # Se o usuário da venda tem o receiver_id que estamos procurando, priorizar ele
    if usuario_venda_receiver == seller_id and usuario_venda_id:
        cursor.execute("""
            SELECT 
                id,
                nome,
                cpf,
                unidade
            FROM users 
            WHERE id = %s
        """, (usuario_venda_id,))
        
        result = cursor.fetchone()
        if result:
            return {
                "tipo": "usuario",
                "id_beneficiario": result[0],
                "nome_beneficiario": result[1],
                "cpf_cnpj": result[2],
                "eh_usuario_venda": True
            }
    
    # Se não, buscar qualquer usuário com esse receiver_id
    cursor.execute("""
        SELECT 
            id,
            nome,
            cpf,
            unidade
        FROM users 
        WHERE bempaggo_receiver_id = %s
        ORDER BY 
            CASE WHEN id = %s THEN 0 ELSE 1 END,  -- Ainda prioriza o usuário da venda se existir
            id
        LIMIT 1
    """, (seller_id, usuario_venda_id or 0))
    
    result = cursor.fetchone()
    if result:
        return {
            "tipo": "usuario",
            "id_beneficiario": result[0],
            "nome_beneficiario": result[1],
            "cpf_cnpj": result[2],
            "eh_usuario_venda": result[0] == usuario_venda_id
        }
    
    # Se não encontrou usuário, tentar buscar empresa
    cursor.execute("""
        SELECT 
            id,
            razao_social,
            cnpj,
            unidade
        FROM empresas 
        WHERE bempaggo_receiver_id = %s
        LIMIT 1
    """, (seller_id,))
    
    result = cursor.fetchone()
    if result:
        return {
            "tipo": "empresa",
            "id_beneficiario": result[0],
            "nome_beneficiario": result[1],
            "cpf_cnpj": result[2],
            "eh_usuario_venda": False
        }
    
    # Se não encontrou nem usuário nem empresa
    return {
        "tipo": "outro",
        "id_beneficiario": None,
        "nome_beneficiario": f"Seller {seller_id}",
        "cpf_cnpj": None,
        "eh_usuario_venda": False
    }

@router.get("/venda-completa/{venda_id}")
async def obter_todos_splits_venda_v6(
    venda_id: int,
    current_user: dict = Depends(get_current_user)
) -> VendaComTodosSplits:
    """
    Obter TODOS os splits de uma venda com mapeamento inteligente de beneficiários.
    
    **Melhorias V6:**
    - Identifica quem fez a venda/pré-venda
    - Quando há múltiplos usuários com mesmo receiver_id, prioriza quem fez a venda
    - Marca quando o beneficiário é o próprio usuário que fez a venda
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # 1. Buscar informações completas da venda
            cursor.execute("""
                SELECT 
                    v.id,
                    v.documento_venda,
                    v.data_venda,
                    p.nome_paciente,
                    p.cpf_cnpj,
                    od.tipo,
                    v.valor_bruto_total,
                    v.valor_liquido_total,
                    v.unidade,
                    v.status_venda,
                    v.pre_venda_id,
                    v.carne_id,
                    v.usuario_venda_id,
                    u.nome as usuario_nome,
                    u.email as usuario_email,
                    u.bempaggo_receiver_id as usuario_receiver_id,
                    u.unidade as usuario_unidade
                FROM vendas v
                JOIN pacientes p ON v.paciente_id = p.paciente_id
                LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                LEFT JOIN users u ON v.usuario_venda_id = u.id
                WHERE v.id = %s
            """, (venda_id,))
            
            venda = cursor.fetchone()
            if not venda:
                raise HTTPException(status_code=404, detail="Venda não encontrada")
            
            # Extrair dados da venda
            pre_venda_id = venda[10]
            carne_id = venda[11]
            usuario_venda_id = venda[12]
            
            # Informações do usuário que fez a venda
            usuario_venda = {
                "id": usuario_venda_id,
                "nome": venda[13],
                "email": venda[14],
                "receiver_id": venda[15],
                "unidade": venda[16]
            }
            
            logger.info(f"Venda {venda_id} feita por: {usuario_venda['nome']} (receiver_id: {usuario_venda['receiver_id']})")
            
            # Preparar resposta
            splits_detalhados = []
            resumo_splits = {
                "total_beneficiarios": 0,
                "total_splits": 0,
                "valor_total_splits": 0,
                "splits_por_tipo": {},
                "beneficiarios_unicos": set()
            }
            
            # 2. Buscar splits da pré-venda
            if pre_venda_id:
                cursor.execute("""
                    SELECT 
                        pvs.seller_id,
                        pvs.percentage,
                        pvs.valor_calculado,
                        pvs.user_id,
                        pvs.empresa_id,
                        pve.valor_pago,
                        pve.status,
                        pve.updated_at as data_pagamento,
                        pve.created_at
                    FROM pre_venda_splits pvs
                    LEFT JOIN pre_vendas_entradas pve ON pvs.pre_venda_id = pve.pre_venda_id
                    WHERE pvs.pre_venda_id = %s
                    ORDER BY pvs.percentage DESC
                """, (pre_venda_id,))
                
                pre_venda_splits = cursor.fetchall()
                if pre_venda_splits:
                    # Pegar informações da primeira linha
                    primeira_linha = pre_venda_splits[0]
                    valor_pago = float(primeira_linha[5]) if primeira_linha[5] else 0
                    status_pagamento = primeira_linha[6]
                    data_pagamento = primeira_linha[7]
                    data_criacao = primeira_linha[8]
                    
                    beneficiarios = []
                    for split in pre_venda_splits:
                        # Buscar beneficiário considerando o contexto da venda
                        beneficiario_info = obter_beneficiario_por_seller_id_com_contexto_venda(
                            cursor, split[0], venda_id, pre_venda_id
                        )
                        
                        logger.debug(f"Split seller_id {split[0]} mapeado para: {beneficiario_info['nome_beneficiario']} (é usuário da venda: {beneficiario_info['eh_usuario_venda']})")
                        
                        beneficiarios.append(BeneficiarioSplit(
                            seller_id=split[0],
                            tipo=beneficiario_info["tipo"],
                            id_beneficiario=beneficiario_info["id_beneficiario"],
                            nome_beneficiario=beneficiario_info["nome_beneficiario"],
                            cpf_cnpj=beneficiario_info["cpf_cnpj"],
                            percentage=float(split[1]),
                            valor_calculado=float(split[2]) if split[2] else 0,
                            status_pagamento=status_pagamento,
                            eh_usuario_venda=beneficiario_info["eh_usuario_venda"]
                        ))
                        
                        # Atualizar resumo
                        if beneficiario_info["id_beneficiario"]:
                            resumo_splits["beneficiarios_unicos"].add(
                                f"{beneficiario_info['tipo']}_{beneficiario_info['id_beneficiario']}"
                            )
                    
                    splits_detalhados.append(SplitDetalhado(
                        tipo_split="pre_venda",
                        id_referencia=pre_venda_id,
                        data_criacao=data_criacao.date() if data_criacao else venda[2],
                        valor_base=valor_pago,
                        status_geral=status_pagamento or "pendente",
                        data_pagamento=data_pagamento.date() if data_pagamento else None,
                        beneficiarios=beneficiarios
                    ))
                    
                    resumo_splits["splits_por_tipo"]["pre_venda"] = {
                        "quantidade": len(beneficiarios),
                        "valor_total": sum(b.valor_calculado for b in beneficiarios)
                    }
            
            # 3. Buscar splits do carnê
            if carne_id:
                cursor.execute("""
                    SELECT 
                        cs.seller_id,
                        cs.percentage,
                        cs.user_id,
                        cs.empresa_id,
                        cp.valor_parcela,
                        cp.total_parcelas,
                        cp.data_criacao,
                        (SELECT COUNT(*) FROM carne_parcelas WHERE carne_id = cp.id AND status = 'paid') as parcelas_pagas
                    FROM carne_splits cs
                    LEFT JOIN carne_pagamento cp ON cs.carne_id = cp.id
                    WHERE cs.carne_id = %s
                    ORDER BY cs.percentage DESC
                """, (carne_id,))
                
                carne_splits = cursor.fetchall()
                if carne_splits:
                    primeira_linha = carne_splits[0]
                    valor_parcela = float(primeira_linha[4]) if primeira_linha[4] else 0
                    qtd_parcelas = primeira_linha[5]
                    data_criacao = primeira_linha[6]
                    parcelas_pagas = primeira_linha[7]
                    valor_total = valor_parcela * qtd_parcelas
                    
                    beneficiarios = []
                    for split in carne_splits:
                        # Buscar beneficiário considerando o contexto
                        beneficiario_info = obter_beneficiario_por_seller_id_com_contexto_venda(
                            cursor, str(split[0]), venda_id, pre_venda_id
                        )
                        
                        valor_split_total = valor_total * float(split[1]) / 100
                        
                        beneficiarios.append(BeneficiarioSplit(
                            seller_id=str(split[0]),
                            tipo=beneficiario_info["tipo"],
                            id_beneficiario=beneficiario_info["id_beneficiario"],
                            nome_beneficiario=beneficiario_info["nome_beneficiario"],
                            cpf_cnpj=beneficiario_info["cpf_cnpj"],
                            percentage=float(split[1]),
                            valor_calculado=round(valor_split_total, 2),
                            status_pagamento=f"{parcelas_pagas}/{qtd_parcelas} pagas",
                            eh_usuario_venda=beneficiario_info["eh_usuario_venda"]
                        ))
                        
                        if beneficiario_info["id_beneficiario"]:
                            resumo_splits["beneficiarios_unicos"].add(
                                f"{beneficiario_info['tipo']}_{beneficiario_info['id_beneficiario']}"
                            )
                    
                    splits_detalhados.append(SplitDetalhado(
                        tipo_split="carne",
                        id_referencia=str(carne_id),
                        data_criacao=data_criacao.date() if data_criacao else venda[2],
                        valor_base=valor_total,
                        status_geral=f"{parcelas_pagas}/{qtd_parcelas} parcelas pagas",
                        data_pagamento=None,
                        beneficiarios=beneficiarios
                    ))
                    
                    resumo_splits["splits_por_tipo"]["carne"] = {
                        "quantidade": len(beneficiarios),
                        "valor_total": sum(b.valor_calculado for b in beneficiarios)
                    }
            
            # 4. Buscar splits de faturas avulsas
            cursor.execute("""
                SELECT 
                    fas.seller_id,
                    fas.percentage,
                    fas.user_id,
                    fas.empresa_id,
                    fa.id,
                    fa.valor_total,
                    fa.status,
                    fa.data_pagamento,
                    fa.criado_em
                FROM fatura_avulsa_splits fas
                LEFT JOIN fatura_avulsa fa ON fas.invoice_id = fa.id
                WHERE fa.venda_id = %s
                ORDER BY fa.id, fas.percentage DESC
            """, (venda_id,))
            
            faturas_splits = cursor.fetchall()
            faturas_processadas = {}
            
            for split in faturas_splits:
                fatura_id = split[4]
                
                if fatura_id not in faturas_processadas:
                    faturas_processadas[fatura_id] = {
                        "valor_total": float(split[5]) if split[5] else 0,
                        "status": split[6],
                        "data_pagamento": split[7],
                        "data_criacao": split[8],
                        "beneficiarios": []
                    }
                
                # Buscar beneficiário considerando o contexto
                beneficiario_info = obter_beneficiario_por_seller_id_com_contexto_venda(
                    cursor, str(split[0]), venda_id, pre_venda_id
                )
                
                valor_calculado = faturas_processadas[fatura_id]["valor_total"] * float(split[1]) / 100
                
                faturas_processadas[fatura_id]["beneficiarios"].append(BeneficiarioSplit(
                    seller_id=str(split[0]),
                    tipo=beneficiario_info["tipo"],
                    id_beneficiario=beneficiario_info["id_beneficiario"],
                    nome_beneficiario=beneficiario_info["nome_beneficiario"],
                    cpf_cnpj=beneficiario_info["cpf_cnpj"],
                    percentage=float(split[1]),
                    valor_calculado=round(valor_calculado, 2),
                    status_pagamento=split[6],
                    eh_usuario_venda=beneficiario_info["eh_usuario_venda"]
                ))
                
                if beneficiario_info["id_beneficiario"]:
                    resumo_splits["beneficiarios_unicos"].add(
                        f"{beneficiario_info['tipo']}_{beneficiario_info['id_beneficiario']}"
                    )
            
            # Adicionar faturas ao resultado
            for fatura_id, fatura_data in faturas_processadas.items():
                splits_detalhados.append(SplitDetalhado(
                    tipo_split="fatura_avulsa",
                    id_referencia=str(fatura_id),
                    data_criacao=fatura_data["data_criacao"].date() if fatura_data["data_criacao"] else venda[2],
                    valor_base=fatura_data["valor_total"],
                    status_geral=fatura_data["status"] or "pendente",
                    data_pagamento=fatura_data["data_pagamento"].date() if fatura_data["data_pagamento"] else None,
                    beneficiarios=fatura_data["beneficiarios"]
                ))
                
                if "fatura_avulsa" not in resumo_splits["splits_por_tipo"]:
                    resumo_splits["splits_por_tipo"]["fatura_avulsa"] = {
                        "quantidade": 0,
                        "valor_total": 0
                    }
                
                resumo_splits["splits_por_tipo"]["fatura_avulsa"]["quantidade"] += len(fatura_data["beneficiarios"])
                resumo_splits["splits_por_tipo"]["fatura_avulsa"]["valor_total"] += sum(
                    b.valor_calculado for b in fatura_data["beneficiarios"]
                )
            
            # 5. Buscar splits de faturas recorrentes
            cursor.execute("""
                SELECT 
                    frs.seller_id,
                    frs.percentage,
                    frs.user_id,
                    frs.empresa_id,
                    frs.subscription_id,
                    fr.valor_mensal,
                    fr.status,
                    frs.created_at
                FROM fatura_recorrente_splits frs
                LEFT JOIN fatura_recorrente fr ON frs.subscription_id = fr.subscription_id
                WHERE fr.venda_id = %s
                ORDER BY frs.percentage DESC
            """, (venda_id,))
            
            recorrente_splits = cursor.fetchall()
            if recorrente_splits:
                primeira_linha = recorrente_splits[0]
                subscription_id = primeira_linha[4]
                valor_mensal = float(primeira_linha[5]) if primeira_linha[5] else 0
                status = primeira_linha[6]
                data_criacao = primeira_linha[7]
                
                beneficiarios = []
                for split in recorrente_splits:
                    # Buscar beneficiário considerando o contexto
                    beneficiario_info = obter_beneficiario_por_seller_id_com_contexto_venda(
                        cursor, str(split[0]), venda_id, pre_venda_id
                    )
                    
                    valor_calculado = valor_mensal * float(split[1]) / 100
                    
                    beneficiarios.append(BeneficiarioSplit(
                        seller_id=str(split[0]),
                        tipo=beneficiario_info["tipo"],
                        id_beneficiario=beneficiario_info["id_beneficiario"],
                        nome_beneficiario=beneficiario_info["nome_beneficiario"],
                        cpf_cnpj=beneficiario_info["cpf_cnpj"],
                        percentage=float(split[1]),
                        valor_calculado=round(valor_calculado, 2),
                        status_pagamento=status,
                        eh_usuario_venda=beneficiario_info["eh_usuario_venda"]
                    ))
                    
                    if beneficiario_info["id_beneficiario"]:
                        resumo_splits["beneficiarios_unicos"].add(
                            f"{beneficiario_info['tipo']}_{beneficiario_info['id_beneficiario']}"
                        )
                
                splits_detalhados.append(SplitDetalhado(
                    tipo_split="fatura_recorrente",
                    id_referencia=str(subscription_id),
                    data_criacao=data_criacao.date() if data_criacao else venda[2],
                    valor_base=valor_mensal,
                    status_geral=status or "ativo",
                    data_pagamento=None,
                    beneficiarios=beneficiarios
                ))
                
                resumo_splits["splits_por_tipo"]["fatura_recorrente"] = {
                    "quantidade": len(beneficiarios),
                    "valor_total": sum(b.valor_calculado for b in beneficiarios)
                }
            
            # Calcular totais do resumo
            resumo_splits["total_beneficiarios"] = len(resumo_splits["beneficiarios_unicos"])
            resumo_splits["beneficiarios_unicos"] = list(resumo_splits["beneficiarios_unicos"])
            
            for tipo_data in resumo_splits["splits_por_tipo"].values():
                resumo_splits["total_splits"] += tipo_data["quantidade"]
                resumo_splits["valor_total_splits"] += tipo_data["valor_total"]
            
            resumo_splits["valor_total_splits"] = round(resumo_splits["valor_total_splits"], 2)
            
            # Montar resposta final
            return VendaComTodosSplits(
                venda_id=venda[0],
                documento_venda=venda[1],
                data_venda=venda[2].date() if venda[2] and hasattr(venda[2], 'date') else venda[2],
                paciente_nome=venda[3],
                paciente_cpf=venda[4],
                odontograma_tipo=venda[5],
                valor_bruto=float(venda[6]) if venda[6] else 0,
                valor_liquido=float(venda[7]) if venda[7] else 0,
                unidade=venda[8],
                status_venda=venda[9],
                usuario_venda=usuario_venda,
                splits_detalhados=splits_detalhados,
                resumo_splits=resumo_splits
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter todos os splits da venda {venda_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter splits da venda: {str(e)}"
        )

@router.get("/vendas-paginado")
async def obter_vendas_com_splits_paginado(
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    usuario_id: Optional[int] = Query(None, description="ID do usuário"),
    tipo_split: Optional[str] = Query(None, description="Tipo de split"),
    unidade: Optional[str] = Query(None, description="Unidade"),
    status: Optional[str] = Query(None, description="Status da venda"),
    page: int = Query(1, ge=1, description="Página"),
    per_page: int = Query(20, ge=1, le=100, description="Items por página"),
    search: Optional[str] = Query(None, description="Busca por documento ou paciente"),
    current_user: dict = Depends(get_current_user)
) -> VendasPaginado:
    """
    Obter lista paginada de vendas com resumo de splits
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Construir filtros
            where_conditions = []
            params = []
            
            if data_inicio:
                where_conditions.append("v.data_venda >= %s")
                params.append(data_inicio)
            
            if data_fim:
                where_conditions.append("v.data_venda <= %s")
                params.append(data_fim)
            
            if usuario_id:
                where_conditions.append("v.usuario_venda_id = %s")
                params.append(usuario_id)
            
            if unidade and unidade != 'Todas Unidades':
                where_conditions.append("v.unidade = %s")
                params.append(unidade)
            
            if status and status != 'Todos':
                where_conditions.append("v.status_venda = %s")
                params.append(status)
            
            if search:
                where_conditions.append("(v.documento_venda ILIKE %s OR p.nome_paciente ILIKE %s)")
                search_param = f"%{search}%"
                params.extend([search_param, search_param])
            
            # Query principal para contar total
            base_query = """
                FROM vendas v
                JOIN pacientes p ON v.paciente_id = p.paciente_id
                JOIN users u ON v.usuario_venda_id = u.id
                WHERE (
                    EXISTS (SELECT 1 FROM pre_venda_splits WHERE pre_venda_id = v.pre_venda_id)
                    OR EXISTS (SELECT 1 FROM carne_splits WHERE carne_id = v.carne_id)
                    OR EXISTS (SELECT 1 FROM fatura_avulsa fa JOIN fatura_avulsa_splits fas ON fa.id = fas.invoice_id WHERE fa.venda_id = v.id)
                    OR EXISTS (SELECT 1 FROM fatura_recorrente fr JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id WHERE fr.venda_id = v.id)
                )
            """
            
            if where_conditions:
                base_query += " AND " + " AND ".join(where_conditions)
            
            # Contar total
            count_query = f"SELECT COUNT(DISTINCT v.id) {base_query}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # Calcular paginação
            offset = (page - 1) * per_page
            total_pages = (total + per_page - 1) // per_page
            
            # Query principal com dados
            main_query = f"""
                SELECT DISTINCT
                    v.id,
                    v.documento_venda,
                    v.data_venda,
                    p.nome_paciente,
                    v.valor_bruto_total,
                    v.valor_liquido_total,
                    u.nome as usuario_nome
                {base_query}
                ORDER BY v.data_venda DESC, v.id DESC
                LIMIT %s OFFSET %s
            """
            
            cursor.execute(main_query, params + [per_page, offset])
            vendas_data = cursor.fetchall()
            
            vendas = []
            for venda in vendas_data:
                venda_id = venda[0]
                
                # Calcular resumo de splits para cada venda
                total_splits = 0
                valor_total_splits = 0
                tipos_split = set()
                
                # Pre-venda splits
                cursor.execute("""
                    SELECT COUNT(*), COALESCE(SUM(valor_calculado), 0)
                    FROM pre_venda_splits 
                    WHERE pre_venda_id = (SELECT pre_venda_id FROM vendas WHERE id = %s)
                """, (venda_id,))
                pre_venda_result = cursor.fetchone()
                if pre_venda_result[0] > 0:
                    total_splits += pre_venda_result[0]
                    valor_total_splits += float(pre_venda_result[1])
                    tipos_split.add("pre_venda")
                
                # Carne splits
                cursor.execute("""
                    SELECT COUNT(*), cp.valor_parcela, cp.total_parcelas
                    FROM carne_splits cs
                    JOIN carne_pagamento cp ON cs.carne_id = cp.id
                    WHERE cs.carne_id = (SELECT carne_id FROM vendas WHERE id = %s)
                    GROUP BY cp.valor_parcela, cp.total_parcelas
                """, (venda_id,))
                carne_result = cursor.fetchone()
                if carne_result and carne_result[0] > 0:
                    total_splits += carne_result[0]
                    valor_carne = float(carne_result[1]) * carne_result[2] if carne_result[1] and carne_result[2] else 0
                    cursor.execute("""
                        SELECT SUM(percentage) FROM carne_splits cs
                        WHERE cs.carne_id = (SELECT carne_id FROM vendas WHERE id = %s)
                    """, (venda_id,))
                    total_percentage = cursor.fetchone()[0] or 0
                    valor_total_splits += valor_carne * (float(total_percentage) / 100)
                    tipos_split.add("carne")
                
                # Fatura avulsa splits
                cursor.execute("""
                    SELECT COUNT(*), COALESCE(SUM(fa.valor_total * fas.percentage / 100), 0)
                    FROM fatura_avulsa fa
                    JOIN fatura_avulsa_splits fas ON fa.id = fas.invoice_id
                    WHERE fa.venda_id = %s
                """, (venda_id,))
                fatura_avulsa_result = cursor.fetchone()
                if fatura_avulsa_result[0] > 0:
                    total_splits += fatura_avulsa_result[0]
                    valor_total_splits += float(fatura_avulsa_result[1])
                    tipos_split.add("fatura_avulsa")
                
                # Fatura recorrente splits
                cursor.execute("""
                    SELECT COUNT(*), COALESCE(SUM(fr.valor_mensal * frs.percentage / 100), 0)
                    FROM fatura_recorrente fr
                    JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id
                    WHERE fr.venda_id = %s
                """, (venda_id,))
                fatura_recorrente_result = cursor.fetchone()
                if fatura_recorrente_result[0] > 0:
                    total_splits += fatura_recorrente_result[0]
                    valor_total_splits += float(fatura_recorrente_result[1])
                    tipos_split.add("fatura_recorrente")
                
                vendas.append(VendaResumo(
                    venda_id=venda_id,
                    documento_venda=venda[1],
                    data_venda=venda[2].date() if venda[2] else None,
                    paciente_nome=venda[3],
                    valor_bruto=float(venda[4]) if venda[4] else 0,
                    valor_liquido=float(venda[5]) if venda[5] else 0,
                    usuario_venda_nome=venda[6],
                    total_splits=total_splits,
                    valor_total_splits=round(valor_total_splits, 2),
                    tipos_split=list(tipos_split)
                ))
            
            return VendasPaginado(
                vendas=vendas,
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages
            )
            
    except Exception as e:
        logger.error(f"Erro ao obter vendas paginadas: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter vendas: {str(e)}"
        )

@router.get("/ranking-usuarios")
async def obter_ranking_usuarios_splits(
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    tipo_split: Optional[str] = Query(None, description="Tipo de split"),
    unidade: Optional[str] = Query(None, description="Unidade"),
    limit: int = Query(10, ge=1, le=50, description="Limite de resultados"),
    current_user: dict = Depends(get_current_user)
) -> List[RankingUsuario]:
    """
    Obter ranking de usuários que mais recebem splits
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Construir filtros de data
            date_filter = ""
            date_params = []
            if data_inicio:
                date_filter += " AND v.data_venda >= %s"
                date_params.append(data_inicio)
            if data_fim:
                date_filter += " AND v.data_venda <= %s"
                date_params.append(data_fim)
            
            # Buscar splits de todas as tabelas
            # Combinando pre_venda_splits, carne_splits, etc.
            query = f"""
                WITH all_splits AS (
                    -- Pre-venda splits
                    SELECT 
                        pvs.seller_id as receiver_id,
                        pvs.valor_calculado,
                        pvs.percentage as percentual_aplicado,
                        v.id as venda_id,
                        v.data_venda,
                        v.usuario_venda_id,
                        pvs.pre_venda_id as referencia_id,
                        'pre_venda' as tipo_split
                    FROM pre_venda_splits pvs
                    INNER JOIN vendas v ON v.pre_venda_id = pvs.pre_venda_id
                    WHERE 1=1 {date_filter}
                    
                    UNION ALL
                    
                    -- Carne splits
                    SELECT 
                        cs.seller_id::text as receiver_id,
                        cp.valor_parcela * cp.total_parcelas * cs.percentage / 100 as valor_calculado,
                        cs.percentage as percentual_aplicado,
                        v.id as venda_id,
                        v.data_venda,
                        v.usuario_venda_id,
                        cs.carne_id::text as referencia_id,
                        'carne' as tipo_split
                    FROM carne_splits cs
                    INNER JOIN carne_pagamento cp ON cs.carne_id = cp.id
                    INNER JOIN vendas v ON v.carne_id = cs.carne_id
                    WHERE 1=1 {date_filter}
                    
                    UNION ALL
                    
                    -- Fatura avulsa splits
                    SELECT 
                        fas.seller_id::text as receiver_id,
                        fa.valor_total * fas.percentage / 100 as valor_calculado,
                        fas.percentage as percentual_aplicado,
                        v.id as venda_id,
                        v.data_venda,
                        v.usuario_venda_id,
                        fas.invoice_id::text as referencia_id,
                        'fatura_avulsa' as tipo_split
                    FROM fatura_avulsa_splits fas
                    INNER JOIN fatura_avulsa fa ON fas.invoice_id = fa.id
                    INNER JOIN vendas v ON v.id = fa.venda_id
                    WHERE 1=1 {date_filter}
                    
                    UNION ALL
                    
                    -- Fatura recorrente splits
                    SELECT 
                        frs.seller_id::text as receiver_id,
                        fr.valor_mensal * frs.percentage / 100 as valor_calculado,
                        frs.percentage as percentual_aplicado,
                        v.id as venda_id,
                        v.data_venda,
                        v.usuario_venda_id,
                        frs.subscription_id::text as referencia_id,
                        'fatura_recorrente' as tipo_split
                    FROM fatura_recorrente_splits frs
                    INNER JOIN fatura_recorrente fr ON frs.subscription_id = fr.subscription_id
                    INNER JOIN vendas v ON v.id = fr.venda_id
                    WHERE 1=1 {date_filter}
                )
                SELECT * FROM all_splits
            """
            
            cursor.execute(query, date_params + date_params + date_params + date_params)
            splits_data = cursor.fetchall()
            
            # Processar cada split usando a lógica de contexto de venda
            ranking_data = {}
            
            for split in splits_data:
                receiver_id = split[0]
                valor_calculado = split[1]
                percentual_aplicado = split[2]
                venda_id = split[3]
                data_venda = split[4]
                usuario_venda_id = split[5]
                referencia_id = split[6]
                tipo_split = split[7]
                
                # Usar a função existente para obter o beneficiário correto
                beneficiario_info = obter_beneficiario_por_seller_id_com_contexto_venda(
                    cursor, receiver_id, venda_id=venda_id
                )
                
                # Só processar se for usuário (não empresa)
                if beneficiario_info and beneficiario_info['tipo'] == 'usuario':
                    user_id = beneficiario_info['id_beneficiario']
                    
                    if user_id not in ranking_data:
                        # Buscar dados do usuário
                        cursor.execute("""
                            SELECT nome, email, bempaggo_receiver_id 
                            FROM users 
                            WHERE id = %s
                        """, (user_id,))
                        user_data = cursor.fetchone()
                        
                        if user_data:
                            ranking_data[user_id] = {
                                'usuario_id': user_id,
                                'usuario_nome': user_data[0],
                                'usuario_email': user_data[1],
                                'receiver_id': user_data[2],
                                'total_recebido': 0,
                                'quantidade_splits': 0,
                                'vendas_participadas': set(),
                                'tipos_split_recebidos': set(),
                                'percentuais': []
                            }
                    
                    # Acumular dados
                    ranking_data[user_id]['total_recebido'] += float(valor_calculado)
                    ranking_data[user_id]['quantidade_splits'] += 1
                    ranking_data[user_id]['vendas_participadas'].add(venda_id)
                    ranking_data[user_id]['tipos_split_recebidos'].add(tipo_split)
                    ranking_data[user_id]['percentuais'].append(float(percentual_aplicado))
            
            # Converter para lista e ordenar
            resultados = []
            for user_id, data in ranking_data.items():
                resultados.append((
                    data['usuario_id'],
                    data['usuario_nome'],
                    data['usuario_email'],
                    data['receiver_id'],
                    data['total_recebido'],
                    data['quantidade_splits'],
                    len(data['vendas_participadas']),
                    list(data['tipos_split_recebidos']),
                    sum(data['percentuais']) / len(data['percentuais']) if data['percentuais'] else 0
                ))
            
            # Ordenar por total recebido e limitar
            resultados.sort(key=lambda x: x[4], reverse=True)
            resultados = resultados[:limit]
            
            ranking = []
            for row in resultados:
                ranking.append(RankingUsuario(
                    usuario_id=row[0],
                    usuario_nome=row[1],
                    usuario_email=row[2],
                    receiver_id=row[3],
                    total_recebido=float(row[4]) if row[4] else 0,
                    quantidade_splits=row[5],
                    vendas_participadas=row[6],
                    tipos_split_recebidos=row[7] if row[7] else [],
                    percentual_medio=float(row[8]) if row[8] else 0
                ))
            
            return ranking
            
    except Exception as e:
        logger.error(f"Erro ao obter ranking de usuários: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter ranking: {str(e)}"
        )

@router.get("/estatisticas")
async def obter_estatisticas_splits(
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    tipo_split: Optional[str] = Query(None, description="Tipo de split"),
    unidade: Optional[str] = Query(None, description="Unidade"),
    current_user: dict = Depends(get_current_user)
) -> EstatisticasSplits:
    """
    Obter estatísticas gerais de splits
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Construir filtros
            where_conditions = []
            params = []
            
            if data_inicio:
                where_conditions.append("v.data_venda >= %s")
                params.append(data_inicio)
            
            if data_fim:
                where_conditions.append("v.data_venda <= %s")
                params.append(data_fim)
            
            if unidade and unidade != 'Todas Unidades':
                where_conditions.append("v.unidade = %s")
                params.append(unidade)
            
            where_clause = ""
            if where_conditions:
                where_clause = " AND " + " AND ".join(where_conditions)
            
            # Total de vendas com splits
            query_vendas = f"""
                SELECT COUNT(DISTINCT v.id)
                FROM vendas v
                WHERE (
                    EXISTS (SELECT 1 FROM pre_venda_splits WHERE pre_venda_id = v.pre_venda_id)
                    OR EXISTS (SELECT 1 FROM carne_splits WHERE carne_id = v.carne_id)
                    OR EXISTS (SELECT 1 FROM fatura_avulsa fa JOIN fatura_avulsa_splits fas ON fa.id = fas.invoice_id WHERE fa.venda_id = v.id)
                    OR EXISTS (SELECT 1 FROM fatura_recorrente fr JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id WHERE fr.venda_id = v.id)
                ) {where_clause}
            """
            
            cursor.execute(query_vendas, params)
            total_vendas = cursor.fetchone()[0]
            
            # Estatísticas por tipo de split
            splits_por_tipo = {}
            valor_total_geral = 0
            beneficiarios_unicos = set()
            
            # Pre-venda
            cursor.execute(f"""
                SELECT COUNT(*), COALESCE(SUM(pvs.valor_calculado), 0)
                FROM pre_venda_splits pvs
                JOIN vendas v ON v.pre_venda_id = pvs.pre_venda_id
                WHERE 1=1 {where_clause}
            """, params)
            pre_venda_stats = cursor.fetchone()
            if pre_venda_stats[0] > 0:
                splits_por_tipo["pre_venda"] = {
                    "quantidade": pre_venda_stats[0],
                    "valor_total": float(pre_venda_stats[1])
                }
                valor_total_geral += float(pre_venda_stats[1])
            
            # Carne
            cursor.execute(f"""
                SELECT COUNT(*), COALESCE(SUM(cp.valor_parcela * cp.total_parcelas * cs.percentage / 100), 0)
                FROM carne_splits cs
                JOIN carne_pagamento cp ON cs.carne_id = cp.id
                JOIN vendas v ON v.carne_id = cs.carne_id
                WHERE 1=1 {where_clause}
            """, params)
            carne_stats = cursor.fetchone()
            if carne_stats[0] > 0:
                splits_por_tipo["carne"] = {
                    "quantidade": carne_stats[0],
                    "valor_total": float(carne_stats[1])
                }
                valor_total_geral += float(carne_stats[1])
            
            # Fatura avulsa
            cursor.execute(f"""
                SELECT COUNT(*), COALESCE(SUM(fa.valor_total * fas.percentage / 100), 0)
                FROM fatura_avulsa_splits fas
                JOIN fatura_avulsa fa ON fas.invoice_id = fa.id
                JOIN vendas v ON v.id = fa.venda_id
                WHERE 1=1 {where_clause}
            """, params)
            fatura_avulsa_stats = cursor.fetchone()
            if fatura_avulsa_stats[0] > 0:
                splits_por_tipo["fatura_avulsa"] = {
                    "quantidade": fatura_avulsa_stats[0],
                    "valor_total": float(fatura_avulsa_stats[1])
                }
                valor_total_geral += float(fatura_avulsa_stats[1])
            
            # Fatura recorrente
            cursor.execute(f"""
                SELECT COUNT(*), COALESCE(SUM(fr.valor_mensal * frs.percentage / 100), 0)
                FROM fatura_recorrente_splits frs
                JOIN fatura_recorrente fr ON frs.subscription_id = frs.subscription_id
                JOIN vendas v ON v.id = fr.venda_id
                WHERE 1=1 {where_clause}
            """, params)
            fatura_recorrente_stats = cursor.fetchone()
            if fatura_recorrente_stats[0] > 0:
                splits_por_tipo["fatura_recorrente"] = {
                    "quantidade": fatura_recorrente_stats[0],
                    "valor_total": float(fatura_recorrente_stats[1])
                }
                valor_total_geral += float(fatura_recorrente_stats[1])
            
            # Contar beneficiários únicos
            cursor.execute(f"""
                SELECT COUNT(DISTINCT 
                    CASE 
                        WHEN u.id IS NOT NULL THEN CONCAT('user_', u.id)
                        WHEN e.id IS NOT NULL THEN CONCAT('empresa_', e.id)
                        ELSE seller_id
                    END
                )
                FROM (
                    SELECT pvs.seller_id FROM pre_venda_splits pvs 
                    JOIN vendas v ON v.pre_venda_id = pvs.pre_venda_id 
                    WHERE 1=1 {where_clause}
                    UNION
                    SELECT cs.seller_id::text FROM carne_splits cs 
                    JOIN vendas v ON v.carne_id = cs.carne_id 
                    WHERE 1=1 {where_clause}
                    UNION
                    SELECT fas.seller_id::text FROM fatura_avulsa_splits fas 
                    JOIN fatura_avulsa fa ON fas.invoice_id = fa.id 
                    JOIN vendas v ON v.id = fa.venda_id 
                    WHERE 1=1 {where_clause}
                    UNION
                    SELECT frs.seller_id::text FROM fatura_recorrente_splits frs 
                    JOIN fatura_recorrente fr ON frs.subscription_id = fr.subscription_id 
                    JOIN vendas v ON v.id = fr.venda_id 
                    WHERE 1=1 {where_clause}
                ) sellers
                LEFT JOIN users u ON u.bempaggo_receiver_id = sellers.seller_id
                LEFT JOIN empresas e ON e.bempaggo_receiver_id = sellers.seller_id
            """, params + params + params + params)
            total_beneficiarios = cursor.fetchone()[0]
            
            # Calcular ticket médio
            ticket_medio = valor_total_geral / total_vendas if total_vendas > 0 else 0
            
            return EstatisticasSplits(
                total_vendas_com_splits=total_vendas,
                valor_total_splits=round(valor_total_geral, 2),
                ticket_medio_splits=round(ticket_medio, 2),
                beneficiarios_unicos=total_beneficiarios,
                splits_por_tipo=splits_por_tipo
            )
            
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter estatísticas: {str(e)}"
        )

@router.get("/opcoes-filtros")
async def obter_opcoes_filtros(
    current_user: dict = Depends(get_current_user)
) -> OpcoesFiltros:
    """
    Obter opções dinâmicas para filtros
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Usuários
            cursor.execute("""
                SELECT DISTINCT u.id, u.nome, u.email
                FROM users u
                JOIN vendas v ON v.usuario_venda_id = u.id
                WHERE (
                    EXISTS (SELECT 1 FROM pre_venda_splits WHERE pre_venda_id = v.pre_venda_id)
                    OR EXISTS (SELECT 1 FROM carne_splits WHERE carne_id = v.carne_id)
                    OR EXISTS (SELECT 1 FROM fatura_avulsa fa JOIN fatura_avulsa_splits fas ON fa.id = fas.invoice_id WHERE fa.venda_id = v.id)
                    OR EXISTS (SELECT 1 FROM fatura_recorrente fr JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id WHERE fr.venda_id = v.id)
                )
                ORDER BY u.nome
            """)
            usuarios = [{"id": row[0], "nome": row[1], "email": row[2]} for row in cursor.fetchall()]
            
            # Unidades
            cursor.execute("""
                SELECT DISTINCT v.unidade
                FROM vendas v
                WHERE v.unidade IS NOT NULL AND v.unidade != ''
                AND (
                    EXISTS (SELECT 1 FROM pre_venda_splits WHERE pre_venda_id = v.pre_venda_id)
                    OR EXISTS (SELECT 1 FROM carne_splits WHERE carne_id = v.carne_id)
                    OR EXISTS (SELECT 1 FROM fatura_avulsa fa JOIN fatura_avulsa_splits fas ON fa.id = fas.invoice_id WHERE fa.venda_id = v.id)
                    OR EXISTS (SELECT 1 FROM fatura_recorrente fr JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id WHERE fr.venda_id = v.id)
                )
                ORDER BY v.unidade
            """)
            unidades = [row[0] for row in cursor.fetchall()]
            
            # Tipos de split
            tipos_split = ["pre_venda", "carne", "fatura_avulsa", "fatura_recorrente"]
            
            # Status de vendas
            cursor.execute("""
                SELECT DISTINCT v.status_venda
                FROM vendas v
                WHERE v.status_venda IS NOT NULL
                AND (
                    EXISTS (SELECT 1 FROM pre_venda_splits WHERE pre_venda_id = v.pre_venda_id)
                    OR EXISTS (SELECT 1 FROM carne_splits WHERE carne_id = v.carne_id)
                    OR EXISTS (SELECT 1 FROM fatura_avulsa fa JOIN fatura_avulsa_splits fas ON fa.id = fas.invoice_id WHERE fa.venda_id = v.id)
                    OR EXISTS (SELECT 1 FROM fatura_recorrente fr JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id WHERE fr.venda_id = v.id)
                )
                ORDER BY v.status_venda
            """)
            status_vendas = [row[0] for row in cursor.fetchall()]
            
            return OpcoesFiltros(
                usuarios=usuarios,
                unidades=unidades,
                tipos_split=tipos_split,
                status_vendas=status_vendas
            )
            
    except Exception as e:
        logger.error(f"Erro ao obter opções de filtros: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter opções: {str(e)}"
        )

@router.get("/exportar")
async def exportar_relatorio_splits(
    formato: str = Query("excel", description="Formato do arquivo (excel, csv)"),
    data_inicio: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    data_fim: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    usuario_id: Optional[int] = Query(None, description="ID do usuário"),
    unidade: Optional[str] = Query(None, description="Unidade"),
    status: Optional[str] = Query(None, description="Status da venda"),
    current_user: dict = Depends(get_current_user)
):
    """
    Exportar relatório de splits em Excel ou CSV
    
    **Formatos suportados:**
    - excel: Arquivo Excel (.xlsx) com formatação
    - csv: Arquivo CSV simples
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Construir filtros
            where_conditions = []
            params = []
            
            if data_inicio:
                where_conditions.append("v.data_venda >= %s")
                params.append(data_inicio)
            
            if data_fim:
                where_conditions.append("v.data_venda <= %s")
                params.append(data_fim)
            
            if usuario_id:
                where_conditions.append("v.usuario_venda_id = %s")
                params.append(usuario_id)
            
            if unidade and unidade != 'Todas Unidades':
                where_conditions.append("v.unidade = %s")
                params.append(unidade)
            
            if status and status != 'Todos':
                where_conditions.append("v.status_venda = %s")
                params.append(status)
            
            # Query para buscar todos os splits detalhados
            base_query = """
                SELECT DISTINCT
                    v.id as venda_id,
                    v.documento_venda,
                    v.data_venda,
                    p.nome_paciente,
                    p.cpf_cnpj as paciente_cpf,
                    od.tipo as odontograma_tipo,
                    v.valor_bruto_total,
                    v.valor_liquido_total,
                    v.unidade,
                    v.status_venda,
                    v.pre_venda_id,
                    v.carne_id,
                    u.nome as usuario_venda_nome,
                    u.email as usuario_venda_email
                FROM vendas v
                JOIN pacientes p ON v.paciente_id = p.paciente_id
                LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                LEFT JOIN users u ON v.usuario_venda_id = u.id
                WHERE (
                    EXISTS (SELECT 1 FROM pre_venda_splits WHERE pre_venda_id = v.pre_venda_id)
                    OR EXISTS (SELECT 1 FROM carne_splits WHERE carne_id = v.carne_id)
                    OR EXISTS (SELECT 1 FROM fatura_avulsa fa JOIN fatura_avulsa_splits fas ON fa.id = fas.invoice_id WHERE fa.venda_id = v.id)
                    OR EXISTS (SELECT 1 FROM fatura_recorrente fr JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id WHERE fr.venda_id = v.id)
                )
            """
            
            if where_conditions:
                base_query += " AND " + " AND ".join(where_conditions)
            
            base_query += " ORDER BY v.data_venda DESC, v.id DESC LIMIT 1000"
            
            cursor.execute(base_query, params)
            vendas = cursor.fetchall()
            
            # Coletar dados detalhados dos splits para cada venda
            dados_exportacao = []
            
            for venda in vendas:
                venda_id = venda[0]
                
                # Buscar splits de pré-venda
                cursor.execute("""
                    SELECT 
                        'pre_venda' as tipo_split,
                        pvs.pre_venda_id as id_referencia,
                        pvs.seller_id,
                        pvs.percentage,
                        pvs.valor_calculado,
                        pve.status,
                        pve.valor_pago,
                        pve.created_at
                    FROM pre_venda_splits pvs
                    LEFT JOIN pre_vendas_entradas pve ON pvs.pre_venda_id = pve.pre_venda_id
                    WHERE pvs.pre_venda_id = %s
                """, (venda[10],))  # pre_venda_id
                
                pre_venda_splits = cursor.fetchall()
                
                for split in pre_venda_splits:
                    # Buscar beneficiário
                    beneficiario_info = obter_beneficiario_por_seller_id_com_contexto_venda(
                        cursor, split[2], venda_id, venda[10]
                    )
                    
                    dados_exportacao.append({
                        'venda_id': venda[0],
                        'documento_venda': venda[1],
                        'data_venda': venda[2].strftime('%d/%m/%Y') if venda[2] else '',
                        'paciente_nome': venda[3],
                        'paciente_cpf': venda[4],
                        'valor_bruto': float(venda[6]) if venda[6] else 0,
                        'valor_liquido': float(venda[7]) if venda[7] else 0,
                        'unidade': venda[8],
                        'status_venda': venda[9],
                        'usuario_venda_nome': venda[12],
                        'tipo_split': split[0],
                        'id_referencia': split[1],
                        'seller_id': split[2],
                        'nome_beneficiario': beneficiario_info['nome_beneficiario'],
                        'tipo_beneficiario': beneficiario_info['tipo'],
                        'percentual': float(split[3]) if split[3] else 0,
                        'valor_split': float(split[4]) if split[4] else 0,
                        'status_split': split[5] or 'pendente',
                        'eh_usuario_venda': beneficiario_info['eh_usuario_venda']
                    })
                
                # Buscar splits de carnê
                if venda[11]:  # carne_id
                    cursor.execute("""
                        SELECT 
                            'carne' as tipo_split,
                            cs.carne_id as id_referencia,
                            cs.seller_id::text,
                            cs.percentage,
                            cp.valor_parcela * cp.total_parcelas * cs.percentage / 100 as valor_calculado,
                            CONCAT((SELECT COUNT(*) FROM carne_parcelas WHERE carne_id = cp.id AND status = 'paid'), '/', cp.total_parcelas, ' pagas') as status,
                            cp.data_criacao
                        FROM carne_splits cs
                        LEFT JOIN carne_pagamento cp ON cs.carne_id = cp.id
                        WHERE cs.carne_id = %s
                    """, (venda[11],))
                    
                    carne_splits = cursor.fetchall()
                    
                    for split in carne_splits:
                        beneficiario_info = obter_beneficiario_por_seller_id_com_contexto_venda(
                            cursor, split[2], venda_id, venda[10]
                        )
                        
                        dados_exportacao.append({
                            'venda_id': venda[0],
                            'documento_venda': venda[1],
                            'data_venda': venda[2].strftime('%d/%m/%Y') if venda[2] else '',
                            'paciente_nome': venda[3],
                            'paciente_cpf': venda[4],
                            'valor_bruto': float(venda[6]) if venda[6] else 0,
                            'valor_liquido': float(venda[7]) if venda[7] else 0,
                            'unidade': venda[8],
                            'status_venda': venda[9],
                            'usuario_venda_nome': venda[12],
                            'tipo_split': split[0],
                            'id_referencia': str(split[1]),
                            'seller_id': split[2],
                            'nome_beneficiario': beneficiario_info['nome_beneficiario'],
                            'tipo_beneficiario': beneficiario_info['tipo'],
                            'percentual': float(split[3]) if split[3] else 0,
                            'valor_split': float(split[4]) if split[4] else 0,
                            'status_split': split[5] or 'pendente',
                            'eh_usuario_venda': beneficiario_info['eh_usuario_venda']
                        })
                
                # Buscar splits de faturas avulsas
                cursor.execute("""
                    SELECT 
                        'fatura_avulsa' as tipo_split,
                        fa.id as id_referencia,
                        fas.seller_id::text,
                        fas.percentage,
                        fa.valor_total * fas.percentage / 100 as valor_calculado,
                        fa.status,
                        fa.criado_em
                    FROM fatura_avulsa_splits fas
                    LEFT JOIN fatura_avulsa fa ON fas.invoice_id = fa.id
                    WHERE fa.venda_id = %s
                """, (venda_id,))
                
                fatura_avulsa_splits = cursor.fetchall()
                
                for split in fatura_avulsa_splits:
                    beneficiario_info = obter_beneficiario_por_seller_id_com_contexto_venda(
                        cursor, split[2], venda_id, venda[10]
                    )
                    
                    dados_exportacao.append({
                        'venda_id': venda[0],
                        'documento_venda': venda[1],
                        'data_venda': venda[2].strftime('%d/%m/%Y') if venda[2] else '',
                        'paciente_nome': venda[3],
                        'paciente_cpf': venda[4],
                        'valor_bruto': float(venda[6]) if venda[6] else 0,
                        'valor_liquido': float(venda[7]) if venda[7] else 0,
                        'unidade': venda[8],
                        'status_venda': venda[9],
                        'usuario_venda_nome': venda[12],
                        'tipo_split': split[0],
                        'id_referencia': str(split[1]),
                        'seller_id': split[2],
                        'nome_beneficiario': beneficiario_info['nome_beneficiario'],
                        'tipo_beneficiario': beneficiario_info['tipo'],
                        'percentual': float(split[3]) if split[3] else 0,
                        'valor_split': float(split[4]) if split[4] else 0,
                        'status_split': split[5] or 'pendente',
                        'eh_usuario_venda': beneficiario_info['eh_usuario_venda']
                    })
                
                # Buscar splits de faturas recorrentes
                cursor.execute("""
                    SELECT 
                        'fatura_recorrente' as tipo_split,
                        fr.subscription_id as id_referencia,
                        frs.seller_id::text,
                        frs.percentage,
                        fr.valor_mensal * frs.percentage / 100 as valor_calculado,
                        fr.status,
                        frs.created_at,
                        COALESCE(NULLIF(v.unidade, ''), u.unidade, '') as unidade_real
                    FROM fatura_recorrente_splits frs
                    LEFT JOIN fatura_recorrente fr ON frs.subscription_id = fr.subscription_id
                    LEFT JOIN vendas v ON fr.venda_id = v.id
                    LEFT JOIN users u ON v.usuario_venda_id = u.id
                    WHERE fr.venda_id = %s
                """, (venda_id,))
                
                fatura_recorrente_splits = cursor.fetchall()
                
                for split in fatura_recorrente_splits:
                    beneficiario_info = obter_beneficiario_por_seller_id_com_contexto_venda(
                        cursor, split[2], venda_id, venda[10]
                    )
                    
                    dados_exportacao.append({
                        'venda_id': venda[0],
                        'documento_venda': venda[1],
                        'data_venda': venda[2].strftime('%d/%m/%Y') if venda[2] else '',
                        'paciente_nome': venda[3],
                        'paciente_cpf': venda[4],
                        'valor_bruto': float(venda[6]) if venda[6] else 0,
                        'valor_liquido': float(venda[7]) if venda[7] else 0,
                        'unidade': split[7] or venda[8],  # Usar unidade_real da fatura recorrente ou da venda
                        'status_venda': venda[9],
                        'usuario_venda_nome': venda[12],
                        'tipo_split': split[0],
                        'id_referencia': str(split[1]),
                        'seller_id': split[2],
                        'nome_beneficiario': beneficiario_info['nome_beneficiario'],
                        'tipo_beneficiario': beneficiario_info['tipo'],
                        'percentual': float(split[3]) if split[3] else 0,
                        'valor_split': float(split[4]) if split[4] else 0,
                        'status_split': split[5] or 'ativo',
                        'eh_usuario_venda': beneficiario_info['eh_usuario_venda']
                    })
            
            # Gerar arquivo baseado no formato solicitado
            if formato.lower() == 'excel':
                return await _gerar_excel(dados_exportacao)
            elif formato.lower() == 'csv':
                return await _gerar_csv(dados_exportacao)
            else:
                raise HTTPException(status_code=400, detail="Formato não suportado. Use 'excel' ou 'csv'")
            
    except Exception as e:
        logger.error(f"Erro ao exportar relatório de splits: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao exportar relatório: {str(e)}"
        )

async def _gerar_excel(dados: List[Dict]) -> StreamingResponse:
    """Gerar arquivo Excel com os dados dos splits"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Relatório de Splits"
    
    # Estilo para cabeçalho
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    # Cabeçalhos
    headers = [
        "ID Venda", "Documento", "Data Venda", "Paciente", "CPF Paciente",
        "Valor Bruto", "Valor Líquido", "Unidade", "Status Venda", "Usuário Venda",
        "Tipo Split", "ID Referência", "Seller ID", "Nome Beneficiário", "Tipo Beneficiário",
        "Percentual (%)", "Valor Split", "Status Split", "É Usuário da Venda"
    ]
    
    # Adicionar cabeçalhos
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    # Adicionar dados
    for row_idx, row_data in enumerate(dados, 2):
        ws.cell(row=row_idx, column=1, value=row_data['venda_id'])
        ws.cell(row=row_idx, column=2, value=row_data['documento_venda'])
        ws.cell(row=row_idx, column=3, value=row_data['data_venda'])
        ws.cell(row=row_idx, column=4, value=row_data['paciente_nome'])
        ws.cell(row=row_idx, column=5, value=row_data['paciente_cpf'])
        ws.cell(row=row_idx, column=6, value=row_data['valor_bruto'])
        ws.cell(row=row_idx, column=7, value=row_data['valor_liquido'])
        ws.cell(row=row_idx, column=8, value=row_data['unidade'])
        ws.cell(row=row_idx, column=9, value=row_data['status_venda'])
        ws.cell(row=row_idx, column=10, value=row_data['usuario_venda_nome'])
        ws.cell(row=row_idx, column=11, value=row_data['tipo_split'])
        ws.cell(row=row_idx, column=12, value=row_data['id_referencia'])
        ws.cell(row=row_idx, column=13, value=row_data['seller_id'])
        ws.cell(row=row_idx, column=14, value=row_data['nome_beneficiario'])
        ws.cell(row=row_idx, column=15, value=row_data['tipo_beneficiario'])
        ws.cell(row=row_idx, column=16, value=row_data['percentual'])
        ws.cell(row=row_idx, column=17, value=row_data['valor_split'])
        ws.cell(row=row_idx, column=18, value=row_data['status_split'])
        ws.cell(row=row_idx, column=19, value="Sim" if row_data['eh_usuario_venda'] else "Não")
    
    # Formatar colunas de valores
    for row in range(2, len(dados) + 2):
        ws.cell(row=row, column=6).number_format = 'R$ #,##0.00'
        ws.cell(row=row, column=7).number_format = 'R$ #,##0.00'
        ws.cell(row=row, column=16).number_format = '0.00"%"'
        ws.cell(row=row, column=17).number_format = 'R$ #,##0.00'
    
    # Ajustar largura das colunas
    column_widths = [10, 15, 12, 30, 15, 12, 12, 15, 12, 25, 12, 12, 10, 30, 15, 10, 12, 15, 12]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[chr(64 + i)].width = width
    
    # Salvar em BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    # Nome do arquivo com timestamp
    filename = f"relatorio_splits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

async def _gerar_csv(dados: List[Dict]) -> StreamingResponse:
    """Gerar arquivo CSV com os dados dos splits"""
    output = io.StringIO()
    
    # Cabeçalhos
    fieldnames = [
        "venda_id", "documento_venda", "data_venda", "paciente_nome", "paciente_cpf",
        "valor_bruto", "valor_liquido", "unidade", "status_venda", "usuario_venda_nome",
        "tipo_split", "id_referencia", "seller_id", "nome_beneficiario", "tipo_beneficiario",
        "percentual", "valor_split", "status_split", "eh_usuario_venda"
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    # Escrever dados
    for row in dados:
        # Converter valores booleanos para texto
        row_copy = row.copy()
        row_copy['eh_usuario_venda'] = "Sim" if row['eh_usuario_venda'] else "Não"
        writer.writerow(row_copy)
    
    output.seek(0)
    
    # Nome do arquivo com timestamp
    filename = f"relatorio_splits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )