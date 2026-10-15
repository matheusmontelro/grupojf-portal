# backend/app/routers/relatorio_caixa.py

from fastapi import APIRouter, Query, HTTPException, Depends, Response
from fastapi.responses import FileResponse
from typing import Optional, List
from datetime import date, datetime, timedelta
import logging

from app.models.relatorio_caixa import (
    RelatorioCaixaDiario,
    RelatorioCaixaFiltros,
    ResumoCaixaDiario,
    VendaCaixaItem,
    MetricasCaixaRapidas,
    FormatoExportacao,
    StatusVenda
)
from app.services.relatorio_caixa_service import RelatorioCaixaService
from app.middleware.auth_middleware import get_current_user

# Configurar logging
logger = logging.getLogger(__name__)

# Criar router
router = APIRouter(
    prefix="/relatorio-caixa",
    tags=["Relatório de Caixa"],
    responses={404: {"description": "Not found"}}
)

@router.get("/diario", response_model=RelatorioCaixaDiario)
async def obter_relatorio_caixa_diario(
    data_inicio: date = Query(..., description="Data de início do período (YYYY-MM-DD)"),
    data_fim: date = Query(..., description="Data de fim do período (YYYY-MM-DD)"),
    dentista_id: Optional[int] = Query(None, description="Filtrar por dentista específico"),
    forma_pagamento_id: Optional[int] = Query(None, description="Filtrar por forma de pagamento"),
    status_venda: Optional[StatusVenda] = Query(None, description="Filtrar por status da venda"),
    tipo_odontograma: Optional[str] = Query(None, description="Filtrar por tipo de odontograma"),
    page: int = Query(1, ge=1, description="Página para paginação"),
    limit: int = Query(10, ge=1, le=100, description="Limite de registros por página"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter relatório de caixa diário com filtros e paginação.
    
    Retorna:
    - Lista de vendas do período
    - Resumo financeiro com totais e métricas
    - Informações de paginação
    """
    try:
        # Validar período
        if data_fim < data_inicio:
            raise HTTPException(
                status_code=400, 
                detail="Data de fim deve ser maior ou igual à data de início"
            )
        
        # Limitar período máximo (opcional, para performance)
        dias_periodo = (data_fim - data_inicio).days
        if dias_periodo > 365:
            raise HTTPException(
                status_code=400,
                detail="Período máximo permitido é de 365 dias"
            )
        
        # Determinar filtro de unidade
        user_unidade = current_user.get('unidade')
        filtro_unidade = None if user_unidade in ['Todas Unidades', 'Todas unidades'] else user_unidade
        
        # Criar filtros
        filtros = RelatorioCaixaFiltros(
            data_inicio=data_inicio,
            data_fim=data_fim,
            dentista_id=dentista_id,
            forma_pagamento_id=forma_pagamento_id,
            status_venda=status_venda,
            tipo_odontograma=tipo_odontograma,
            unidade=filtro_unidade,  # Filtrar por unidade do usuário (None = todas)
            page=page,
            limit=limit
        )
        
        # Obter relatório
        service = RelatorioCaixaService()
        relatorio = await service.obter_relatorio_diario(filtros)
        
        logger.info(f"Relatório de caixa gerado para usuário {current_user.get('email')} - Período: {data_inicio} a {data_fim}")
        
        return relatorio
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar relatório de caixa: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao gerar relatório"
        )

@router.get("/resumo", response_model=ResumoCaixaDiario)
async def obter_resumo_caixa(
    data_inicio: date = Query(..., description="Data de início do período"),
    data_fim: date = Query(..., description="Data de fim do período"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter apenas o resumo financeiro do caixa (sem lista de vendas).
    Útil para dashboards e métricas rápidas.
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
        
        service = RelatorioCaixaService()
        resumo = await service.obter_resumo_periodo(
            data_inicio=data_inicio,
            data_fim=data_fim,
            unidade=filtro_unidade
        )
        
        return resumo
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter resumo do caixa: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao obter resumo"
        )

@router.get("/metricas-rapidas", response_model=MetricasCaixaRapidas)
async def obter_metricas_rapidas(
    data_inicio: Optional[date] = Query(None, description="Data início (padrão: início do mês)"),
    data_fim: Optional[date] = Query(None, description="Data fim (padrão: hoje)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter métricas rápidas do caixa para dashboard.
    Se não informado, usa período do mês atual.
    """
    try:
        # Definir período padrão se não informado
        if not data_inicio or not data_fim:
            hoje = date.today()
            data_inicio = data_inicio or date(hoje.year, hoje.month, 1)
            data_fim = data_fim or hoje
        
        service = RelatorioCaixaService()
        metricas = await service.obter_metricas_rapidas(
            data_inicio=data_inicio,
            data_fim=data_fim,
            unidade=current_user.get('unidade')
        )
        
        return metricas
        
    except Exception as e:
        logger.error(f"Erro ao obter métricas rápidas: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao obter métricas"
        )

@router.get("/vendas-dentista/{dentista_id}", response_model=List[VendaCaixaItem])
async def obter_vendas_por_dentista(
    dentista_id: int,
    data_inicio: date = Query(..., description="Data de início"),
    data_fim: date = Query(..., description="Data de fim"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter vendas detalhadas de um dentista específico no período.
    """
    try:
        service = RelatorioCaixaService()
        vendas = await service.obter_vendas_por_dentista(
            dentista_id=dentista_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            unidade=current_user.get('unidade')
        )
        
        return vendas
        
    except Exception as e:
        logger.error(f"Erro ao obter vendas do dentista {dentista_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao obter vendas do dentista"
        )

@router.get("/vendas-forma-pagamento/{forma_pagamento_id}", response_model=List[VendaCaixaItem])
async def obter_vendas_por_forma_pagamento(
    forma_pagamento_id: int,
    data_inicio: date = Query(..., description="Data de início"),
    data_fim: date = Query(..., description="Data de fim"),
    current_user: dict = Depends(get_current_user)
):
    """
    Obter vendas detalhadas de uma forma de pagamento específica no período.
    """
    try:
        service = RelatorioCaixaService()
        vendas = await service.obter_vendas_por_forma_pagamento(
            forma_pagamento_id=forma_pagamento_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            unidade=current_user.get('unidade')
        )
        
        return vendas
        
    except Exception as e:
        logger.error(f"Erro ao obter vendas da forma de pagamento {forma_pagamento_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao obter vendas da forma de pagamento"
        )

# --- Endpoints de Exportação ---

@router.get("/diario/export/pdf")
async def exportar_relatorio_pdf(
    data_inicio: date = Query(..., description="Data de início"),
    data_fim: date = Query(..., description="Data de fim"),
    dentista_id: Optional[int] = Query(None, description="Filtrar por dentista"),
    forma_pagamento_id: Optional[int] = Query(None, description="Filtrar por forma de pagamento"),
    status_venda: Optional[StatusVenda] = Query(None, description="Filtrar por status"),
    current_user: dict = Depends(get_current_user)
):
    """
    Exportar relatório de caixa em formato PDF.
    """
    try:
        filtros = RelatorioCaixaFiltros(
            data_inicio=data_inicio,
            data_fim=data_fim,
            dentista_id=dentista_id,
            forma_pagamento_id=forma_pagamento_id,
            status_venda=status_venda,
            unidade=current_user.get('unidade'),
            page=1,
            limit=10000  # Exportar todos os registros
        )
        
        service = RelatorioCaixaService()
        arquivo_pdf = await service.exportar_pdf(filtros)
        
        # Gerar nome do arquivo
        periodo = f"{data_inicio.strftime('%d-%m-%Y')}_a_{data_fim.strftime('%d-%m-%Y')}"
        nome_arquivo = f"relatorio_caixa_{periodo}.pdf"
        
        return FileResponse(
            path=arquivo_pdf,
            media_type='application/pdf',
            filename=nome_arquivo
        )
        
    except Exception as e:
        logger.error(f"Erro ao exportar PDF: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao exportar PDF"
        )

@router.get("/diario/export/excel")
async def exportar_relatorio_excel(
    data_inicio: date = Query(..., description="Data de início"),
    data_fim: date = Query(..., description="Data de fim"),
    dentista_id: Optional[int] = Query(None, description="Filtrar por dentista"),
    forma_pagamento_id: Optional[int] = Query(None, description="Filtrar por forma de pagamento"),
    status_venda: Optional[StatusVenda] = Query(None, description="Filtrar por status"),
    current_user: dict = Depends(get_current_user)
):
    """
    Exportar relatório de caixa em formato Excel.
    """
    try:
        filtros = RelatorioCaixaFiltros(
            data_inicio=data_inicio,
            data_fim=data_fim,
            dentista_id=dentista_id,
            forma_pagamento_id=forma_pagamento_id,
            status_venda=status_venda,
            unidade=current_user.get('unidade'),
            page=1,
            limit=10000  # Exportar todos os registros
        )
        
        service = RelatorioCaixaService()
        arquivo_excel = await service.exportar_excel(filtros)
        
        # Gerar nome do arquivo
        periodo = f"{data_inicio.strftime('%d-%m-%Y')}_a_{data_fim.strftime('%d-%m-%Y')}"
        nome_arquivo = f"relatorio_caixa_{periodo}.xlsx"
        
        return FileResponse(
            path=arquivo_excel,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=nome_arquivo
        )
        
    except Exception as e:
        logger.error(f"Erro ao exportar Excel: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao exportar Excel"
        )

@router.get("/diario/export/csv")
async def exportar_relatorio_csv(
    data_inicio: date = Query(..., description="Data de início"),
    data_fim: date = Query(..., description="Data de fim"),
    dentista_id: Optional[int] = Query(None, description="Filtrar por dentista"),
    forma_pagamento_id: Optional[int] = Query(None, description="Filtrar por forma de pagamento"),
    status_venda: Optional[StatusVenda] = Query(None, description="Filtrar por status"),
    current_user: dict = Depends(get_current_user)
):
    """
    Exportar relatório de caixa em formato CSV.
    """
    try:
        filtros = RelatorioCaixaFiltros(
            data_inicio=data_inicio,
            data_fim=data_fim,
            dentista_id=dentista_id,
            forma_pagamento_id=forma_pagamento_id,
            status_venda=status_venda,
            unidade=current_user.get('unidade'),
            page=1,
            limit=10000  # Exportar todos os registros
        )
        
        service = RelatorioCaixaService()
        arquivo_csv = await service.exportar_csv(filtros)
        
        # Gerar nome do arquivo
        periodo = f"{data_inicio.strftime('%d-%m-%Y')}_a_{data_fim.strftime('%d-%m-%Y')}"
        nome_arquivo = f"relatorio_caixa_{periodo}.csv"
        
        return FileResponse(
            path=arquivo_csv,
            media_type='text/csv',
            filename=nome_arquivo
        )
        
    except Exception as e:
        logger.error(f"Erro ao exportar CSV: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao exportar CSV"
        )

# --- Endpoints auxiliares ---

@router.get("/tipos-odontograma", response_model=List[str])
async def obter_tipos_odontograma_disponiveis(
    current_user: dict = Depends(get_current_user)
):
    """
    Obter lista de tipos de odontograma disponíveis para filtro.
    """
    try:
        service = RelatorioCaixaService()
        tipos = await service.obter_tipos_odontograma_disponiveis()
        
        return tipos
        
    except Exception as e:
        logger.error(f"Erro ao obter tipos de odontograma: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao obter tipos de odontograma"
        )

@router.get("/status")
async def verificar_status():
    """
    Verificar se o serviço de relatório de caixa está funcionando.
    """
    return {
        "status": "OK",
        "service": "Relatório de Caixa",
        "timestamp": datetime.now().isoformat()
    }