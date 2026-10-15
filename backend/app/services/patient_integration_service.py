"""Orquestracao duravel da sincronizacao de pacientes com Delta e Asaas.

O request grava somente jobs tecnicos na mesma transacao do paciente. O worker
recarrega os dados pessoais diretamente do PostgreSQL depois de adquirir um
claim com fencing; nenhum payload pessoal passa pelo Redis ou e persistido na
outbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import logging
from typing import Any, Iterable, Literal, Optional

from psycopg2.errors import UniqueViolation

from app.asaas_sdk import (
    AsaasAPIError,
    AsaasConfig,
    AsaasConfigurationError,
    AsaasConnectionError,
    AsaasCustomerConflictError,
    AsaasSDK,
    AsaasValidationError,
    Environment as AsaasEnvironment,
)
from app.database.db import DatabaseConnection
from app.pacientes_sdk import (
    DeltaAPIError,
    DeltaConfigurationError,
    DeltaConnectionError,
    DeltaValidationError,
    PatientAPI,
    get_token_and_seller_for_unidade,
    transform_to_delta_format,
    validate_patient_data,
)
from app.services import asaas_patient_customer_service as asaas_links
from app.services import delta_patient_customer_service as delta_links
from app.services import patient_integration_job_service as jobs
from app.services.patient_integration_config import (
    PatientIntegrationConfigError,
    build_delta_target_key,
    canonicalize_patient_unit,
    get_patient_integration_environment,
    is_patient_integration_enabled,
)


logger = logging.getLogger(__name__)

Provider = Literal["delta", "asaas"]
SUPPORTED_PROVIDERS = frozenset({"delta", "asaas"})
MAX_ATTEMPTS = 8
PROCESSING_STALE_AFTER = timedelta(minutes=5)
FEATURE_DISABLED_RETRY_AFTER = timedelta(minutes=5)
_ASAAS_REMOTE_VALIDATION_ERROR_CODES = {
    "invalid_action": "asaas_invalid_action",
}


class PatientIntegrationDataError(ValueError):
    """Dados locais nao atendem ao contrato minimo dos provedores."""


class PatientIntegrationIdentityPendingError(PatientIntegrationDataError):
    """Uma mutacao de identidade exige vinculo remoto previamente resolvido."""


class _AsaasLinkBusyError(RuntimeError):
    pass


class _DeltaCustomerConflictError(RuntimeError):
    status_code = 409


class _IntegrationClaimLostError(RuntimeError):
    pass


@dataclass(frozen=True)
class PatientSnapshot:
    paciente_id: int
    nome_paciente: str
    cpf_cnpj: str
    email: Optional[str]
    data_nascimento: Optional[date]
    is_minor: bool
    responsavel_id: Optional[int]
    phone_country_code: Optional[str]
    phone_area_code: Optional[str]
    phone_number: Optional[str]
    street: Optional[str]
    street_number: Optional[str]
    line_two: Optional[str]
    neighborhood: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    unidade: str
    updated_at: datetime


@dataclass(frozen=True)
class _FailureDecision:
    status: str
    error_code: str
    http_status: Optional[int]
    next_retry_at: Optional[datetime]


@dataclass(frozen=True)
class _AsaasClaim:
    link_id: int
    claim_attempt: int
    customer_id: Optional[str]
    remote_creation_allowed: bool


PATIENT_COLUMNS = """
    paciente_id,
    nome_paciente,
    cpf_cnpj,
    email,
    data_nascimento,
    is_minor,
    responsavel_id,
    phone_country_code,
    phone_area_code,
    phone_number,
    street,
    street_number,
    line_two,
    neighborhood,
    city,
    state,
    zip_code,
    unidade,
    updated_at
