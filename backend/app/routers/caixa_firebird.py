from datetime import datetime, date
import re
import unicodedata
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.security.auth_dependencies import get_current_user
from app.services.caixa_firebird_service import CATEGORIAS, CaixaFirebirdService, CaixaFonteResultado, UNIDADES

router = APIRouter(tags=["Caixa"])
_UNIDADE_CHAVES = {"ni1": "Nova Iguaçu 1", "nova iguacu 1": "Nova Iguaçu 1", "sjm": "São João de Meriti", "sao joao de meriti": "São João de Meriti", "vilar": "Vilar dos Teles", "vilar dos teles": "Vilar dos Teles"}

def _normalizar(valor: str | None) -> str:
    sem_acento = unicodedata.normalize("NFKD", valor or "").encode("ascii", "ignore").decode("ascii")
    return "".join(char for char in sem_acento.lower() if char.isalnum() or char.isspace()).strip()

def _unidade_usuario(usuario: dict) -> str | None:
    normalizada = _normalizar(usuario.get("unidade"))
    return _UNIDADE_CHAVES.get(normalizada)

def _autorizadas(usuario: dict, solicitada: str | None) -> tuple[str, ...]:
    role = _normalizar(usuario.get("role"))
    if role in {"master", "administrador"}:
        if not solicitada or solicitada == "all":
            return tuple(UNIDADES)
        unidade = _UNIDADE_CHAVES.get(_normalizar(solicitada))
        if not unidade:
            raise HTTPException(422, "Unidade inválida")
        return (unidade,)
    if role not in {"financeiro", "gerente"}:
        raise HTTPException(403, "Sem permissão para consultar caixa")
    unidade = _unidade_usuario(usuario)
    if not unidade:
        raise HTTPException(403, "Unidade do usuário não autorizada")
    if solicitada and _UNIDADE_CHAVES.get(_normalizar(solicitada)) != unidade:
        raise HTTPException(403, "A unidade solicitada não é permitida")
    return (unidade,)

def _resposta(mes: date, resultado: dict) -> dict:
    fontes: list[CaixaFonteResultado] = resultado["fontes"]
    consolidado: dict[tuple[str, date], dict] = {}
    for fonte in fontes:
        for item in fonte.dias:
            chave = (fonte.unidade, item["data"])
            dia = consolidado.setdefault(chave, {"data": item["data"], "unidade": fonte.unidade, "total_centavos": 0, "categorias": {categoria: 0 for categoria in CATEGORIAS}, "manutencoes_recebidas": 0, "fontes": [], "status_fechamento": "sem_movimento", "codigos_nao_classificados": [], "codigos_nao_homologados": []})
            dia["total_centavos"] += item["total_centavos"]
            dia["manutencoes_recebidas"] += item["manutencoes_recebidas"]
            dia["fontes"].append(fonte.alias)
            for categoria in CATEGORIAS: dia["categorias"][categoria] += item["categorias"][categoria]
            for campo in ("codigos_nao_classificados", "codigos_nao_homologados"):
                dia[campo] = sorted(set(dia[campo]).union(item.get(campo, [])))
            if item["status_fechamento"] == "aberto": dia["status_fechamento"] = "aberto"
            elif item["status_fechamento"] == "sem_fechamento" and dia["status_fechamento"] != "aberto": dia["status_fechamento"] = "sem_fechamento"
            elif item["status_fechamento"] == "fechado" and dia["status_fechamento"] == "sem_movimento": dia["status_fechamento"] = "fechado"
    unidades_incompletas = {falha.get("unidade") for falha in resultado["falhas"]}
    falha_geral = None in unidades_incompletas
    dias = sorted(consolidado.values(), key=lambda item: (item["data"], item["unidade"]))
    for dia in dias:
        dia["status_consulta"] = "parcial" if falha_geral or dia["unidade"] in unidades_incompletas else "completo"
    categorias = {categoria: sum(item["categorias"][categoria] for item in dias) for categoria in CATEGORIAS}
    formas: dict[str, int] = {}
    for fonte in fontes:
        for nome, valor in fonte.formas_pagamento.items(): formas[nome] = formas.get(nome, 0) + valor
    status = "parcial" if resultado["falhas"] and fontes else ("indisponivel" if resultado["falhas"] else "completo")
    return {
        "mes": mes.strftime("%Y-%m"),
        "unidades_consultadas": list(dict.fromkeys(f.unidade for f in fontes)),
        "status": status,
        "resumo": {
            "total_centavos": sum(item["total_centavos"] for item in dias) if fontes else None,
            "categorias": categorias if fontes else {categoria: None for categoria in CATEGORIAS},
            "manutencoes_recebidas": sum(item["manutencoes_recebidas"] for item in dias) if fontes else None,
            "contratos_vendidos": None,
            "vidas_vendidas": None,
            "ortos_vendidos": None,
            "media_diaria": None,
            "projecao": None,
        },
        "dias": dias,
        "formas_pagamento": [{"nome": nome, "total_centavos": valor} for nome, valor in sorted(formas.items())],
        "falhas": resultado["falhas"],
        "atualizado_em": resultado.get("atualizado_em"),
    }

@router.get("/caixa-firebird")
def consultar_caixa_firebird(response: Response, mes: str = Query(...), unidade: str | None = Query(None), usuario: dict = Depends(get_current_user)):
    if not re.fullmatch(r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])", mes):
        raise HTTPException(422, "Mês deve usar YYYY-MM")
    try:
        mes_data = datetime.strptime(mes, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise HTTPException(422, "Mês deve usar YYYY-MM") from exc
    unidades = _autorizadas(usuario, unidade)
    resultado = CaixaFirebirdService().consultar_mes(mes=mes_data, unidades=unidades)
    # Defesa adicional para que mocks/configuracoes incorretas nao exponham outra unidade.
    resultado["fontes"] = [fonte for fonte in resultado["fontes"] if fonte.unidade in unidades]
    resultado["falhas"] = [falha for falha in resultado["falhas"] if not falha.get("unidade") or falha["unidade"] in unidades]
    response.headers["Cache-Control"] = "no-store"
    return _resposta(mes_data, resultado)
