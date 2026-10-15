# backend/app/routers/relatorio_vendas.py

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List
from datetime import date, datetime, timedelta
import logging

from app.models.relatorio_vendas import (
    RelatorioVendasCompleto,
    RelatorioVendasFiltros,
    VendaPorPaciente
)
from app.services.relatorio_vendas_service import RelatorioVendasService
from app.middleware.auth_middleware import get_current_user

# Configurar logging
logger = logging.getLogger(__name__)

# Criar router
router = APIRouter(
    prefix="/relatorio-vendas",
    tags=["Relatório de Vendas"],
    responses={404: {"description": "Not found"}}
)

@router.get("/completo", response_model=RelatorioVendasCompleto)
async def obter_relatorio_vendas_completo(
    data_inicio: date = Query(..., description="Data de início do período (YYYY-MM-DD)"),
    data_fim: date = Query(..., description="Data de fim do período (YYYY-MM-DD)"),
    tipo_odontograma: Optional[str] = Query(None, description="Filtrar por tipo de odontograma específico"),
    current_user: dict = Depends(get_current_user)
):
    """
    Gerar relatório de vendas completo com análise detalhada por:
    
    **Seções do Relatório:**
    - 📊 **Vendas por Tipo de Odontograma**: Total de vendas, taxa de conversão, ticket médio
    - 💳 **Vendas por Forma de Pagamento Delta**: Análise por método de pagamento
    - 💰 **Valores Efetivamente Pagos**: Consolidado de valores recebidos por origem
    - 🔄 **Análises Cruzadas**: Matriz tipo odontograma x forma de pagamento
    - 📈 **Resumo Executivo**: Métricas consolidadas e indicadores principais
    
    **Parâmetros:**
    - **data_inicio/data_fim**: Período para análise (máximo 2 anos)
    - **tipo_odontograma**: Filtro opcional por tipo específico
    
    **Retorna:**
    - Relatório completo com todas as seções e análises
    - Dados consolidados de vendas, pagamentos e recebimentos
    - Métricas de performance e indicadores financeiros
    """
    try:
        # Validar período
        if data_fim < data_inicio:
            raise HTTPException(
                status_code=400, 
                detail="Data de fim deve ser maior ou igual à data de início"
            )
        
        # Limitar período máximo (2 anos para performance)
        dias_periodo = (data_fim - data_inicio).days
        if dias_periodo > 730:  # 2 anos
            raise HTTPException(
                status_code=400,
                detail="Período máximo permitido é de 2 anos (730 dias)"
            )
        
        # Determinar filtro de unidade baseado no usuário
        user_unidade = current_user.get('unidade')
        filtro_unidade = None if user_unidade in ['Todas Unidades', 'Todas unidades'] else user_unidade
        
        # Criar filtros
        filtros = RelatorioVendasFiltros(
            data_inicio=data_inicio,
            data_fim=data_fim,
            unidade=filtro_unidade,
            tipo_odontograma=tipo_odontograma
        )
        
        # Gerar relatório
        service = RelatorioVendasService()
        relatorio = service.gerar_relatorio_completo(filtros)
        
        logger.info(
            f"Relatório de vendas completo gerado para usuário {current_user.get('email')} - "
            f"Período: {data_inicio} a {data_fim} - "
            f"Unidade: {filtro_unidade or 'Todas'} - "
            f"Tipo Odontograma: {tipo_odontograma or 'Todos'}"
        )
        
        return relatorio
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar relatório de vendas completo: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao gerar relatório de vendas"
        )

