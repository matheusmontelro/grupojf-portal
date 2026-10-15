import unicodedata
from datetime import date
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.financeiro_pagamentos import (
    FinanceiroPagamentoItem,
    FinanceiroPagamentosFiltros,
    FinanceiroPagamentosResponse,
    FinanceiroPagamentosResumo,
)
from app.services.financeiro_pagamentos_service import (
    FinanceiroPagamentosService,
    TODAS_UNIDADES,
)


router = APIRouter(prefix="/financeiro", tags=["Financeiro - Pagamentos"])

STATUS_PERMITIDOS = {
    "pago",
    "pendente",
    "vencido",
    "cancelado",
    "falha",
    "estornado",
    "disputa",
    "todos",
    "todas",
}

STATUS_ALIASES = {
    "paga": "pago",
    "paid": "pago",
    "pay": "pago",
    "cancelada": "cancelado",
    "canceled": "cancelado",
    "cancelled": "cancelado",
    "void": "cancelado",
    "em_aberto": "pendente",
    "atrasado": "vencido",
    "falhou": "falha",
    "failed": "falha",
    "refund": "estornado",
    "refunded": "estornado",
    "chargeback": "disputa",
}

TIPOS_PERMITIDOS = {
    "entrada",
    "taxa_adesao",
    "carne",
    "fatura_recorrente",
    "parcela_venda",
    "todos",
    "todas",
}

TIPO_ALIASES = {
    "cartao_recorrente": "fatura_recorrente",
    "cartao_credito_recorrente": "fatura_recorrente",
    "recorrente": "fatura_recorrente",
    "assinatura": "fatura_recorrente",
    "parcela": "parcela_venda",
    "parcelas": "parcela_venda",
    "taxa": "taxa_adesao",
}


