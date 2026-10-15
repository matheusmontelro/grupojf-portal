# app/routers/pacientes.py

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Response, Query, Request # Adicionado Response
from datetime import datetime, date # Adicionado datetime
import psycopg2 # Adicionado psycopg2

# Importar a classe de conexão e Schemas Pydantic
from app.database.db import DatabaseConnection # Ajuste o caminho
from app.models.pacientes import ( # Importa de app/models/
    PacienteCreate,
    PacienteRead,
    # PacienteUpdate - Seria ideal ter um schema específico para Update com campos opcionais
)
from app.services.patient_integration_config import (
    GLOBAL_UNIT_ALIASES,
    PatientIntegrationConfigError,
    canonicalize_patient_unit,
    patient_unit_storage_values,
    resolve_patient_unit,
)
from app.services.patient_integration_service import (
    PatientIntegrationDataError,
    PatientIntegrationIdentityPendingError,
    enqueue_patient_jobs_for_patient,
    ensure_remote_identities_before_document_change,
)
# Importar User e dependência de autenticação, se aplicável
# from app.models.user import User
# from app.dependencies import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pacientes", tags=["pacientes"])


def _resolve_request_unit(request: Request, requested_unit: Optional[str]) -> str:
    current_user = getattr(request.state, "user", {})
    try:
        return resolve_patient_unit(current_user.get("unidade"), requested_unit)
    except PatientIntegrationConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


def _resolve_read_unit_scope(
    request: Request,
    requested_unit: Optional[str] = None,
) -> Optional[str]:
    current_user = getattr(request.state, "user", {})
    authenticated_unit = current_user.get("unidade")
    canonical = canonicalize_patient_unit(authenticated_unit)
    if canonical:
        return canonical
    if str(authenticated_unit or "").strip().casefold() in GLOBAL_UNIT_ALIASES:
        if requested_unit is None:
            return None
        try:
            return resolve_patient_unit(authenticated_unit, requested_unit)
        except PatientIntegrationConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
    raise HTTPException(status_code=403, detail="Unidade do usuário inválida.")


def _ensure_patient_unit_access(stored_unit: Optional[str], unidade: str) -> None:
    if canonicalize_patient_unit(stored_unit) != unidade:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")

# --- Constante de Colunas (Atualizada) ---
# Define a ordem exata para SELECT e RETURNING, facilitando o mapeamento
PACIENTE_COLS = """
    paciente_id, nome_paciente, cpf_cnpj, email, data_nascimento,
    is_minor, responsavel_id, phone_country_code, phone_area_code,
    phone_number, street, street_number, line_two, neighborhood, city, state,
    zip_code, created_at, updated_at, unidade,
    rg_ie, genero, observacoes, midia_origem
"""

# --- Helper de Mapeamento (Atualizado) ---
def _map_row_to_paciente_read(row) -> Optional[PacienteRead]:
    """ Mapeia uma linha do cursor (tupla) para o schema PacienteRead. """
    if not row:
        return None
    # Índices baseados na ordem em PACIENTE_COLS
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
        line_two=row[12],
        neighborhood=row[13],
        city=row[14],
        state=row[15],
        zip_code=row[16],
        created_at=row[17],
        updated_at=row[18],
        unidade=row[19],
        # Novos campos
        rg_ie=row[20],
        genero=row[21],
        observacoes=row[22],
        midia_origem=row[23],
    )

# --- Endpoints (Atualizados) ---

