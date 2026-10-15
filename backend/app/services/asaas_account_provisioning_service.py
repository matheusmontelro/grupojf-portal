"""Provisionamento fail-closed de subcontas Asaas PF no Sandbox.

Cada criacao remota e precedida por uma tentativa duravel:

``reserved -> started -> confirmed | rejected | uncertain``.

O token da tentativa e aleatorio, nunca e exposto nem registrado em log e
autoriza somente a propria transicao ``reserved -> started``. Qualquer
rejeicao remota definitiva permite uma nova tentativa explicita. Qualquer
resultado incerto bloqueia uma nova chamada e exige reconciliacao manual. Uma
reserva antiga, que comprovadamente ainda nao iniciou o POST, pode ser retomada
sem duplicar o efeito remoto.

A apiKey retornada pelo Asaas e cifrada antes de ser persistida. O plaintext
nunca e gravado nem logado.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal
from uuid import uuid4

from app.asaas_sdk.exceptions import (
    AsaasAPIError,
    AsaasConnectionError,
    AsaasIntegrationError,
    AsaasValidationError,
)
from app.asaas_sales_sdk import AsaasSalesSDK
from app.asaas_sales_sdk.account_manager import prepare_account_payload
from app.security.asaas_account_secret import encrypt_api_key
from app.services.asaas_sale_database import (
    AsaasSaleDatabaseConfigError,
    DatabaseConnection,
)
from app.services.asaas_sales_config import (
    AsaasSalesConfigError,
    canonicalize_asaas_sales_unit,
    is_asaas_sales_subaccount_provisioning_enabled,
)
from app.services.asaas_sales_preflight import (
    AsaasSalesPreflightError,
    is_asaas_sales_pf_user_excluded,
)


logger = logging.getLogger(__name__)

ProvisionStatus = Literal[
    "sucesso",
    "existente",
    "erro_kyc",
    "erro_validacao",
    "erro_integracao",
]

# Renda mensal padrao enquanto o schema canonico de users nao guardar renda.
DEFAULT_INCOME_VALUE = 5000.00
_ELIGIBLE_CARGO_IDS = (3, 4)
_MANUAL_RECONCILIATION_MESSAGE = (
    "Provisionamento já iniciado; reconciliação manual necessária."
)
_DAILY_LIMIT_ERROR_CODES = frozenset(
    {"account_daily_limit_exceeded", "daily_limit_exceeded", "limit_exceeded"}
)
_RESERVED_STALE_AFTER_SECONDS = 15 * 60
_DEFINITIVE_REJECTION_HTTP_STATUSES = frozenset({400, 422, 429})


@dataclass(frozen=True)
class ProvisionResult:
    """Resultado controlado do provisionamento de uma subconta Asaas."""

    status: ProvisionStatus
    wallet_id: str | None = None
    account_id: str | None = None
    integration_status: str | None = None
    mensagem: str | None = None


@dataclass(frozen=True)
class _UserData:
    user_id: int
    unidade: str
    cargo_id: int
    nome: str
    cpf: str
    email: str
    mobile_phone: str
    address: str
    address_number: str
    province: str
    postal_code: str
    birth_date: str
    wallet_id: str | None
    account_id: str | None
    integration_status: str | None


@dataclass(frozen=True)
class _Reservation:
    user: _UserData
    attempt_token: str
    payload: Mapping[str, Any]


def provision_asaas_account_for_user(
    user_id: int,
    *,
    expected_unit: str,
) -> ProvisionResult:
    """Provisiona uma subconta PF sem permitir repeticao remota incerta.

    As transacoes de reserva, inicio e conclusao sao independentes e curtas.
    O ``POST /accounts`` ocorre com o SDK ainda aberto e somente depois do
    commit de ``started``.
    """
    _validate_user_id(user_id)
    unidade = canonicalize_asaas_sales_unit(expected_unit)
    if unidade is None:
        return ProvisionResult(
            status="erro_validacao",
            mensagem="Unidade do usuário não reconhecida para vendas Asaas.",
        )
    if not is_asaas_sales_subaccount_provisioning_enabled(unidade):
        return ProvisionResult(
            status="erro_integracao",
            mensagem=(
                "Provisionamento de subcontas Asaas indisponível para a "
                "unidade do usuário."
            ),
        )
    try:
        excluded = is_asaas_sales_pf_user_excluded(user_id, unidade)
    except AsaasSalesPreflightError as exc:
        raise AsaasSalesConfigError(
            "Manifesto de exclusões PF inválido."
        ) from exc
    if excluded:
        return ProvisionResult(
            status="erro_validacao",
            mensagem=(
                "Usuário temporariamente excluído do provisionamento de "
                "subconta Asaas."
            ),
        )

    # Autorizacao/eligibilidade vem antes ate da instanciacao do SDK. A reserva
    # revalida tudo sob lock para fechar a janela entre este precheck e o POST.
    precheck = _precheck_target(
        user_id=user_id,
        expected_unit=unidade,
    )
    if precheck is not None:
        return precheck

    reservation: _Reservation | None = None
    remote_started = False
    created: Mapping[str, Any] | None = None

    try:
        # Um unico contexto mantem o cliente HTTP aberto durante create_account
        # e garante exatamente um close no caminho normal ou excepcional.
        with AsaasSalesSDK.for_unit(unidade) as sdk:
            account = sdk.account
            if (
                account.environment != "sandbox"
                or canonicalize_asaas_sales_unit(account.unidade) != unidade
            ):
                logger.error(
                    "Provisionamento Asaas bloqueado por conta incompatível. "
                    "user_id=%s environment=%s",
                    user_id,
                    account.environment,
                )
                return ProvisionResult(
                    status="erro_integracao",
                    mensagem=(
                        "Provisionamento de subconta disponível somente no "
                        "Sandbox da unidade selecionada."
                    ),
                )

            reserved = _reserve_attempt(
                user_id=user_id,
                expected_unit=unidade,
                environment=account.environment,
            )
            if isinstance(reserved, ProvisionResult):
                return reserved
            reservation = reserved

            _transition_attempt_to_started(
                user_id=user_id,
                attempt_token=reservation.attempt_token,
            )
            remote_started = True
            created_value = sdk.accounts.create_account(reservation.payload)
            if isinstance(created_value, Mapping):
                created = created_value
            else:
                created = {}
    except AsaasSaleDatabaseConfigError:
        raise
    except AsaasValidationError as exc:
        codes = list(getattr(exc, "errors", []) or [])
        status_code = getattr(exc, "status_code", None)
        next_status: ProvisionStatus = (
            "erro_kyc" if _is_kyc_validation(codes) else "erro_validacao"
        )
        mensagem = _describe_validation_error(codes)
        if remote_started and reservation is not None:
            if status_code in {400, 422}:
                _mark_rejected_safely(
                    user_id=user_id,
                    expected_unit=unidade,
                    attempt_token=reservation.attempt_token,
                    user_status=next_status,
                    error_code=f"provider_validation_{status_code}",
                )
            else:
                _mark_uncertain_safely(
                    user_id=user_id,
                    expected_unit=unidade,
                    attempt_token=reservation.attempt_token,
                    user_status=next_status,
                    error_code="local_validation_after_start",
                )
        logger.warning(
            "Criacao de subconta Asaas rejeitada. user_id=%s status=%s "
            "remote_started=%s error_type=%s",
            user_id,
            next_status,
            remote_started,
            type(exc).__name__,
        )
        return ProvisionResult(status=next_status, mensagem=mensagem)
    except AsaasAPIError as exc:
        status_code = getattr(exc, "status_code", None)
        mensagem = (
            "limite diário de subcontas sandbox atingido"
            if status_code == 429
            else "falha na criação da subconta no Asaas"
        )
        if remote_started and reservation is not None:
            if status_code in _DEFINITIVE_REJECTION_HTTP_STATUSES:
                _mark_rejected_safely(
                    user_id=user_id,
                    expected_unit=unidade,
                    attempt_token=reservation.attempt_token,
                    user_status=(
                        "erro_validacao"
                        if status_code in {400, 422}
                        else "erro_integracao"
                    ),
                    error_code=(
                        "provider_rate_limit_429"
                        if status_code == 429
                        else f"provider_rejection_{status_code}"
                    ),
                )
            else:
                _mark_uncertain_safely(
                    user_id=user_id,
                    expected_unit=unidade,
                    attempt_token=reservation.attempt_token,
                    user_status="erro_integracao",
                    error_code="provider_api_error",
                )
        logger.warning(
            "Criacao de subconta Asaas falhou. user_id=%s http_status=%s "
            "remote_started=%s error_type=%s",
            user_id,
            status_code,
            remote_started,
            type(exc).__name__,
        )
        return ProvisionResult(status="erro_integracao", mensagem=mensagem)
    except AsaasConnectionError as exc:
        if remote_started and reservation is not None:
            _mark_uncertain_safely(
                user_id=user_id,
                expected_unit=unidade,
                attempt_token=reservation.attempt_token,
                user_status="erro_integracao",
                error_code="provider_connection_error",
            )
        logger.error(
            "Comunicacao com Asaas falhou no provisionamento. user_id=%s "
            "remote_started=%s error_type=%s",
            user_id,
            remote_started,
            type(exc).__name__,
        )
        return ProvisionResult(
            status="erro_integracao",
            mensagem="falha de comunicação com o Asaas",
        )
    except (AsaasSalesConfigError, AsaasIntegrationError) as exc:
        if remote_started and reservation is not None:
            _mark_uncertain_safely(
                user_id=user_id,
                expected_unit=unidade,
                attempt_token=reservation.attempt_token,
                user_status="erro_integracao",
                error_code="provider_integration_error",
                wallet_id=_remote_identifier(created, "walletId"),
                account_id=_remote_identifier(created, "id"),
            )
        logger.error(
            "Integracao Asaas indisponivel no provisionamento. user_id=%s "
            "remote_started=%s error_type=%s",
            user_id,
            remote_started,
            type(exc).__name__,
        )
        return ProvisionResult(
            status="erro_integracao",
            mensagem="Configuração da conta Asaas indisponível.",
        )
    except Exception as exc:
        # Inclui falha no fechamento do cliente depois do POST e falhas locais
        # inesperadas. Se started foi commitado, a tentativa nunca volta a ser
        # elegivel automaticamente.
        if remote_started and reservation is not None:
            _mark_uncertain_safely(
                user_id=user_id,
                expected_unit=unidade,
                attempt_token=reservation.attempt_token,
                user_status="erro_integracao",
                error_code="unexpected_provisioning_error",
                wallet_id=_remote_identifier(created, "walletId"),
                account_id=_remote_identifier(created, "id"),
            )
        logger.error(
            "Falha inesperada no provisionamento Asaas. user_id=%s "
            "remote_started=%s error_type=%s",
            user_id,
            remote_started,
            type(exc).__name__,
        )
        return ProvisionResult(
            status="erro_integracao",
            mensagem=(
                _MANUAL_RECONCILIATION_MESSAGE
                if reservation is not None
                else "Infraestrutura de subcontas Asaas indisponível."
            ),
        )

    if reservation is None or created is None:
        # Defesa em profundidade: o fluxo normal sempre define ambos.
        return ProvisionResult(
            status="erro_integracao",
            mensagem="Infraestrutura de subcontas Asaas indisponível.",
        )

    wallet_id = _remote_identifier(created, "walletId")
    account_id = _remote_identifier(created, "id")
    api_key = _remote_identifier(created, "apiKey")
    if not wallet_id or not account_id or not api_key:
        _mark_uncertain_safely(
            user_id=user_id,
            expected_unit=unidade,
            attempt_token=reservation.attempt_token,
            user_status="erro_integracao",
            error_code="incomplete_provider_response",
            wallet_id=wallet_id,
            account_id=account_id,
        )
        logger.error(
            "Resposta de subconta Asaas incompleta. user_id=%s "
            "has_wallet=%s has_account=%s has_apikey=%s",
            user_id,
            bool(wallet_id),
            bool(account_id),
            bool(api_key),
        )
        return ProvisionResult(
            status="erro_integracao",
            mensagem=(
                "Resposta do Asaas incompleta; reconciliação manual necessária."
            ),
        )

    try:
        encrypted_api_key = encrypt_api_key(api_key)
        if not _non_empty(encrypted_api_key):
            raise ValueError("encrypted_api_key_empty")
    except Exception as exc:
        _mark_uncertain_safely(
            user_id=user_id,
            expected_unit=unidade,
            attempt_token=reservation.attempt_token,
            user_status="erro_integracao",
            error_code="secret_encryption_error",
            wallet_id=wallet_id,
            account_id=account_id,
        )
        logger.error(
            "Cifragem da apiKey falhou apos criacao de subconta. "
            "user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )
        return ProvisionResult(
            status="erro_integracao",
            mensagem=(
                "Subconta criada, mas a credencial não pôde ser protegida; "
                "reconciliação manual necessária."
            ),
        )

    try:
        _confirm_attempt(
            user_id=user_id,
            expected_unit=unidade,
            attempt_token=reservation.attempt_token,
            wallet_id=wallet_id,
            account_id=account_id,
            encrypted_api_key=encrypted_api_key,
        )
    except Exception as exc:
        # Uma falha/resultado desconhecido no commit final nao autoriza novo
        # POST. Se o commit nao ocorreu, started permanece; se ocorreu, a
        # tentativa ja esta confirmed e a operacao abaixo apenas falha fechada.
        _mark_uncertain_safely(
            user_id=user_id,
            expected_unit=unidade,
            attempt_token=reservation.attempt_token,
            user_status="erro_integracao",
            error_code="confirmation_persistence_error",
            wallet_id=wallet_id,
            account_id=account_id,
        )
        logger.error(
            "Persistencia final da subconta ficou indeterminada. "
            "user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )
        return ProvisionResult(
            status="erro_integracao",
            mensagem=_MANUAL_RECONCILIATION_MESSAGE,
        )

    logger.info(
        "Subconta Asaas provisionada. user_id=%s wallet_id_present=%s "
        "account_id_present=%s",
        user_id,
        True,
        True,
    )
    return ProvisionResult(
        status="sucesso",
        wallet_id=wallet_id,
        account_id=account_id,
        integration_status="integrado",
    )


def _reserve_attempt(
    *,
    user_id: int,
    expected_unit: str,
    environment: str,
) -> _Reservation | ProvisionResult:
    """Valida o alvo e commita ``reserved`` antes de qualquer efeito remoto."""
    attempt_token = str(uuid4())
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"asaas-account-provisioning:{user_id}",),
        )
        user = _load_eligible_user(
            cursor,
            user_id=user_id,
            expected_unit=expected_unit,
            lock=True,
        )
        if user is None:
            return ProvisionResult(
                status="erro_validacao",
                mensagem="Usuário não encontrado ou inelegível para subconta PF.",
            )

        existing_or_partial = _existing_or_partial_result(user)
        if existing_or_partial is not None:
            return existing_or_partial

        validation_error = _validate_user_data(user)
        if validation_error is not None:
            _mark_user_status(
                cursor,
                user_id=user_id,
                expected_unit=expected_unit,
                status_value="erro_validacao",
            )
            return ProvisionResult(
                status="erro_validacao",
                mensagem=validation_error,
            )

        # A validacao estrita do manager ocorre antes de inserir a reserva.
        # Portanto nenhuma falha local deterministica pode consumir uma
        # tentativa nem acontecer depois de ``started``.
        payload = prepare_account_payload(_build_account_payload(user))

        cursor.execute(
            """
            SELECT
                attempt_token::text,
                lifecycle_state,
                (
                    lifecycle_state = 'reserved'
                    AND unidade = %s
                    AND environment = %s
                    AND updated_at <= (
                        NOW() - (%s * INTERVAL '1 second')
                    )
                ) AS reusable_stale_reservation
            FROM asaas_account_provision_attempts
            WHERE user_id = %s
              AND lifecycle_state <> 'rejected'
            ORDER BY id DESC
            LIMIT 1
            FOR UPDATE
            """,
            (
                expected_unit,
                environment,
                _RESERVED_STALE_AFTER_SECONDS,
                user_id,
            ),
        )
        active_attempt = cursor.fetchone()
        if active_attempt is not None and not bool(active_attempt[2]):
            return ProvisionResult(
                status="erro_integracao",
                mensagem=_MANUAL_RECONCILIATION_MESSAGE,
            )
        if active_attempt is not None:
            stale_attempt_token = str(active_attempt[0])
            cursor.execute(
                """
                UPDATE asaas_account_provision_attempts
                SET updated_at = NOW()
                WHERE user_id = %s
                  AND attempt_token = %s
                  AND lifecycle_state = 'reserved'
                  AND remote_attempt_count = 0
                RETURNING id
                """,
                (user_id, stale_attempt_token),
            )
            if cursor.fetchone() is None:
                return ProvisionResult(
                    status="erro_integracao",
                    mensagem=_MANUAL_RECONCILIATION_MESSAGE,
                )
            return _Reservation(
                user=user,
                attempt_token=stale_attempt_token,
                payload=payload,
            )

        cursor.execute(
            """
            INSERT INTO asaas_account_provision_attempts (
                user_id,
                unidade,
                environment,
                attempt_token,
                lifecycle_state,
                remote_attempt_count
            )
            VALUES (%s, %s, %s, %s, 'reserved', 0)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (user_id, expected_unit, environment, attempt_token),
        )
        if cursor.fetchone() is None:
            return ProvisionResult(
                status="erro_integracao",
                mensagem=_MANUAL_RECONCILIATION_MESSAGE,
            )
    return _Reservation(
        user=user,
        attempt_token=attempt_token,
        payload=payload,
    )