def _normalizar_token(value: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(ch for ch in sem_acento if not unicodedata.combining(ch))
    return ascii_value.strip().lower().replace("-", "_").replace(" ", "_")


def _parse_multi(values: Optional[List[str]], aliases: Optional[Dict[str, str]] = None) -> Optional[List[str]]:
    if not values:
        return None

    parsed: List[str] = []
    for value in values:
        for part in value.split(","):
            if not part.strip():
                continue
            token = _normalizar_token(part)
            parsed.append((aliases or {}).get(token, token))

    return parsed or None


def _validar_lista(nome: str, values: Optional[List[str]], permitidos: set) -> None:
    invalidos = [value for value in (values or []) if value not in permitidos]
    if invalidos:
        raise HTTPException(
            status_code=400,
            detail=f"{nome} invalido(s): {', '.join(invalidos)}",
        )


def _unidade_efetiva(current_user: Dict, unidade: Optional[str]) -> Optional[str]:
    user_unidade = current_user.get("unidade")
    if user_unidade and user_unidade not in TODAS_UNIDADES:
        return user_unidade
    return unidade


def _validar_datas(
    data_inicio: Optional[date],
    data_fim: Optional[date],
    campo: str,
) -> None:
    if data_inicio and data_fim and data_fim < data_inicio:
        raise HTTPException(
            status_code=400,
            detail=f"Data final de {campo} deve ser maior ou igual a data inicial",
        )


def _build_filtros(
    current_user: Dict,
    data_vencimento_inicio: Optional[date],
    data_vencimento_fim: Optional[date],
    data_pagamento_inicio: Optional[date],
    data_pagamento_fim: Optional[date],
    status: Optional[List[str]],
    tipo: Optional[List[str]],
    unidade: Optional[str],
    cpf: Optional[str],
    nome: Optional[str],
    venda_id: Optional[int],
    documento_venda: Optional[str],
    forma_pagamento_id: Optional[int],
    tipo_odontograma: Optional[str],
) -> FinanceiroPagamentosFiltros:
    _validar_datas(data_vencimento_inicio, data_vencimento_fim, "vencimento")
    _validar_datas(data_pagamento_inicio, data_pagamento_fim, "pagamento")

    status_normalizado = _parse_multi(status, STATUS_ALIASES)
    tipo_normalizado = _parse_multi(tipo, TIPO_ALIASES)
    _validar_lista("status", status_normalizado, STATUS_PERMITIDOS)
    _validar_lista("tipo", tipo_normalizado, TIPOS_PERMITIDOS)

    return FinanceiroPagamentosFiltros(
        data_vencimento_inicio=data_vencimento_inicio,
        data_vencimento_fim=data_vencimento_fim,
        data_pagamento_inicio=data_pagamento_inicio,
        data_pagamento_fim=data_pagamento_fim,
        status=status_normalizado,
        tipo=tipo_normalizado,
        unidade=_unidade_efetiva(current_user, unidade),
        cpf=cpf,
        nome=nome,
        venda_id=venda_id,
        documento_venda=documento_venda,
        forma_pagamento_id=forma_pagamento_id,
        tipo_odontograma=tipo_odontograma,
    )


@router.get("/pagamentos", response_model=FinanceiroPagamentosResponse)
async def listar_pagamentos_financeiros(
    data_vencimento_inicio: Optional[date] = Query(None),
    data_vencimento_fim: Optional[date] = Query(None),
    data_pagamento_inicio: Optional[date] = Query(None),
    data_pagamento_fim: Optional[date] = Query(None),
    status: Optional[List[str]] = Query(
        None,
        description="pago, pendente, vencido, cancelado, falha, estornado ou disputa. Aceita repetido ou separado por virgula.",
    ),
    tipo: Optional[List[str]] = Query(
        None,
        description="entrada, taxa_adesao, carne, fatura_recorrente ou parcela_venda. Aceita repetido ou separado por virgula.",
    ),
    unidade: Optional[str] = Query(None),
    cpf: Optional[str] = Query(None),
    nome: Optional[str] = Query(None),
    venda_id: Optional[int] = Query(None),
    documento_venda: Optional[str] = Query(None),
    forma_pagamento_id: Optional[int] = Query(None),
    tipo_odontograma: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    order_by: str = Query("data_vencimento"),
    order_dir: str = Query("desc", regex="^(asc|desc)$"),
    current_user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filtros = _build_filtros(
        current_user=current_user,
        data_vencimento_inicio=data_vencimento_inicio,
        data_vencimento_fim=data_vencimento_fim,
        data_pagamento_inicio=data_pagamento_inicio,
        data_pagamento_fim=data_pagamento_fim,
        status=status,
        tipo=tipo,
        unidade=unidade,
        cpf=cpf,
        nome=nome,
        venda_id=venda_id,
        documento_venda=documento_venda,
        forma_pagamento_id=forma_pagamento_id,
        tipo_odontograma=tipo_odontograma,
    )
    service = FinanceiroPagamentosService()
    return service.listar_pagamentos(
        db=db,
        filtros=filtros,
        page=page,
        per_page=per_page,
        order_by=order_by,
        order_dir=order_dir,
    )


@router.get("/pagamentos/resumo", response_model=FinanceiroPagamentosResumo)
async def resumo_pagamentos_financeiros(
    data_vencimento_inicio: Optional[date] = Query(None),
    data_vencimento_fim: Optional[date] = Query(None),
    data_pagamento_inicio: Optional[date] = Query(None),
    data_pagamento_fim: Optional[date] = Query(None),
    status: Optional[List[str]] = Query(None),
    tipo: Optional[List[str]] = Query(None),
    unidade: Optional[str] = Query(None),
    cpf: Optional[str] = Query(None),
    nome: Optional[str] = Query(None),
    venda_id: Optional[int] = Query(None),
    documento_venda: Optional[str] = Query(None),
    forma_pagamento_id: Optional[int] = Query(None),
    tipo_odontograma: Optional[str] = Query(None),
    current_user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filtros = _build_filtros(
        current_user=current_user,
        data_vencimento_inicio=data_vencimento_inicio,
        data_vencimento_fim=data_vencimento_fim,
        data_pagamento_inicio=data_pagamento_inicio,
        data_pagamento_fim=data_pagamento_fim,
        status=status,
        tipo=tipo,
        unidade=unidade,
        cpf=cpf,
        nome=nome,
        venda_id=venda_id,
        documento_venda=documento_venda,
        forma_pagamento_id=forma_pagamento_id,
        tipo_odontograma=tipo_odontograma,
    )
    service = FinanceiroPagamentosService()
    return service.obter_resumo(db=db, filtros=filtros)


@router.get("/vendas/{venda_id}/pagamentos", response_model=List[FinanceiroPagamentoItem])
async def pagamentos_da_venda(
    venda_id: int,
    current_user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = FinanceiroPagamentosService()
    pagamentos = service.pagamentos_da_venda(db=db, venda_id=venda_id)

    unidade_usuario = _unidade_efetiva(current_user, None)
    if unidade_usuario:
        pagamentos = [item for item in pagamentos if item.unidade == unidade_usuario]

    return pagamentos