"""


def ensure_remote_identities_before_document_change(
    cursor: Any,
    *,
    paciente_id: int,
    unidade: str,
    current_document: Any,
    requested_document: Any,
) -> None:
    """Bloqueia troca de documento enquanto uma identidade remota estiver pendente.

    O chamador deve manter a linha de ``pacientes`` travada com ``FOR UPDATE``.
    Assim a reserva Delta segue paciente -> vinculo, e o vinculo Asaas tambem e
    travado aqui antes da mutacao local.
    """
    if _only_digits(current_document) == _only_digits(requested_document):
        return
    canonical_unit = canonicalize_patient_unit(unidade)
    if not canonical_unit:
        raise PatientIntegrationConfigError("Unidade de paciente nao reconhecida")
    if not is_patient_integration_enabled(canonical_unit):
        _ensure_disabled_unit_has_no_pending_identity(cursor, paciente_id)
        return

    environment = get_patient_integration_environment()
    target_key = build_delta_target_key(canonical_unit, environment)
    link = delta_links.get_delta_customer_link(
        cursor,
        paciente_id=paciente_id,
        environment=environment,
        target_key=target_key,
    )
    if link is None or not link.delta_customer_id:
        raise PatientIntegrationIdentityPendingError(
            "delta_identity_reconciliation_required"
        )

    asaas_config = _load_strict_asaas_config(canonical_unit, environment)
    wallet_id = _required_wallet_id(asaas_config)
    asaas_link = asaas_links.get_customer_link_for_update(
        cursor,
        paciente_id=paciente_id,
        environment=environment,
        account_wallet_id=wallet_id,
    )
    if asaas_link is None or not asaas_link.asaas_customer_id:
        raise PatientIntegrationIdentityPendingError(
            "asaas_identity_reconciliation_required"
        )


def _ensure_disabled_unit_has_no_pending_identity(
    cursor: Any,
    paciente_id: int,
) -> None:
    """Mantem o bloqueio depois que uma unidade integrada e desabilitada.

    Antes da migracao a consulta ao catalogo permanece inerte. A presenca de um
    vinculo Delta identifica que o paciente ja entrou no fluxo novo; nesse caso
    ambos os IDs devem estar resolvidos antes de permitir a troca de documento.
    """
    cursor.execute(
        """
        SELECT
            to_regclass('public.patient_delta_customers'),
            to_regclass('public.asaas_patient_customers')
        """
    )
    tables = cursor.fetchone()
    if not tables or tables[0] is None:
        return

    cursor.execute(
        """
        SELECT delta_customer_id
        FROM patient_delta_customers
        WHERE paciente_id = %s
        FOR UPDATE
        """,
        (paciente_id,),
    )
    delta_rows = cursor.fetchall()
    if not delta_rows:
        return
    if any(not str(row[0] or "").strip() for row in delta_rows):
        raise PatientIntegrationIdentityPendingError(
            "delta_identity_reconciliation_required"
        )

    if tables[1] is None:
        raise PatientIntegrationIdentityPendingError(
            "asaas_identity_reconciliation_required"
        )
    cursor.execute(
        """
        SELECT asaas_customer_id
        FROM asaas_patient_customers
        WHERE paciente_id = %s
        FOR UPDATE
        """,
        (paciente_id,),
    )
    asaas_rows = cursor.fetchall()
    if not asaas_rows or any(
        not str(row[0] or "").strip() for row in asaas_rows
    ):
        raise PatientIntegrationIdentityPendingError(
            "asaas_identity_reconciliation_required"
        )


def enqueue_patient_jobs_for_patient(
    cursor: Any,
    *,
    paciente_id: int,
    unidade: str,
    patient_version: datetime,
    providers: Iterable[str] = ("delta", "asaas"),
    confirmed_delta_customer_id: Optional[str] = None,
    allow_delta_customer_creation: bool = False,
    allow_asaas_customer_creation: bool = False,
) -> list[jobs.PatientIntegrationJobRecord]:
    """Grava jobs por provedor na transacao que persiste o paciente.

    A allowlist vazia retorna antes de consultar paciente, credenciais, vinculo
    Asaas ou tabela de jobs. As permissoes de criacao remota sao independentes
    para evitar que uma edicao autorizada no Asaas amplie o efeito para Delta.
    """
    canonical_unit = canonicalize_patient_unit(unidade)
    if not canonical_unit:
        raise PatientIntegrationConfigError("Unidade de paciente nao reconhecida")
    if not is_patient_integration_enabled(canonical_unit):
        return []

    normalized_providers = _normalize_providers(providers)
    if not isinstance(allow_delta_customer_creation, bool):
        raise PatientIntegrationConfigError(
            "allow_delta_customer_creation deve ser booleano"
        )
    if not isinstance(allow_asaas_customer_creation, bool):
        raise PatientIntegrationConfigError(
            "allow_asaas_customer_creation deve ser booleano"
        )
    if confirmed_delta_customer_id is not None and "delta" not in normalized_providers:
        raise PatientIntegrationConfigError(
            "Customer Delta confirmado exige o provider delta"
        )
    requested_version = _as_utc(patient_version, field="patient_version")
    requested_patient = _load_patient(cursor, paciente_id)
    if requested_patient is None:
        raise PatientIntegrationDataError("patient_not_found")

    effective_patient = _resolve_effective_patient(cursor, requested_patient)
    effective_unit = _canonical_snapshot_unit(effective_patient)
    if effective_unit != canonical_unit:
        raise PatientIntegrationDataError("patient_unit_mismatch")

    effective_version = _as_utc(
        effective_patient.updated_at,
        field="patient_updated_at",
    )
    if effective_patient.paciente_id == paciente_id and effective_version != requested_version:
        raise PatientIntegrationDataError("patient_version_mismatch")
    if (
        confirmed_delta_customer_id is not None
        and effective_patient.paciente_id != paciente_id
    ):
        raise PatientIntegrationDataError(
            "confirmed_delta_customer_requires_effective_patient"
        )
    _validate_patient(effective_patient)

    environment = get_patient_integration_environment()
    created_jobs: list[jobs.PatientIntegrationJobRecord] = []

    if "delta" in normalized_providers:
        _validate_delta_configuration(effective_unit, environment)
        delta_target_key = build_delta_target_key(effective_unit, environment)
        delta_link = delta_links.ensure_delta_customer_link(
            cursor,
            paciente_id=effective_patient.paciente_id,
            environment=environment,
            target_key=delta_target_key,
            allow_remote_create=(
                allow_delta_customer_creation
                and confirmed_delta_customer_id is None
                and effective_patient.paciente_id == paciente_id
            ),
        )
        delta_initial_status = "pendente"
        if confirmed_delta_customer_id is not None:
            try:
                delta_links.set_delta_customer_id(
                    cursor,
                    link_id=delta_link.id,
                    delta_customer_id=confirmed_delta_customer_id,
                )
            except UniqueViolation:
                raise PatientIntegrationDataError("delta_customer_owned") from None
            except ValueError:
                raise PatientIntegrationDataError("delta_customer_remap") from None
            delta_initial_status = "integrado"
        created_jobs.append(
            jobs.enqueue_patient_integration_job(
                cursor,
                paciente_id=effective_patient.paciente_id,
                provider="delta",
                target_key=delta_target_key,
                environment=environment,
                patient_version=effective_version,
                initial_status=delta_initial_status,
            )
        )
        if delta_initial_status == "pendente":
            cursor.execute(
                """
                UPDATE pacientes
                SET delta_integration_status = 'pendente'
                WHERE paciente_id = %s
                  AND updated_at = %s
                """,
                (effective_patient.paciente_id, effective_patient.updated_at),
            )

    if "asaas" in normalized_providers:
        asaas_config = _load_strict_asaas_config(effective_unit, environment)
        wallet_id = _required_wallet_id(asaas_config)
        link = asaas_links.ensure_customer_link(
            cursor,
            paciente_id=effective_patient.paciente_id,
            unidade=effective_unit,
            environment=environment,
            account_wallet_id=wallet_id,
            allow_remote_create=(
                allow_asaas_customer_creation
                and effective_patient.paciente_id == paciente_id
            ),
        )
        asaas_links.request_customer_sync(
            cursor,
            link_id=link.id,
            patient_updated_at=effective_version,
        )
        created_jobs.append(
            jobs.enqueue_patient_integration_job(
                cursor,
                paciente_id=effective_patient.paciente_id,
                provider="asaas",
                target_key=_build_asaas_target_key(environment, wallet_id),
                environment=environment,
                patient_version=effective_version,
            )
        )

    return created_jobs


def process_patient_integration_job(
    job_id: int,
    *,
    expected_provider: Provider,
) -> None:
    """Processa um job por ID sem manter conexao DB durante chamadas HTTP."""
    _validate_job_id(job_id)
    provider = _normalize_expected_provider(expected_provider)
    job = _get_job(job_id)
    if job is None:
        logger.info("Job de integracao inexistente. provider=%s job_id=%s", provider, job_id)
        return
    if job.provider != provider:
        logger.warning(
            "Job recebido na fila incorreta. provider=%s job_id=%s",
            provider,
            job_id,
        )
        return
    if job.status not in {"pendente", "retry", "processando"}:
        logger.debug(
            "Job de integracao ja encerrado. provider=%s job_id=%s status=%s",
            provider,
            job_id,
            job.status,
        )
        return

    try:
        preflight_patient = _load_effective_patient_by_id(job.paciente_id)
    except PatientIntegrationDataError:
        _claim_and_finish_without_http(job_id, provider, "patient_invalid")
        return
    if preflight_patient is None:
        _claim_and_finish_without_http(job_id, provider, "patient_not_found")
        return
    if preflight_patient.paciente_id != job.paciente_id:
        _claim_and_supersede(job_id, provider)
        return
    preflight_unit = canonicalize_patient_unit(preflight_patient.unidade)
    if not preflight_unit:
        _claim_and_finish_without_http(job_id, provider, "patient_unit_invalid")
        return

    try:
        enabled = is_patient_integration_enabled(preflight_unit)
    except PatientIntegrationConfigError:
        logger.error(
            "Allowlist de integracao invalida. provider=%s job_id=%s",
            provider,
            job_id,
        )
        return
    if not enabled:
        logger.info(
            "Job mantido aguardando habilitacao. provider=%s job_id=%s unidade=%s",
            provider,
            job_id,
            preflight_unit,
        )
        return
    try:
        current_environment = get_patient_integration_environment()
    except PatientIntegrationConfigError:
        logger.error(
            "Ambiente de integracao invalido. provider=%s job_id=%s",
            provider,
            job_id,
        )
        return
    if current_environment != job.environment:
        _claim_and_finish_without_http(
            job_id,
            provider,
            "environment_mismatch",
        )
        return

    claimed = _claim_job(job_id)
    if claimed is None:
        logger.debug("Job sem claim elegivel. provider=%s job_id=%s", provider, job_id)
        return

    try:
        current_patient = _load_effective_patient_by_id(claimed.paciente_id)
    except PatientIntegrationDataError:
        _mark_job_terminal(claimed, "patient_invalid")
        return
    if current_patient is None:
        _mark_job_terminal(claimed, "patient_not_found")
        return
    if current_patient.paciente_id != claimed.paciente_id:
        _mark_job_superseded(claimed)
        return

    try:
        current_version = _as_utc(
            current_patient.updated_at,
            field="patient_updated_at",
        )
        claimed_version = _as_utc(
            claimed.patient_version,
            field="patient_version",
        )
    except PatientIntegrationDataError:
        _mark_job_terminal(claimed, "patient_version_invalid")
        return
    if current_version > claimed_version:
        _mark_job_superseded(claimed)
        return
    if current_version < claimed_version:
        _mark_job_terminal(claimed, "patient_version_invalid")
        return

    current_unit = canonicalize_patient_unit(current_patient.unidade)
    if not current_unit:
        _mark_job_terminal(claimed, "patient_unit_invalid")
        return
    try:
        if not is_patient_integration_enabled(current_unit):
            _mark_job_retry_after_feature_disable(claimed)
            return
        _validate_patient(current_patient)
    except PatientIntegrationConfigError:
        _mark_job_retry_after_feature_disable(claimed)
        return
    except PatientIntegrationDataError:
        _mark_job_terminal(claimed, "patient_invalid")
        return

    if provider == "delta":
        _process_delta(claimed, current_patient, current_unit)
    else:
        _process_asaas(claimed, current_patient, current_unit)


def _process_delta(
    job: jobs.PatientIntegrationJobRecord,
    patient: PatientSnapshot,
    unidade: str,
) -> None:
    link = None
    try:
        expected_target = build_delta_target_key(unidade, job.environment)
        if expected_target != job.target_key:
            _mark_job_superseded(job)
            return

        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            link = delta_links.get_delta_customer_link(
                cursor,
                paciente_id=job.paciente_id,
                environment=job.environment,
                target_key=job.target_key,
            )
        if link is None:
            raise PatientIntegrationDataError("delta_link_not_found")

        token, seller_id = get_token_and_seller_for_unidade(unidade, job.environment)
        payload = transform_to_delta_format(_snapshot_payload(patient))
        is_valid, _ = validate_patient_data(payload)
        if not is_valid:
            raise DeltaValidationError(["patient_invalid"])

        # Nao ha conexao com o PostgreSQL aberta durante a chamada externa.
        with PatientAPI(token, seller_id, job.environment) as patient_api:
            known_customer_id = link.delta_customer_id
            if known_customer_id is None:
                existing = patient_api.get_patient_by_document(payload["document"])
                if existing is not None:
                    known_customer_id = patient_api.extract_customer_id(existing)
                    if known_customer_id is None:
                        raise DeltaAPIError(502, detail="Resposta invalida da API")
                    _reserve_delta_customer_id(
                        job,
                        link_id=link.id,
                        customer_id=known_customer_id,
                    )
                elif not link.remote_creation_allowed:
                    raise _DeltaCustomerConflictError(
                        "delta_identity_reconciliation_required"
                    )

            try:
                if known_customer_id is None:
                    # A ausencia foi confirmada imediatamente antes. Criar
                    # diretamente impede que uma corrida entre outro lookup e
                    # um PUT aproprie um customer ja vinculado localmente.
                    result = patient_api.create_patient(payload)
                else:
                    result = patient_api.sync_patient(
                        payload,
                        known_customer_id=known_customer_id,
                    )
            except DeltaAPIError as exc:
                if known_customer_id is not None and exc.status_code == 404:
                    raise _DeltaCustomerConflictError(
                        "delta_customer_missing"
                    ) from None
                raise
            customer_id = patient_api.extract_customer_id(result)
            if customer_id is None:
                recovered = patient_api.get_patient_by_document(payload["document"])
                if recovered is not None:
                    customer_id = patient_api.extract_customer_id(recovered)
            if customer_id is None:
                raise DeltaAPIError(502, detail="Resposta invalida da API")

        # Reserva a identidade antes da conclusao. Se outro paciente ja for o
        # dono do ID, a colisao termina como conflito sem repetir um PUT.
        _reserve_delta_customer_id(
            job,
            link_id=link.id,
            customer_id=customer_id,
        )
    except _IntegrationClaimLostError:
        logger.info(
            "Claim perdido antes da conclusao. provider=delta job_id=%s",
            job.id,
        )
        return
    except Exception as exc:
        _record_provider_failure(job, "delta", exc)
        return

    try:
        _mark_delta_and_job_integrated(
            job,
            link_id=link.id,
            customer_id=customer_id,
        )
    except (UniqueViolation, ValueError):
        _record_provider_failure(
            job,
            "delta",
            _DeltaCustomerConflictError("delta_customer_remap"),
        )
        return
    except LookupError:
        logger.info(
            "Claim perdido durante conclusao. provider=delta job_id=%s",
            job.id,
        )
        return
    logger.info(
        "Paciente sincronizado. provider=delta job_id=%s paciente_id=%s unidade=%s attempt=%s",
        job.id,
        job.paciente_id,
        unidade,
        job.attempt_count,
    )


def _process_asaas(
    job: jobs.PatientIntegrationJobRecord,
    patient: PatientSnapshot,
    unidade: str,
) -> None:
    link_claim: Optional[_AsaasClaim] = None
    try:
        config = _load_strict_asaas_config(unidade, job.environment)
        wallet_id = _required_wallet_id(config)
        if _build_asaas_target_key(job.environment, wallet_id) != job.target_key:
            _mark_job_superseded(job)
            return

        link_claim, already_integrated = _claim_asaas_link(job, wallet_id)
        if already_integrated:
            _mark_job_integrated(job)
            return
        if link_claim is None:
            raise _AsaasLinkBusyError("asaas_link_busy")

        customer_payload = transform_to_delta_format(_snapshot_payload(patient))
        customer_payload["externalReference"] = asaas_links.build_external_reference(
            patient.paciente_id
        )
        notification_disabled = job.environment == "sandbox"
        customer_payload["notificationDisabled"] = notification_disabled

        # Nao ha conexao com o PostgreSQL aberta durante a chamada externa.
        with AsaasSDK(config) as sdk:
            customer_manager = sdk.customer_manager
            known_customer_id = link_claim.customer_id
            if known_customer_id is None:
                existing = customer_manager.find_existing_customer(customer_payload)
                if existing is not None:
                    known_customer_id = str(existing.get("id") or "").strip()
                    if not known_customer_id:
                        raise AsaasAPIError(502, detail="invalid_customer_response")
                    _reserve_asaas_customer_id(
                        link_claim,
                        customer_id=known_customer_id,
                    )
                    link_claim = _AsaasClaim(
                        link_id=link_claim.link_id,
                        claim_attempt=link_claim.claim_attempt,
                        customer_id=known_customer_id,
                        remote_creation_allowed=False,
                    )
                elif not link_claim.remote_creation_allowed:
                    raise AsaasCustomerConflictError(
                        "identity_reconciliation_required"
                    )

            if known_customer_id is None:
                customer = customer_manager.create_customer(customer_payload)
            else:
                customer = customer_manager.sync_customer(
                    customer_payload,
                    known_customer_id=known_customer_id,
                )
            customer_id = str(customer.get("id") or "").strip()
            if not customer_id:
                raise AsaasAPIError(502, detail="invalid_customer_response")

            # Reserva a identidade antes de qualquer outra mutacao remota. Se
            # a configuracao falhar, o retry reutiliza o mesmo customer.
            _reserve_asaas_customer_id(link_claim, customer_id=customer_id)
            link_claim = _AsaasClaim(
                link_id=link_claim.link_id,
                claim_attempt=link_claim.claim_attempt,
                customer_id=customer_id,
                remote_creation_allowed=False,
            )
            if customer.get("notificationDisabled") is not notification_disabled:
                raise AsaasAPIError(
                    502,
                    detail="notification_policy_not_applied",
                )
            if job.environment == "production":
                sdk.notification_manager.apply_full_notification_policy(customer_id)
    except _IntegrationClaimLostError:
        logger.info(
            "Claim perdido antes da conclusao. provider=asaas job_id=%s",
            job.id,
        )
        return
    except Exception as exc:
        _record_provider_failure(job, "asaas", exc, link_claim=link_claim)
        return

    try:
        _mark_asaas_and_job_integrated(
            job,
            link_claim=link_claim,
            customer_id=customer_id,
        )
    except UniqueViolation:
        _record_provider_failure(
            job,
            "asaas",
            AsaasCustomerConflictError("customer_remap"),
            link_claim=link_claim,
        )
        return
    except LookupError:
        logger.info(
            "Claim perdido durante conclusao. provider=asaas job_id=%s",
            job.id,
        )
        return
    logger.info(
        "Paciente sincronizado. provider=asaas job_id=%s paciente_id=%s unidade=%s attempt=%s",
        job.id,
        job.paciente_id,
        unidade,
        job.attempt_count,
    )


def _claim_asaas_link(
    job: jobs.PatientIntegrationJobRecord,
    wallet_id: str,
) -> tuple[Optional[_AsaasClaim], bool]:
    stale_before = datetime.now(timezone.utc) - PROCESSING_STALE_AFTER
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        link = asaas_links.get_customer_link(
            cursor,
            paciente_id=job.paciente_id,
            environment=job.environment,
            account_wallet_id=wallet_id,
        )
        if link is None:
            raise PatientIntegrationDataError("asaas_link_not_found")
        claimed_link = asaas_links.claim_customer_sync(
            cursor,
            link_id=link.id,
            stale_before=stale_before,
        )
        if claimed_link is not None:
            return (
                _AsaasClaim(
                    link_id=claimed_link.id,
                    claim_attempt=claimed_link.attempt_count,
                    customer_id=claimed_link.asaas_customer_id,
                    remote_creation_allowed=claimed_link.remote_creation_allowed,
                ),
                False,
            )

        refreshed = asaas_links.get_customer_link(
            cursor,
            paciente_id=job.paciente_id,
            environment=job.environment,
            account_wallet_id=wallet_id,
        )
        if (
            refreshed is not None
            and refreshed.status == "integrado"
            and refreshed.last_synced_patient_updated_at is not None
            and _as_utc(
                refreshed.last_synced_patient_updated_at,
                field="last_synced_patient_updated_at",
            )
            >= _as_utc(job.patient_version, field="patient_version")
        ):
            return None, True
        return None, False


def _reserve_delta_customer_id(
    job: jobs.PatientIntegrationJobRecord,
    *,
    link_id: int,
    customer_id: str,
) -> None:
    """Reserva o ID com a mesma ordem de locks usada pelas rotas."""
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT paciente_id
                FROM pacientes
                WHERE paciente_id = %s
                FOR UPDATE
                """,
                (job.paciente_id,),
            )
            if not cursor.fetchone():
                raise PatientIntegrationDataError("patient_not_found")
            try:
                delta_links.set_delta_customer_id(
                    cursor,
                    link_id=link_id,
                    delta_customer_id=customer_id,
                )
            except ValueError:
                raise _DeltaCustomerConflictError("delta_customer_remap") from None
            cursor.execute(
                """
                SELECT id
                FROM patient_integration_jobs
                WHERE id = %s
                  AND status = 'processando'
                  AND attempt_count = %s
                FOR UPDATE
                """,
                (job.id, job.attempt_count),
            )
            if not cursor.fetchone():
                raise _IntegrationClaimLostError("delta_job_claim_lost")
    except UniqueViolation:
        raise _DeltaCustomerConflictError("delta_customer_owned") from None