@router.post("", response_model=PacienteRead, status_code=status.HTTP_201_CREATED)
def criar_paciente(data: PacienteCreate, request: Request):
    """ Cria um novo paciente, incluindo os novos campos. """
    logger.info("Criando paciente")
    unidade = _resolve_request_unit(request, data.unidade)

    # Validação extra (ex: CPF/CNPJ único)
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT paciente_id FROM pacientes WHERE cpf_cnpj = %s", (data.cpf_cnpj,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="CPF/CNPJ já cadastrado.")

        # Query INSERT atualizada
        query = f"""
            INSERT INTO pacientes (
                nome_paciente, cpf_cnpj, email, data_nascimento, is_minor,
                responsavel_id, phone_country_code, phone_area_code, phone_number,
                street, street_number, line_two, neighborhood, city, state, zip_code,
                unidade, rg_ie, genero, observacoes, midia_origem
                -- created_at e updated_at usam default do DB
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            RETURNING {PACIENTE_COLS};
        """
        values = (
            data.nome_paciente, data.cpf_cnpj, data.email, data.data_nascimento, data.is_minor,
            data.responsavel_id, data.phone_country_code, data.phone_area_code, data.phone_number,
            data.street, data.street_number, data.line_two, data.neighborhood, data.city, data.state, data.zip_code,
            unidade, data.rg_ie, data.genero, data.observacoes, data.midia_origem # Novos valores
        )
        try:
            cursor.execute(query, values)
            row = cursor.fetchone()
            if not row: raise HTTPException(status_code=500, detail="Falha ao criar paciente.")
            enqueue_patient_jobs_for_patient(
                cursor,
                paciente_id=row[0],
                unidade=unidade,
                patient_version=row[18],
                allow_delta_customer_creation=True,
                allow_asaas_customer_creation=True,
            )
            conn.commit()
            logger.info(f"Paciente ID {row[0]} criado.")
            return _map_row_to_paciente_read(row)
        except psycopg2.Error as db_err: # Agora psycopg2 está definido
            logger.error(
                "Erro DB ao criar paciente. error_type=%s",
                type(db_err).__name__,
            )
            conn.rollback()
            raise HTTPException(status_code=500, detail="Erro de banco de dados.")
        except PatientIntegrationConfigError:
            conn.rollback()
            logger.error("Configuracao de integracao de pacientes invalida")
            raise HTTPException(
                status_code=503,
                detail="Integracao de pacientes temporariamente indisponivel.",
            ) from None
        except PatientIntegrationDataError:
            conn.rollback()
            raise HTTPException(
                status_code=400,
                detail="Dados do paciente inválidos para integração.",
            ) from None
        except Exception as e:
            logger.error(
                "Erro inesperado ao criar paciente. error_type=%s",
                type(e).__name__,
            )
            conn.rollback()
            raise HTTPException(status_code=500, detail="Erro interno inesperado.")