@router.get("/resumo-executivo")
async def obter_resumo_executivo_vendas(
    data_inicio: date = Query(..., description="Data de início do período"),
    data_fim: date = Query(..., description="Data de fim do período"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter apenas o resumo executivo do relatório de vendas.
    Útil para dashboards e visão geral rápida.
    
    **Métricas Incluídas:**
    - Total de vendas e taxa de conversão
    - Valores brutos, líquidos e descontos
    - Total recebido e percentual de recebimento
    - Saldo a receber
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
        
        # Criar filtros
        filtros = RelatorioVendasFiltros(
            data_inicio=data_inicio,
            data_fim=data_fim,
            unidade=filtro_unidade
        )
        
        # Gerar apenas o resumo executivo
        service = RelatorioVendasService()
        
        # Usar DatabaseConnection para obter apenas o resumo
        from app.database.db import DatabaseConnection
        with DatabaseConnection() as conn:
            resumo = service._obter_resumo_executivo(conn, filtros)
        
        return resumo
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter resumo executivo de vendas: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao obter resumo executivo"
        )

@router.get("/vendas-por-tipo-odontograma")
async def obter_vendas_por_tipo_odontograma(
    data_inicio: date = Query(..., description="Data de início do período"),
    data_fim: date = Query(..., description="Data de fim do período"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter análise de vendas agrupadas por tipo de odontograma.
    
    **Dados Incluídos:**
    - Total de vendas por tipo
    - Taxa de conversão
    - Ticket médio, menor e maior venda
    - Valores brutos, descontos e líquidos
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
        
        # Criar filtros
        filtros = RelatorioVendasFiltros(
            data_inicio=data_inicio,
            data_fim=data_fim,
            unidade=filtro_unidade
        )
        
        # Obter dados
        service = RelatorioVendasService()
        
        # Usar DatabaseConnection
        from app.database.db import DatabaseConnection
        with DatabaseConnection() as conn:
            vendas_por_tipo = service._obter_vendas_por_tipo_odontograma(conn, filtros)
        
        return vendas_por_tipo
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter vendas por tipo de odontograma: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao obter vendas por tipo"
        )

@router.get("/vendas-por-forma-pagamento")
async def obter_vendas_por_forma_pagamento_delta(
    data_inicio: date = Query(..., description="Data de início do período"),
    data_fim: date = Query(..., description="Data de fim do período"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter análise de vendas agrupadas por forma de pagamento Delta.
    
    **Métodos Analisados:**
    - Carnê
    - Boleto Avulso Delta
    - PIX Avulso Delta  
    - Cartão Avulso Delta
    - Cartão Recorrente Delta
    - Outros/Não-Delta
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
        
        # Criar filtros
        filtros = RelatorioVendasFiltros(
            data_inicio=data_inicio,
            data_fim=data_fim,
            unidade=filtro_unidade
        )
        
        # Obter dados
        service = RelatorioVendasService()
        
        # Usar DatabaseConnection
        from app.database.db import DatabaseConnection
        with DatabaseConnection() as conn:
            vendas_por_forma = service._obter_vendas_por_forma_pagamento_delta(conn, filtros)
        
        return vendas_por_forma
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter vendas por forma de pagamento: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao obter vendas por forma de pagamento"
        )

@router.get("/valores-efetivamente-pagos")
async def obter_valores_efetivamente_pagos(
    data_inicio: date = Query(..., description="Data de início do período"),
    data_fim: date = Query(..., description="Data de fim do período"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter consolidado de valores efetivamente pagos por tipo e origem.
    
    **Tipos de Pagamento:**
    - Entradas (Vendas e Pré-Vendas)
    - Parcelas de Carnê
    - Parcelas de Venda Direta
    - Cartão/Boleto/PIX Avulso Delta
    - Cartão Recorrente Delta
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
        
        # Criar filtros
        filtros = RelatorioVendasFiltros(
            data_inicio=data_inicio,
            data_fim=data_fim,
            unidade=filtro_unidade
        )
        
        # Obter dados
        service = RelatorioVendasService()
        
        # Usar DatabaseConnection
        from app.database.db import DatabaseConnection
        with DatabaseConnection() as conn:
            valores_pagos = service._obter_valores_efetivamente_pagos(conn, filtros)
        
        return valores_pagos
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter valores efetivamente pagos: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao obter valores pagos"
        )


@router.get("/vendas-por-paciente", response_model=List[VendaPorPaciente])
async def obter_vendas_por_paciente(
    data_inicio: date = Query(..., description="Data de início do período"),
    data_fim: date = Query(..., description="Data de fim do período"),
    paciente_id: Optional[int] = Query(None, description="Filtrar por paciente específico"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter relatório detalhado de vendas por paciente.
    
    **Dados Incluídos:**
    - Nome e dados do paciente
    - Quantidade de vendas por paciente
    - Valor total, líquido, desconto e entrada
    - Valor pago e saldo a receber
    - Tipo de odontograma de cada venda
    - Formas de pagamento utilizadas
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
        
        # Criar filtros
        filtros = RelatorioVendasFiltros(
            data_inicio=data_inicio,
            data_fim=data_fim,
            unidade=filtro_unidade
        )
        
        # Obter dados
        service = RelatorioVendasService()
        
        # Usar DatabaseConnection
        from app.database.db import DatabaseConnection
        with DatabaseConnection() as conn:
            vendas_por_paciente = service._obter_vendas_por_paciente(conn, filtros, paciente_id)
        
        return vendas_por_paciente
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter vendas por paciente: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao obter vendas por paciente"
        )

@router.get("/status")
async def verificar_status():
    """
    Verificar se o serviço de relatório de vendas está funcionando.
    """
    return {
        "status": "OK",
        "service": "Relatório de Vendas Completo",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "description": "Relatório completo de vendas com análise por tipo de odontograma, formas de pagamento Delta e valores pagos"
    }

@router.get("/splits-por-seller")
async def obter_relatorio_splits_por_seller(
    seller_id: str = Query(..., description="ID do seller para filtrar"),
    data_inicio: date = Query(..., description="Data de início do período"),
    data_fim: date = Query(..., description="Data de fim do período"),
    incluir_produtos: bool = Query(True, description="Incluir produtos vendidos no relatório"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter relatório de vendas com splits pagos para um seller específico.
    
    **Dados Incluídos:**
    - Nome e CPF do paciente
    - Odontograma (tipo e ID)
    - Produtos vendidos (opcional)
    - Valor do split apenas do seller especificado
    - Tipo de pagamento (Entrada, Carnê, Fatura)
    - Data do pagamento
    
    **Parâmetros:**
    - **seller_id**: ID do seller (ex: '1' para Seller ID 1)
    - **data_inicio/data_fim**: Período para análise
    - **incluir_produtos**: Se deve incluir lista de produtos vendidos
    
    **Retorna:**
    - Lista de vendas com valores pagos que têm split para o seller
    - Total geral recebido pelo seller
    - Resumo por tipo de pagamento
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
        
        logger.info(
            f"Gerando relatório de splits para seller {seller_id} - "
            f"Período: {data_inicio} a {data_fim} - "
            f"Unidade: {filtro_unidade or 'Todas'}"
        )
        
        from app.database.db import DatabaseConnection
        
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Query principal
            if incluir_produtos:
                query = """
                WITH vendas_com_splits AS (
                    -- Pré-vendas pagas
                    SELECT 
                        v.id as venda_id,
                        p.nome_paciente,
                        p.cpf_cnpj,
                        od.id as odontograma_id,
                        od.tipo as tipo_odontograma,
                        pve.valor_pago as valor_total,
                        pvs.percentage,
                        pvs.valor_calculado as valor_split,
                        'Entrada' as tipo_pagamento,
                        pve.created_at::date as data_pagamento,
                        v.unidade
                    FROM pre_venda_splits pvs
                    INNER JOIN pre_vendas_entradas pve ON pvs.pre_venda_id = pve.pre_venda_id
                    LEFT JOIN vendas v ON pve.pre_venda_id = v.pre_venda_id
                    LEFT JOIN pacientes p ON v.paciente_id = p.paciente_id
                    LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                    WHERE pvs.seller_id = %s 
                    AND pve.status = 'pago'
                    AND pve.created_at::date BETWEEN %s AND %s
                """
            else:
                query = """
                WITH vendas_com_splits AS (
                    -- Pré-vendas pagas
                    SELECT 
                        p.nome_paciente,
                        p.cpf_cnpj,
                        od.id as odontograma_id,
                        od.tipo as tipo_odontograma,
                        pve.valor_pago as valor_total,
                        pvs.percentage,
                        pvs.valor_calculado as valor_split,
                        'Entrada' as tipo_pagamento,
                        pve.created_at::date as data_pagamento,
                        v.unidade,
                        NULL as produtos
                    FROM pre_venda_splits pvs
                    INNER JOIN pre_vendas_entradas pve ON pvs.pre_venda_id = pve.pre_venda_id
                    LEFT JOIN vendas v ON pve.pre_venda_id = v.pre_venda_id
                    LEFT JOIN pacientes p ON v.paciente_id = p.paciente_id
                    LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                    WHERE pvs.seller_id = %s 
                    AND pve.status = 'pago'
                    AND pve.created_at::date BETWEEN %s AND %s
                """
            
            # Adicionar filtro de unidade se necessário
            params = [seller_id, data_inicio, data_fim]
            if filtro_unidade:
                query = query.replace("WHERE pvs.seller_id", "WHERE v.unidade = %s AND pvs.seller_id")
                params = [filtro_unidade] + params
            
            # Adicionar UNION para carnês e faturas
            query += """
                UNION ALL
                
                -- Carnês com parcelas pagas
                SELECT 
                    p.nome_paciente,
                    p.cpf_cnpj,
                    od.id as odontograma_id,
                    od.tipo as tipo_odontograma,
                    SUM(cpa.valor_parcela) as valor_total,
                    cs.percentage,
                    CAST(SUM(cpa.valor_parcela) * cs.percentage / 100 AS NUMERIC(10,2)) as valor_split,
                    'Carnê' as tipo_pagamento,
                    MAX(cpa.data_pagamento)::date as data_pagamento,
                    v.unidade
            """
            
            if incluir_produtos:
                query += """
                FROM carne_splits cs
                INNER JOIN carne_pagamento cp ON cs.carne_id = cp.id
                INNER JOIN carne_parcelas cpa ON cp.id = cpa.carne_id
                LEFT JOIN vendas v ON cp.venda_id = v.id
                LEFT JOIN pacientes p ON v.paciente_id = p.paciente_id
                LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                WHERE cs.seller_id = %s::integer 
                AND cpa.status = 'paid'
                AND cpa.data_pagamento::date BETWEEN %s AND %s
                """
            else:
                query += """,
                    NULL as produtos
                FROM carne_splits cs
                INNER JOIN carne_pagamento cp ON cs.carne_id = cp.id
                INNER JOIN carne_parcelas cpa ON cp.id = cpa.carne_id
                LEFT JOIN vendas v ON cp.venda_id = v.id
                LEFT JOIN pacientes p ON v.paciente_id = p.paciente_id
                LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                WHERE cs.seller_id = %s::integer 
                AND cpa.status = 'paid'
                AND cpa.data_pagamento::date BETWEEN %s AND %s
                """
            
            # Adicionar filtro de unidade para carnês
            if filtro_unidade:
                query = query.replace("WHERE cs.seller_id", "WHERE v.unidade = %s AND cs.seller_id")
                params.extend([filtro_unidade, seller_id, data_inicio, data_fim])
            else:
                params.extend([seller_id, data_inicio, data_fim])
            
            query += """
                GROUP BY p.nome_paciente, p.cpf_cnpj, od.id, od.tipo, cs.percentage, v.unidade
                
                UNION ALL
                
                -- Faturas avulsas pagas
                SELECT 
                    p.nome_paciente,
                    p.cpf_cnpj,
                    od.id as odontograma_id,
                    od.tipo as tipo_odontograma,
                    fa.valor_total,
                    fas.percentage,
                    CAST(fa.valor_total * fas.percentage / 100 AS NUMERIC(10,2)) as valor_split,
                    'Fatura' as tipo_pagamento,
                    fa.data_pagamento::date as data_pagamento,
                    v.unidade
            """
            
            if incluir_produtos:
                query += """
                FROM fatura_avulsa_splits fas
                INNER JOIN fatura_avulsa fa ON fas.invoice_id = fa.id
                LEFT JOIN vendas v ON fa.venda_id = v.id
                LEFT JOIN pacientes p ON v.paciente_id = p.paciente_id
                LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                WHERE fas.seller_id = %s::integer 
                AND fa.status = 'paid'
                AND fa.data_pagamento::date BETWEEN %s AND %s
                """
            else:
                query += """,
                    NULL as produtos
                FROM fatura_avulsa_splits fas
                INNER JOIN fatura_avulsa fa ON fas.invoice_id = fa.id
                LEFT JOIN vendas v ON fa.venda_id = v.id
                LEFT JOIN pacientes p ON v.paciente_id = p.paciente_id
                LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                WHERE fas.seller_id = %s::integer 
                AND fa.status = 'paid'
                AND fa.data_pagamento::date BETWEEN %s AND %s
                """
            
            # Adicionar filtro de unidade para faturas
            if filtro_unidade:
                query = query.replace("WHERE fas.seller_id", "WHERE v.unidade = %s AND fas.seller_id")
                params.extend([filtro_unidade, seller_id, data_inicio, data_fim])
            else:
                params.extend([seller_id, data_inicio, data_fim])
            
            # Finalizar query
            if incluir_produtos:
                query += """
                )
                SELECT 
                    vs.*,
                    STRING_AGG(DISTINCT pr.nome || ' (R$ ' || oi.valor_registrado || ')', ', ') as produtos
                FROM vendas_com_splits vs
                LEFT JOIN odontograma_itens oi ON vs.odontograma_id = oi.odontograma_id
                LEFT JOIN produtos pr ON oi.produto_id = pr.id
                GROUP BY 
                    vs.venda_id, vs.nome_paciente, vs.cpf_cnpj, vs.odontograma_id, 
                    vs.tipo_odontograma, vs.valor_total, vs.percentage, vs.valor_split,
                    vs.tipo_pagamento, vs.data_pagamento, vs.unidade
                ORDER BY vs.data_pagamento DESC, vs.valor_split DESC
                """
            else:
                query += """
                )
                SELECT * FROM vendas_com_splits
                ORDER BY data_pagamento DESC, valor_split DESC
                """
            
            cursor.execute(query, params)
            vendas = cursor.fetchall()
            
            # Preparar resposta
            resultado = {
                "seller_id": seller_id,
                "periodo": {
                    "data_inicio": data_inicio.isoformat(),
                    "data_fim": data_fim.isoformat()
                },
                "vendas": [],
                "resumo": {
                    "total_geral": 0,
                    "total_por_tipo": {},
                    "quantidade_vendas": 0
                }
            }
            
            # Processar vendas
            for venda in vendas:
                if incluir_produtos:
                    venda_dict = {
                        "nome_paciente": venda[1],
                        "cpf": venda[2],
                        "odontograma": {
                            "id": venda[3],
                            "tipo": venda[4]
                        },
                        "valor_total": float(venda[5]) if venda[5] else 0,
                        "percentual_seller": float(venda[6]) if venda[6] else 0,
                        "valor_split": float(venda[7]) if venda[7] else 0,
                        "tipo_pagamento": venda[8],
                        "data_pagamento": venda[9].isoformat() if venda[9] else None,
                        "unidade": venda[10],
                        "produtos": venda[11] or "Sem produtos registrados"
                    }
                else:
                    venda_dict = {
                        "nome_paciente": venda[0],
                        "cpf": venda[1],
                        "odontograma": {
                            "id": venda[2],
                            "tipo": venda[3]
                        },
                        "valor_total": float(venda[4]) if venda[4] else 0,
                        "percentual_seller": float(venda[5]) if venda[5] else 0,
                        "valor_split": float(venda[6]) if venda[6] else 0,
                        "tipo_pagamento": venda[7],
                        "data_pagamento": venda[8].isoformat() if venda[8] else None,
                        "unidade": venda[9]
                    }
                
                resultado["vendas"].append(venda_dict)
                
                # Atualizar resumo
                resultado["resumo"]["total_geral"] += venda_dict["valor_split"]
                resultado["resumo"]["quantidade_vendas"] += 1
                
                tipo = venda_dict["tipo_pagamento"]
                if tipo not in resultado["resumo"]["total_por_tipo"]:
                    resultado["resumo"]["total_por_tipo"][tipo] = {
                        "quantidade": 0,
                        "valor_total": 0
                    }
                resultado["resumo"]["total_por_tipo"][tipo]["quantidade"] += 1
                resultado["resumo"]["total_por_tipo"][tipo]["valor_total"] += venda_dict["valor_split"]
            
            # Formatar valores do resumo
            resultado["resumo"]["total_geral"] = round(resultado["resumo"]["total_geral"], 2)
            for tipo in resultado["resumo"]["total_por_tipo"]:
                resultado["resumo"]["total_por_tipo"][tipo]["valor_total"] = round(
                    resultado["resumo"]["total_por_tipo"][tipo]["valor_total"], 2
                )
            
            return resultado
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar relatório de splits por seller: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno ao gerar relatório de splits: {str(e)}"
        )

@router.get("/unidades")
async def obter_unidades_disponiveis(
    data_inicio: Optional[date] = Query(None, description="Data de início do período"),
    data_fim: Optional[date] = Query(None, description="Data de fim do período"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter lista de unidades disponíveis para o filtro de relatórios.
    Retorna as unidades únicas com vendas no período especificado.
    
    Se o usuário tem acesso apenas a uma unidade específica, retorna apenas essa unidade.
    Se o usuário tem acesso a todas as unidades, retorna todas as unidades com vendas.
    """
    try:
        logger.info(f"[obter_unidades_disponiveis] Usuário: {current_user.get('email')}, Unidade: {current_user.get('unidade')}")
        
        user_unidade = current_user.get('unidade')
        
        # Se o usuário tem acesso apenas a uma unidade específica
        if user_unidade and user_unidade not in ['Todas Unidades', 'Todas unidades']:
            logger.info(f"[obter_unidades_disponiveis] Usuário restrito à unidade: {user_unidade}")
            return {"unidades": [user_unidade]}
        
        # Se o usuário tem acesso a todas as unidades, buscar do banco
        from app.database.db import DatabaseConnection
        
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Query para buscar unidades únicas
            query = """
                SELECT DISTINCT v.unidade
                FROM vendas v
                WHERE v.unidade IS NOT NULL
                AND v.unidade != ''
            """
            
            params = []
            
            # Adicionar filtro de período se fornecido
            if data_inicio and data_fim:
                query += " AND v.data_venda::date BETWEEN %s AND %s"
                params.extend([data_inicio, data_fim])
            
            query += " ORDER BY v.unidade"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            unidades = [row[0] for row in rows if row[0]]
            
            logger.info(f"[obter_unidades_disponiveis] Encontradas {len(unidades)} unidades: {unidades}")
            
            return {"unidades": unidades}
            
    except Exception as e:
        logger.error(f"[obter_unidades_disponiveis] Erro: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter unidades disponíveis"
        )