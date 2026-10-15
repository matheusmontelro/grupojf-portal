# app/routers/patients_integrated.py

import logging
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from fastapi import APIRouter, HTTPException, status, Depends, Query, Response, Request
import psycopg2

# Importações do banco de dados e models
from app.database.db import DatabaseConnection
from app.models.pacientes import PacienteCreate, PacienteRead, DependenteRead, DadosDependenteModel
# Remover import de get_current_user pois vamos usar request.state

# Importações da SDK de pacientes para Delta
from app.pacientes_sdk import (
    PatientAPI, 
    get_token_and_seller_for_unidade, 
    validate_patient_data,
    transform_to_delta_format,
    transform_from_delta_format,
    DeltaAPIError,
    DeltaConnectionError,
    DeltaValidationError,
    DeltaConfigurationError
)
from app.services.patient_integration_config import (
    GLOBAL_UNIT_ALIASES,
    PatientIntegrationConfigError,
    canonicalize_patient_unit,
    is_patient_integration_enabled,
    patient_unit_storage_values,
    resolve_patient_unit,
)
from app.services.patient_integration_service import (
    PatientIntegrationDataError,
    PatientIntegrationIdentityPendingError,
    enqueue_patient_jobs_for_patient,
    ensure_remote_identities_before_document_change,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pacientes-integrados", tags=["pacientes-integrados"])

# Constante de colunas para select/insert/update
PACIENTE_COLS = """
    paciente_id, nome_paciente, cpf_cnpj, email, data_nascimento,
    is_minor, responsavel_id, phone_country_code, phone_area_code,
    phone_number, street, street_number, line_two, neighborhood, city, state,
    zip_code, created_at, updated_at, unidade,
    rg_ie, genero, observacoes, midia_origem, street_id
"""

DEPENDENTE_COLS = """
    dependente_id, responsavel_paciente_id, nome_dependente, data_nascimento_dependente,
    genero_dependente, parentesco, observacoes_dependente, ativo, created_at, updated_at
"""

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
        street_id=row[24],
    )

def _map_row_to_dependente_read(row) -> Optional[DependenteRead]:
    """ Mapeia uma linha do cursor (tupla) para o schema DependenteRead. """
    if not row:
        return None
    # Índices baseados na ordem em DEPENDENTE_COLS
    return DependenteRead(
        dependente_id=row[0],
        responsavel_paciente_id=row[1],
        nome_dependente=row[2],
        data_nascimento_dependente=row[3],
        genero_dependente=row[4],
        parentesco=row[5],
        observacoes_dependente=row[6],
        ativo=row[7],
        created_at=row[8],
        updated_at=row[9]
    )

def _get_patient_sdk_client(unidade: str):
    """
    Cria e retorna um cliente da SDK de pacientes configurado para a unidade.
    
    Args:
        unidade (str): Unidade para definir o token de API.
        
    Returns:
        PatientAPI: Cliente configurado da SDK.
    """
    try:
        # Definir ambiente
        environment = "sandbox"
        if os.getenv("ENVIRONMENT", "development") == "production":
            environment = "production"
        
        # Obter token de API e seller_id
        api_token, seller_id = get_token_and_seller_for_unidade(unidade, environment)
        
        # Criar e retornar o cliente de API
        return PatientAPI(api_token, seller_id, environment)
    except Exception as exc:
        logger.error(
            "Erro ao configurar SDK Delta. unidade=%s error_type=%s",
            unidade,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Integração com Delta temporariamente indisponível.",
        ) from None


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


def _async_patient_integration_enabled(unidade: str) -> bool:
    try:
        return is_patient_integration_enabled(unidade)
    except PatientIntegrationConfigError:
        logger.error("Allowlist da integracao de pacientes invalida")
        raise HTTPException(
            status_code=503,
            detail="Integracao de pacientes temporariamente indisponivel.",
        ) from None


def _ensure_patient_unit_access(stored_unit: Optional[str], unidade: str) -> None:
    if canonicalize_patient_unit(stored_unit) != unidade:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")


def _patient_frontend_response(patient: PacienteRead, delta_status: str) -> Dict[str, Any]:
    return {
        "id": patient.paciente_id,
        "nome": patient.nome_paciente,
        "cpf": patient.cpf_cnpj,
        "telefone": f"{patient.phone_area_code or ''}{patient.phone_number or ''}",
        "email": patient.email,
        "data_nascimento": patient.data_nascimento.isoformat() if patient.data_nascimento else None,
        "endereco": patient.street,
        "numero": patient.street_number,
        "complemento": patient.line_two,
        "bairro": patient.neighborhood,
        "cidade": patient.city,
        "estado": patient.state,
        "cep": patient.zip_code,
        "observacoes": patient.observacoes,
        "midia_origem": patient.midia_origem,
        "street_id": patient.street_id,
        "unidade": patient.unidade,
        "ativo": True,
        "created_at": patient.created_at.isoformat() if patient.created_at else None,
        "updated_at": patient.updated_at.isoformat() if patient.updated_at else None,
        "delta_integration_status": delta_status,
    }


def _validate_async_patient_payload(data: PacienteCreate) -> None:
    delta_data = transform_to_delta_format(data.model_dump(exclude_none=True))
    is_valid, validation_errors = validate_patient_data(delta_data)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Dados do responsavel/paciente invalidos: {', '.join(validation_errors)}",
        )