@router.get("", response_model=List[PacienteRead])
def listar_pacientes(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    nome: Optional[str] = None,
    cpf_cnpj: Optional[str] = None,
    # Adicionar parâmetro para busca por prefixo de CPF
    cpf_startsWith: Optional[str] = Query(None, description="Busca pacientes cujo CPF/CNPJ começa com este valor (apenas dígitos)."),
    unidade: Optional[str] = Query(None),
):
    """ Lista pacientes com paginação e filtros. Inclui busca por prefixo de CPF. """
    logger.info("Listando pacientes: skip=%s, limit=%s, filtros=%s", skip, limit, bool(nome or cpf_cnpj or cpf_startsWith))
    query = f"SELECT {PACIENTE_COLS} FROM pacientes"
    filters = []
    params = []

    unit_scope = _resolve_read_unit_scope(request, unidade)
    if unit_scope is not None:
        filters.append("unidade = ANY(%s)")
        params.append(list(patient_unit_storage_values(unit_scope)))

    if nome: filters.append("nome_paciente ILIKE %s"); params.append(f"%{nome}%")
    if cpf_cnpj: filters.append("cpf_cnpj = %s"); params.append(cpf_cnpj.replace(".", "").replace("-", "").replace("/", "")) # Limpa CPF/CNPJ completo
    if cpf_startsWith:
        # Limpa o prefixo para buscar apenas dígitos
        prefixo_limpo = "".join(filter(str.isdigit, cpf_startsWith))
        if prefixo_limpo: # Só adiciona o filtro se houver dígitos
            filters.append("cpf_cnpj LIKE %s")
            params.append(f"{prefixo_limpo}%") # Adiciona wildcard no final

    if filters: query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY nome_paciente OFFSET %s LIMIT %s"
    params.extend([skip, limit])

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            logger.debug("Executando consulta de pacientes com %s parâmetros", len(params))
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [_map_row_to_paciente_read(r) for r in rows]
    except Exception as exc:
        logger.error(
            "Erro ao listar pacientes. error_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="Erro ao buscar pacientes.")

@router.get("/{paciente_id}", response_model=PacienteRead)
def obter_paciente(paciente_id: int, request: Request):
    """ Busca um paciente pelo ID. """
    logger.info(f"Buscando paciente ID={paciente_id}")
    unit_scope = _resolve_read_unit_scope(request)
    query = f"SELECT {PACIENTE_COLS} FROM pacientes WHERE paciente_id = %s"
    params = [paciente_id]
    if unit_scope is not None:
        query += " AND unidade = ANY(%s)"
        params.append(list(patient_unit_storage_values(unit_scope)))
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Paciente não encontrado.")
            return _map_row_to_paciente_read(row)
    except HTTPException as http_exc: raise http_exc
    except Exception as exc:
        logger.error(
            "Erro ao buscar paciente. paciente_id=%s error_type=%s",
            paciente_id,
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="Erro ao buscar detalhes do paciente.")


@router.put("/{paciente_id}", response_model=PacienteRead)
def atualizar_paciente(paciente_id: int, data: PacienteCreate, request: Request): # Usando PacienteCreate para PUT
    """ Atualiza dados de um paciente existente. """
    logger.info("Atualizando paciente ID=%s", paciente_id)
    unidade = _resolve_request_unit(request, data.unidade)

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        # Verificar se existe
        cursor.execute(
            "SELECT paciente_id, unidade, cpf_cnpj FROM pacientes WHERE paciente_id = %s FOR UPDATE",
            (paciente_id,),
        )
        existing_patient = cursor.fetchone()
        if not existing_patient:
            raise HTTPException(status_code=404, detail="Paciente não encontrado.")
        _ensure_patient_unit_access(existing_patient[1], unidade)
        try:
            ensure_remote_identities_before_document_change(
                cursor,
                paciente_id=paciente_id,
                unidade=unidade,
                current_document=existing_patient[2],
                requested_document=data.cpf_cnpj,
            )
        except PatientIntegrationIdentityPendingError:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Uma identidade remota ainda está pendente; aguarde a integração "
                    "ou execute a reconciliação antes de alterar o CPF/CNPJ."
                ),
            ) from None
        except PatientIntegrationConfigError:
            raise HTTPException(
                status_code=503,
                detail="Integração de pacientes temporariamente indisponível.",
            ) from None

        # Verificar CPF duplicado (se diferente do atual)
        cursor.execute("SELECT paciente_id FROM pacientes WHERE cpf_cnpj = %s AND paciente_id <> %s", (data.cpf_cnpj, paciente_id))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="CPF/CNPJ já pertence a outro paciente.")

        # Query UPDATE atualizada
        query = f"""
            UPDATE pacientes
            SET
                nome_paciente = %s, cpf_cnpj = %s, email = %s, data_nascimento = %s, is_minor = %s,
                responsavel_id = %s, phone_country_code = %s, phone_area_code = %s, phone_number = %s,
                street = %s, street_number = %s, line_two = %s, neighborhood = %s, city = %s, state = %s, zip_code = %s,
                unidade = %s, rg_ie = %s, genero = %s, observacoes = %s, midia_origem = %s,
                updated_at = GREATEST(
                    clock_timestamp() AT TIME ZONE 'UTC',
                    updated_at + INTERVAL '1 microsecond'
                )
            WHERE paciente_id = %s
            RETURNING {PACIENTE_COLS};
        """
        values = (
            data.nome_paciente, data.cpf_cnpj, data.email, data.data_nascimento, data.is_minor,
            data.responsavel_id, data.phone_country_code, data.phone_area_code, data.phone_number,
            data.street, data.street_number, data.line_two, data.neighborhood, data.city, data.state, data.zip_code,
            unidade, data.rg_ie, data.genero, data.observacoes, data.midia_origem, # Novos valores
            paciente_id # WHERE clause
        )
        try:
            cursor.execute(query, values)
            row = cursor.fetchone()
            if not row: raise HTTPException(status_code=404, detail="Paciente não encontrado durante atualização.")
            enqueue_patient_jobs_for_patient(
                cursor,
                paciente_id=row[0],
                unidade=unidade,
                patient_version=row[18],
                allow_asaas_customer_creation=True,
            )
            conn.commit()
            logger.info(f"Paciente ID {paciente_id} atualizado.")
            return _map_row_to_paciente_read(row)
        except psycopg2.Error as db_err: # Agora psycopg2 está definido
             logger.error(
                 "Erro DB ao atualizar paciente. paciente_id=%s error_type=%s",
                 paciente_id,
                 type(db_err).__name__,
             )
             conn.rollback()
             raise HTTPException(status_code=500, detail="Erro de banco de dados.")
        except PatientIntegrationConfigError:
             conn.rollback()
             logger.error("Configuracao de integracao de pacientes invalida")
             raise HTTPException(
                 status_code=503,
                 detail="Integracao de pacientes temporariamente indisponivel.",
             ) from None
        except PatientIntegrationDataError:
             conn.rollback()
             raise HTTPException(
                 status_code=400,
                 detail="Dados do paciente inválidos para integração.",
             ) from None
        except Exception as e:
            logger.error(
                "Erro inesperado ao atualizar paciente. paciente_id=%s error_type=%s",
                paciente_id,
                type(e).__name__,
            )
            conn.rollback()
            raise HTTPException(status_code=500, detail="Erro interno inesperado.")