def _precheck_target(
    *,
    user_id: int,
    expected_unit: str,
) -> ProvisionResult | None:
    """Bloqueia alvo inelegivel/ja tentado sem sequer instanciar o SDK."""
    with DatabaseConnection(read_only=True) as conn:
        cursor = conn.cursor()
        user = _load_eligible_user(
            cursor,
            user_id=user_id,
            expected_unit=expected_unit,
            lock=False,
        )
        if user is None:
            return ProvisionResult(
                status="erro_validacao",
                mensagem="Usuário não encontrado ou inelegível para subconta PF.",
            )
        existing_or_partial = _existing_or_partial_result(user)
        if existing_or_partial is not None:
            return existing_or_partial
        validation_error = _validate_user_data(user)
        if validation_error is not None:
            return ProvisionResult(
                status="erro_validacao",
                mensagem=validation_error,
            )
        cursor.execute(
            """
            SELECT
                lifecycle_state,
                (
                    lifecycle_state = 'reserved'
                    AND unidade = %s
                    AND environment = 'sandbox'
                    AND updated_at <= (
                        NOW() - (%s * INTERVAL '1 second')
                    )
                ) AS reusable_stale_reservation
            FROM asaas_account_provision_attempts
            WHERE user_id = %s
              AND lifecycle_state <> 'rejected'
            ORDER BY id DESC
            LIMIT 1
            """,
            (expected_unit, _RESERVED_STALE_AFTER_SECONDS, user_id),
        )
        active_attempt = cursor.fetchone()
        if active_attempt is not None and not bool(active_attempt[1]):
            return ProvisionResult(
                status="erro_integracao",
                mensagem=_MANUAL_RECONCILIATION_MESSAGE,
            )
    return None