def _reserve_asaas_customer_id(
    link_claim: _AsaasClaim,
    *,
    customer_id: str,
) -> None:
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            asaas_links.reserve_customer_id(
                cursor,
                link_id=link_claim.link_id,
                claim_attempt=link_claim.claim_attempt,
                asaas_customer_id=customer_id,
            )
    except UniqueViolation:
        raise AsaasCustomerConflictError("customer_owned") from None
    except LookupError:
        if _asaas_link_claim_is_current(link_claim):
            raise AsaasCustomerConflictError("customer_remap") from None
        raise _IntegrationClaimLostError("asaas_link_claim_lost") from None


def _asaas_link_claim_is_current(link_claim: _AsaasClaim) -> bool:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM asaas_patient_customers
            WHERE id = %s
              AND status = 'processando'
              AND attempt_count = %s
            LIMIT 1
            """,
            (link_claim.link_id, link_claim.claim_attempt),
        )
        return cursor.fetchone() is not None


def _record_provider_failure(
    job: jobs.PatientIntegrationJobRecord,
    provider: Provider,
    exc: Exception,
    *,
    link_claim: Optional[_AsaasClaim] = None,
) -> None:
    decision = _classify_failure(
        provider,
        exc,
        attempt_count=job.attempt_count,
        job_id=job.id,
    )
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        if provider == "asaas" and link_claim is not None:
            asaas_links.mark_customer_failed(
                cursor,
                link_id=link_claim.link_id,
                claim_attempt=link_claim.claim_attempt,
                error_code=decision.error_code,
                http_status=decision.http_status,
                next_retry_at=decision.next_retry_at,
                status="conflito" if decision.status == "conflito" else "erro",
                patient_updated_at=_as_utc(
                    job.patient_version,
                    field="patient_version",
                ),
            )
        if provider == "delta" and decision.status != "retry":
            cursor.execute(
                """
                UPDATE pacientes
                SET delta_integration_status = 'erro_integracao'
                WHERE paciente_id = %s
                  AND updated_at = %s
                """,
                (job.paciente_id, job.patient_version),
            )
        jobs.mark_job_failed(
            cursor,
            job_id=job.id,
            claim_attempt=job.attempt_count,
            error_code=decision.error_code,
            status=decision.status,
            http_status=decision.http_status,
            next_retry_at=decision.next_retry_at,
        )

    logger.warning(
        "Falha controlada na integracao. provider=%s job_id=%s paciente_id=%s "
        "attempt=%s status=%s http_status=%s error_code=%s error_type=%s",
        provider,
        job.id,
        job.paciente_id,
        job.attempt_count,
        decision.status,
        decision.http_status,
        decision.error_code,
        type(exc).__name__,
    )


def _classify_failure(
    provider: Provider,
    exc: Exception,
    *,
    attempt_count: int,
    job_id: int,
) -> _FailureDecision:
    http_status = _safe_http_status(getattr(exc, "status_code", None))

    if isinstance(exc, AsaasCustomerConflictError):
        return _FailureDecision("conflito", "asaas_conflict", None, None)
    if isinstance(exc, _DeltaCustomerConflictError):
        return _FailureDecision("conflito", "delta_conflict", 409, None)

    if isinstance(exc, AsaasValidationError) and http_status in {400, 422}:
        remote_errors = getattr(exc, "errors", None)
        if isinstance(remote_errors, list) and len(remote_errors) == 1:
            controlled_error_code = _ASAAS_REMOTE_VALIDATION_ERROR_CODES.get(
                remote_errors[0]
            )
            if controlled_error_code is not None:
                return _FailureDecision(
                    "erro_terminal",
                    controlled_error_code,
                    http_status,
                    None,
                )

    terminal_types = (
        PatientIntegrationDataError,
        PatientIntegrationConfigError,
        AsaasConfigurationError,
        AsaasValidationError,
        DeltaConfigurationError,
        DeltaValidationError,
        ValueError,
    )
    if isinstance(exc, terminal_types):
        return _FailureDecision(
            "erro_terminal",
            f"{provider}_validation",
            http_status,
            None,
        )

    if isinstance(exc, (AsaasConnectionError, DeltaConnectionError, _AsaasLinkBusyError)):
        return _retry_or_terminal(
            provider,
            "link_busy" if isinstance(exc, _AsaasLinkBusyError) else "connection",
            attempt_count=attempt_count,
            job_id=job_id,
            http_status=http_status,
        )

    if isinstance(exc, (AsaasAPIError, DeltaAPIError)):
        if http_status in {400, 401, 403, 422}:
            suffix = "auth" if http_status in {401, 403} else "validation"
            return _FailureDecision(
                "erro_terminal",
                f"{provider}_{suffix}",
                http_status,
                None,
            )
        if http_status in {404, 408, 409, 425, 429} or (
            http_status is not None and http_status >= 500
        ):
            return _retry_or_terminal(
                provider,
                "remote",
                attempt_count=attempt_count,
                job_id=job_id,
                http_status=http_status,
            )
        return _FailureDecision(
            "erro_terminal",
            f"{provider}_remote",
            http_status,
            None,
        )

    return _retry_or_terminal(
        provider,
        "unexpected",
        attempt_count=attempt_count,
        job_id=job_id,
        http_status=http_status,
    )


def _retry_or_terminal(
    provider: Provider,
    suffix: str,
    *,
    attempt_count: int,
    job_id: int,
    http_status: Optional[int],
) -> _FailureDecision:
    error_code = f"{provider}_{suffix}"
    if attempt_count >= MAX_ATTEMPTS:
        return _FailureDecision("erro_terminal", error_code, http_status, None)
    return _FailureDecision(
        "retry",
        error_code,
        http_status,
        _next_retry_at(attempt_count, job_id),
    )


def _next_retry_at(attempt_count: int, job_id: int) -> datetime:
    exponent = max(0, min(attempt_count - 1, 7))
    delay_seconds = min(3600, 30 * (2**exponent))
    deterministic_jitter = job_id % 17
    return datetime.now(timezone.utc) + timedelta(
        seconds=delay_seconds + deterministic_jitter
    )


def _mark_asaas_and_job_integrated(
    job: jobs.PatientIntegrationJobRecord,
    *,
    link_claim: Optional[_AsaasClaim],
    customer_id: str,
) -> None:
    if link_claim is None:
        raise RuntimeError("asaas_link_claim_missing")
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        asaas_links.mark_customer_integrated(
            cursor,
            link_id=link_claim.link_id,
            claim_attempt=link_claim.claim_attempt,
            asaas_customer_id=customer_id,
            patient_updated_at=_as_utc(job.patient_version, field="patient_version"),
        )
        jobs.mark_job_integrated(
            cursor,
            job_id=job.id,
            claim_attempt=job.attempt_count,
        )


def _mark_delta_and_job_integrated(
    job: jobs.PatientIntegrationJobRecord,
    *,
    link_id: int,
    customer_id: str,
) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        # Ordem global de locks: paciente -> link -> job. As rotas usam a
        # mesma sequencia ao persistir uma nova versao e criar a outbox.
        cursor.execute(
            """
            UPDATE pacientes
            SET delta_integration_status = 'integrado'
            WHERE paciente_id = %s
              AND updated_at = %s
            """,
            (job.paciente_id, job.patient_version),
        )
        delta_links.set_delta_customer_id(
            cursor,
            link_id=link_id,
            delta_customer_id=customer_id,
        )
        jobs.mark_job_integrated(
            cursor,
            job_id=job.id,
            claim_attempt=job.attempt_count,
        )


def _mark_job_integrated(job: jobs.PatientIntegrationJobRecord) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        if job.provider == "delta":
            cursor.execute(
                """
                UPDATE pacientes
                SET delta_integration_status = 'integrado'
                WHERE paciente_id = %s
                  AND updated_at = %s
                """,
                (job.paciente_id, job.patient_version),
            )
        jobs.mark_job_integrated(
            cursor,
            job_id=job.id,
            claim_attempt=job.attempt_count,
        )


def _mark_job_superseded(job: jobs.PatientIntegrationJobRecord) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        jobs.mark_job_superseded(
            cursor,
            job_id=job.id,
            claim_attempt=job.attempt_count,
        )


def _mark_job_terminal(
    job: jobs.PatientIntegrationJobRecord,
    error_code: str,
) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        if job.provider == "delta":
            cursor.execute(
                """
                UPDATE pacientes
                SET delta_integration_status = 'erro_integracao'
                WHERE paciente_id = %s
                  AND updated_at = %s
                """,
                (job.paciente_id, job.patient_version),
            )
        jobs.mark_job_failed(
            cursor,
            job_id=job.id,
            claim_attempt=job.attempt_count,
            error_code=error_code,
            status="erro_terminal",
        )


def _mark_job_retry_after_feature_disable(
    job: jobs.PatientIntegrationJobRecord,
) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        jobs.mark_job_failed(
            cursor,
            job_id=job.id,
            claim_attempt=job.attempt_count,
            error_code="feature_disabled",
            status="retry",
            next_retry_at=datetime.now(timezone.utc) + FEATURE_DISABLED_RETRY_AFTER,
        )


def _claim_and_finish_without_http(
    job_id: int,
    provider: Provider,
    error_code: str,
) -> None:
    claimed = _claim_job(job_id)
    if claimed is not None and claimed.provider == provider:
        _mark_job_terminal(claimed, error_code)


def _claim_and_supersede(job_id: int, provider: Provider) -> None:
    claimed = _claim_job(job_id)
    if claimed is not None and claimed.provider == provider:
        _mark_job_superseded(claimed)


def _get_job(job_id: int) -> Optional[jobs.PatientIntegrationJobRecord]:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        return jobs.get_job(cursor, job_id=job_id)


def _claim_job(job_id: int) -> Optional[jobs.PatientIntegrationJobRecord]:
    stale_before = datetime.now(timezone.utc) - PROCESSING_STALE_AFTER
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        return jobs.claim_job(
            cursor,
            job_id=job_id,
            stale_before=stale_before,
        )


def _load_effective_patient_by_id(paciente_id: int) -> Optional[PatientSnapshot]:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        patient = _load_patient(cursor, paciente_id)
        if patient is None:
            return None
        return _resolve_effective_patient(cursor, patient)


def _load_patient(cursor: Any, paciente_id: int) -> Optional[PatientSnapshot]:
    if isinstance(paciente_id, bool) or not isinstance(paciente_id, int) or paciente_id <= 0:
        raise PatientIntegrationDataError("patient_id_invalid")
    cursor.execute(
        f"""
        SELECT {PATIENT_COLUMNS}
        FROM pacientes
        WHERE paciente_id = %s
        LIMIT 1
        """,
        (paciente_id,),
    )
    row = cursor.fetchone()
    return PatientSnapshot(*row) if row else None


def _resolve_effective_patient(
    cursor: Any,
    patient: PatientSnapshot,
) -> PatientSnapshot:
    current = patient
    expected_unit = _canonical_snapshot_unit(patient)
    visited_ids = {patient.paciente_id}

    while current.is_minor:
        if not current.responsavel_id:
            raise PatientIntegrationDataError("responsible_required")
        if current.responsavel_id in visited_ids:
            raise PatientIntegrationDataError("responsible_cycle")
        visited_ids.add(current.responsavel_id)
        responsible = _load_patient(cursor, current.responsavel_id)
        if responsible is None:
            raise PatientIntegrationDataError("responsible_not_found")
        if _canonical_snapshot_unit(responsible) != expected_unit:
            raise PatientIntegrationDataError("responsible_unit_mismatch")
        current = responsible

    return current


def _validate_patient(patient: PatientSnapshot) -> None:
    if not str(patient.nome_paciente or "").strip():
        raise PatientIntegrationDataError("patient_name_required")
    document = _only_digits(patient.cpf_cnpj)
    if len(document) not in {11, 14}:
        raise PatientIntegrationDataError("patient_document_invalid")


def _snapshot_payload(patient: PatientSnapshot) -> dict[str, Any]:
    return {
        "nome_paciente": patient.nome_paciente,
        "cpf_cnpj": patient.cpf_cnpj,
        "email": patient.email,
        "data_nascimento": patient.data_nascimento,
        "phone_country_code": patient.phone_country_code,
        "phone_area_code": patient.phone_area_code,
        "phone_number": patient.phone_number,
        "street": patient.street,
        "street_number": patient.street_number,
        "line_two": patient.line_two,
        "neighborhood": patient.neighborhood,
        "city": patient.city,
        "state": patient.state,
        "zip_code": patient.zip_code,
    }


def _validate_delta_configuration(unidade: str, environment: str) -> None:
    try:
        token, seller_id = get_token_and_seller_for_unidade(unidade, environment)
    except Exception:
        raise PatientIntegrationConfigError(
            "Configuracao Delta incompleta para a unidade"
        ) from None
    if not str(token or "").strip() or not str(seller_id or "").strip():
        raise PatientIntegrationConfigError(
            "Configuracao Delta incompleta para a unidade"
        )


def _load_strict_asaas_config(unidade: str, environment: str) -> AsaasConfig:
    try:
        config = AsaasConfig.from_env(unidade, strict=True)
    except AsaasConfigurationError:
        raise PatientIntegrationConfigError(
            "Configuracao Asaas incompleta para a unidade"
        ) from None
    config_environment = (
        "production"
        if config.environment == AsaasEnvironment.PRODUCTION
        else "sandbox"
    )
    if config_environment != environment:
        raise PatientIntegrationConfigError("Ambiente Asaas divergente do job")
    return config


def _required_wallet_id(config: AsaasConfig) -> str:
    wallet_id = str(config.account_wallet_id or "").strip()
    if not wallet_id:
        raise PatientIntegrationConfigError("Wallet Asaas ausente para a unidade")
    return wallet_id


def _build_asaas_target_key(environment: str, wallet_id: str) -> str:
    if environment not in {"sandbox", "production"}:
        raise PatientIntegrationConfigError("Ambiente Asaas invalido")
    normalized_wallet = str(wallet_id or "").strip()
    if not normalized_wallet:
        raise PatientIntegrationConfigError("Wallet Asaas ausente para a unidade")
    return f"asaas:{environment}:{normalized_wallet}"


def _canonical_snapshot_unit(patient: PatientSnapshot) -> str:
    canonical = canonicalize_patient_unit(patient.unidade)
    if not canonical:
        raise PatientIntegrationDataError("patient_unit_invalid")
    return canonical


def _normalize_providers(providers: Iterable[str]) -> tuple[Provider, ...]:
    if isinstance(providers, str):
        raw_providers = (providers,)
    else:
        raw_providers = tuple(providers)
    normalized: list[Provider] = []
    for raw_provider in raw_providers:
        provider = str(raw_provider or "").strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise PatientIntegrationConfigError("Provider de paciente nao suportado")
        if provider not in normalized:
            normalized.append(provider)  # type: ignore[arg-type]
    if not normalized:
        raise PatientIntegrationConfigError("Ao menos um provider e obrigatorio")
    return tuple(normalized)


def _normalize_expected_provider(provider: Any) -> Provider:
    normalized = str(provider or "").strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ValueError("expected_provider deve ser delta ou asaas")
    return normalized  # type: ignore[return-value]


def _validate_job_id(job_id: Any) -> None:
    if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0:
        raise ValueError("job_id deve ser um inteiro positivo")


def _as_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise PatientIntegrationDataError(f"{field}_invalid")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_http_status(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if not 100 <= value <= 599:
        return None
    # Uma excecao de API com status de sucesso representa resposta
    # semanticamente invalida; persista-a como falha de gateway.
    return 502 if value < 300 else value


def _only_digits(value: Any) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())