def _create_patient_with_async_integrations(
    data: PacienteCreate,
    unidade: str,
) -> Dict[str, Any]:
    """Persiste o contrato local e a outbox antes de qualquer chamada remota."""
    _validate_async_patient_payload(data)

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT paciente_id, unidade FROM pacientes WHERE cpf_cnpj = %s FOR UPDATE",
                (data.cpf_cnpj,),
            )
            existing = cursor.fetchone()

            if existing:
                _ensure_patient_unit_access(existing[1], unidade)
                paciente_id = existing[0]
                cursor.execute(
                    f"""
                    UPDATE pacientes SET
                        nome_paciente = %s,
                        email = %s,
                        data_nascimento = %s,
                        is_minor = %s,
                        responsavel_id = %s,
                        phone_country_code = %s,
                        phone_area_code = %s,
                        phone_number = %s,
                        street = %s,
                        street_number = %s,
                        line_two = %s,
                        neighborhood = %s,
                        city = %s,
                        state = %s,
                        zip_code = %s,
                        unidade = %s,
                        rg_ie = %s,
                        genero = %s,
                        observacoes = %s,
                        midia_origem = %s,
                        street_id = %s,
                        delta_integration_status = 'pendente',
                        updated_at = GREATEST(
                            clock_timestamp() AT TIME ZONE 'UTC',
                            updated_at + INTERVAL '1 microsecond'
                        )
                    WHERE paciente_id = %s
                    RETURNING {PACIENTE_COLS}
                    """,
                    (
                        data.nome_paciente,
                        data.email,
                        data.data_nascimento,
                        data.is_minor,
                        data.responsavel_id,
                        data.phone_country_code,
                        data.phone_area_code,
                        data.phone_number,
                        data.street,
                        data.street_number,
                        data.line_two,
                        data.neighborhood,
                        data.city,
                        data.state,
                        data.zip_code,
                        unidade,
                        data.rg_ie,
                        data.genero,
                        data.observacoes,
                        data.midia_origem,
                        data.street_id,
                        paciente_id,
                    ),
                )
            else:
                cursor.execute(
                    f"""
                    INSERT INTO pacientes (
                        nome_paciente, cpf_cnpj, email, data_nascimento, is_minor,
                        responsavel_id, phone_country_code, phone_area_code, phone_number,
                        street, street_number, line_two, neighborhood, city, state, zip_code,
                        unidade, rg_ie, genero, observacoes, midia_origem, street_id,
                        delta_integration_status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendente'
                    )
                    RETURNING {PACIENTE_COLS}
                    """,
                    (
                        data.nome_paciente,
                        data.cpf_cnpj,
                        data.email,
                        data.data_nascimento,
                        data.is_minor,
                        data.responsavel_id,
                        data.phone_country_code,
                        data.phone_area_code,
                        data.phone_number,
                        data.street,
                        data.street_number,
                        data.line_two,
                        data.neighborhood,
                        data.city,
                        data.state,
                        data.zip_code,
                        unidade,
                        data.rg_ie,
                        data.genero,
                        data.observacoes,
                        data.midia_origem,
                        data.street_id,
                    ),
                )

            patient_row = cursor.fetchone()
            if not patient_row:
                raise HTTPException(status_code=500, detail="Falha ao salvar paciente local.")
            patient = _map_row_to_paciente_read(patient_row)

            dependent_info = None
            if data.is_cadastro_dependente and data.dados_dependente:
                cursor.execute(
                    """
                    INSERT INTO dependentes (
                        responsavel_paciente_id, nome_dependente,
                        data_nascimento_dependente, genero_dependente, parentesco,
                        observacoes_dependente, ativo
                    ) VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                    RETURNING dependente_id, nome_dependente,
                              data_nascimento_dependente, genero_dependente,
                              parentesco, observacoes_dependente, ativo
                    """,
                    (
                        patient.paciente_id,
                        data.dados_dependente.nome_dependente,
                        data.dados_dependente.data_nascimento_dependente,
                        data.dados_dependente.genero_dependente,
                        data.dados_dependente.parentesco,
                        data.dados_dependente.observacoes_dependente,
                    ),
                )
                dependent_row = cursor.fetchone()
                if not dependent_row:
                    raise HTTPException(status_code=500, detail="Falha ao salvar dependente local.")
                dependent_info = {
                    "dependente_id": dependent_row[0],
                    "nome_dependente": dependent_row[1],
                    "data_nascimento_dependente": dependent_row[2],
                    "genero_dependente": dependent_row[3],
                    "parentesco": dependent_row[4],
                    "observacoes_dependente": dependent_row[5],
                    "ativo": dependent_row[6],
                }

            enqueue_patient_jobs_for_patient(
                cursor,
                paciente_id=patient.paciente_id,
                unidade=unidade,
                patient_version=patient.updated_at,
                allow_delta_customer_creation=existing is None,
                allow_asaas_customer_creation=True,
            )
            conn.commit()

            response = _patient_frontend_response(patient, "pendente")
            if dependent_info is not None:
                return {"responsavel": response, "dependente": dependent_info}
            return response
    except HTTPException:
        raise
    except PatientIntegrationConfigError:
        logger.error("Configuracao de integracao de pacientes invalida")
        raise HTTPException(
            status_code=503,
            detail="Integracao de pacientes temporariamente indisponivel.",
        ) from None
    except PatientIntegrationDataError:
        raise HTTPException(
            status_code=400,
            detail="Dados do paciente inválidos para integração.",
        ) from None
    except psycopg2.Error as exc:
        logger.error(
            "Erro DB no cadastro assincrono de paciente. error_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="Erro de banco de dados.") from None


def _update_patient_with_async_integrations(
    paciente_id: int,
    data: PacienteCreate,
    unidade: str,
) -> Dict[str, Any]:
    _validate_async_patient_payload(data)

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT paciente_id, unidade, cpf_cnpj FROM pacientes WHERE paciente_id = %s FOR UPDATE",
                (paciente_id,),
            )
            existing_patient = cursor.fetchone()
            if not existing_patient:
                raise HTTPException(status_code=404, detail="Paciente não encontrado.")
            _ensure_patient_unit_access(existing_patient[1], unidade)
            ensure_remote_identities_before_document_change(
                cursor,
                paciente_id=paciente_id,
                unidade=unidade,
                current_document=existing_patient[2],
                requested_document=data.cpf_cnpj,
            )

            cursor.execute(
                """
                SELECT paciente_id
                FROM pacientes
                WHERE cpf_cnpj = %s AND paciente_id <> %s
                """,
                (data.cpf_cnpj, paciente_id),
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="CPF/CNPJ já pertence a outro paciente.")

            cursor.execute(
                f"""
                UPDATE pacientes SET
                    nome_paciente = %s,
                    cpf_cnpj = %s,
                    email = %s,
                    data_nascimento = %s,
                    is_minor = %s,
                    responsavel_id = %s,
                    phone_country_code = %s,
                    phone_area_code = %s,
                    phone_number = %s,
                    street = %s,
                    street_number = %s,
                    line_two = %s,
                    neighborhood = %s,
                    city = %s,
                    state = %s,
                    zip_code = %s,
                    unidade = %s,
                    rg_ie = %s,
                    genero = %s,
                    observacoes = %s,
                    midia_origem = %s,
                    street_id = %s,
                    delta_integration_status = 'pendente',
                    updated_at = GREATEST(
                        clock_timestamp() AT TIME ZONE 'UTC',
                        updated_at + INTERVAL '1 microsecond'
                    )
                WHERE paciente_id = %s
                RETURNING {PACIENTE_COLS}
                """,
                (
                    data.nome_paciente,
                    data.cpf_cnpj,
                    data.email,
                    data.data_nascimento,
                    data.is_minor,
                    data.responsavel_id,
                    data.phone_country_code,
                    data.phone_area_code,
                    data.phone_number,
                    data.street,
                    data.street_number,
                    data.line_two,
                    data.neighborhood,
                    data.city,
                    data.state,
                    data.zip_code,
                    unidade,
                    data.rg_ie,
                    data.genero,
                    data.observacoes,
                    data.midia_origem,
                    data.street_id,
                    paciente_id,
                ),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Paciente não encontrado durante atualização.")

            patient = _map_row_to_paciente_read(row)
            enqueue_patient_jobs_for_patient(
                cursor,
                paciente_id=patient.paciente_id,
                unidade=unidade,
                patient_version=patient.updated_at,
                allow_asaas_customer_creation=True,
            )
            conn.commit()
            return _patient_frontend_response(patient, "pendente")
    except HTTPException:
        raise
    except PatientIntegrationConfigError:
        logger.error("Configuracao de integracao de pacientes invalida")
        raise HTTPException(
            status_code=503,
            detail="Integracao de pacientes temporariamente indisponivel.",
        ) from None
    except PatientIntegrationIdentityPendingError:
        raise HTTPException(
            status_code=409,
            detail=(
                "Uma identidade remota ainda está pendente; aguarde a integração "
                "ou execute a reconciliação antes de alterar o CPF/CNPJ."
            ),
        ) from None
    except PatientIntegrationDataError:
        raise HTTPException(
            status_code=400,
            detail="Dados do paciente inválidos para integração.",
        ) from None
    except psycopg2.Error as exc:
        logger.error(
            "Erro DB na atualizacao assincrona de paciente. paciente_id=%s error_type=%s",
            paciente_id,
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="Erro de banco de dados.") from None

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def criar_paciente_integrado(
    data: PacienteCreate,
    request: Request
):
    """
    Cria um paciente de forma integrada (Delta OBRIGATÓRIA) ou um responsável com dependente.
    Se data.is_cadastro_dependente for True:
        - O 'data' principal (cpf_cnpj, nome_paciente, etc.) refere-se ao RESPONSÁVEL.
        - data.dados_dependente contém as informações do dependente.
        - O RESPONSÁVEL é criado/validado na Delta.
        - O RESPONSÁVEL é salvo na tabela local 'pacientes'.
        - O DEPENDENTE é salvo na tabela local 'dependentes'.
    Se data.is_cadastro_dependente for False:
        - Fluxo original: paciente é criado na Delta e na tabela local 'pacientes'.
    """
    if data.is_cadastro_dependente:
        logger.info("Criando responsável com dependente")
        if not data.dados_dependente or not data.dados_dependente.nome_dependente:
            raise HTTPException(
                status_code=400,
                detail="Nome do dependente é obrigatório ao cadastrar como dependente."
            )
    else:
        logger.info("Criando paciente integrado")

    # Verificar campos obrigatórios para o Responsável/Paciente Principal
    if not data.cpf_cnpj or not data.nome_paciente:
        raise HTTPException(
            status_code=400, 
            detail="CPF/CNPJ e Nome (do responsável/paciente) são campos obrigatórios"
        )
    
    # A unidade autenticada e a unica fonte permitida para usuarios de unidade.
    # Usuarios globais precisam escolher explicitamente uma unidade real.
    unidade = _resolve_request_unit(request, data.unidade)
    logger.info("Criando paciente. unidade=%s", unidade)

    if _async_patient_integration_enabled(unidade):
        return _create_patient_with_async_integrations(data, unidade)

    id_responsavel_local: Optional[int] = None
    paciente_responsavel_criado_localmente = False

    # Verificar se o CPF do Responsável/Paciente Principal já existe no banco local
    with DatabaseConnection() as conn_check:
        cursor_check = conn_check.cursor()
        cursor_check.execute(
            "SELECT paciente_id, unidade FROM pacientes WHERE cpf_cnpj = %s",
            (data.cpf_cnpj,),
        )
        existing_patient_row = cursor_check.fetchone()
        if existing_patient_row:
            _ensure_patient_unit_access(existing_patient_row[1], unidade)
            id_responsavel_local = existing_patient_row[0]
            logger.info("Paciente já existe localmente com ID=%s", id_responsavel_local)
            # Mudança: em vez de retornar erro, vamos permitir atualização
            # if not data.is_cadastro_dependente:
            #     # Se NÃO é fluxo de dependente e o CPF já existe, é um erro.
            #     raise HTTPException(
            #         status_code=400, 
            #         detail=f"CPF/CNPJ {data.cpf_cnpj} já existe no sistema local para um paciente principal."
            #     )
            # Se é fluxo de dependente e o responsável já existe, usaremos o id_responsavel_local.
            # A chamada à Delta ainda ocorrerá para validar/atualizar o responsável na Delta.
        cursor_check.close()

    
    try:
        # 🎯 CRÍTICO: Tentar Delta PRIMEIRO (com os dados do RESPONSÁVEL/PACIENTE PRINCIPAL)
        logger.info("Validando paciente na Delta")
        
        # Montar payload para a Delta SOMENTE com campos do PacienteBase/Responsável
        # Excluir is_cadastro_dependente e dados_dependente do payload para a Delta
        delta_payload_dict = data.model_dump(exclude_none=True)
        delta_payload_dict.pop('is_cadastro_dependente', None)
        delta_payload_dict.pop('dados_dependente', None)
        
        # Assegurar que campos esperados por transform_to_delta_format estejam presentes
        # Esta é uma simplificação, idealmente transform_to_delta_format deveria ser robusto
        # ou ter um modelo Pydantic específico para o payload Delta.
        campos_para_delta = {
            "nome_paciente": data.nome_paciente,
            "cpf_cnpj": data.cpf_cnpj,
            "email": data.email,
            "data_nascimento": data.data_nascimento,
            "is_minor": data.is_minor, # do responsável/paciente principal
            "responsavel_id": data.responsavel_id, # do responsável/paciente principal, se houver
            "phone_country_code": data.phone_country_code,
            "phone_area_code": data.phone_area_code,
            "phone_number": data.phone_number,
            "street": data.street,
            "street_number": data.street_number,
            "line_two": data.line_two,
            "neighborhood": data.neighborhood,
            "city": data.city,
            "state": data.state,
            "zip_code": data.zip_code,
            "unidade": unidade,
            "rg_ie": data.rg_ie,
            "genero": data.genero,
            "observacoes": data.observacoes,
            "midia_origem": data.midia_origem
        }
        
        # Remover chaves com valor None para evitar problemas com transform_to_delta_format se ele não os espera
        campos_para_delta_cleaned = {k: v for k, v in campos_para_delta.items() if v is not None}

        delta_data_transformed = transform_to_delta_format(campos_para_delta_cleaned)
        
        is_valid, validation_errors = validate_patient_data(delta_data_transformed)
        if not is_valid:
            logger.error(f"❌ DADOS INVÁLIDOS (Responsável/Paciente): {validation_errors}")
            raise HTTPException(
                status_code=400, 
                detail=f"Dados do responsável/paciente inválidos para Delta: {', '.join(validation_errors)}"
            )

        patient_api = _get_patient_sdk_client(unidade)
        try:
            patient_api.upsert_patient(delta_data_transformed)
            logger.info("Paciente sincronizado na Delta")

            # Log adicional sobre status local
            if id_responsavel_local is not None:
                logger.info(
                    "Paciente ja existia localmente. paciente_id=%s",
                    id_responsavel_local,
                )
            else:
                logger.info("Paciente sera criado localmente")
        except DeltaValidationError:
            logger.warning("Delta rejeitou dados do paciente")
            raise HTTPException(
                status_code=400,
                detail="Delta rejeitou os dados do paciente.",
            ) from None
        except DeltaConnectionError:
            logger.warning("Falha de comunicacao com Delta no cadastro")
            raise HTTPException(
                status_code=503,
                detail="Integração com Delta temporariamente indisponível.",
            ) from None
        except DeltaAPIError as exc:
            logger.warning(
                "Delta recusou sincronizacao. status=%s",
                exc.status_code,
            )
            response_status = (
                503
                if exc.status_code in {408, 429} or exc.status_code >= 500
                else 400
            )
            raise HTTPException(
                status_code=response_status,
                detail="Não foi possível sincronizar o paciente na Delta.",
            ) from None
        finally:
            patient_api.close()
        
        # 🎯 SEGUNDO: Delta OK → Salvar no banco local
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            paciente_criado_ou_atualizado_local = None

            if id_responsavel_local is None: # Responsável/Paciente não existia localmente
                logger.info("Salvando novo paciente local")
                query_insert_paciente = f"""
                INSERT INTO pacientes (
                    nome_paciente, cpf_cnpj, email, data_nascimento, is_minor,
                    responsavel_id, phone_country_code, phone_area_code, phone_number,
                    street, street_number, line_two, neighborhood, city, state, zip_code,
                    unidade, rg_ie, genero, observacoes, midia_origem, street_id, delta_integration_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING {PACIENTE_COLS};
            """
                values_paciente = (
                data.nome_paciente, data.cpf_cnpj, data.email, data.data_nascimento, data.is_minor,
                data.responsavel_id, data.phone_country_code, data.phone_area_code, data.phone_number,
                data.street, data.street_number, data.line_two, data.neighborhood, data.city, data.state, data.zip_code,
                    unidade, data.rg_ie, data.genero, data.observacoes, data.midia_origem, 
                    getattr(data, 'street_id', None),  # street_id
                    "criado_integrado"
                )
                try:
                    cursor.execute(query_insert_paciente, values_paciente)
                    row_paciente = cursor.fetchone()
                    if not row_paciente:
                        conn.rollback()
                        raise HTTPException(status_code=500, detail="Falha ao criar paciente/responsável local após sucesso na Delta.")
                    id_responsavel_local = row_paciente[0] # paciente_id
                    paciente_criado_ou_atualizado_local = _map_row_to_paciente_read(row_paciente)
                    paciente_responsavel_criado_localmente = True
                    logger.info(f"💾 Paciente/Responsável {id_responsavel_local} salvo localmente.")
                except psycopg2.Error as db_err:
                    conn.rollback()
                    logger.error("Erro de banco ao inserir paciente após sucesso na Delta", exc_info=True)
                    raise HTTPException(status_code=500, detail=f"Erro crítico: Operação Delta OK, mas falha ao salvar Paciente/Responsável local. Contate suporte.")
            else:
                # Responsável já existia localmente. Vamos atualizar seus dados.
                logger.info("Atualizando paciente local ID=%s", id_responsavel_local)
                
                # Atualizar os dados do paciente existente
                query_update_paciente = f"""
                    UPDATE pacientes SET
                        nome_paciente = %s,
                        email = %s,
                        data_nascimento = %s,
                        is_minor = %s,
                        responsavel_id = %s,
                        phone_country_code = %s,
                        phone_area_code = %s,
                        phone_number = %s,
                        street = %s,
                        street_number = %s,
                        line_two = %s,
                        neighborhood = %s,
                        city = %s,
                        state = %s,
                        zip_code = %s,
                        unidade = %s,
                        rg_ie = %s,
                        genero = %s,
                        observacoes = %s,
                        midia_origem = %s,
                        street_id = %s,
                        delta_integration_status = %s,
                        updated_at = GREATEST(
                            clock_timestamp() AT TIME ZONE 'UTC',
                            updated_at + INTERVAL '1 microsecond'
                        )
                    WHERE paciente_id = %s
                    RETURNING {PACIENTE_COLS};
                """
                values_update = (
                    data.nome_paciente, data.email, data.data_nascimento, data.is_minor,
                    data.responsavel_id, data.phone_country_code, data.phone_area_code, data.phone_number,
                    data.street, data.street_number, data.line_two, data.neighborhood, data.city, data.state, data.zip_code,
                    unidade, data.rg_ie, data.genero, data.observacoes, data.midia_origem,
                    getattr(data, 'street_id', None),
                    "atualizado_integrado",
                    id_responsavel_local
                )
                
                try:
                    cursor.execute(query_update_paciente, values_update)
                    row_paciente_atualizado = cursor.fetchone()
                    if row_paciente_atualizado:
                        paciente_criado_ou_atualizado_local = _map_row_to_paciente_read(row_paciente_atualizado)
                        logger.info(f"✅ Paciente/Responsável ID {id_responsavel_local} atualizado com sucesso.")
                    else:
                        conn.rollback()
                        raise HTTPException(status_code=500, detail=f"Erro ao atualizar paciente ID {id_responsavel_local}.")
                except psycopg2.Error as db_err:
                    conn.rollback()
                    logger.error("Erro de banco ao atualizar paciente local ID=%s", id_responsavel_local, exc_info=True)
                    raise HTTPException(status_code=500, detail=f"Erro ao atualizar paciente local. Delta já foi afetada!")

            # Se for cadastro de dependente, salvar o dependente
            if data.is_cadastro_dependente and data.dados_dependente and id_responsavel_local is not None:
                logger.info(f"💾 SALVANDO LOCAL (Dependente) para Responsável ID: {id_responsavel_local}")
                query_insert_dependente = """
                    INSERT INTO dependentes (
                        responsavel_paciente_id, nome_dependente, data_nascimento_dependente,
                        genero_dependente, parentesco, observacoes_dependente, ativo
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING dependente_id, nome_dependente, data_nascimento_dependente, genero_dependente, parentesco, observacoes_dependente, ativo;
                """
                values_dependente = (
                    id_responsavel_local,
                    data.dados_dependente.nome_dependente,
                    data.dados_dependente.data_nascimento_dependente,
                    data.dados_dependente.genero_dependente,
                    data.dados_dependente.parentesco,
                    data.dados_dependente.observacoes_dependente,
                    True # ativo
                )
                try:
                    cursor.execute(query_insert_dependente, values_dependente)
                    row_dependente = cursor.fetchone()
                    if not row_dependente:
                        conn.rollback() # Importante reverter a inserção do responsável se ele foi criado nesta transação
                        raise HTTPException(status_code=500, detail="Falha ao criar dependente local após sucesso na Delta e salvamento do responsável.")
                    
                    dependente_criado_info = {
                        "dependente_id": row_dependente[0],
                        "nome_dependente": row_dependente[1],
                        "data_nascimento_dependente": row_dependente[2],
                        "genero_dependente": row_dependente[3],
                        "parentesco": row_dependente[4],
                        "observacoes_dependente": row_dependente[5],
                        "ativo": row_dependente[6]
                    }
                    logger.info("Dependente salvo com ID=%s", dependente_criado_info['dependente_id'])
                    
                    # Preparar resposta para o frontend
                    if paciente_criado_ou_atualizado_local:
                        retorno_responsavel = {
                            "id": paciente_criado_ou_atualizado_local.paciente_id,
                            "nome": paciente_criado_ou_atualizado_local.nome_paciente,
                            "cpf": paciente_criado_ou_atualizado_local.cpf_cnpj,
                            "telefone": f"{paciente_criado_ou_atualizado_local.phone_area_code or ''}{paciente_criado_ou_atualizado_local.phone_number or ''}",
                            "email": paciente_criado_ou_atualizado_local.email,
                            "data_nascimento": paciente_criado_ou_atualizado_local.data_nascimento.isoformat() if paciente_criado_ou_atualizado_local.data_nascimento else None,
                            # ... outros campos do responsável conforme formato atual de retorno
                            "observacoes": paciente_criado_ou_atualizado_local.observacoes,
                            "midia_origem": paciente_criado_ou_atualizado_local.midia_origem,
                            "street_id": paciente_criado_ou_atualizado_local.street_id,
                            "unidade": paciente_criado_ou_atualizado_local.unidade,
                            "ativo": True, # Assumindo que o responsável está ativo
                            "created_at": paciente_criado_ou_atualizado_local.created_at.isoformat() if paciente_criado_ou_atualizado_local.created_at else None,
                            "updated_at": paciente_criado_ou_atualizado_local.updated_at.isoformat() if paciente_criado_ou_atualizado_local.updated_at else None,
                            "delta_integration_status": paciente_criado_ou_atualizado_local.delta_integration_status if hasattr(paciente_criado_ou_atualizado_local, 'delta_integration_status') else "criado_integrado"
                        }
                        conn.commit()
                        logger.info(f"🎉 SUCESSO TOTAL: Responsável {retorno_responsavel['id']} e Dependente {dependente_criado_info['dependente_id']} criados.")
                        return {"responsavel": retorno_responsavel, "dependente": dependente_criado_info}
                    else: # Não deveria acontecer se a lógica estiver correta
                        conn.rollback()
                        raise HTTPException(status_code=500, detail="Falha ao obter dados do responsável para o retorno.")

                except psycopg2.Error as db_err_dep:
                    conn.rollback() # Importante reverter a inserção do responsável se ele foi criado nesta transação
                    logger.error(
                        "Erro DB ao inserir dependente. responsavel_id=%s error_type=%s",
                        id_responsavel_local,
                        type(db_err_dep).__name__,
                    )
                    # Se paciente_responsavel_criado_localmente for True, pode haver um órfão na tabela pacientes.
                    # Idealmente, toda a operação (Delta + responsável local + dependente local) é uma unidade.
                    # A Delta já foi chamada, então a inconsistência seria entre Delta e local.
                    raise HTTPException(status_code=500, detail=f"Erro crítico: Falha ao salvar Dependente local. Responsável pode ter sido afetado na Delta/Local. Contate suporte.")

            else: # Cadastro de Paciente Padrão (não dependente)
                if paciente_criado_ou_atualizado_local:
                    # Formato de retorno original para paciente padrão
                    result = {
                        "id": paciente_criado_ou_atualizado_local.paciente_id,
                        "nome": paciente_criado_ou_atualizado_local.nome_paciente,
                        "cpf": paciente_criado_ou_atualizado_local.cpf_cnpj,
                        "telefone": f"{paciente_criado_ou_atualizado_local.phone_area_code or ''}{paciente_criado_ou_atualizado_local.phone_number or ''}",
                        "email": paciente_criado_ou_atualizado_local.email,
                        "data_nascimento": paciente_criado_ou_atualizado_local.data_nascimento.isoformat() if paciente_criado_ou_atualizado_local.data_nascimento else None,
                        "endereco": paciente_criado_ou_atualizado_local.street,
                        "numero": paciente_criado_ou_atualizado_local.street_number,
                        "complemento": paciente_criado_ou_atualizado_local.line_two,
                        "bairro": paciente_criado_ou_atualizado_local.neighborhood,
                        "cidade": paciente_criado_ou_atualizado_local.city,
                        "estado": paciente_criado_ou_atualizado_local.state,
                        "cep": paciente_criado_ou_atualizado_local.zip_code,
                        "observacoes": paciente_criado_ou_atualizado_local.observacoes,
                        "midia_origem": paciente_criado_ou_atualizado_local.midia_origem,
                        "street_id": paciente_criado_ou_atualizado_local.street_id,
                        "unidade": paciente_criado_ou_atualizado_local.unidade,
                        "ativo": True,
                        "created_at": paciente_criado_ou_atualizado_local.created_at.isoformat() if paciente_criado_ou_atualizado_local.created_at else None,
                        "updated_at": paciente_criado_ou_atualizado_local.updated_at.isoformat() if paciente_criado_ou_atualizado_local.updated_at else None,
                        "delta_integration_status": paciente_criado_ou_atualizado_local.delta_integration_status if hasattr(paciente_criado_ou_atualizado_local, 'delta_integration_status') else "criado_integrado"
                    }
                    conn.commit()
                    logger.info(f"🎉 SUCESSO TOTAL: Paciente Padrão {result['id']} criado/atualizado.")
                    return result
                else: # Não deveria acontecer
                    conn.rollback()
                    raise HTTPException(status_code=500, detail="Falha ao obter dados do paciente padrão para o retorno.")
            # Fim do with DatabaseConnection() conn: (commit/rollback automático)
        
    except HTTPException:
        # Repassa HTTPExceptions já levantadas (ex: validações, erros Delta)
        raise
    except Exception as exc:
        logger.error(
            "Erro inesperado no fluxo integrado de criacao. error_type=%s",
            type(exc).__name__,
        )
        # Aqui, não sabemos o estado da Delta ou do banco local.
        raise HTTPException(
            status_code=500,
            detail="Erro interno no fluxo de criação."
        ) from None

@router.get("/consultar/{documento}", response_model=Dict[str, Any])
async def consultar_paciente_delta(
    documento: str,
    request: Request,
    unidade: Optional[str] = Query(None),
):
    """
    Consulta um paciente diretamente na Delta pelo CPF/CNPJ.
    Retorna os dados originais da Delta.
    """
    unidade_resolvida = _resolve_request_unit(request, unidade)
    try:
        # Consulta o paciente na Delta
        document_clean = ''.join(filter(lambda x: x.isdigit(), documento))
        if len(document_clean) not in {11, 14}:
            raise HTTPException(
                status_code=400, 
                detail="Documento inválido. Informe um CPF/CNPJ válido."
            )

        with _get_patient_sdk_client(unidade_resolvida) as patient_api:
            patient_data = patient_api.get_patient_by_document(document_clean)
        
        if not patient_data:
            raise HTTPException(
                status_code=404, 
                detail="Paciente não encontrado na Delta."
            )
        
        # Retorna os dados originais da Delta
        return {
            "origem": "delta",
            "data": patient_data
        }
        
    except DeltaConnectionError:
        logger.warning("Falha de comunicacao ao consultar paciente na Delta")
        raise HTTPException(
            status_code=503, 
            detail="Integração com Delta temporariamente indisponível."
        ) from None
    except DeltaAPIError as exc:
        logger.warning("Delta recusou consulta. status=%s", exc.status_code)
        raise HTTPException(
            status_code=502,
            detail="Não foi possível consultar o paciente na Delta."
        ) from None
    except HTTPException:
        # Repassa HTTPExceptions já criadas
        raise
    except Exception as exc:
        logger.error(
            "Erro inesperado na consulta Delta. error_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao consultar paciente."
        ) from None

@router.post("/importar/{documento}", response_model=PacienteRead)
async def importar_paciente_delta(
    documento: str, 
    request: Request,
    unidade: Optional[str] = Query(None),
):
    """
    Importa um paciente da Delta para o nosso banco de dados.
    1. Consulta o paciente na Delta
    2. Converte para o formato interno
    3. Salva no nosso banco de dados
    """
    try:
        # Usar a unidade do usuário autenticado
        unidade_resolvida = _resolve_request_unit(request, unidade)
        async_integration_enabled = _async_patient_integration_enabled(
            unidade_resolvida
        )
        logger.info("Importando paciente da Delta. unidade=%s", unidade_resolvida)
        
        # Consulta o paciente na Delta
        document_clean = ''.join(filter(lambda x: x.isdigit(), documento))
        if len(document_clean) not in {11, 14}:
            raise HTTPException(
                status_code=400, 
                detail="Documento inválido. Informe apenas números do CPF/CNPJ."
            )
        
        # Verificar se já existe no nosso banco
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT paciente_id FROM pacientes WHERE cpf_cnpj = %s", 
                (document_clean,)
            )
            result = cursor.fetchone()
            if result:
                logger.info("Paciente importado já existe no banco local")
                raise HTTPException(
                    status_code=400, 
                    detail="Paciente já existe no sistema local"
                )
        
        # Buscar na Delta
        with _get_patient_sdk_client(unidade_resolvida) as patient_api:
            delta_patient = patient_api.get_patient_by_document(document_clean)
        
        if not delta_patient:
            raise HTTPException(
                status_code=404, 
                detail=f"Paciente com documento {documento} não encontrado na Delta."
            )

        confirmed_delta_customer_id = None
        if async_integration_enabled:
            confirmed_delta_customer_id = PatientAPI.extract_customer_id(
                delta_patient
            )
            if confirmed_delta_customer_id is None:
                raise HTTPException(
                    status_code=502,
                    detail="A Delta não retornou a identidade técnica do paciente.",
                )
        
        # Converter para formato interno
        internal_data = transform_from_delta_format(delta_patient)
        internal_data["unidade"] = unidade_resolvida  # Adicionar a unidade informada
        
        # Salvar no banco de dados
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Query INSERT
            query = f"""
                INSERT INTO pacientes (
                    nome_paciente, cpf_cnpj, email, data_nascimento,
                    phone_country_code, phone_area_code, phone_number,
                    street, street_number, line_two, neighborhood, city, state, zip_code,
                    unidade, midia_origem, delta_integration_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING {PACIENTE_COLS};
            """
            
            values = (
                internal_data.get("nome_paciente", ""),
                internal_data.get("cpf_cnpj", ""),
                internal_data.get("email"),
                internal_data.get("data_nascimento"),
                internal_data.get("phone_country_code"),
                internal_data.get("phone_area_code"),
                internal_data.get("phone_number"),
                internal_data.get("street"),
                internal_data.get("street_number"),
                internal_data.get("line_two"),
                internal_data.get("neighborhood"),
                internal_data.get("city"),
                internal_data.get("state"),
                internal_data.get("zip_code"),
                internal_data.get("unidade", unidade_resolvida),
                internal_data.get("midia_origem"),  # Adicionar midia_origem
                "importado_delta"  # Status de integração
            )
            
            try:
                cursor.execute(query, values)
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=500, detail="Falha ao importar paciente.")

                enqueue_patient_jobs_for_patient(
                    cursor,
                    paciente_id=row[0],
                    unidade=unidade_resolvida,
                    patient_version=row[18],
                    providers=(
                        ("delta", "asaas")
                        if async_integration_enabled
                        else ("asaas",)
                    ),
                    confirmed_delta_customer_id=confirmed_delta_customer_id,
                    allow_asaas_customer_creation=True,
                )
                conn.commit()
                
                logger.info("Paciente importado da Delta. paciente_id=%s", row[0])
                return _map_row_to_paciente_read(row)
            except psycopg2.Error as db_err:
                conn.rollback()
                logger.error(
                    "Erro DB ao importar paciente. error_type=%s",
                    type(db_err).__name__,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Erro de banco de dados.",
                ) from None
        
    except DeltaConnectionError:
        logger.warning("Falha de comunicacao ao importar paciente da Delta")
        raise HTTPException(
            status_code=503, 
            detail="Integração com Delta temporariamente indisponível."
        ) from None
    except DeltaAPIError as exc:
        logger.warning("Delta recusou importacao. status=%s", exc.status_code)
        raise HTTPException(
            status_code=502,
            detail="Não foi possível importar o paciente da Delta."
        ) from None
    except PatientIntegrationConfigError:
        logger.error("Configuracao da integracao de pacientes invalida")
        raise HTTPException(
            status_code=503,
            detail="Integração de pacientes temporariamente indisponível.",
        ) from None
    except PatientIntegrationDataError:
        raise HTTPException(
            status_code=400,
            detail="Dados do paciente inválidos para integração.",
        ) from None
    except HTTPException:
        # Repassa HTTPExceptions já criadas
        raise
    except Exception as exc:
        logger.error(
            "Erro inesperado na importacao Delta. error_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500, 
            detail="Erro interno ao importar paciente."
        ) from None

