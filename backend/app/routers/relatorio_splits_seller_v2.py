# backend/app/routers/relatorio_splits_seller_v2.py

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
    prefix="/relatorio-splits-v2",
    tags=["Relatório de Splits V2"],
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
    
class SplitDetalhado(BaseModel):
    tipo_split: str  # 'pre_venda', 'venda', 'carne', 'fatura_avulsa', 'fatura_recorrente'
    id_referencia: str  # ID da pré-venda, carnê, fatura, etc
    data_criacao: date
    valor_base: float  # Valor sobre o qual o split é calculado
    status_geral: str  # Status do pagamento principal
    data_pagamento: Optional[date]
    beneficiarios: List[BeneficiarioSplit]
    
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
    splits_detalhados: List[SplitDetalhado]
    resumo_splits: Dict[str, Any]

@router.get("/venda-completa/{venda_id}")
async def obter_todos_splits_venda(
    venda_id: int,
    current_user: dict = Depends(get_current_user)
) -> VendaComTodosSplits:
    """
    Obter TODOS os splits de uma venda, incluindo empresas e status de pagamento.
    
    **Retorna:**
    - Informações completas da venda
    - Todos os splits (pagos e não pagos) de:
      - Pré-venda/entrada
      - Venda direta
      - Carnê
      - Faturas avulsas
      - Faturas recorrentes
    - Detalhes de cada beneficiário (usuário ou empresa)
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # 1. Buscar informações da venda
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
                    v.carne_id
                FROM vendas v
                JOIN pacientes p ON v.paciente_id = p.paciente_id
                LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                WHERE v.id = %s
            """, (venda_id,))
            
            venda = cursor.fetchone()
            if not venda:
                raise HTTPException(status_code=404, detail="Venda não encontrada")
            
            # Extrair dados da venda
            pre_venda_id = venda[10]
            carne_id = venda[11]
            
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
                        pve.created_at,
                        -- Dados do usuário
                        u.nome as user_nome,
                        u.cpf as user_cpf,
                        -- Dados da empresa
                        e.razao_social as empresa_nome,
                        e.cnpj as empresa_cnpj
                    FROM pre_venda_splits pvs
                    LEFT JOIN pre_vendas_entradas pve ON pvs.pre_venda_id = pve.pre_venda_id
                    LEFT JOIN users u ON pvs.user_id = u.id
                    LEFT JOIN empresas e ON pvs.empresa_id = e.id
                    WHERE pvs.pre_venda_id = %s
                    ORDER BY pvs.percentage DESC
                """, (pre_venda_id,))
                
                pre_venda_splits = cursor.fetchall()
                if pre_venda_splits:
                    # Pegar informações da primeira linha (são as mesmas para todos os splits)
                    primeira_linha = pre_venda_splits[0]
                    valor_pago = float(primeira_linha[5]) if primeira_linha[5] else 0
                    status_pagamento = primeira_linha[6]
                    data_pagamento = primeira_linha[7]
                    data_criacao = primeira_linha[8]
                    
                    beneficiarios = []
                    for split in pre_venda_splits:
                        # Determinar tipo e dados do beneficiário
                        if split[3]:  # user_id existe
                            tipo = "usuario"
                            id_beneficiario = split[3]
                            nome_beneficiario = split[9]
                            cpf_cnpj = split[10]
                        elif split[4]:  # empresa_id existe
                            tipo = "empresa"
                            id_beneficiario = split[4]
                            nome_beneficiario = split[11]
                            cpf_cnpj = split[12]
                        else:
                            tipo = "outro"
                            id_beneficiario = None
                            nome_beneficiario = f"Seller {split[0]}"
                            cpf_cnpj = None
                        
                        beneficiarios.append(BeneficiarioSplit(
                            seller_id=split[0],
                            tipo=tipo,
                            id_beneficiario=id_beneficiario,
                            nome_beneficiario=nome_beneficiario,
                            cpf_cnpj=cpf_cnpj,
                            percentage=float(split[1]),
                            valor_calculado=float(split[2]) if split[2] else 0,
                            status_pagamento=status_pagamento
                        ))
                        
                        # Atualizar resumo
                        resumo_splits["beneficiarios_unicos"].add(f"{tipo}_{id_beneficiario}")
                    
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
                        cp.created_at,
                        (SELECT COUNT(*) FROM carne_parcelas WHERE carne_id = cp.id AND status = 'paid') as parcelas_pagas,
                        -- Dados do usuário
                        u.nome as user_nome,
                        u.cpf as user_cpf,
                        -- Dados da empresa
                        e.razao_social as empresa_nome,
                        e.cnpj as empresa_cnpj
                    FROM carne_splits cs
                    LEFT JOIN carne_pagamento cp ON cs.carne_id = cp.id
                    LEFT JOIN users u ON cs.user_id = u.id
                    LEFT JOIN empresas e ON cs.empresa_id = e.id
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
                        # Determinar tipo e dados do beneficiário
                        if split[2]:  # user_id existe
                            tipo = "usuario"
                            id_beneficiario = split[2]
                            nome_beneficiario = split[8]
                            cpf_cnpj = split[9]
                        elif split[3]:  # empresa_id existe
                            tipo = "empresa"
                            id_beneficiario = split[3]
                            nome_beneficiario = split[10]
                            cpf_cnpj = split[11]
                        else:
                            tipo = "outro"
                            id_beneficiario = None
                            nome_beneficiario = f"Seller {split[0]}"
                            cpf_cnpj = None
                        
                        valor_split_total = valor_total * float(split[1]) / 100
                        
                        beneficiarios.append(BeneficiarioSplit(
                            seller_id=str(split[0]),
                            tipo=tipo,
                            id_beneficiario=id_beneficiario,
                            nome_beneficiario=nome_beneficiario,
                            cpf_cnpj=cpf_cnpj,
                            percentage=float(split[1]),
                            valor_calculado=round(valor_split_total, 2),
                            status_pagamento=f"{parcelas_pagas}/{qtd_parcelas} pagas"
                        ))
                        
                        resumo_splits["beneficiarios_unicos"].add(f"{tipo}_{id_beneficiario}")
                    
                    splits_detalhados.append(SplitDetalhado(
                        tipo_split="carne",
                        id_referencia=str(carne_id),
                        data_criacao=data_criacao.date() if data_criacao else venda[2],
                        valor_base=valor_total,
                        status_geral=f"{parcelas_pagas}/{qtd_parcelas} parcelas pagas",
                        data_pagamento=None,  # Carnê não tem data única de pagamento
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
                    fa.created,
                    -- Dados do usuário
                    u.nome as user_nome,
                    u.cpf as user_cpf,
                    -- Dados da empresa
                    e.nome as empresa_nome,
                    e.cnpj as empresa_cnpj
                FROM fatura_avulsa_splits fas
                LEFT JOIN fatura_avulsa fa ON fas.invoice_id = fa.id
                LEFT JOIN users u ON fas.user_id = u.id
                LEFT JOIN empresas e ON fas.empresa_id = e.id
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
                
                # Determinar tipo e dados do beneficiário
                if split[2]:  # user_id existe
                    tipo = "usuario"
                    id_beneficiario = split[2]
                    nome_beneficiario = split[9]
                    cpf_cnpj = split[10]
                elif split[3]:  # empresa_id existe
                    tipo = "empresa"
                    id_beneficiario = split[3]
                    nome_beneficiario = split[11]
                    cpf_cnpj = split[12]
                else:
                    tipo = "outro"
                    id_beneficiario = None
                    nome_beneficiario = f"Seller {split[0]}"
                    cpf_cnpj = None
                
                valor_calculado = faturas_processadas[fatura_id]["valor_total"] * float(split[1]) / 100
                
                faturas_processadas[fatura_id]["beneficiarios"].append(BeneficiarioSplit(
                    seller_id=str(split[0]),
                    tipo=tipo,
                    id_beneficiario=id_beneficiario,
                    nome_beneficiario=nome_beneficiario,
                    cpf_cnpj=cpf_cnpj,
                    percentage=float(split[1]),
                    valor_calculado=round(valor_calculado, 2),
                    status_pagamento=split[6]
                ))
                
                resumo_splits["beneficiarios_unicos"].add(f"{tipo}_{id_beneficiario}")
            
            # Adicionar faturas ao resultado
            for fatura_id, fatura_data in faturas_processadas.items():
                splits_detalhados.append(SplitDetalhado(
                    tipo_split="fatura_avulsa",
                    id_referencia=str(fatura_id),
                    data_criacao=fatura_data["data_criacao"].date() if fatura_data["data_criacao"] else venda[2],
                    valor_base=fatura_data["valor_total"],
                    status_geral=fatura_data["status"] or "pendente",
                    data_pagamento=fatura_data["data_pagamento"],
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
                    fr.created_at,
                    -- Dados do usuário
                    u.nome as user_nome,
                    u.cpf as user_cpf,
                    -- Dados da empresa
                    e.nome as empresa_nome,
                    e.cnpj as empresa_cnpj
                FROM fatura_recorrente_splits frs
                LEFT JOIN fatura_recorrente fr ON frs.subscription_id = fr.subscription_id_delta
                LEFT JOIN users u ON frs.user_id = u.id
                LEFT JOIN empresas e ON frs.empresa_id = e.id
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
                    # Determinar tipo e dados do beneficiário
                    if split[2]:  # user_id existe
                        tipo = "usuario"
                        id_beneficiario = split[2]
                        nome_beneficiario = split[8]
                        cpf_cnpj = split[9]
                    elif split[3]:  # empresa_id existe
                        tipo = "empresa"
                        id_beneficiario = split[3]
                        nome_beneficiario = split[10]
                        cpf_cnpj = split[11]
                    else:
                        tipo = "outro"
                        id_beneficiario = None
                        nome_beneficiario = f"Seller {split[0]}"
                        cpf_cnpj = None
                    
                    valor_calculado = valor_mensal * float(split[1]) / 100
                    
                    beneficiarios.append(BeneficiarioSplit(
                        seller_id=str(split[0]),
                        tipo=tipo,
                        id_beneficiario=id_beneficiario,
                        nome_beneficiario=nome_beneficiario,
                        cpf_cnpj=cpf_cnpj,
                        percentage=float(split[1]),
                        valor_calculado=round(valor_calculado, 2),
                        status_pagamento=status
                    ))
                    
                    resumo_splits["beneficiarios_unicos"].add(f"{tipo}_{id_beneficiario}")
                
                splits_detalhados.append(SplitDetalhado(
                    tipo_split="fatura_recorrente",
                    id_referencia=subscription_id,
                    data_criacao=data_criacao.date() if data_criacao else venda[2],
                    valor_base=valor_mensal,
                    status_geral=status or "ativo",
                    data_pagamento=None,  # Recorrente não tem data única
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
                data_venda=venda[2],
                paciente_nome=venda[3],
                paciente_cpf=venda[4],
                odontograma_tipo=venda[5],
                valor_bruto=float(venda[6]) if venda[6] else 0,
                valor_liquido=float(venda[7]) if venda[7] else 0,
                unidade=venda[8],
                status_venda=venda[9],
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

@router.get("/relatorio-completo")
async def obter_relatorio_completo_splits(
    data_inicio: date = Query(..., description="Data de início do período"),
    data_fim: date = Query(..., description="Data de fim do período"),
    seller_id: Optional[str] = Query(None, description="Filtrar por seller específico"),
    incluir_empresas: bool = Query(True, description="Incluir splits de empresas"),
    incluir_usuarios: bool = Query(True, description="Incluir splits de usuários"),
    apenas_pagos: bool = Query(False, description="Mostrar apenas splits pagos"),
    current_user: dict = Depends(get_current_user)
):
    """
    Relatório completo de splits mostrando todas as vendas e seus beneficiários.
    
    **Parâmetros:**
    - **data_inicio/data_fim**: Período para análise
    - **seller_id**: Filtrar por um seller específico
    - **incluir_empresas**: Se deve incluir splits que vão para empresas
    - **incluir_usuarios**: Se deve incluir splits que vão para usuários
    - **apenas_pagos**: Se deve mostrar apenas splits já pagos
    
    **Retorna:**
    - Lista de vendas com todos os seus splits
    - Separação clara entre beneficiários (usuários e empresas)
    - Status de pagamento de cada split
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
            
            # Query principal para buscar vendas no período
            query_vendas = """
                SELECT DISTINCT
                    v.id,
                    v.documento_venda,
                    v.data_venda,
                    p.nome_paciente,
                    p.cpf_cnpj,
                    od.tipo,
                    v.valor_bruto_total,
                    v.valor_liquido_total,
                    v.unidade,
                    v.status_venda
                FROM vendas v
                JOIN pacientes p ON v.paciente_id = p.paciente_id
                LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                WHERE v.data_venda BETWEEN %s AND %s
            """
            
            params = [data_inicio, data_fim]
            
            if filtro_unidade:
                query_vendas += " AND v.unidade = %s"
                params.append(filtro_unidade)
            
            query_vendas += " ORDER BY v.data_venda DESC"
            
            cursor.execute(query_vendas, params)
            vendas = cursor.fetchall()
            
            resultado = {
                "periodo": {
                    "data_inicio": data_inicio.isoformat(),
                    "data_fim": data_fim.isoformat()
                },
                "filtros": {
                    "seller_id": seller_id,
                    "incluir_empresas": incluir_empresas,
                    "incluir_usuarios": incluir_usuarios,
                    "apenas_pagos": apenas_pagos,
                    "unidade": filtro_unidade
                },
                "resumo": {
                    "total_vendas": len(vendas),
                    "total_splits": 0,
                    "valor_total_splits": 0,
                    "splits_por_tipo": {},
                    "beneficiarios": {
                        "usuarios": {},
                        "empresas": {}
                    }
                },
                "vendas": []
            }
            
            # Processar cada venda
            for venda in vendas:
                venda_id = venda[0]
                
                # Buscar todos os splits desta venda
                venda_obj = await obter_todos_splits_venda(venda_id, current_user)
                
                # Filtrar splits conforme parâmetros
                splits_filtrados = []
                for split_detalhado in venda_obj.splits_detalhados:
                    beneficiarios_filtrados = []
                    
                    for beneficiario in split_detalhado.beneficiarios:
                        # Aplicar filtros
                        if seller_id and beneficiario.seller_id != seller_id:
                            continue
                        
                        if not incluir_empresas and beneficiario.tipo == "empresa":
                            continue
                        
                        if not incluir_usuarios and beneficiario.tipo == "usuario":
                            continue
                        
                        if apenas_pagos and beneficiario.status_pagamento not in ["pago", "paid"]:
                            continue
                        
                        beneficiarios_filtrados.append(beneficiario)
                        
                        # Atualizar resumo
                        resultado["resumo"]["total_splits"] += 1
                        resultado["resumo"]["valor_total_splits"] += beneficiario.valor_calculado
                        
                        # Contabilizar por tipo
                        tipo_split = split_detalhado.tipo_split
                        if tipo_split not in resultado["resumo"]["splits_por_tipo"]:
                            resultado["resumo"]["splits_por_tipo"][tipo_split] = {
                                "quantidade": 0,
                                "valor_total": 0
                            }
                        resultado["resumo"]["splits_por_tipo"][tipo_split]["quantidade"] += 1
                        resultado["resumo"]["splits_por_tipo"][tipo_split]["valor_total"] += beneficiario.valor_calculado
                        
                        # Contabilizar beneficiários
                        if beneficiario.tipo == "usuario" and beneficiario.id_beneficiario:
                            user_key = str(beneficiario.id_beneficiario)
                            if user_key not in resultado["resumo"]["beneficiarios"]["usuarios"]:
                                resultado["resumo"]["beneficiarios"]["usuarios"][user_key] = {
                                    "nome": beneficiario.nome_beneficiario,
                                    "cpf": beneficiario.cpf_cnpj,
                                    "total_recebido": 0,
                                    "quantidade_splits": 0
                                }
                            resultado["resumo"]["beneficiarios"]["usuarios"][user_key]["total_recebido"] += beneficiario.valor_calculado
                            resultado["resumo"]["beneficiarios"]["usuarios"][user_key]["quantidade_splits"] += 1
                            
                        elif beneficiario.tipo == "empresa" and beneficiario.id_beneficiario:
                            emp_key = str(beneficiario.id_beneficiario)
                            if emp_key not in resultado["resumo"]["beneficiarios"]["empresas"]:
                                resultado["resumo"]["beneficiarios"]["empresas"][emp_key] = {
                                    "nome": beneficiario.nome_beneficiario,
                                    "cnpj": beneficiario.cpf_cnpj,
                                    "total_recebido": 0,
                                    "quantidade_splits": 0
                                }
                            resultado["resumo"]["beneficiarios"]["empresas"][emp_key]["total_recebido"] += beneficiario.valor_calculado
                            resultado["resumo"]["beneficiarios"]["empresas"][emp_key]["quantidade_splits"] += 1
                    
                    if beneficiarios_filtrados:
                        split_detalhado.beneficiarios = beneficiarios_filtrados
                        splits_filtrados.append(split_detalhado)
                
                # Adicionar venda ao resultado apenas se tiver splits após filtros
                if splits_filtrados:
                    venda_obj.splits_detalhados = splits_filtrados
                    resultado["vendas"].append(venda_obj.dict())
            
            # Arredondar valores do resumo
            resultado["resumo"]["valor_total_splits"] = round(resultado["resumo"]["valor_total_splits"], 2)
            for tipo in resultado["resumo"]["splits_por_tipo"]:
                resultado["resumo"]["splits_por_tipo"][tipo]["valor_total"] = round(
                    resultado["resumo"]["splits_por_tipo"][tipo]["valor_total"], 2
                )
            
            for usuarios in resultado["resumo"]["beneficiarios"]["usuarios"].values():
                usuarios["total_recebido"] = round(usuarios["total_recebido"], 2)
            
            for empresas in resultado["resumo"]["beneficiarios"]["empresas"].values():
                empresas["total_recebido"] = round(empresas["total_recebido"], 2)
            
            return resultado
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar relatório completo de splits: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar relatório: {str(e)}"
        )