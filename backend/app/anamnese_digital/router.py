# app/anamnese_digital/router.py

import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import StreamingResponse
import io

from app.middleware.auth_middleware import get_current_user
from app.database.db import DatabaseConnection
from app.services.meta_whatsapp_official_service import resolve_sender_unit
from app.services.whatsapp_document_audit_service import (
    AUTOMATIC_ORIGIN,
    MANUAL_ORIGIN,
)
from .models import (
    AnamneseCreate, AnamneseUpdate, AnamneseResponse,
    AssinaturaCreate, TokenCreate, TokenResponse,
    LinkEnvio, LinkStatus, AnamneseStatus,
    AnamneseConsultaDetalhe, AnamneseConsultaItem,
    AnamneseConsultaResponse, AnamneseConsultaResumo
)
from .service import AnamneseService
from .token_service import TokenService
from .notification_service import NotificationService
from .pdf_generator import AnamnesePDFGenerator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/anamnese-digital", tags=["anamnese"])

TODAS_UNIDADES = {"todas unidades", "todas as unidades"}

BASE_FROM_CONSULTA = """
    FROM anamneses_digitais a
    INNER JOIN pacientes p ON p.paciente_id = a.paciente_id
    LEFT JOIN dependentes d ON d.dependente_id = a.dependente_id
"""

VENDEDOR_JOIN = """
    LEFT JOIN LATERAL (
        SELECT u.nome
        FROM vendas v
        INNER JOIN users u ON u.id = v.usuario_venda_id
        WHERE v.paciente_id = a.paciente_id
          AND (
              (a.dependente_id IS NULL AND v.dependente_id IS NULL)
              OR v.dependente_id = a.dependente_id
          )
          AND COALESCE(v.status_venda, '') <> 'Cancelada'
        ORDER BY
            ABS(EXTRACT(EPOCH FROM (
                COALESCE(v.data_venda, v.created_at)
                - COALESCE(a.signed_at, a.updated_at, a.created_at)
            ))) ASC,
            v.id DESC
        LIMIT 1
    ) venda_responsavel ON TRUE
"""


def _obter_unidade_restrita(current_user: Optional[Dict[str, Any]]) -> Optional[str]:
    unidade = ((current_user or {}).get("unidade") or "").strip()
    if not unidade:
        raise HTTPException(status_code=403, detail="Usuário sem unidade vinculada")
    if unidade.lower() in TODAS_UNIDADES:
        return None
    return unidade


def _mascarar_documento(documento: Optional[str]) -> str:
    digitos = "".join(char for char in (documento or "") if char.isdigit())
    if len(digitos) == 11:
        return f"***.***.{digitos[-5:-2]}-{digitos[-2:]}"
    if len(digitos) == 14:
        return f"**.***.***/****-{digitos[-2:]}"
    return "Não informado"


def _valor_cadastral(preferido: Any, fallback: Any = None) -> Any:
    if preferido is None:
        return fallback
    if isinstance(preferido, str) and not preferido.strip():
        return fallback
    return preferido


def _formatar_data_cadastral(valor: Any) -> Any:
    return valor.isoformat() if hasattr(valor, "isoformat") else valor