def _existing_or_partial_result(user: _UserData) -> ProvisionResult | None:
    if user.integration_status == "integrado" and _non_empty(user.wallet_id):
        return ProvisionResult(
            status="existente",
            wallet_id=user.wallet_id,
            account_id=user.account_id,
            integration_status="integrado",
            mensagem="Subconta Asaas já provisionada.",
        )
    # Compatibilidade fail-closed com qualquer gravacao parcial legada,
    # independentemente do status: wallet OU account pode significar efeito
    # remoto ja ocorrido.
    if _non_empty(user.wallet_id) or _non_empty(user.account_id):
        return ProvisionResult(
            status="erro_integracao",
            wallet_id=user.wallet_id,
            account_id=user.account_id,
            integration_status=user.integration_status,
            mensagem=_MANUAL_RECONCILIATION_MESSAGE,
        )
    return None


def _transition_attempt_to_started(
    *,
    user_id: int,
    attempt_token: str,
) -> None:
    """Commita ``started``; somente o token da reserva pode transicionar."""
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_account_provision_attempts
            SET lifecycle_state = 'started',
                remote_attempt_count = 1,
                remote_started_at = NOW(),
                updated_at = NOW()
            WHERE user_id = %s
              AND attempt_token = %s
              AND lifecycle_state = 'reserved'
              AND remote_attempt_count = 0
            RETURNING id
            """,
            (user_id, attempt_token),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("asaas_account_attempt_start_conflict")


def _mark_attempt_uncertain(
    *,
    user_id: int,
    expected_unit: str,
    attempt_token: str,
    user_status: str,
    error_code: str,
    wallet_id: str | None = None,
    account_id: str | None = None,
) -> None:
    """Persiste resultado remoto incerto e identificadores nao secretos."""
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_account_provision_attempts
            SET lifecycle_state = 'uncertain',
                last_error_code = %s,
                remote_uncertain_at = NOW(),
                updated_at = NOW()
            WHERE user_id = %s
              AND attempt_token = %s
              AND lifecycle_state = 'started'
              AND remote_attempt_count = 1
            RETURNING id
            """,
            (error_code, user_id, attempt_token),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("asaas_account_attempt_uncertain_conflict")
        cursor.execute(
            """
            UPDATE users
            SET asaas_wallet_id = COALESCE(%s, asaas_wallet_id),
                asaas_account_id = COALESCE(%s, asaas_account_id),
                asaas_integration_status = %s,
                asaas_account_updated_at = NOW()
            WHERE id = %s
              AND unidade = %s
              AND cargo_id IN %s
              AND status_aprovacao = 'aprovado'
              AND LENGTH(
                    REGEXP_REPLACE(
                        COALESCE(cpf, ''),
                        '[^0-9]',
                        '',
                        'g'
                    )
                  ) = 11
            RETURNING id
            """,
            (
                wallet_id,
                account_id,
                user_status,
                user_id,
                expected_unit,
                _ELIGIBLE_CARGO_IDS,
            ),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("asaas_account_attempt_user_missing")


def _mark_attempt_rejected(
    *,
    user_id: int,
    expected_unit: str,
    attempt_token: str,
    user_status: str,
    error_code: str,
) -> None:
    """Fecha uma rejeicao remota definitiva e libera retry explicito."""
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_account_provision_attempts
            SET lifecycle_state = 'rejected',
                last_error_code = %s,
                remote_rejected_at = NOW(),
                updated_at = NOW()
            WHERE user_id = %s
              AND attempt_token = %s
              AND lifecycle_state = 'started'
              AND remote_attempt_count = 1
            RETURNING id
            """,
            (error_code, user_id, attempt_token),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("asaas_account_attempt_rejected_conflict")
        cursor.execute(
            """
            UPDATE users
            SET asaas_integration_status = %s,
                asaas_account_updated_at = NOW()
            WHERE id = %s
              AND unidade = %s
              AND cargo_id IN %s
              AND status_aprovacao = 'aprovado'
              AND LENGTH(
                    REGEXP_REPLACE(
                        COALESCE(cpf, ''),
                        '[^0-9]',
                        '',
                        'g'
                    )
                  ) = 11
              AND NULLIF(BTRIM(asaas_wallet_id), '') IS NULL
              AND NULLIF(BTRIM(asaas_account_id), '') IS NULL
            RETURNING id
            """,
            (
                user_status,
                user_id,
                expected_unit,
                _ELIGIBLE_CARGO_IDS,
            ),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("asaas_account_attempt_user_missing")


def _confirm_attempt(
    *,
    user_id: int,
    expected_unit: str,
    attempt_token: str,
    wallet_id: str,
    account_id: str,
    encrypted_api_key: str,
) -> None:
    """Persiste credencial cifrada e ``confirmed`` atomicamente."""
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET asaas_wallet_id = %s,
                asaas_account_id = %s,
                asaas_integration_status = 'integrado',
                asaas_account_api_key_enc = %s,
                asaas_account_updated_at = NOW()
            WHERE id = %s
              AND unidade = %s
              AND cargo_id IN %s
              AND status_aprovacao = 'aprovado'
              AND LENGTH(
                    REGEXP_REPLACE(
                        COALESCE(cpf, ''),
                        '[^0-9]',
                        '',
                        'g'
                    )
                  ) = 11
            RETURNING id
            """,
            (
                wallet_id,
                account_id,
                encrypted_api_key,
                user_id,
                expected_unit,
                _ELIGIBLE_CARGO_IDS,
            ),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("asaas_account_attempt_user_scope_changed")
        cursor.execute(
            """
            UPDATE asaas_account_provision_attempts
            SET lifecycle_state = 'confirmed',
                last_error_code = NULL,
                remote_confirmed_at = NOW(),
                updated_at = NOW()
            WHERE user_id = %s
              AND attempt_token = %s
              AND lifecycle_state = 'started'
              AND remote_attempt_count = 1
            RETURNING id
            """,
            (user_id, attempt_token),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("asaas_account_attempt_confirm_conflict")


def _mark_uncertain_safely(
    *,
    user_id: int,
    expected_unit: str,
    attempt_token: str,
    user_status: str,
    error_code: str,
    wallet_id: str | None = None,
    account_id: str | None = None,
) -> None:
    try:
        _mark_attempt_uncertain(
            user_id=user_id,
            expected_unit=expected_unit,
            attempt_token=attempt_token,
            user_status=user_status,
            error_code=error_code,
            wallet_id=wallet_id,
            account_id=account_id,
        )
    except Exception as exc:
        # ``started`` ja foi commitado. Mesmo se este UPDATE falhar, uma nova
        # requisicao continuara bloqueada e nao duplicara o efeito remoto.
        logger.error(
            "Falha ao persistir estado incerto de subconta. user_id=%s "
            "error_type=%s",
            user_id,
            type(exc).__name__,
        )


def _mark_rejected_safely(
    *,
    user_id: int,
    expected_unit: str,
    attempt_token: str,
    user_status: str,
    error_code: str,
) -> None:
    try:
        _mark_attempt_rejected(
            user_id=user_id,
            expected_unit=expected_unit,
            attempt_token=attempt_token,
            user_status=user_status,
            error_code=error_code,
        )
    except Exception as exc:
        # Se a classificacao definitiva nao puder ser persistida, ``started``
        # permanece ativo e bloqueia retry. O fallback conservador evita POST
        # duplicado ate intervencao operacional.
        logger.error(
            "Falha ao persistir rejeição de subconta. user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )


def _load_eligible_user(
    cursor: Any,
    *,
    user_id: int,
    expected_unit: str,
    lock: bool,
) -> _UserData | None:
    query = """
        SELECT
            id,
            unidade,
            cargo_id,
            nome,
            cpf,
            email,
            phone_country_code,
            phone_area_code,
            phone_number,
            street,
            street_number,
            neighborhood,
            zip_code,
            birthdate,
            asaas_wallet_id,
            asaas_account_id,
            asaas_integration_status
        FROM users
        WHERE id = %s
          AND unidade = %s
          AND cargo_id IN %s
          AND status_aprovacao = 'aprovado'
          AND LENGTH(
                REGEXP_REPLACE(
                    COALESCE(cpf, ''),
                    '[^0-9]',
                    '',
                    'g'
                )
              ) = 11
        LIMIT 1
    """
    if lock:
        query += "\nFOR UPDATE"
    cursor.execute(
        query,
        (user_id, expected_unit, _ELIGIBLE_CARGO_IDS),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    if isinstance(row, Mapping):
        values = {
            "unidade": row.get("unidade"),
            "cargo_id": row.get("cargo_id"),
            "nome": row.get("nome"),
            "cpf": row.get("cpf"),
            "email": row.get("email"),
            "phone_country_code": row.get("phone_country_code"),
            "phone_area_code": row.get("phone_area_code"),
            "phone_number": row.get("phone_number"),
            "address": row.get("street"),
            "address_number": row.get("street_number"),
            "province": row.get("neighborhood"),
            "postal_code": row.get("zip_code"),
            "birthdate": row.get("birthdate"),
            "wallet_id": row.get("asaas_wallet_id"),
            "account_id": row.get("asaas_account_id"),
            "integration_status": row.get("asaas_integration_status"),
        }
    else:
        (
            _row_id,
            unit_value,
            cargo_id,
            nome,
            cpf,
            email,
            phone_country_code,
            phone_area_code,
            phone_number,
            address,
            address_number,
            province,
            postal_code,
            birthdate,
            wallet_id,
            account_id,
            integration_status,
        ) = row
        values = {
            "unidade": unit_value,
            "cargo_id": cargo_id,
            "nome": nome,
            "cpf": cpf,
            "email": email,
            "phone_country_code": phone_country_code,
            "phone_area_code": phone_area_code,
            "phone_number": phone_number,
            "address": address,
            "address_number": address_number,
            "province": province,
            "postal_code": postal_code,
            "birthdate": birthdate,
            "wallet_id": wallet_id,
            "account_id": account_id,
            "integration_status": integration_status,
        }

    try:
        cargo_id_value = int(values["cargo_id"])
    except (TypeError, ValueError):
        return None
    return _UserData(
        user_id=user_id,
        unidade=_as_str(values["unidade"]),
        cargo_id=cargo_id_value,
        nome=_as_str(values["nome"]),
        cpf=_digits(values["cpf"]),
        email=_as_str(values["email"]),
        mobile_phone=_compose_mobile_phone(
            values["phone_country_code"],
            values["phone_area_code"],
            values["phone_number"],
        ),
        address=_as_str(values["address"]),
        address_number=_as_str(values["address_number"]),
        province=_as_str(values["province"]),
        postal_code=_as_str(values["postal_code"]),
        birth_date=_birth_date_str(values["birthdate"]),
        wallet_id=(
            _as_str(values["wallet_id"])
            if values["wallet_id"] is not None
            else None
        ),
        account_id=(
            _as_str(values["account_id"])
            if values["account_id"] is not None
            else None
        ),
        integration_status=(
            _as_str(values["integration_status"])
            if values["integration_status"] is not None
            else None
        ),
    )


def _mark_user_status(
    cursor: Any,
    *,
    user_id: int,
    expected_unit: str,
    status_value: str,
) -> None:
    cursor.execute(
        """
        UPDATE users
        SET asaas_integration_status = %s,
            asaas_account_updated_at = NOW()
        WHERE id = %s
          AND unidade = %s
        RETURNING id
        """,
        (status_value, user_id, expected_unit),
    )
    if cursor.fetchone() is None:
        raise RuntimeError("asaas_account_attempt_user_scope_changed")


def _validate_user_id(user_id: Any) -> None:
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id deve ser um inteiro positivo.")


def _validate_user_data(user: _UserData) -> str | None:
    if not _non_empty(user.nome):
        return "Nome do usuário ausente."
    if len(user.cpf) != 11 or not user.cpf.isascii() or not user.cpf.isdigit():
        return "CPF do usuário ausente ou inválido."
    if not _non_empty(user.email) or "@" not in user.email:
        return "Email do usuário ausente ou inválido."
    if not _non_empty(user.mobile_phone):
        return "Telefone do usuário ausente ou inválido."
    if not _non_empty(user.address):
        return "Endereço do usuário ausente."
    if not _non_empty(user.address_number):
        return "Número do endereço do usuário ausente."
    if not _non_empty(user.province):
        return "Bairro do usuário ausente."
    if not _non_empty(user.postal_code):
        return "CEP do usuário ausente."
    if not _non_empty(user.birth_date):
        return "Data de nascimento do usuário ausente."
    return None


def _build_account_payload(user: _UserData) -> dict[str, Any]:
    return {
        "name": user.nome,
        "email": user.email,
        "cpfCnpj": user.cpf,
        "mobilePhone": user.mobile_phone,
        "incomeValue": DEFAULT_INCOME_VALUE,
        "address": user.address,
        "addressNumber": user.address_number,
        "province": user.province,
        "postalCode": user.postal_code,
        "birthDate": user.birth_date,
    }


def _compose_mobile_phone(
    country_code: Any,
    area_code: Any,
    number: Any,
) -> str:
    cc = _digits(country_code) or "55"
    ac = _digits(area_code)
    num = _digits(number)
    if not ac or not num:
        return ""
    digits = f"{cc}{ac}{num}"
    return f"+{digits}" if 10 <= len(digits) <= 15 else ""


def _remote_identifier(
    payload: Mapping[str, Any] | None,
    key: str,
) -> str | None:
    if payload is None:
        return None
    value = payload.get(key)
    normalized = str(value or "").strip()
    return normalized or None


def _digits(value: Any) -> str:
    return "".join(char for char in str(value or "") if char in "0123456789")


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).strip()


def _birth_date_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_kyc_validation(codes: list[str]) -> bool:
    markers = ("kyc", "document", "cpf", "cnpj", "birth", "identity", "underage")
    return any(
        marker in str(code).casefold()
        for code in codes
        for marker in markers
    )


def _describe_validation_error(codes: list[str]) -> str:
    if any(str(code) in _DAILY_LIMIT_ERROR_CODES for code in codes):
        return "limite diário de subcontas sandbox atingido"
    return "validação rejeitada pelo Asaas"
