# backend/app/routers/relatorio_splits_seller.py

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import logging

from app.database.db import DatabaseConnection
from app.middleware.auth_middleware import get_current_user
from pydantic import BaseModel

# Configurar logging
logger = logging.getLogger(__name__)

# Criar router
router = APIRouter(
    prefix="/relatorio-splits",
    tags=["Relatório de Splits"],
    responses={404: {"description": "Not found"}}
)

# Modelos de resposta
class SplitInfo(BaseModel):
    seller_id: str
    nome_beneficiario: str
    tipo_beneficiario: str  # 'usuario' ou 'empresa'
    percentage: float
    valor_calculado: float

class VendaComSplits(BaseModel):
    venda_id: int
    numero_documento: str
    data_venda: date
    paciente_nome: str
    paciente_cpf: str
    valor_bruto: float
    valor_liquido: float
    forma_pagamento: str
    tipo_odontograma: str
    unidade: str
    status_venda: str
    splits: List[SplitInfo]
    
class PreVendaComSplits(BaseModel):
    pre_venda_id: str
    data_criacao: date
    paciente_nome: str
    paciente_cpf: str
    valor_entrada: float
    status_pagamento: str
    data_pagamento: Optional[date]
    splits: List[SplitInfo]

class CarneComSplits(BaseModel):
    carne_id: int
    venda_id: Optional[int]
    data_criacao: date
    paciente_nome: str
    paciente_cpf: str
    valor_parcela: float
    quantidade_parcelas: int
    valor_total: float
    parcelas_pagas: int
    splits: List[SplitInfo]

class FaturaAvulsaComSplits(BaseModel):
    fatura_id: int
    venda_id: Optional[int]
    data_criacao: date
    paciente_nome: str
    paciente_cpf: str
    valor_total: float
    status: str
    data_pagamento: Optional[date]
    splits: List[SplitInfo]

class RelatorioSplitsCompleto(BaseModel):
    seller_id: Optional[str]
    periodo: Dict[str, str]
    resumo: Dict[str, Any]
    vendas_com_splits: List[VendaComSplits]
    pre_vendas_com_splits: List[PreVendaComSplits]
    carnes_com_splits: List[CarneComSplits]
    faturas_avulsas_com_splits: List[FaturaAvulsaComSplits]