@router.get("", response_model=dict)
async def listar_pacientes_integrados(
    request: Request,
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(100, ge=1, le=1000, description="Limite de registros por página"),
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    cpf_cnpj: Optional[str] = Query(None, description="Filtrar por CPF/CNPJ exato"),
    cpf_startsWith: Optional[str] = Query(None, description="Filtrar por CPF que inicia com"),
    telefone: Optional[str] = Query(None, description="Filtrar por telefone"),
    email: Optional[str] = Query(None, description="Filtrar por email"),
    ativo: Optional[bool] = Query(None, description="Filtrar por status ativo"),
    page: Optional[int] = Query(None, description="Número da página"),
    per_page: Optional[int] = Query(None, description="Registros por página"),
    unidade: Optional[str] = Query(None, description="Filtrar por unidade"),
):
    """
    Lista pacientes integrados com filtros e paginação.
    """
    # Ajustar paginação se page/per_page foram fornecidos
    if page is not None and per_page is not None:
        skip = (page - 1) * per_page
        limit = per_page
    
    unit_scope = _resolve_read_unit_scope(request, unidade)
    
    logger.info("Listando pacientes integrados: skip=%s, limit=%s, filtros=%s", skip, limit, bool(nome or cpf_cnpj or cpf_startsWith))
    logger.info("Aplicando escopo de unidade. unidade=%s", unit_scope or "todas")
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Construir query dinamicamente
            where_conditions = []
            params = []
            
            if unit_scope is not None:
                where_conditions.append("unidade = ANY(%s)")
                params.append(list(patient_unit_storage_values(unit_scope)))
            # Se for "Todas unidades", não adiciona filtro de unidade, mostra todos
            
            if nome:
                where_conditions.append("nome_paciente ILIKE %s")
                params.append(f"%{nome}%")
            
            if cpf_cnpj:
                where_conditions.append("cpf_cnpj = %s")
                params.append(cpf_cnpj)
            
            # CORREÇÃO PRINCIPAL: Implementar busca por prefixo de CPF
            if cpf_startsWith:
                # Versão simples: remover pontos, traços e espaços comuns
                clean_cpf_starts = ''.join(filter(str.isdigit, cpf_startsWith))
                where_conditions.append("REPLACE(REPLACE(REPLACE(cpf_cnpj, '.', ''), '-', ''), ' ', '') LIKE %s")
                params.append(f"{clean_cpf_starts}%")
                logger.info("Aplicando filtro por prefixo de documento")
            
            if telefone:
                where_conditions.append("phone_number LIKE %s")
                params.append(f"%{telefone}%")
            
            if email:
                where_conditions.append("email ILIKE %s")
                params.append(f"%{email}%")
            
            if ativo is not None:
                # Se não houver coluna 'ativo', pode remover esta condição ou adaptar
                where_conditions.append("(delta_integration_status IS NOT NULL)")
            
            # Query principal
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # Query para contar total
            count_query = f"SELECT COUNT(*) FROM pacientes {where_clause}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # Query principal com paginação
            main_query = f"""
                SELECT {PACIENTE_COLS}
                FROM pacientes 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            
            # DEBUG: Log da query final
            logger.info(f"Query SQL: {main_query}")
            logger.info("Consulta de pacientes com %s parâmetros", len(params) + 2)
            
            cursor.execute(main_query, params + [limit, skip])
            rows = cursor.fetchall()
            
            logger.info(f"Rows retornadas do banco: {len(rows)}")
            if rows:
                logger.info("Primeiro paciente retornado com ID=%s", rows[0][0])
            
            # Mapear resultados
            pacientes = []
            paciente_ids = []

            for row in rows:
                paciente = _map_row_to_paciente_read(row)
                if paciente:
                    paciente_ids.append(paciente.paciente_id)
                    # Converter para dict para compatibilidade com frontend
                    paciente_dict = {
                        "id": paciente.paciente_id,
                        "nome": paciente.nome_paciente,
                        "cpf": paciente.cpf_cnpj,
                        "telefone": f"({paciente.phone_area_code or ''}) {paciente.phone_number or ''}".strip(),
                        "email": paciente.email,
                        "data_nascimento": paciente.data_nascimento.isoformat() if paciente.data_nascimento else None,
                        "endereco": paciente.street,
                        "numero": paciente.street_number,
                        "complemento": paciente.line_two,
                        "bairro": paciente.neighborhood,
                        "cidade": paciente.city,
                        "estado": paciente.state,
                        "cep": paciente.zip_code,
                        "nome_responsavel": "",
                        "cpf_responsavel": "",
                        "telefone_responsavel": "",
                        "observacoes": paciente.observacoes,
                        "midia_origem": paciente.midia_origem,
                        "street_id": paciente.street_id,
                        "unidade": paciente.unidade,
                        "ativo": True,
                        "created_at": paciente.created_at.isoformat() if paciente.created_at else None,
                        "updated_at": paciente.updated_at.isoformat() if paciente.updated_at else None,
                        "dados_dependente": None  # Será preenchido abaixo
                    }
                    pacientes.append(paciente_dict)

            # Buscar todos os dependentes dos pacientes listados de uma vez (otimização)
            if paciente_ids:
                dependentes_query = f"""
                    SELECT {DEPENDENTE_COLS}
                    FROM dependentes 
                    WHERE responsavel_paciente_id = ANY(%s) AND ativo = TRUE
                    ORDER BY responsavel_paciente_id, created_at
                """
                cursor.execute(dependentes_query, (paciente_ids,))
                dependentes_rows = cursor.fetchall()
                
                # Criar um mapa de responsavel_id -> dependente
                dependentes_map = {}
                for dep_row in dependentes_rows:
                    dependente = _map_row_to_dependente_read(dep_row)
                    if dependente and dependente.responsavel_paciente_id not in dependentes_map:
                        # Pegar apenas o primeiro dependente ativo de cada responsável
                        dependentes_map[dependente.responsavel_paciente_id] = {
                            "dependente_id": dependente.dependente_id,
                            "responsavel_paciente_id": dependente.responsavel_paciente_id,
                            "nome_dependente": dependente.nome_dependente,
                            "data_nascimento_dependente": dependente.data_nascimento_dependente.isoformat() if dependente.data_nascimento_dependente else None,
                            "genero_dependente": dependente.genero_dependente,
                            "parentesco": dependente.parentesco,
                            "observacoes_dependente": dependente.observacoes_dependente,
                            "ativo": dependente.ativo,
                            "created_at": dependente.created_at.isoformat() if dependente.created_at else None,
                            "updated_at": dependente.updated_at.isoformat() if dependente.updated_at else None
                        }
                
                # Associar dependentes aos pacientes
                for paciente in pacientes:
                    if paciente["id"] in dependentes_map:
                        paciente["dados_dependente"] = dependentes_map[paciente["id"]]
            
            # Calcular páginas
            total_pages = (total + limit - 1) // limit if limit > 0 else 1
            current_page = (skip // limit) + 1 if limit > 0 else 1
            
            logger.info(f"Encontrados {len(pacientes)} pacientes de {total} total")
            
            return {
                "pacientes": pacientes,
                "total": total,
                "page": current_page,
                "per_page": limit,
                "total_pages": total_pages
            }
            
    except psycopg2.Error as exc:
        logger.error(
            "Erro DB ao listar pacientes integrados. error_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Erro de banco de dados."
        ) from None
    except Exception as exc:
        logger.error(
            "Erro inesperado ao listar pacientes integrados. error_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao listar pacientes."
        ) from None
    
@router.get("/{paciente_id}", response_model=dict)
async def obter_paciente_integrado(paciente_id: int, request: Request):
    """
    Obtém um paciente específico por ID no formato compatível com o frontend.
    """
    unit_scope = _resolve_read_unit_scope(request)
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            query = f"SELECT {PACIENTE_COLS} FROM pacientes WHERE paciente_id = %s"
            params = [paciente_id]
            if unit_scope is not None:
                query += " AND unidade = ANY(%s)"
                params.append(list(patient_unit_storage_values(unit_scope)))
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Paciente com ID {paciente_id} não encontrado"
                )
            
            paciente = _map_row_to_paciente_read(row)
            
            # Retornar no formato esperado pelo frontend (tipo Paciente)
            return {
                "id": paciente.paciente_id,
                "nome": paciente.nome_paciente,
                "cpf": paciente.cpf_cnpj,
                "telefone": f"({paciente.phone_area_code or ''}) {paciente.phone_number or ''}".strip(),
                "email": paciente.email,
                "data_nascimento": paciente.data_nascimento,
                "endereco": paciente.street,
                "numero": paciente.street_number,
                "complemento": paciente.line_two,
                "bairro": paciente.neighborhood,
                "cidade": paciente.city,
                "estado": paciente.state,
                "cep": paciente.zip_code,
                "nome_responsavel": "",
                "cpf_responsavel": "",
                "telefone_responsavel": "",
                "observacoes": paciente.observacoes,
                "midia_origem": paciente.midia_origem,
                "street_id": paciente.street_id,
                "unidade": paciente.unidade,
                "ativo": True,
                "created_at": paciente.created_at.isoformat() if paciente.created_at else None,
                "updated_at": paciente.updated_at.isoformat() if paciente.updated_at else None
            }
            
    except psycopg2.Error as exc:
        logger.error(
            "Erro DB ao obter paciente integrado. paciente_id=%s error_type=%s",
            paciente_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Erro de banco de dados."
        ) from None
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Erro inesperado ao obter paciente integrado. paciente_id=%s error_type=%s",
            paciente_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao obter paciente."
        ) from None

@router.get("/{responsavel_paciente_id}/dependentes", response_model=List[DependenteRead])
async def listar_dependentes_do_responsavel(
    responsavel_paciente_id: int,
    request: Request
):
    """ Lista todos os dependentes ativos de um paciente responsável específico. """
    unit_scope = _resolve_read_unit_scope(request)
    
    logger.info(f"Listando dependentes para o responsável ID: {responsavel_paciente_id}")
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT paciente_id FROM pacientes WHERE paciente_id = %s"
            params = [responsavel_paciente_id]
            if unit_scope is not None:
                query += " AND unidade = ANY(%s)"
                params.append(list(patient_unit_storage_values(unit_scope)))
            cursor.execute(query, tuple(params))
            
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Responsável com ID {responsavel_paciente_id} não encontrado.")
            
            query = f"SELECT {DEPENDENTE_COLS} FROM dependentes WHERE responsavel_paciente_id = %s AND ativo = TRUE ORDER BY nome_dependente"
            cursor.execute(query, (responsavel_paciente_id,))
            rows = cursor.fetchall()
            
            dependentes = [_map_row_to_dependente_read(row) for row in rows if row is not None]
            logger.info(f"Encontrados {len(dependentes)} dependentes para o responsável ID: {responsavel_paciente_id}")
            return dependentes
            
    except psycopg2.Error as db_err:
        logger.error(
            "Erro DB ao listar dependentes. responsavel_id=%s error_type=%s",
            responsavel_paciente_id,
            type(db_err).__name__,
        )
        raise HTTPException(status_code=500, detail="Erro de banco de dados.") from None
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Erro inesperado ao listar dependentes. responsavel_id=%s error_type=%s",
            responsavel_paciente_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao listar dependentes.",
        ) from None

@router.post("/{responsavel_paciente_id}/dependentes", response_model=DependenteRead, status_code=status.HTTP_201_CREATED)
async def criar_dependente_para_responsavel_existente(
    responsavel_paciente_id: int,
    dados_dependente: DadosDependenteModel,
    request: Request,
):
    """
    Cria um novo dependente para um paciente responsável já existente no sistema.
    O CPF do dependente não é armazenado. O vínculo é feito pelo responsavel_paciente_id.
    """
    logger.info("Criando dependente para responsável ID=%s", responsavel_paciente_id)
    unit_scope = _resolve_read_unit_scope(request)

    if not dados_dependente.nome_dependente: # Validação extra, embora Pydantic já faça.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome do dependente é obrigatório."
        )

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        try:
            # 1. Verificar se o paciente responsável existe
            query = "SELECT paciente_id FROM pacientes WHERE paciente_id = %s"
            params = [responsavel_paciente_id]
            if unit_scope is not None:
                query += " AND unidade = ANY(%s)"
                params.append(list(patient_unit_storage_values(unit_scope)))
            cursor.execute(query, tuple(params))
            responsavel_existente = cursor.fetchone()
            if not responsavel_existente:
                logger.warning(f"Responsável com ID {responsavel_paciente_id} não encontrado.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Paciente responsável com ID {responsavel_paciente_id} não encontrado."
                )
            logger.info(f"Responsável ID {responsavel_paciente_id} encontrado. Prosseguindo com cadastro do dependente.")

            # 2. Inserir o novo dependente
            # Colunas: dependente_id (SERIAL), responsavel_paciente_id, nome_dependente, data_nascimento_dependente,
            # genero_dependente, parentesco, observacoes_dependente, ativo (DEFAULT TRUE),
            # created_at (DEFAULT NOW()), updated_at (DEFAULT NOW())
            
            # DEPENDENTE_COLS_INSERT omite dependente_id, ativo, created_at, updated_at pois são gerenciados pelo BD ou tem default
            dependente_cols_insert = """
                responsavel_paciente_id, nome_dependente, data_nascimento_dependente,
                genero_dependente, parentesco, observacoes_dependente
            """ # ativo, created_at e updated_at terão seus defaults no BD
            
            query_insert_dependente = f"""
                INSERT INTO dependentes ({dependente_cols_insert})
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING {DEPENDENTE_COLS}; 
            """
            # Nota: ativo, created_at, updated_at usarão defaults da tabela.
            # Se precisarmos definir 'ativo' explicitamente no insert:
            # query_insert_dependente = f"""
            #     INSERT INTO dependentes (
            #         responsavel_paciente_id, nome_dependente, data_nascimento_dependente,
            #         genero_dependente, parentesco, observacoes_dependente, ativo
            #     )
            #     VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            #     RETURNING {DEPENDENTE_COLS};
            # """

            dependente_data_tuple = (
                responsavel_paciente_id,
                dados_dependente.nome_dependente,
                dados_dependente.data_nascimento_dependente,
                dados_dependente.genero_dependente,
                dados_dependente.parentesco,
                dados_dependente.observacoes_dependente
            )
            
            logger.debug(
                "Inserindo dependente para responsavel. paciente_id=%s",
                responsavel_paciente_id,
            )
            cursor.execute(query_insert_dependente, dependente_data_tuple)
            novo_dependente_row = cursor.fetchone()
            
            if not novo_dependente_row:
                logger.error("Falha ao inserir dependente, RETURNING não trouxe resultados.")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Falha ao criar o dependente após a inserção."
                )
            
            conn.commit()
            logger.info("Dependente ID=%s criado para responsável ID=%s", novo_dependente_row[0], responsavel_paciente_id)
            
            return _map_row_to_dependente_read(novo_dependente_row)

        except psycopg2.Error as exc:
            conn.rollback()
            logger.error(
                "Erro DB ao criar dependente. responsavel_id=%s error_type=%s",
                responsavel_paciente_id,
                type(exc).__name__,
            )
            # Verificar se é um erro de FK violada para o responsável (embora já checado)
            if exc.pgcode == '23503': # foreign_key_violation
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Paciente responsável com ID {responsavel_paciente_id} não encontrado ou inválido.")
            raise HTTPException(status_code=500, detail="Erro interno de banco de dados.") from None
        except HTTPException: # Re-raise HTTPExceptions para não serem capturadas como erro 500 genérico
            raise
        except Exception as exc:
            conn.rollback()
            logger.error(
                "Erro inesperado ao criar dependente. responsavel_id=%s error_type=%s",
                responsavel_paciente_id,
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=500,
                detail="Erro inesperado no servidor.",
            ) from None
        finally:
            cursor.close()