@router.delete("/{paciente_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_paciente(paciente_id: int, request: Request):
    """ Exclui um paciente permanentemente. Cuidado com FKs! """
    logger.warning(f"Tentando EXCLUIR permanentemente paciente ID={paciente_id}")
    unit_scope = _resolve_read_unit_scope(request)
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        scope_clause = "" if unit_scope is None else " AND unidade = ANY(%s)"
        scope_params = (
            (paciente_id,)
            if unit_scope is None
            else (paciente_id, list(patient_unit_storage_values(unit_scope)))
        )
        cursor.execute(
            f"SELECT paciente_id FROM pacientes WHERE paciente_id = %s{scope_clause}",
            scope_params,
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Paciente não encontrado.")

        try:
            cursor.execute(
                f"DELETE FROM pacientes WHERE paciente_id = %s{scope_clause}",
                scope_params,
            )
            conn.commit()
            if cursor.rowcount == 0:
                 raise HTTPException(status_code=404, detail="Paciente não encontrado (ou já excluído).")
            logger.info(f"Paciente ID {paciente_id} excluído com sucesso.")
            # Retorna 204 No Content (Response agora está importado)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except psycopg2.Error as db_err: # Agora psycopg2 está definido
            # Captura erro específico de FK violation (código 23503)
            if hasattr(db_err, 'pgcode') and db_err.pgcode == '23503':
                 logger.warning(f"Não foi possível excluir paciente ID {paciente_id} devido a referências existentes (FK constraint).")
                 conn.rollback()
                 raise HTTPException(status_code=409, detail="Não é possível excluir o paciente pois ele possui registros associados (vendas, odontogramas, etc.). Considere inativá-lo.")
            else:
                 logger.error(
                     "Erro DB ao excluir paciente. paciente_id=%s error_type=%s",
                     paciente_id,
                     type(db_err).__name__,
                 )
                 conn.rollback()
                 raise HTTPException(status_code=500, detail="Erro de banco de dados.")
        except Exception as exc:
            logger.error(
                "Erro inesperado ao excluir paciente. paciente_id=%s error_type=%s",
                paciente_id,
                type(exc).__name__,
            )
            conn.rollback()
            raise HTTPException(status_code=500, detail="Erro interno inesperado.")