@router.get("/por-venda/{venda_id}")
async def obter_splits_por_venda(
    venda_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Obter todos os splits de uma venda específica, incluindo todas as formas de pagamento.
    
    **Retorna:**
    - Informações da venda
    - Splits da venda direta (se houver)
    - Splits da pré-venda/entrada (se houver)
    - Splits do carnê (se houver)
    - Splits de faturas avulsas (se houver)
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # 1. Buscar informações da venda
            cursor.execute("""
                SELECT 
                    v.id,
                    v.numero_documento,
                    v.data_venda,
                    p.nome as paciente_nome,
                    pac.cpf_cnpj as paciente_cpf,
                    v.valor_bruto,
                    v.valor_liquido,
                    fp.descricao as forma_pagamento,
                    tod.nome as tipo_odontograma,
                    v.unidade,
                    v.status,
                    v.pre_venda_id,
                    v.carne_id
                FROM vendas v
                LEFT JOIN pacientes pac ON v.paciente_id = pac.id
                LEFT JOIN users p ON pac.user_id = p.id
                LEFT JOIN forma_pagamento fp ON v.forma_pagamento_id = fp.id
                LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                LEFT JOIN tipos_odontograma tod ON od.tipo_id = tod.id
                WHERE v.id = %s
            """, (venda_id,))
            
            venda_data = cursor.fetchone()
            if not venda_data:
                raise HTTPException(status_code=404, detail="Venda não encontrada")
            
            resultado = {
                "venda": {
                    "id": venda_data[0],
                    "numero_documento": venda_data[1],
                    "data_venda": venda_data[2].isoformat() if venda_data[2] else None,
                    "paciente_nome": venda_data[3],
                    "paciente_cpf": venda_data[4],
                    "valor_bruto": float(venda_data[5]) if venda_data[5] else 0,
                    "valor_liquido": float(venda_data[6]) if venda_data[6] else 0,
                    "forma_pagamento": venda_data[7],
                    "tipo_odontograma": venda_data[8],
                    "unidade": venda_data[9],
                    "status": venda_data[10]
                },
                "splits": {
                    "venda_direta": [],
                    "pre_venda": [],
                    "carne": [],
                    "fatura_avulsa": [],
                    "fatura_recorrente": []
                },
                "resumo": {
                    "total_splits": 0,
                    "valor_total_splits": 0
                }
            }
            
            pre_venda_id = venda_data[11]
            carne_id = venda_data[12]
            
            # 2. Buscar splits da venda direta
            cursor.execute("""
                SELECT 
                    vs.seller_id,
                    vs.percentage,
                    vs.valor_calculado,
                    CASE 
                        WHEN vs.user_id IS NOT NULL THEN u.nome
                        WHEN vs.empresa_id IS NOT NULL THEN e.razao_social
                        ELSE 'Seller ' || vs.seller_id
                    END as nome_beneficiario,
                    CASE 
                        WHEN vs.user_id IS NOT NULL THEN 'usuario'
                        WHEN vs.empresa_id IS NOT NULL THEN 'empresa'
                        ELSE 'outro'
                    END as tipo_beneficiario
                FROM vendas_splits vs
                LEFT JOIN users u ON vs.user_id = u.id
                LEFT JOIN empresas e ON vs.empresa_id = e.id
                WHERE vs.venda_id = %s
                ORDER BY vs.percentage DESC
            """, (venda_id,))
            
            for split in cursor.fetchall():
                split_info = {
                    "seller_id": split[0],
                    "percentage": float(split[1]),
                    "valor_calculado": float(split[2]) if split[2] else 0,
                    "nome_beneficiario": split[3],
                    "tipo_beneficiario": split[4]
                }
                resultado["splits"]["venda_direta"].append(split_info)
                resultado["resumo"]["total_splits"] += 1
                resultado["resumo"]["valor_total_splits"] += split_info["valor_calculado"]
            
            # 3. Buscar splits da pré-venda (se houver)
            if pre_venda_id:
                cursor.execute("""
                    SELECT 
                        pvs.seller_id,
                        pvs.percentage,
                        pvs.valor_calculado,
                        pve.valor_entrada,
                        pve.status_pagamento,
                        pve.data_pagamento,
                        CASE 
                            WHEN pvs.user_id IS NOT NULL THEN u.nome
                            WHEN pvs.empresa_id IS NOT NULL THEN e.razao_social
                            ELSE 'Seller ' || pvs.seller_id
                        END as nome_beneficiario,
                        CASE 
                            WHEN pvs.user_id IS NOT NULL THEN 'usuario'
                            WHEN pvs.empresa_id IS NOT NULL THEN 'empresa'
                            ELSE 'outro'
                        END as tipo_beneficiario
                    FROM pre_venda_splits pvs
                    LEFT JOIN pre_vendas_entradas pve ON pvs.pre_venda_id = pve.pre_venda_id
                    LEFT JOIN users u ON pvs.user_id = u.id
                    LEFT JOIN empresas e ON pvs.empresa_id = e.id
                    WHERE pvs.pre_venda_id = %s
                    ORDER BY pvs.percentage DESC
                """, (pre_venda_id,))
                
                pre_venda_splits = cursor.fetchall()
                if pre_venda_splits:
                    valor_entrada = float(pre_venda_splits[0][3]) if pre_venda_splits[0][3] else 0
                    status_pagamento = pre_venda_splits[0][4]
                    data_pagamento = pre_venda_splits[0][5]
                    
                    resultado["splits"]["pre_venda"] = {
                        "pre_venda_id": pre_venda_id,
                        "valor_entrada": valor_entrada,
                        "status_pagamento": status_pagamento,
                        "data_pagamento": data_pagamento.isoformat() if data_pagamento else None,
                        "splits": []
                    }
                    
                    for split in pre_venda_splits:
                        split_info = {
                            "seller_id": split[0],
                            "percentage": float(split[1]),
                            "valor_calculado": float(split[2]) if split[2] else 0,
                            "nome_beneficiario": split[6],
                            "tipo_beneficiario": split[7]
                        }
                        resultado["splits"]["pre_venda"]["splits"].append(split_info)
                        resultado["resumo"]["total_splits"] += 1
                        resultado["resumo"]["valor_total_splits"] += split_info["valor_calculado"]
            
            # 4. Buscar splits do carnê (se houver)
            if carne_id:
                cursor.execute("""
                    SELECT 
                        cs.seller_id,
                        cs.percentage,
                        cp.valor_parcela,
                        cp.quantidade_parcelas,
                        (SELECT COUNT(*) FROM carne_parcelas WHERE carne_id = cp.id AND status = 'paid') as parcelas_pagas,
                        CASE 
                            WHEN cs.user_id IS NOT NULL THEN u.nome
                            WHEN cs.empresa_id IS NOT NULL THEN e.razao_social
                            ELSE 'Seller ' || cs.seller_id
                        END as nome_beneficiario,
                        CASE 
                            WHEN cs.user_id IS NOT NULL THEN 'usuario'
                            WHEN cs.empresa_id IS NOT NULL THEN 'empresa'
                            ELSE 'outro'
                        END as tipo_beneficiario
                    FROM carne_splits cs
                    LEFT JOIN carne_pagamento cp ON cs.carne_id = cp.id
                    LEFT JOIN users u ON cs.user_id = u.id
                    LEFT JOIN empresas e ON cs.empresa_id = e.id
                    WHERE cs.carne_id = %s
                    ORDER BY cs.percentage DESC
                """, (carne_id,))
                
                carne_splits = cursor.fetchall()
                if carne_splits:
                    valor_parcela = float(carne_splits[0][2]) if carne_splits[0][2] else 0
                    qtd_parcelas = carne_splits[0][3]
                    parcelas_pagas = carne_splits[0][4]
                    
                    resultado["splits"]["carne"] = {
                        "carne_id": carne_id,
                        "valor_parcela": valor_parcela,
                        "quantidade_parcelas": qtd_parcelas,
                        "parcelas_pagas": parcelas_pagas,
                        "valor_total": valor_parcela * qtd_parcelas,
                        "splits": []
                    }
                    
                    for split in carne_splits:
                        split_info = {
                            "seller_id": split[0],
                            "percentage": float(split[1]),
                            "valor_por_parcela": round(valor_parcela * float(split[1]) / 100, 2),
                            "valor_total": round(valor_parcela * qtd_parcelas * float(split[1]) / 100, 2),
                            "nome_beneficiario": split[5],
                            "tipo_beneficiario": split[6]
                        }
                        resultado["splits"]["carne"]["splits"].append(split_info)
                        resultado["resumo"]["total_splits"] += 1
            
            # 5. Buscar splits de faturas avulsas
            cursor.execute("""
                SELECT 
                    fas.seller_id,
                    fas.percentage,
                    fa.valor_total,
                    fa.status,
                    fa.data_pagamento,
                    fa.id,
                    CASE 
                        WHEN fas.user_id IS NOT NULL THEN u.nome
                        WHEN fas.empresa_id IS NOT NULL THEN e.razao_social
                        ELSE 'Seller ' || fas.seller_id
                    END as nome_beneficiario,
                    CASE 
                        WHEN fas.user_id IS NOT NULL THEN 'usuario'
                        WHEN fas.empresa_id IS NOT NULL THEN 'empresa'
                        ELSE 'outro'
                    END as tipo_beneficiario
                FROM fatura_avulsa_splits fas
                LEFT JOIN fatura_avulsa fa ON fas.invoice_id = fa.id
                LEFT JOIN users u ON fas.user_id = u.id
                LEFT JOIN empresas e ON fas.empresa_id = e.id
                WHERE fa.venda_id = %s
                ORDER BY fas.percentage DESC
            """, (venda_id,))
            
            faturas_avulsas = {}
            for split in cursor.fetchall():
                fatura_id = split[5]
                if fatura_id not in faturas_avulsas:
                    faturas_avulsas[fatura_id] = {
                        "fatura_id": fatura_id,
                        "valor_total": float(split[2]) if split[2] else 0,
                        "status": split[3],
                        "data_pagamento": split[4].isoformat() if split[4] else None,
                        "splits": []
                    }
                
                split_info = {
                    "seller_id": split[0],
                    "percentage": float(split[1]),
                    "valor_calculado": round(float(split[2]) * float(split[1]) / 100, 2) if split[2] else 0,
                    "nome_beneficiario": split[6],
                    "tipo_beneficiario": split[7]
                }
                faturas_avulsas[fatura_id]["splits"].append(split_info)
                resultado["resumo"]["total_splits"] += 1
                if split[3] == 'paid':
                    resultado["resumo"]["valor_total_splits"] += split_info["valor_calculado"]
            
            resultado["splits"]["fatura_avulsa"] = list(faturas_avulsas.values())
            
            # 6. Buscar splits de faturas recorrentes
            cursor.execute("""
                SELECT 
                    frs.seller_id,
                    frs.percentage,
                    frs.subscription_id,
                    CASE 
                        WHEN frs.user_id IS NOT NULL THEN u.nome
                        WHEN frs.empresa_id IS NOT NULL THEN e.razao_social
                        ELSE 'Seller ' || frs.seller_id
                    END as nome_beneficiario,
                    CASE 
                        WHEN frs.user_id IS NOT NULL THEN 'usuario'
                        WHEN frs.empresa_id IS NOT NULL THEN 'empresa'
                        ELSE 'outro'
                    END as tipo_beneficiario
                FROM fatura_recorrente_splits frs
                LEFT JOIN fatura_recorrente fr ON frs.subscription_id = fr.subscription_id_delta
                LEFT JOIN users u ON frs.user_id = u.id
                LEFT JOIN empresas e ON frs.empresa_id = e.id
                WHERE fr.venda_id = %s
                ORDER BY frs.percentage DESC
            """, (venda_id,))
            
            for split in cursor.fetchall():
                split_info = {
                    "seller_id": split[0],
                    "percentage": float(split[1]),
                    "subscription_id": split[2],
                    "nome_beneficiario": split[3],
                    "tipo_beneficiario": split[4]
                }
                resultado["splits"]["fatura_recorrente"].append(split_info)
                resultado["resumo"]["total_splits"] += 1
            
            # Arredondar valores do resumo
            resultado["resumo"]["valor_total_splits"] = round(resultado["resumo"]["valor_total_splits"], 2)
            
            return resultado
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter splits da venda {venda_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter splits da venda: {str(e)}"
        )

@router.get("/detalhado")
async def obter_relatorio_splits_detalhado(
    seller_id: Optional[str] = Query(None, description="ID do seller específico (deixe vazio para todos)"),
    data_inicio: date = Query(..., description="Data de início do período"),
    data_fim: date = Query(..., description="Data de fim do período"),
    tipo_pagamento: Optional[str] = Query(None, description="Filtrar por tipo (pre_venda, carne, fatura_avulsa, fatura_recorrente)"),
    current_user: dict = Depends(get_current_user)
) -> RelatorioSplitsCompleto:
    """
    Obter relatório detalhado de splits com todas as vendas e suas respectivas divisões.
    
    **Parâmetros:**
    - **seller_id**: ID do seller específico (opcional)
    - **data_inicio/data_fim**: Período para análise
    - **tipo_pagamento**: Filtrar por tipo específico (opcional)
    
    **Retorna:**
    - Lista completa de vendas com seus splits
    - Separação por tipo de pagamento
    - Resumo com totalizadores
    """
    try:
        # Validar período
        if data_fim < data_inicio:
            raise HTTPException(
                status_code=400, 
                detail="Data de fim deve ser maior ou igual à data de início"
            )
        
        # Determinar filtro de unidade
        user_unidade = current_user.get('unidade')
        filtro_unidade = None if user_unidade in ['Todas Unidades', 'Todas unidades'] else user_unidade
        
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            resultado = {
                "seller_id": seller_id,
                "periodo": {
                    "data_inicio": data_inicio.isoformat(),
                    "data_fim": data_fim.isoformat()
                },
                "resumo": {
                    "total_geral": 0,
                    "quantidade_total": 0,
                    "por_tipo": {}
                },
                "vendas_com_splits": [],
                "pre_vendas_com_splits": [],
                "carnes_com_splits": [],
                "faturas_avulsas_com_splits": []
            }
            
            # 1. Buscar vendas com splits diretos
            if not tipo_pagamento or tipo_pagamento == 'venda':
                query_vendas = """
                    SELECT DISTINCT
                        v.id,
                        v.numero_documento,
                        v.data_venda,
                        p.nome as paciente_nome,
                        pac.cpf_cnpj as paciente_cpf,
                        v.valor_bruto,
                        v.valor_liquido,
                        fp.descricao as forma_pagamento,
                        tod.nome as tipo_odontograma,
                        v.unidade,
                        v.status
                    FROM vendas v
                    INNER JOIN vendas_splits vs ON v.id = vs.venda_id
                    LEFT JOIN pacientes pac ON v.paciente_id = pac.id
                    LEFT JOIN users p ON pac.user_id = p.id
                    LEFT JOIN forma_pagamento fp ON v.forma_pagamento_id = fp.id
                    LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                    LEFT JOIN tipos_odontograma tod ON od.tipo_id = tod.id
                    WHERE v.data_venda BETWEEN %s AND %s
                """
                
                params = [data_inicio, data_fim]
                
                if seller_id:
                    query_vendas += " AND vs.seller_id = %s"
                    params.append(seller_id)
                
                if filtro_unidade:
                    query_vendas += " AND v.unidade = %s"
                    params.append(filtro_unidade)
                
                query_vendas += " ORDER BY v.data_venda DESC"
                
                cursor.execute(query_vendas, params)
                vendas = cursor.fetchall()
                
                for venda in vendas:
                    venda_id = venda[0]
                    
                    # Buscar splits desta venda
                    query_splits = """
                        SELECT 
                            vs.seller_id,
                            vs.percentage,
                            vs.valor_calculado,
                            CASE 
                                WHEN vs.user_id IS NOT NULL THEN u.nome
                                WHEN vs.empresa_id IS NOT NULL THEN e.razao_social
                                ELSE 'Seller ' || vs.seller_id
                            END as nome_beneficiario,
                            CASE 
                                WHEN vs.user_id IS NOT NULL THEN 'usuario'
                                WHEN vs.empresa_id IS NOT NULL THEN 'empresa'
                                ELSE 'outro'
                            END as tipo_beneficiario
                        FROM vendas_splits vs
                        LEFT JOIN users u ON vs.user_id = u.id
                        LEFT JOIN empresas e ON vs.empresa_id = e.id
                        WHERE vs.venda_id = %s
                    """
                    
                    if seller_id:
                        query_splits += " AND vs.seller_id = %s"
                        cursor.execute(query_splits, (venda_id, seller_id))
                    else:
                        cursor.execute(query_splits, (venda_id,))
                    
                    splits = cursor.fetchall()
                    
                    venda_obj = VendaComSplits(
                        venda_id=venda[0],
                        numero_documento=venda[1],
                        data_venda=venda[2],
                        paciente_nome=venda[3] or "N/A",
                        paciente_cpf=venda[4] or "N/A",
                        valor_bruto=float(venda[5]) if venda[5] else 0,
                        valor_liquido=float(venda[6]) if venda[6] else 0,
                        forma_pagamento=venda[7] or "N/A",
                        tipo_odontograma=venda[8] or "N/A",
                        unidade=venda[9] or "N/A",
                        status_venda=venda[10],
                        splits=[
                            SplitInfo(
                                seller_id=split[0],
                                nome_beneficiario=split[3],
                                tipo_beneficiario=split[4],
                                percentage=float(split[1]),
                                valor_calculado=float(split[2]) if split[2] else 0
                            ) for split in splits
                        ]
                    )
                    
                    resultado["vendas_com_splits"].append(venda_obj)
                    
                    # Atualizar resumo
                    for split in splits:
                        if seller_id and split[0] == seller_id:
                            resultado["resumo"]["total_geral"] += float(split[2]) if split[2] else 0
            
            # 2. Buscar pré-vendas com splits
            if not tipo_pagamento or tipo_pagamento == 'pre_venda':
                query_pre_vendas = """
                    SELECT DISTINCT
                        pve.pre_venda_id,
                        pve.created_at,
                        p.nome as paciente_nome,
                        pac.cpf_cnpj as paciente_cpf,
                        pve.valor_entrada,
                        pve.status_pagamento,
                        pve.data_pagamento
                    FROM pre_vendas_entradas pve
                    INNER JOIN pre_venda_splits pvs ON pve.pre_venda_id = pvs.pre_venda_id
                    LEFT JOIN vendas v ON pve.pre_venda_id = v.pre_venda_id
                    LEFT JOIN pacientes pac ON v.paciente_id = pac.id
                    LEFT JOIN users p ON pac.user_id = p.id
                    WHERE pve.created_at BETWEEN %s AND %s
                """
                
                params = [data_inicio, data_fim]
                
                if seller_id:
                    query_pre_vendas += " AND pvs.seller_id = %s"
                    params.append(seller_id)
                
                if filtro_unidade:
                    query_pre_vendas += " AND v.unidade = %s"
                    params.append(filtro_unidade)
                
                query_pre_vendas += " ORDER BY pve.created_at DESC"
                
                cursor.execute(query_pre_vendas, params)
                pre_vendas = cursor.fetchall()
                
                for pre_venda in pre_vendas:
                    pre_venda_id = pre_venda[0]
                    
                    # Buscar splits desta pré-venda
                    query_splits = """
                        SELECT 
                            pvs.seller_id,
                            pvs.percentage,
                            pvs.valor_calculado,
                            CASE 
                                WHEN pvs.user_id IS NOT NULL THEN u.nome
                                WHEN pvs.empresa_id IS NOT NULL THEN e.razao_social
                                ELSE 'Seller ' || pvs.seller_id
                            END as nome_beneficiario,
                            CASE 
                                WHEN pvs.user_id IS NOT NULL THEN 'usuario'
                                WHEN pvs.empresa_id IS NOT NULL THEN 'empresa'
                                ELSE 'outro'
                            END as tipo_beneficiario
                        FROM pre_venda_splits pvs
                        LEFT JOIN users u ON pvs.user_id = u.id
                        LEFT JOIN empresas e ON pvs.empresa_id = e.id
                        WHERE pvs.pre_venda_id = %s
                    """
                    
                    if seller_id:
                        query_splits += " AND pvs.seller_id = %s"
                        cursor.execute(query_splits, (pre_venda_id, seller_id))
                    else:
                        cursor.execute(query_splits, (pre_venda_id,))
                    
                    splits = cursor.fetchall()
                    
                    pre_venda_obj = PreVendaComSplits(
                        pre_venda_id=pre_venda[0],
                        data_criacao=pre_venda[1],
                        paciente_nome=pre_venda[2] or "N/A",
                        paciente_cpf=pre_venda[3] or "N/A",
                        valor_entrada=float(pre_venda[4]) if pre_venda[4] else 0,
                        status_pagamento=pre_venda[5],
                        data_pagamento=pre_venda[6],
                        splits=[
                            SplitInfo(
                                seller_id=split[0],
                                nome_beneficiario=split[3],
                                tipo_beneficiario=split[4],
                                percentage=float(split[1]),
                                valor_calculado=float(split[2]) if split[2] else 0
                            ) for split in splits
                        ]
                    )
                    
                    resultado["pre_vendas_com_splits"].append(pre_venda_obj)
                    
                    # Atualizar resumo se pago
                    if pre_venda[5] == 'pago':
                        for split in splits:
                            if not seller_id or split[0] == seller_id:
                                valor = float(split[2]) if split[2] else 0
                                resultado["resumo"]["total_geral"] += valor
                                
                                if "pre_venda" not in resultado["resumo"]["por_tipo"]:
                                    resultado["resumo"]["por_tipo"]["pre_venda"] = {
                                        "quantidade": 0,
                                        "valor_total": 0
                                    }
                                resultado["resumo"]["por_tipo"]["pre_venda"]["quantidade"] += 1
                                resultado["resumo"]["por_tipo"]["pre_venda"]["valor_total"] += valor
            
            # 3. Buscar carnês com splits
            if not tipo_pagamento or tipo_pagamento == 'carne':
                query_carnes = """
                    SELECT DISTINCT
                        cp.id,
                        cp.venda_id,
                        cp.created_at,
                        p.nome as paciente_nome,
                        pac.cpf_cnpj as paciente_cpf,
                        cp.valor_parcela,
                        cp.quantidade_parcelas,
                        (SELECT COUNT(*) FROM carne_parcelas WHERE carne_id = cp.id AND status = 'paid') as parcelas_pagas
                    FROM carne_pagamento cp
                    INNER JOIN carne_splits cs ON cp.id = cs.carne_id
                    LEFT JOIN vendas v ON cp.venda_id = v.id
                    LEFT JOIN pacientes pac ON v.paciente_id = pac.id
                    LEFT JOIN users p ON pac.user_id = p.id
                    WHERE cp.created_at BETWEEN %s AND %s
                """
                
                params = [data_inicio, data_fim]
                
                if seller_id:
                    query_carnes += " AND cs.seller_id = %s"
                    params.append(seller_id)
                
                if filtro_unidade:
                    query_carnes += " AND v.unidade = %s"
                    params.append(filtro_unidade)
                
                query_carnes += " ORDER BY cp.created_at DESC"
                
                cursor.execute(query_carnes, params)
                carnes = cursor.fetchall()
                
                for carne in carnes:
                    carne_id = carne[0]
                    
                    # Buscar splits deste carnê
                    query_splits = """
                        SELECT 
                            cs.seller_id,
                            cs.percentage,
                            CASE 
                                WHEN cs.user_id IS NOT NULL THEN u.nome
                                WHEN cs.empresa_id IS NOT NULL THEN e.razao_social
                                ELSE 'Seller ' || cs.seller_id
                            END as nome_beneficiario,
                            CASE 
                                WHEN cs.user_id IS NOT NULL THEN 'usuario'
                                WHEN cs.empresa_id IS NOT NULL THEN 'empresa'
                                ELSE 'outro'
                            END as tipo_beneficiario
                        FROM carne_splits cs
                        LEFT JOIN users u ON cs.user_id = u.id
                        LEFT JOIN empresas e ON cs.empresa_id = e.id
                        WHERE cs.carne_id = %s
                    """
                    
                    if seller_id:
                        query_splits += " AND cs.seller_id = %s"
                        cursor.execute(query_splits, (carne_id, seller_id))
                    else:
                        cursor.execute(query_splits, (carne_id,))
                    
                    splits = cursor.fetchall()
                    
                    valor_parcela = float(carne[5]) if carne[5] else 0
                    qtd_parcelas = carne[6]
                    valor_total = valor_parcela * qtd_parcelas
                    
                    carne_obj = CarneComSplits(
                        carne_id=carne[0],
                        venda_id=carne[1],
                        data_criacao=carne[2],
                        paciente_nome=carne[3] or "N/A",
                        paciente_cpf=carne[4] or "N/A",
                        valor_parcela=valor_parcela,
                        quantidade_parcelas=qtd_parcelas,
                        valor_total=valor_total,
                        parcelas_pagas=carne[7],
                        splits=[
                            SplitInfo(
                                seller_id=split[0],
                                nome_beneficiario=split[2],
                                tipo_beneficiario=split[3],
                                percentage=float(split[1]),
                                valor_calculado=round(valor_total * float(split[1]) / 100, 2)
                            ) for split in splits
                        ]
                    )
                    
                    resultado["carnes_com_splits"].append(carne_obj)
                    
                    # Atualizar resumo com parcelas pagas
                    parcelas_pagas = carne[7]
                    if parcelas_pagas > 0:
                        for split in splits:
                            if not seller_id or split[0] == str(seller_id):
                                valor_pago = round(valor_parcela * parcelas_pagas * float(split[1]) / 100, 2)
                                resultado["resumo"]["total_geral"] += valor_pago
                                
                                if "carne" not in resultado["resumo"]["por_tipo"]:
                                    resultado["resumo"]["por_tipo"]["carne"] = {
                                        "quantidade": 0,
                                        "valor_total": 0
                                    }
                                resultado["resumo"]["por_tipo"]["carne"]["quantidade"] += 1
                                resultado["resumo"]["por_tipo"]["carne"]["valor_total"] += valor_pago
            
            # 4. Buscar faturas avulsas com splits
            if not tipo_pagamento or tipo_pagamento == 'fatura_avulsa':
                query_faturas = """
                    SELECT DISTINCT
                        fa.id,
                        fa.venda_id,
                        fa.created_at,
                        p.nome as paciente_nome,
                        pac.cpf_cnpj as paciente_cpf,
                        fa.valor_total,
                        fa.status,
                        fa.data_pagamento
                    FROM fatura_avulsa fa
                    INNER JOIN fatura_avulsa_splits fas ON fa.id = fas.invoice_id
                    LEFT JOIN vendas v ON fa.venda_id = v.id
                    LEFT JOIN pacientes pac ON v.paciente_id = pac.id
                    LEFT JOIN users p ON pac.user_id = p.id
                    WHERE fa.created_at BETWEEN %s AND %s
                """
                
                params = [data_inicio, data_fim]
                
                if seller_id:
                    query_faturas += " AND fas.seller_id = %s"
                    params.append(seller_id)
                
                if filtro_unidade:
                    query_faturas += " AND v.unidade = %s"
                    params.append(filtro_unidade)
                
                query_faturas += " ORDER BY fa.created_at DESC"
                
                cursor.execute(query_faturas, params)
                faturas = cursor.fetchall()
                
                for fatura in faturas:
                    fatura_id = fatura[0]
                    
                    # Buscar splits desta fatura
                    query_splits = """
                        SELECT 
                            fas.seller_id,
                            fas.percentage,
                            CASE 
                                WHEN fas.user_id IS NOT NULL THEN u.nome
                                WHEN fas.empresa_id IS NOT NULL THEN e.razao_social
                                ELSE 'Seller ' || fas.seller_id
                            END as nome_beneficiario,
                            CASE 
                                WHEN fas.user_id IS NOT NULL THEN 'usuario'
                                WHEN fas.empresa_id IS NOT NULL THEN 'empresa'
                                ELSE 'outro'
                            END as tipo_beneficiario
                        FROM fatura_avulsa_splits fas
                        LEFT JOIN users u ON fas.user_id = u.id
                        LEFT JOIN empresas e ON fas.empresa_id = e.id
                        WHERE fas.invoice_id = %s
                    """
                    
                    if seller_id:
                        query_splits += " AND fas.seller_id = %s"
                        cursor.execute(query_splits, (fatura_id, seller_id))
                    else:
                        cursor.execute(query_splits, (fatura_id,))
                    
                    splits = cursor.fetchall()
                    
                    valor_total = float(fatura[5]) if fatura[5] else 0
                    
                    fatura_obj = FaturaAvulsaComSplits(
                        fatura_id=fatura[0],
                        venda_id=fatura[1],
                        data_criacao=fatura[2],
                        paciente_nome=fatura[3] or "N/A",
                        paciente_cpf=fatura[4] or "N/A",
                        valor_total=valor_total,
                        status=fatura[6],
                        data_pagamento=fatura[7],
                        splits=[
                            SplitInfo(
                                seller_id=split[0],
                                nome_beneficiario=split[2],
                                tipo_beneficiario=split[3],
                                percentage=float(split[1]),
                                valor_calculado=round(valor_total * float(split[1]) / 100, 2)
                            ) for split in splits
                        ]
                    )
                    
                    resultado["faturas_avulsas_com_splits"].append(fatura_obj)
                    
                    # Atualizar resumo se pago
                    if fatura[6] == 'paid':
                        for split in splits:
                            if not seller_id or split[0] == str(seller_id):
                                valor = round(valor_total * float(split[1]) / 100, 2)
                                resultado["resumo"]["total_geral"] += valor
                                
                                if "fatura_avulsa" not in resultado["resumo"]["por_tipo"]:
                                    resultado["resumo"]["por_tipo"]["fatura_avulsa"] = {
                                        "quantidade": 0,
                                        "valor_total": 0
                                    }
                                resultado["resumo"]["por_tipo"]["fatura_avulsa"]["quantidade"] += 1
                                resultado["resumo"]["por_tipo"]["fatura_avulsa"]["valor_total"] += valor
            
            # Calcular quantidade total
            resultado["resumo"]["quantidade_total"] = (
                len(resultado["vendas_com_splits"]) +
                len(resultado["pre_vendas_com_splits"]) +
                len(resultado["carnes_com_splits"]) +
                len(resultado["faturas_avulsas_com_splits"])
            )
            
            # Arredondar valores
            resultado["resumo"]["total_geral"] = round(resultado["resumo"]["total_geral"], 2)
            for tipo in resultado["resumo"]["por_tipo"]:
                resultado["resumo"]["por_tipo"][tipo]["valor_total"] = round(
                    resultado["resumo"]["por_tipo"][tipo]["valor_total"], 2
                )
            
            return RelatorioSplitsCompleto(**resultado)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar relatório detalhado de splits: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar relatório: {str(e)}"
        )