@router.put("/{paciente_id}", response_model=dict)
async def atualizar_paciente_integrado(paciente_id: int, data: PacienteCreate, request: Request):
    """
    Atualiza dados de um paciente de forma integrada (Delta OBRIGATÓRIA):
    1. PRIMEIRO: Valida e atualiza na Delta (crítico - CPF deve ser válido)
    2. SEGUNDO: Se Delta OK → atualiza no banco local
    3. Se Delta falhar → FALHA TUDO (não atualiza local)
    """
    logger.info(f"Atualizando paciente integrado ID={paciente_id}")
    unidade = _resolve_request_unit(request, data.unidade)
    logger.info("Atualizando paciente. paciente_id=%s unidade=%s", paciente_id, unidade)

    if _async_patient_integration_enabled(unidade):
        return _update_patient_with_async_integrations(paciente_id, data, unidade)
    
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Buscar paciente atual
            cursor.execute(f"SELECT {PACIENTE_COLS} FROM pacientes WHERE paciente_id = %s FOR UPDATE", (paciente_id,))
            current_row = cursor.fetchone()
            if not current_row:
                raise HTTPException(status_code=404, detail="Paciente não encontrado.")
            
            current_paciente = _map_row_to_paciente_read(current_row)
            _ensure_patient_unit_access(current_paciente.unidade, unidade)
            ensure_remote_identities_before_document_change(
                cursor,
                paciente_id=paciente_id,
                unidade=unidade,
                current_document=current_paciente.cpf_cnpj,
                requested_document=data.cpf_cnpj,
            )
            logger.info("Paciente atual localizado. paciente_id=%s", paciente_id)

            # Verificar CPF duplicado
            if data.cpf_cnpj != current_paciente.cpf_cnpj:
                cursor.execute("SELECT paciente_id FROM pacientes WHERE cpf_cnpj = %s AND paciente_id <> %s", (data.cpf_cnpj, paciente_id))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="CPF/CNPJ já pertence a outro paciente.")

            # 🎯 CRÍTICO: Tentar Delta PRIMEIRO (validação de CPF obrigatória)
            logger.info("Validando atualizacao do paciente na Delta")
            
            # Transformar dados para formato Delta
            delta_data = transform_to_delta_format(data.model_dump())
            
            # Validar dados
            is_valid, validation_errors = validate_patient_data(delta_data)
            if not is_valid:
                logger.warning("Dados locais invalidos para atualizacao Delta")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Dados inválidos para Delta: {', '.join(validation_errors)}"
                )
            
            # 🚨 MOMENTO CRÍTICO: Atualizar na Delta
            patient_api = _get_patient_sdk_client(unidade)
            try:
                patient_api.update_patient(current_paciente.cpf_cnpj, delta_data)
                logger.info("Paciente atualizado na Delta")
            except DeltaValidationError:
                logger.warning("Delta rejeitou atualizacao de paciente")
                raise HTTPException(
                    status_code=400,
                    detail="Delta rejeitou os dados do paciente.",
                ) from None
            except DeltaConnectionError:
                logger.warning("Falha de comunicacao com Delta na atualizacao")
                raise HTTPException(
                    status_code=503,
                    detail="Integração com Delta temporariamente indisponível.",
                ) from None
            except DeltaAPIError as exc:
                logger.warning("Delta recusou atualizacao. status=%s", exc.status_code)
                if exc.status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail="Paciente não encontrado na Delta. Não é possível atualizar."
                    ) from None
                raise HTTPException(
                    status_code=502,
                    detail="Não foi possível atualizar o paciente na Delta.",
                ) from None
            finally:
                patient_api.close()

            # 🎯 SEGUNDO: Delta OK → Atualizar no banco local
            logger.info(f"💾 ATUALIZANDO LOCAL: Delta aprovada, atualizando banco")
            
            query = f"""
                UPDATE pacientes
                SET
                    nome_paciente = %s, cpf_cnpj = %s, email = %s, data_nascimento = %s, is_minor = %s,
                    responsavel_id = %s, phone_country_code = %s, phone_area_code = %s, phone_number = %s,
                    street = %s, street_number = %s, line_two = %s, neighborhood = %s, city = %s, state = %s, zip_code = %s,
                    unidade = %s, rg_ie = %s, genero = %s, observacoes = %s, midia_origem = %s, street_id = %s,
                    updated_at = GREATEST(
                        clock_timestamp() AT TIME ZONE 'UTC',
                        updated_at + INTERVAL '1 microsecond'
                    ),
                    delta_integration_status = %s
                WHERE paciente_id = %s
                RETURNING {PACIENTE_COLS};
            """
            
            values = (
                data.nome_paciente, data.cpf_cnpj, data.email, data.data_nascimento, data.is_minor,
                data.responsavel_id, data.phone_country_code, data.phone_area_code, data.phone_number,
                data.street, data.street_number, data.line_two, data.neighborhood, data.city, data.state, data.zip_code,
                unidade, data.rg_ie, data.genero, data.observacoes, data.midia_origem,
                getattr(data, 'street_id', None),  # street_id
                "atualizado_integrado",  # delta_integration_status
                paciente_id  # WHERE clause
            )
            
            try:
                cursor.execute(query, values)
                row = cursor.fetchone()
                conn.commit()
                
                if not row:
                    raise HTTPException(status_code=404, detail="Paciente não encontrado durante atualização.")
                
                paciente_updated = _map_row_to_paciente_read(row)
                
                # Retornar formato frontend
                result = {
                    "id": paciente_updated.paciente_id,
                    "nome": paciente_updated.nome_paciente,
                    "cpf": paciente_updated.cpf_cnpj,
                    "telefone": f"{paciente_updated.phone_area_code or ''}{paciente_updated.phone_number or ''}",
                    "email": paciente_updated.email,
                    "data_nascimento": paciente_updated.data_nascimento,
                    "endereco": paciente_updated.street,
                    "numero": paciente_updated.street_number,
                    "complemento": paciente_updated.line_two,
                    "bairro": paciente_updated.neighborhood,
                    "cidade": paciente_updated.city,
                    "estado": paciente_updated.state,
                    "cep": paciente_updated.zip_code,
                    "observacoes": paciente_updated.observacoes,
                    "midia_origem": paciente_updated.midia_origem,
                    "street_id": paciente_updated.street_id,
                    "unidade": paciente_updated.unidade,
                    "ativo": True,
                    "created_at": paciente_updated.created_at.isoformat() if paciente_updated.created_at else None,
                    "updated_at": paciente_updated.updated_at.isoformat() if paciente_updated.updated_at else None,
                    "delta_integration_status": "atualizado_integrado"
                }
                
                logger.info(f"🎉 SUCESSO TOTAL: Paciente {paciente_id} atualizado em ambos sistemas")
                return result
                
            except psycopg2.Error as db_err:
                conn.rollback()
                logger.error(
                    "Erro DB apos atualizacao Delta. paciente_id=%s error_type=%s",
                    paciente_id,
                    type(db_err).__name__,
                )
                raise HTTPException(
                    status_code=500, 
                    detail=f"Erro crítico: Paciente atualizado na Delta mas falhou no banco local. Entre em contato com suporte."
                )
                
    except HTTPException:
        # Repassa HTTPExceptions
        raise
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
    except Exception as exc:
        logger.error(
            "Erro inesperado na atualizacao integrada. paciente_id=%s error_type=%s",
            paciente_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Erro interno na integração."
        ) from None