def _mesclar_dados_identificacao(
    dados_anamnese: Dict[str, Any],
    dados_cadastrais: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    informado = dict((dados_anamnese or {}).get("dados_identificacao") or {})
    cadastro_titular = dados_cadastrais.get("titular") or {}
    cadastro_dependente = dados_cadastrais.get("dependente") or None

    telefone_partes = [
        f"+{cadastro_titular.get('telefone_pais')}" if cadastro_titular.get("telefone_pais") else "",
        f"({cadastro_titular.get('telefone_ddd')})" if cadastro_titular.get("telefone_ddd") else "",
        str(cadastro_titular.get("telefone_numero") or "").strip(),
    ]
    telefone_cadastro = " ".join(parte for parte in telefone_partes if parte)
    endereco_partes = [
        str(cadastro_titular.get("logradouro") or "").strip(),
        str(cadastro_titular.get("numero") or "").strip(),
    ]
    endereco_cadastro = ", ".join(parte for parte in endereco_partes if parte)

    titular = dict(informado)
    titular.update({
        "nome": _valor_cadastral(cadastro_titular.get("nome"), informado.get("nome")),
        "cpf": _valor_cadastral(cadastro_titular.get("cpf"), informado.get("cpf")),
        "rg": _valor_cadastral(cadastro_titular.get("rg"), informado.get("rg")),
        "nascimento": _formatar_data_cadastral(
            _valor_cadastral(cadastro_titular.get("data_nascimento"), informado.get("nascimento"))
        ),
        "genero": _valor_cadastral(cadastro_titular.get("genero"), informado.get("genero")),
        "email": _valor_cadastral(cadastro_titular.get("email"), informado.get("email")),
        "celular": _valor_cadastral(telefone_cadastro, informado.get("celular")),
        "endereco": _valor_cadastral(endereco_cadastro, informado.get("endereco")),
        "numero": _valor_cadastral(cadastro_titular.get("numero"), informado.get("numero")),
        "complemento": _valor_cadastral(cadastro_titular.get("complemento"), informado.get("complemento")),
        "bairro": _valor_cadastral(cadastro_titular.get("bairro"), informado.get("bairro")),
        "cidade": _valor_cadastral(cadastro_titular.get("cidade"), informado.get("cidade")),
        "estado": _valor_cadastral(cadastro_titular.get("estado"), informado.get("estado")),
        "cep": _valor_cadastral(cadastro_titular.get("cep"), informado.get("cep")),
        "como_conheceu": _valor_cadastral(
            cadastro_titular.get("midia_origem"), informado.get("como_conheceu")
        ),
        "unidade": cadastro_titular.get("unidade"),
    })

    if cadastro_dependente:
        beneficiario = dict(informado)
        beneficiario.update({
            "nome": _valor_cadastral(cadastro_dependente.get("nome"), informado.get("nome")),
            "nascimento": _formatar_data_cadastral(
                _valor_cadastral(cadastro_dependente.get("data_nascimento"), informado.get("nascimento"))
            ),
            "genero": _valor_cadastral(cadastro_dependente.get("genero"), informado.get("genero")),
            "parentesco": _valor_cadastral(cadastro_dependente.get("parentesco"), informado.get("parentesco")),
            "observacoes_cadastrais": cadastro_dependente.get("observacoes"),
        })
    else:
        beneficiario = dict(titular)

    return {"titular": titular, "beneficiario": beneficiario}


def _montar_filtros_consulta(
    current_user: Dict[str, Any],
    busca: Optional[str],
    status: Optional[AnamneseStatus],
    tipo_beneficiario: Optional[str],
    unidade: Optional[str],
    data_inicio: Optional[date],
    data_fim: Optional[date],
):
    filtros = []
    parametros: List[Any] = []
    unidade_restrita = _obter_unidade_restrita(current_user)

    if unidade_restrita:
        filtros.append("p.unidade = %s")
        parametros.append(unidade_restrita)
    elif unidade and unidade.strip():
        filtros.append("p.unidade = %s")
        parametros.append(unidade.strip())

    if busca and busca.strip():
        termo = busca.strip()
        termo_documento = "".join(char for char in termo if char.isdigit())
        filtros_busca = [
            "p.nome_paciente ILIKE %s",
            "COALESCE(d.nome_dependente, '') ILIKE %s",
        ]
        parametros.extend([f"%{termo}%", f"%{termo}%"])
        if termo_documento:
            filtros_busca.append(
                "regexp_replace(COALESCE(p.cpf_cnpj, ''), '[^0-9]', '', 'g') LIKE %s"
            )
            parametros.append(f"%{termo_documento}%")
        filtros.append(f"({' OR '.join(filtros_busca)})")

    if status:
        filtros.append("a.status = %s")
        parametros.append(status.value)

    if tipo_beneficiario:
        tipo_normalizado = tipo_beneficiario.strip().lower()
        if tipo_normalizado not in {"titular", "dependente"}:
            raise HTTPException(status_code=400, detail="Tipo de beneficiário inválido")
        filtros.append(
            "a.dependente_id IS NULL"
            if tipo_normalizado == "titular"
            else "a.dependente_id IS NOT NULL"
        )

    data_referencia = "COALESCE(a.signed_at, a.updated_at, a.created_at)::date"
    if data_inicio:
        filtros.append(f"{data_referencia} >= %s")
        parametros.append(data_inicio)
    if data_fim:
        filtros.append(f"{data_referencia} <= %s")
        parametros.append(data_fim)

    where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    return where_clause, parametros


@router.get("/consulta", response_model=AnamneseConsultaResponse)
async def listar_anamneses_consulta(
    busca: Optional[str] = Query(None, max_length=120),
    status: Optional[AnamneseStatus] = Query(None),
    tipo_beneficiario: Optional[str] = Query(None),
    unidade: Optional[str] = Query(None, max_length=100),
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Lista anamneses para consulta interna, respeitando a unidade do usuário."""
    if data_inicio and data_fim and data_inicio > data_fim:
        raise HTTPException(status_code=400, detail="A data inicial não pode ser posterior à data final")

    try:
        where_clause, parametros = _montar_filtros_consulta(
            current_user,
            busca,
            status,
            tipo_beneficiario,
            unidade,
            data_inicio,
            data_fim,
        )
        with DatabaseConnection() as conn:
            conn.set_session(readonly=True)
            cursor = conn.cursor()

            cursor.execute(
                f"""
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE a.status = 'rascunho') AS rascunhos,
                        COUNT(*) FILTER (WHERE a.status = 'aguardando_assinatura') AS aguardando_assinatura,
                        COUNT(*) FILTER (WHERE a.status = 'assinado') AS assinadas,
                        COUNT(*) FILTER (WHERE a.status = 'expirado') AS expiradas
                    {BASE_FROM_CONSULTA}
                    {where_clause}
                """,
                parametros,
            )
            total, rascunhos, aguardando, assinadas, expiradas = cursor.fetchone()

            offset = (page - 1) * per_page
            cursor.execute(
                f"""
                    SELECT
                        a.id,
                        a.paciente_id,
                        a.dependente_id,
                        COALESCE(d.nome_dependente, p.nome_paciente) AS beneficiario_nome,
                        p.nome_paciente AS titular_nome,
                        CASE WHEN a.dependente_id IS NULL THEN 'titular' ELSE 'dependente' END,
                        d.parentesco,
                        p.cpf_cnpj,
                        p.unidade,
                        a.status,
                        COALESCE(a.signed_at, a.updated_at, a.created_at) AS preenchida_em,
                        a.signed_at,
                        a.validade_ate,
                        venda_responsavel.nome AS vendedor_nome
                    {BASE_FROM_CONSULTA}
                    {VENDEDOR_JOIN}
                    {where_clause}
                    ORDER BY COALESCE(a.signed_at, a.updated_at, a.created_at) DESC, a.id DESC
                    LIMIT %s OFFSET %s
                """,
                [*parametros, per_page, offset],
            )

            itens = [
                AnamneseConsultaItem(
                    id=row[0],
                    paciente_id=row[1],
                    dependente_id=row[2],
                    beneficiario_nome=row[3],
                    titular_nome=row[4],
                    tipo_beneficiario=row[5],
                    parentesco=row[6],
                    cpf_mascarado=_mascarar_documento(row[7]),
                    unidade=row[8],
                    status=row[9],
                    preenchida_em=row[10],
                    signed_at=row[11],
                    validade_ate=row[12],
                    vendedor_nome=row[13],
                )
                for row in cursor.fetchall()
            ]

        return AnamneseConsultaResponse(
            total=total,
            page=page,
            per_page=per_page,
            resumo=AnamneseConsultaResumo(
                total=total,
                rascunhos=rascunhos,
                aguardando_assinatura=aguardando,
                assinadas=assinadas,
                expiradas=expiradas,
            ),
            anamneses=itens,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro ao listar anamneses para consulta: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar anamneses")


@router.get("/consulta/{anamnese_id}", response_model=AnamneseConsultaDetalhe)
async def obter_anamnese_consulta(
    anamnese_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Obtém o detalhe de uma anamnese dentro da unidade permitida."""
    unidade_restrita = _obter_unidade_restrita(current_user)
    filtros = ["a.id = %s"]
    parametros: List[Any] = [anamnese_id]
    if unidade_restrita:
        filtros.append("p.unidade = %s")
        parametros.append(unidade_restrita)

    try:
        with DatabaseConnection() as conn:
            conn.set_session(readonly=True)
            cursor = conn.cursor()
            cursor.execute(
                f"""
                    SELECT
                        a.id,
                        a.paciente_id,
                        a.dependente_id,
                        COALESCE(d.nome_dependente, p.nome_paciente) AS beneficiario_nome,
                        p.nome_paciente AS titular_nome,
                        CASE WHEN a.dependente_id IS NULL THEN 'titular' ELSE 'dependente' END,
                        d.parentesco,
                        p.cpf_cnpj,
                        p.unidade,
                        a.status,
                        COALESCE(a.signed_at, a.updated_at, a.created_at) AS preenchida_em,
                        a.signed_at,
                        a.validade_ate,
                        a.dados_anamnese,
                        a.observacoes_profissional,
                        a.created_at,
                        a.updated_at,
                        p.email,
                        p.data_nascimento,
                        p.phone_country_code,
                        p.phone_area_code,
                        p.phone_number,
                        p.street,
                        p.street_number,
                        (to_jsonb(p) ->> 'line_two') AS line_two,
                        p.neighborhood,
                        p.city,
                        p.state,
                        p.zip_code,
                        p.rg_ie,
                        p.genero,
                        p.midia_origem,
                        d.data_nascimento_dependente,
                        d.genero_dependente,
                        d.observacoes_dependente,
                        venda_responsavel.nome AS vendedor_nome
                    {BASE_FROM_CONSULTA}
                    {VENDEDOR_JOIN}
                    WHERE {' AND '.join(filtros)}
                """,
                parametros,
            )
            row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Anamnese não encontrada")

        dados_cadastrais = {
            "titular": {
                "nome": row[4],
                "cpf": row[7],
                "rg": row[29],
                "email": row[17],
                "data_nascimento": row[18],
                "genero": row[30],
                "telefone_pais": row[19],
                "telefone_ddd": row[20],
                "telefone_numero": row[21],
                "logradouro": row[22],
                "numero": row[23],
                "complemento": row[24],
                "bairro": row[25],
                "cidade": row[26],
                "estado": row[27],
                "cep": row[28],
                "midia_origem": row[31],
                "unidade": row[8],
            },
            "dependente": {
                "nome": row[3],
                "data_nascimento": row[32],
                "genero": row[33],
                "parentesco": row[6],
                "observacoes": row[34],
            } if row[2] is not None else None,
        }
        identificacao_mesclada = _mesclar_dados_identificacao(row[13], dados_cadastrais)

        return AnamneseConsultaDetalhe(
            id=row[0],
            paciente_id=row[1],
            dependente_id=row[2],
            beneficiario_nome=row[3],
            titular_nome=row[4],
            tipo_beneficiario=row[5],
            parentesco=row[6],
            cpf_mascarado=_mascarar_documento(row[7]),
            unidade=row[8],
            status=row[9],
            preenchida_em=row[10],
            signed_at=row[11],
            validade_ate=row[12],
            vendedor_nome=row[35],
            dados_anamnese=row[13],
            dados_cadastrais=dados_cadastrais,
            dados_identificacao_mesclados=identificacao_mesclada,
            observacoes=row[14],
            created_at=row[15],
            updated_at=row[16],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro ao obter anamnese para consulta: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar anamnese")


@router.get("/verificar/{paciente_id}")
async def verificar_anamnese_valida(
    paciente_id: int,
    dependente_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Verifica se o paciente/dependente possui anamnese válida"""
    try:
        result = AnamneseService.verificar_anamnese_valida(paciente_id, dependente_id)
        return result
    except Exception as e:
        logger.error(f"Erro ao verificar anamnese: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/criar", response_model=Dict[str, Any])
async def criar_anamnese(
    data: AnamneseCreate,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Cria uma nova anamnese"""
    try:
        # Capturar IP e user agent
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        result = AnamneseService.criar_anamnese(
            data,
            user_id=current_user.get("user_id")
        )
        
        # Atualizar com IP e user agent
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE anamneses_digitais SET ip_address = %s, user_agent = %s WHERE id = %s",
                (client_ip, user_agent, result["id"])
            )
            conn.commit()
        
        return result
        
    except Exception as e:
        logger.error(f"Erro ao criar anamnese: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/paciente/{paciente_id}/atual")
async def obter_anamnese_atual_paciente(
    paciente_id: int,
    dependente_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Obtém a anamnese atual do paciente/dependente"""
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Buscar a anamnese mais recente assinada ou em aguardando assinatura
            if dependente_id is None:
                query = """
                    SELECT 
                        id, paciente_id, dependente_id, status, dados_anamnese,
                        observacoes_profissional, created_at, updated_at,
                        signed_at, validade_ate, created_by
                    FROM anamneses_digitais
                    WHERE paciente_id = %s 
                    AND dependente_id IS NULL
                    AND status IN ('assinado', 'aguardando_assinatura')
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                cursor.execute(query, (paciente_id,))
            else:
                query = """
                    SELECT 
                        id, paciente_id, dependente_id, status, dados_anamnese,
                        observacoes_profissional, created_at, updated_at,
                        signed_at, validade_ate, created_by
                    FROM anamneses_digitais
                    WHERE paciente_id = %s 
                    AND dependente_id = %s
                    AND status IN ('assinado', 'aguardando_assinatura')
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                cursor.execute(query, (paciente_id, dependente_id))
            
            result = cursor.fetchone()
            
            if not result:
                # Se não encontrar assinada, buscar rascunho mais recente
                if dependente_id is None:
                    query_rascunho = """
                        SELECT 
                            id, paciente_id, dependente_id, status, dados_anamnese,
                            observacoes_profissional, created_at, updated_at,
                            signed_at, validade_ate, created_by
                        FROM anamneses_digitais
                        WHERE paciente_id = %s 
                        AND dependente_id IS NULL
                        AND status = 'rascunho'
                        ORDER BY created_at DESC
                        LIMIT 1
                    """
                    cursor.execute(query_rascunho, (paciente_id,))
                else:
                    query_rascunho = """
                        SELECT 
                            id, paciente_id, dependente_id, status, dados_anamnese,
                            observacoes_profissional, created_at, updated_at,
                            signed_at, validade_ate, created_by
                        FROM anamneses_digitais
                        WHERE paciente_id = %s 
                        AND dependente_id = %s
                        AND status = 'rascunho'
                        ORDER BY created_at DESC
                        LIMIT 1
                    """
                    cursor.execute(query_rascunho, (paciente_id, dependente_id))
                result = cursor.fetchone()
                
                if not result:
                    raise HTTPException(status_code=404, detail="Paciente não possui anamnese")
            
            (id_, paciente_id, dep_id, status, dados_anamnese, observacoes,
             created_at, updated_at, signed_at, validade_ate, created_by) = result
            
            return {
                "id": id_,
                "paciente_id": paciente_id,
                "dependente_id": dep_id,
                "status": status,
                "dados_anamnese": dados_anamnese,
                "observacoes_profissional": observacoes,
                "created_at": created_at.isoformat() if created_at else None,
                "updated_at": updated_at.isoformat() if updated_at else None,
                "signed_at": signed_at.isoformat() if signed_at else None,
                "validade_ate": validade_ate.isoformat() if validade_ate else None,
                "created_by": created_by
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter anamnese atual do paciente: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{anamnese_id}")
async def obter_anamnese(
    anamnese_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Obtém uma anamnese específica"""
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    id, paciente_id, dependente_id, status, dados_anamnese,
                    observacoes_profissional, created_at, updated_at,
                    signed_at, validade_ate, created_by
                FROM anamneses_digitais
                WHERE id = %s
            """
            
            cursor.execute(query, (anamnese_id,))
            result = cursor.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Anamnese não encontrada")
            
            (id_, paciente_id, dep_id, status, dados_anamnese, observacoes,
             created_at, updated_at, signed_at, validade_ate, created_by) = result
            
            return {
                "id": id_,
                "paciente_id": paciente_id,
                "dependente_id": dep_id,
                "status": status,
                "dados_anamnese": dados_anamnese,
                "observacoes": observacoes,
                "created_at": created_at,
                "updated_at": updated_at,
                "signed_at": signed_at,
                "validade_ate": validade_ate,
                "created_by": created_by
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter anamnese: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{anamnese_id}")
async def atualizar_anamnese(
    anamnese_id: int,
    data: AnamneseUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Atualiza uma anamnese em rascunho"""
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Verificar se pode editar
            cursor.execute(
                "SELECT status FROM anamneses_digitais WHERE id = %s",
                (anamnese_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Anamnese não encontrada")
            
            if result[0] != "rascunho":
                raise HTTPException(
                    status_code=400,
                    detail="Apenas anamneses em rascunho podem ser editadas"
                )
            
            # Preparar dados para atualização
            updates = []
            values = []
            
            if data.dados_identificacao:
                updates.append("dados_anamnese = jsonb_set(dados_anamnese, '{dados_identificacao}', %s)")
                values.append(data.dados_identificacao.model_dump_json())
            
            if data.saude_geral:
                updates.append("dados_anamnese = jsonb_set(dados_anamnese, '{saude_geral}', %s)")
                values.append(data.saude_geral.model_dump_json())
            
            if data.saude_bucal:
                updates.append("dados_anamnese = jsonb_set(dados_anamnese, '{saude_bucal}', %s)")
                values.append(data.saude_bucal.model_dump_json())
            
            if data.observacoes is not None:
                updates.append("observacoes_profissional = %s")
                values.append(data.observacoes)
            
            updates.append("updated_at = NOW()")
            values.append(anamnese_id)
            
            update_query = f"""
                UPDATE anamneses_digitais
                SET {', '.join(updates)}
                WHERE id = %s
            """
            
            cursor.execute(update_query, values)
            conn.commit()
            
            return {"success": True, "message": "Anamnese atualizada com sucesso"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar anamnese: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{anamnese_id}/assinar")
async def assinar_anamnese(
    anamnese_id: int,
    assinatura: AssinaturaCreate,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Registra assinatura digital da anamnese"""
    try:
        # Adicionar IP e user agent
        assinatura_data = assinatura.model_dump()
        assinatura_data["ip_address"] = request.client.host
        assinatura_data["user_agent"] = request.headers.get("user-agent", "")
        
        success = AnamneseService.assinar_anamnese(anamnese_id, assinatura_data)
        
        if success:
            return {"success": True, "message": "Anamnese assinada com sucesso"}
        else:
            raise HTTPException(status_code=500, detail="Erro ao assinar anamnese")
            
    except Exception as e:
        logger.error(f"Erro ao assinar anamnese: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/gerar-link/{paciente_id}", response_model=TokenResponse)
async def gerar_link_anamnese(
    paciente_id: int,
    data: TokenCreate,
    current_user: dict = Depends(get_current_user)
):
    """Gera link público para preenchimento da anamnese"""
    try:
        result = AnamneseService.gerar_link_anamnese(
            paciente_id,
            data.dependente_id,
            data.validade_horas
        )
        
        return TokenResponse(
            token=result["token"],
            link_publico=result["link_publico"],
            expires_at=result["expires_at"]
        )
        
    except Exception as e:
        logger.error(f"Erro ao gerar link: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gerar-e-enviar/{paciente_id}")
async def gerar_e_enviar_link_anamnese(
    paciente_id: int,
    data: TokenCreate,
    current_user: dict = Depends(get_current_user),
):
    """Gera ou reutiliza o link e realiza uma única tentativa automática."""
    try:
        sender_unit = resolve_sender_unit(
            current_user.get("role"),
            current_user.get("unidade"),
        )
        if not sender_unit:
            raise HTTPException(
                status_code=400,
                detail="Não foi possível identificar o WhatsApp da unidade",
            )

        token_result = AnamneseService.gerar_link_anamnese(
            paciente_id,
            data.dependente_id,
            data.validade_horas,
        )
        delivery = await NotificationService().enviar_link(
            LinkEnvio(
                token=token_result["token"],
                meio_envio="whatsapp",
                destinatario="",
                unidade=sender_unit,
            ),
            origin=AUTOMATIC_ORIGIN,
            requested_by=current_user.get("user_id"),
        )
        return {
            "token": token_result["token"],
            "link_publico": token_result["link_publico"],
            "expires_at": token_result["expires_at"],
            "whatsapp_sent": delivery["success"],
            "whatsapp_status": delivery["delivery_status"],
            "whatsapp_message": (
                "Link enviado automaticamente pelo WhatsApp da unidade"
                if delivery["success"]
                else delivery.get("error")
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Erro ao gerar e enviar anamnese automaticamente (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Não foi possível preparar o envio automático da anamnese",
        )

@router.post("/enviar-link")
async def enviar_link_anamnese(
    data: LinkEnvio,
    current_user: dict = Depends(get_current_user)
):
    """Envia o link da anamnese pelo WhatsApp oficial da unidade."""
    try:
        sender_unit = resolve_sender_unit(
            current_user.get("role"),
            current_user.get("unidade"),
        )
        if not sender_unit:
            raise HTTPException(
                status_code=400,
                detail="Não foi possível identificar o WhatsApp da unidade",
            )

        data.unidade = sender_unit
        logger.info(f"Enviando link via {data.meio_envio} pela unidade: {data.unidade}")
        
        notification_service = NotificationService()
        result = await notification_service.enviar_link(
            data,
            origin=MANUAL_ORIGIN,
            requested_by=current_user.get("user_id"),
        )
        
        if result["success"]:
            return {"success": True, "message": f"Link enviado via {data.meio_envio}"}
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao enviar link de anamnese (%s)", type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível enviar o link da anamnese",
        )

@router.get("/status-link/{token}")
async def obter_status_link(
    token: str,
    current_user: dict = Depends(get_current_user)
):
    """Obtém status do link enviado"""
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    t.token,
                    t.paciente_id,
                    t.created_at,
                    t.expires_at,
                    t.used,
                    t.used_at,
                    e.meio_envio,
                    e.visualizado_em,
                    e.preenchido_em
                FROM anamnese_tokens t
                LEFT JOIN anamnese_envios e ON e.token_id = t.id
                WHERE t.token = %s
                ORDER BY e.id DESC
                LIMIT 1
            """
            
            cursor.execute(query, (token,))
            result = cursor.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Token não encontrado")
            
            (token, paciente_id, created_at, expires_at, used, used_at,
             meio_envio, visualizado_em, preenchido_em) = result
            
            # Determinar status
            if used:
                status = "preenchido"
            elif visualizado_em:
                status = "visualizado"
            elif meio_envio:
                status = "enviado"
            else:
                status = "gerado"
            
            return LinkStatus(
                token=token,
                paciente_id=paciente_id,
                status=status,
                created_at=created_at,
                expires_at=expires_at,
                usado=used,
                usado_em=used_at,
                enviado_via=meio_envio,
                visualizado_em=visualizado_em,
                preenchido_em=preenchido_em
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter status do link: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{anamnese_id}/pdf")
async def gerar_pdf_anamnese(
    anamnese_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Gera PDF de uma anamnese concluída dentro da unidade permitida."""
    try:
        detalhe = await obter_anamnese_consulta(anamnese_id, current_user)
        if detalhe.status not in {AnamneseStatus.ASSINADO, AnamneseStatus.EXPIRADO}:
            raise HTTPException(
                status_code=400,
                detail="Apenas anamneses assinadas ou expiradas podem ser impressas"
            )

        anamnese = detalhe.model_dump()
        identificacao_titular = detalhe.dados_identificacao_mesclados.get("titular") or {}
        identificacao_beneficiario = (
            detalhe.dados_identificacao_mesclados.get("beneficiario") or {}
        )
        dados_anamnese = dict(detalhe.dados_anamnese)
        dados_anamnese["dados_identificacao"] = identificacao_beneficiario
        anamnese["dados_anamnese"] = dados_anamnese
        anamnese["dados_titular"] = identificacao_titular
        anamnese["paciente_nome"] = identificacao_titular.get("nome") or detalhe.titular_nome
        anamnese["paciente_cpf"] = identificacao_titular.get("cpf") or ""
        if detalhe.dependente_id:
            anamnese["dependente_nome"] = (
                identificacao_beneficiario.get("nome") or detalhe.beneficiario_nome
            )
            anamnese["dependente_parentesco"] = (
                identificacao_beneficiario.get("parentesco") or detalhe.parentesco or ""
            )
            
        pdf_generator = AnamnesePDFGenerator()
        pdf_buffer = pdf_generator.generate(anamnese)
        
        # Retornar como stream
        return StreamingResponse(
            io.BytesIO(pdf_buffer),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=anamnese_{anamnese_id}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/paciente/{paciente_id}/historico")
async def listar_anamneses_paciente(
    paciente_id: int,
    dependente_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Lista histórico de anamneses do paciente/dependente"""
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            if dependente_id is None:
                query = """
                    SELECT 
                        id, status, created_at, signed_at, validade_ate,
                        created_by, dependente_id
                    FROM anamneses_digitais
                    WHERE paciente_id = %s AND dependente_id IS NULL
                    ORDER BY created_at DESC
                """
                cursor.execute(query, (paciente_id,))
            else:
                query = """
                    SELECT 
                        id, status, created_at, signed_at, validade_ate,
                        created_by, dependente_id
                    FROM anamneses_digitais
                    WHERE paciente_id = %s AND dependente_id = %s
                    ORDER BY created_at DESC
                """
                cursor.execute(query, (paciente_id, dependente_id))
            
            results = cursor.fetchall()
            
            anamneses = []
            for row in results:
                id_, status, created_at, signed_at, validade_ate, created_by, dep_id = row
                
                anamneses.append({
                    "id": id_,
                    "status": status,
                    "created_at": created_at,
                    "signed_at": signed_at,
                    "validade_ate": validade_ate,
                    "created_by": created_by,
                    "dependente_id": dep_id,
                    "valida": validade_ate > datetime.now() if validade_ate else False
                })
            
            return {"anamneses": anamneses, "total": len(anamneses)}
            
    except Exception as e:
        logger.error(f"Erro ao listar anamneses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