@router.get("/resumo-seller/{seller_id}")
async def obter_resumo_splits_seller(
    seller_id: str,
    data_inicio: date = Query(..., description="Data de início do período"),
    data_fim: date = Query(..., description="Data de fim do período"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter resumo consolidado de splits para um seller específico.
    
    **Retorna:**
    - Total recebido no período
    - Breakdown por tipo de pagamento
    - Média de comissão
    - Comparativo com período anterior
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Identificar o seller
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN u.nome IS NOT NULL THEN u.nome
                        WHEN e.razao_social IS NOT NULL THEN e.razao_social
                        ELSE 'Seller ' || %s
                    END as nome_seller,
                    CASE 
                        WHEN u.id IS NOT NULL THEN 'usuario'
                        WHEN e.id IS NOT NULL THEN 'empresa'
                        ELSE 'outro'
                    END as tipo_seller
                FROM (VALUES (%s)) AS s(id)
                LEFT JOIN users u ON u.bempaggo_receiver_id::varchar = s.id
                LEFT JOIN empresas e ON e.bempaggo_receiver_id::varchar = s.id
                LIMIT 1
            """, (seller_id, seller_id))
            
            seller_info = cursor.fetchone()
            nome_seller = seller_info[0] if seller_info else f"Seller {seller_id}"
            tipo_seller = seller_info[1] if seller_info else "outro"
            
            resultado = {
                "seller": {
                    "id": seller_id,
                    "nome": nome_seller,
                    "tipo": tipo_seller
                },
                "periodo": {
                    "data_inicio": data_inicio.isoformat(),
                    "data_fim": data_fim.isoformat()
                },
                "resumo": {
                    "total_recebido": 0,
                    "quantidade_transacoes": 0,
                    "ticket_medio": 0,
                    "percentual_medio": 0
                },
                "por_tipo": {},
                "evolucao_mensal": []
            }
            
            # Consultas para cada tipo de split
            
            # 1. Pré-vendas pagas
            cursor.execute("""
                SELECT 
                    COUNT(*) as quantidade,
                    SUM(pvs.valor_calculado) as total,
                    AVG(pvs.percentage) as percentual_medio
                FROM pre_venda_splits pvs
                JOIN pre_vendas_entradas pve ON pvs.pre_venda_id = pve.pre_venda_id
                WHERE pvs.seller_id = %s
                AND pve.status_pagamento = 'pago'
                AND pve.data_pagamento BETWEEN %s AND %s
            """, (seller_id, data_inicio, data_fim))
            
            pre_vendas = cursor.fetchone()
            if pre_vendas[0] > 0:
                resultado["por_tipo"]["pre_venda"] = {
                    "quantidade": pre_vendas[0],
                    "valor_total": float(pre_vendas[1]) if pre_vendas[1] else 0,
                    "percentual_medio": float(pre_vendas[2]) if pre_vendas[2] else 0
                }
                resultado["resumo"]["total_recebido"] += resultado["por_tipo"]["pre_venda"]["valor_total"]
                resultado["resumo"]["quantidade_transacoes"] += pre_vendas[0]
            
            # 2. Carnês (parcelas pagas)
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT cs.carne_id) as quantidade_carnes,
                    SUM(cpa.valor_parcela * cs.percentage / 100) as total,
                    AVG(cs.percentage) as percentual_medio
                FROM carne_splits cs
                JOIN carne_parcelas cpa ON cs.carne_id = cpa.carne_id
                WHERE cs.seller_id::varchar = %s
                AND cpa.status = 'paid'
                AND cpa.data_pagamento BETWEEN %s AND %s
            """, (seller_id, data_inicio, data_fim))
            
            carnes = cursor.fetchone()
            if carnes[0] > 0:
                resultado["por_tipo"]["carne"] = {
                    "quantidade": carnes[0],
                    "valor_total": float(carnes[1]) if carnes[1] else 0,
                    "percentual_medio": float(carnes[2]) if carnes[2] else 0
                }
                resultado["resumo"]["total_recebido"] += resultado["por_tipo"]["carne"]["valor_total"]
                resultado["resumo"]["quantidade_transacoes"] += carnes[0]
            
            # 3. Faturas avulsas pagas
            cursor.execute("""
                SELECT 
                    COUNT(*) as quantidade,
                    SUM(fa.valor_total * fas.percentage / 100) as total,
                    AVG(fas.percentage) as percentual_medio
                FROM fatura_avulsa_splits fas
                JOIN fatura_avulsa fa ON fas.invoice_id = fa.id
                WHERE fas.seller_id::varchar = %s
                AND fa.status = 'paid'
                AND fa.data_pagamento BETWEEN %s AND %s
            """, (seller_id, data_inicio, data_fim))
            
            faturas = cursor.fetchone()
            if faturas[0] > 0:
                resultado["por_tipo"]["fatura_avulsa"] = {
                    "quantidade": faturas[0],
                    "valor_total": float(faturas[1]) if faturas[1] else 0,
                    "percentual_medio": float(faturas[2]) if faturas[2] else 0
                }
                resultado["resumo"]["total_recebido"] += resultado["por_tipo"]["fatura_avulsa"]["valor_total"]
                resultado["resumo"]["quantidade_transacoes"] += faturas[0]
            
            # Calcular médias gerais
            if resultado["resumo"]["quantidade_transacoes"] > 0:
                resultado["resumo"]["ticket_medio"] = round(
                    resultado["resumo"]["total_recebido"] / resultado["resumo"]["quantidade_transacoes"], 2
                )
                
                # Calcular percentual médio ponderado
                total_percentual = sum(
                    tipo["percentual_medio"] * tipo["quantidade"] 
                    for tipo in resultado["por_tipo"].values()
                )
                resultado["resumo"]["percentual_medio"] = round(
                    total_percentual / resultado["resumo"]["quantidade_transacoes"], 2
                )
            
            # Evolução mensal
            cursor.execute("""
                WITH monthly_data AS (
                    -- Pré-vendas
                    SELECT 
                        DATE_TRUNC('month', pve.data_pagamento) as mes,
                        SUM(pvs.valor_calculado) as valor
                    FROM pre_venda_splits pvs
                    JOIN pre_vendas_entradas pve ON pvs.pre_venda_id = pve.pre_venda_id
                    WHERE pvs.seller_id = %s
                    AND pve.status_pagamento = 'pago'
                    AND pve.data_pagamento BETWEEN %s AND %s
                    GROUP BY DATE_TRUNC('month', pve.data_pagamento)
                    
                    UNION ALL
                    
                    -- Carnês
                    SELECT 
                        DATE_TRUNC('month', cpa.data_pagamento) as mes,
                        SUM(cpa.valor_parcela * cs.percentage / 100) as valor
                    FROM carne_splits cs
                    JOIN carne_parcelas cpa ON cs.carne_id = cpa.carne_id
                    WHERE cs.seller_id::varchar = %s
                    AND cpa.status = 'paid'
                    AND cpa.data_pagamento BETWEEN %s AND %s
                    GROUP BY DATE_TRUNC('month', cpa.data_pagamento)
                    
                    UNION ALL
                    
                    -- Faturas avulsas
                    SELECT 
                        DATE_TRUNC('month', fa.data_pagamento) as mes,
                        SUM(fa.valor_total * fas.percentage / 100) as valor
                    FROM fatura_avulsa_splits fas
                    JOIN fatura_avulsa fa ON fas.invoice_id = fa.id
                    WHERE fas.seller_id::varchar = %s
                    AND fa.status = 'paid'
                    AND fa.data_pagamento BETWEEN %s AND %s
                    GROUP BY DATE_TRUNC('month', fa.data_pagamento)
                )
                SELECT 
                    TO_CHAR(mes, 'YYYY-MM') as mes,
                    SUM(valor) as total
                FROM monthly_data
                GROUP BY mes
                ORDER BY mes
            """, (seller_id, data_inicio, data_fim, seller_id, data_inicio, data_fim, 
                  seller_id, data_inicio, data_fim))
            
            for row in cursor.fetchall():
                resultado["evolucao_mensal"].append({
                    "mes": row[0],
                    "valor": float(row[1]) if row[1] else 0
                })
            
            # Arredondar valores finais
            resultado["resumo"]["total_recebido"] = round(resultado["resumo"]["total_recebido"], 2)
            for tipo in resultado["por_tipo"]:
                resultado["por_tipo"][tipo]["valor_total"] = round(
                    resultado["por_tipo"][tipo]["valor_total"], 2
                )
            
            return resultado
            
    except Exception as e:
        logger.error(f"Erro ao obter resumo do seller {seller_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter resumo: {str(e)}"
        )