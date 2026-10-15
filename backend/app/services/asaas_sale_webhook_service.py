"""Inbox idempotente e minimizada para webhooks de vendas Asaas."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import re
from typing import Any, Optional
from uuid import UUID
from zoneinfo import ZoneInfo


MAX_WEBHOOK_BODY_BYTES = 512 * 1024
MAX_EVENT_ATTEMPTS_WITHOUT_RESOURCE = 4

_EVENT_ID_PATTERN = re.compile(r"^evt_[A-Za-z0-9_&-]{1,116}$")
_EVENT_TYPE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,99}$")
_RESOURCE_ID_PATTERN = re.compile(
    r"^(?=.{1,120}$)(?=.*[0-9])(?=.*[_-])[A-Za-z0-9_-]+$"
)
_ERROR_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{0,99}$")
_EXTERNAL_REFERENCE_PATTERN = re.compile(
    r"^grupojf:venda:[1-9][0-9]{0,9}:r[1-9][0-9]{0,4}$"
)
_ASAAS_TIMEZONE = ZoneInfo("America/Sao_Paulo")

_ALLOWED_REMOTE_STATUSES = frozenset(
    {
        "PENDING",
        "RECEIVED",
        "CONFIRMED",
        "OVERDUE",
        "REFUNDED",
        "RECEIVED_IN_CASH",
        "REFUND_REQUESTED",
        "REFUND_IN_PROGRESS",
        "CHARGEBACK_REQUESTED",
        "CHARGEBACK_DISPUTE",
        "AWAITING_CHARGEBACK_REVERSAL",
        "DUNNING_REQUESTED",
        "DUNNING_RECEIVED",
        "PARTIALLY_REFUNDED",
        "AWAITING_RISK_ANALYSIS",
        "CREATED",
        "ACTIVE",
        "INACTIVE",
        "CANCELLED",
        "CANCELED",
        "EXPIRED",
        "REFUSED",
        "AWAITING_REQUEST",
        "SCHEDULED",
        "ELIGIBLE",
        "INELIGIBLE",
        "PAID",
        "DONE",
    }
)

_ALLOWED_TECHNICAL_KEYS = frozenset(
    {
        "id",
        "event",
        "dateCreated",
        "account",
        "status",
        "payment",
        "checkout",
        "subscription",
        "installment",
        "pixAutomaticAuthorization",
        "paymentInstruction",
        "authorization",
        "dueDate",
        "paymentDate",
        "confirmedDate",
        "clientPaymentDate",
        "externalReference",
    }
)

_RESOURCE_KEYS = {
    "payment": "payment",
    "checkout": "checkout",
    "subscription": "subscription",
    "installment": "installment",
    "pixAutomaticAuthorization": "pix_authorization",
    "paymentInstruction": "pix_instruction",
    "authorization": "pix_authorization",
}

RETURNING_COLUMNS = """
    id,
    unidade,
    environment,
    account_wallet_id,
    event_id,
    event_type,
    technical_data,
    resource_id,
    status,
    attempt_count,
    last_error_code,
    last_attempt_at,
    next_retry_at,
    processed_at,
    received_at,
    created_at,
    updated_at
"""


@dataclass(frozen=True)
class AsaasSaleWebhookEventRecord:
    id: int
    unidade: str
    environment: str
    account_wallet_id: str
    event_id: str
    event_type: str
    technical_data: dict[str, Any]
    resource_id: Optional[int]
    status: str
    attempt_count: int
    last_error_code: Optional[str]
    last_attempt_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    processed_at: Optional[datetime]
    received_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AsaasSaleResourceMatch:
    id: int
    integration_id: int
    resource_type: str
    asaas_resource_id: str


@dataclass(frozen=True)
class AsaasSaleResourceEventUpdate:
    needs_reconciliation: bool
    event_applied: bool


@dataclass(frozen=True)
class AsaasSalePaymentProjection:
    payment_id: str
    remote_status: Optional[str]
    due_date: Optional[date]
    paid_at: Optional[datetime]
    external_reference: Optional[str]


def sanitize_webhook_event(payload: Any) -> dict[str, Any]:
    """Retem somente IDs e estados; descarta dados pessoais e financeiros."""
    if not isinstance(payload, dict):
        raise ValueError("Webhook Asaas deve ser um objeto JSON")

    event_id = payload.get("id")
    event_type = payload.get("event")
    if not isinstance(event_id, str) or not _EVENT_ID_PATTERN.fullmatch(event_id):
        raise ValueError("Webhook Asaas sem identificador valido")
    if (
        not isinstance(event_type, str)
        or not _EVENT_TYPE_PATTERN.fullmatch(event_type)
    ):
        raise ValueError("Webhook Asaas sem tipo de evento valido")
    event_created_at = payload.get("dateCreated")
    parsed_event_created_at = (
        _parse_provider_datetime(event_created_at)
        if isinstance(event_created_at, str)
        else None
    )
    if parsed_event_created_at is None:
        raise ValueError("Webhook Asaas sem data de criacao valida")
    account = payload.get("account")
    raw_account_id = account.get("id") if isinstance(account, Mapping) else None
    try:
        account_id = str(UUID(str(raw_account_id or "")))
    except (ValueError, AttributeError):
        raise ValueError("Webhook Asaas sem conta de origem valida") from None

    sanitized = _sanitize_mapping(payload, depth=0)
    sanitized["id"] = event_id
    sanitized["event"] = event_type
    sanitized["dateCreated"] = parsed_event_created_at.isoformat()
    sanitized["account"] = {"id": account_id}
    return sanitized


def store_webhook_event(
    cursor: Any,
    *,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    technical_data: dict[str, Any],
) -> tuple[AsaasSaleWebhookEventRecord, bool]:
    minimized_data = sanitize_webhook_event(technical_data)
    event_id = minimized_data.get("id")
    event_type = minimized_data.get("event")
    if not isinstance(event_id, str) or not _EVENT_ID_PATTERN.fullmatch(event_id):
        raise ValueError("event_id de webhook invalido")
    if (
        not isinstance(event_type, str)
        or not _EVENT_TYPE_PATTERN.fullmatch(event_type)
    ):
        raise ValueError("event_type de webhook invalido")
    normalized_unit = _normalize_required(unidade, "unidade", 100)
    normalized_environment = _normalize_environment(environment)
    normalized_wallet = _normalize_required(
        account_wallet_id,
        "account_wallet_id",
        100,
    )
    serialized = json.dumps(
        minimized_data,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    cursor.execute(
        f"""
        INSERT INTO asaas_sale_webhook_events (
            unidade,
            environment,
            account_wallet_id,
            event_id,
            event_type,
            technical_data
        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (environment, account_wallet_id, event_id)
        DO NOTHING
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            normalized_unit,
            normalized_environment,
            normalized_wallet,
            event_id,
            event_type,
            serialized,
        ),
    )
    inserted = cursor.fetchone()
    if inserted is not None:
        return _record_from_row(inserted), True

    cursor.execute(
        f"""
        SELECT {RETURNING_COLUMNS}
        FROM asaas_sale_webhook_events
        WHERE environment = %s
          AND account_wallet_id = %s
          AND event_id = %s
        LIMIT 1
        """,
        (normalized_environment, normalized_wallet, event_id),
    )
    existing = _required_record(
        cursor.fetchone(),
        "Evento Asaas duplicado nao localizado",
    )
    if (
        existing.unidade != normalized_unit
        or existing.event_type != event_type
        or existing.technical_data != minimized_data
    ):
        raise RuntimeError("Conflito na identidade idempotente do evento Asaas")
    return existing, False


def get_webhook_event(
    cursor: Any,
    *,
    event_id: int,
) -> Optional[AsaasSaleWebhookEventRecord]:
    _validate_positive_id(event_id, "event_id")
    cursor.execute(
        f"""
        SELECT {RETURNING_COLUMNS}
        FROM asaas_sale_webhook_events
        WHERE id = %s
        LIMIT 1
        """,
        (event_id,),
    )
    row = cursor.fetchone()
    return _record_from_row(row) if row else None


def claim_webhook_event(
    cursor: Any,
    *,
    event_id: int,
    stale_before: Optional[datetime] = None,
) -> Optional[AsaasSaleWebhookEventRecord]:
    _validate_positive_id(event_id, "event_id")
    cursor.execute(
        f"""
        UPDATE asaas_sale_webhook_events
        SET status = 'processando',
            attempt_count = attempt_count + 1,
            last_error_code = NULL,
            last_attempt_at = NOW(),
            next_retry_at = NULL,
            updated_at = NOW()
        WHERE id = %s
          AND (
                status = 'pendente'
                OR (status = 'retry' AND next_retry_at <= NOW())
                OR (
                    status = 'processando'
                    AND %s IS NOT NULL
                    AND last_attempt_at <= %s
                )
              )
        RETURNING {RETURNING_COLUMNS}
        """,
        (event_id, stale_before, stale_before),
    )
    row = cursor.fetchone()
    return _record_from_row(row) if row else None


def find_resource_for_event(
    cursor: Any,
    *,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    event_type: str,
    candidates: list[tuple[str, str]],
) -> Optional[AsaasSaleResourceMatch]:
    normalized_unit = _normalize_required(unidade, "unidade", 100)
    normalized_environment = _normalize_environment(environment)
    normalized_wallet = _normalize_required(
        account_wallet_id,
        "account_wallet_id",
        100,
    )
    expected_resource_type = _expected_resource_type(event_type)
    if expected_resource_type is None:
        return None
    normalized_candidates = [
        (resource_type, resource_id)
        for resource_type, resource_id in candidates
        if resource_type == expected_resource_type
        and _RESOURCE_ID_PATTERN.fullmatch(resource_id)
    ]
    if not normalized_candidates:
        return None

    resource_types = [item[0] for item in normalized_candidates]
    resource_ids = [item[1] for item in normalized_candidates]
    cursor.execute(
        """
        SELECT id, integration_id, resource_type, asaas_resource_id
        FROM asaas_sale_resources
        WHERE unidade = %s
          AND environment = %s
          AND account_wallet_id = %s
          AND resource_type = ANY(%s)
          AND asaas_resource_id = ANY(%s)
        ORDER BY id
        """,
        (
            normalized_unit,
            normalized_environment,
            normalized_wallet,
            resource_types,
            resource_ids,
        ),
    )
    matches = cursor.fetchall()
    by_key = {
        (
            row[2] if not isinstance(row, Mapping) else row["resource_type"],
            row[3] if not isinstance(row, Mapping) else row["asaas_resource_id"],
        ): row
        for row in matches
    }
    for candidate in normalized_candidates:
        row = by_key.get(candidate)
        if row is None:
            continue
        if isinstance(row, Mapping):
            return AsaasSaleResourceMatch(
                id=row["id"],
                integration_id=row["integration_id"],
                resource_type=row["resource_type"],
                asaas_resource_id=row["asaas_resource_id"],
            )
        return AsaasSaleResourceMatch(*row)
    return None


def find_related_resource_context(
    cursor: Any,
    *,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    event_type: str,
    candidates: list[tuple[str, str]],
) -> Optional[AsaasSaleResourceMatch]:
    """Resolve um unico pai tecnico para vincular um recurso novo.

    O fallback nunca escolhe entre duas integracoes. Ele so aceita relacoes
    oficiais presentes no mesmo evento autenticado e no mesmo escopo de conta.
    """
    expected = _expected_resource_type(event_type)
    allowed_parents = {
        "payment": {
            "subscription",
            "installment",
            "pix_instruction",
            "pix_authorization",
            "checkout",
        },
        "subscription": {"checkout", "pix_authorization"},
        "pix_instruction": {"pix_authorization"},
    }.get(expected, set())
    normalized_candidates = [
        (resource_type, resource_id)
        for resource_type, resource_id in dict.fromkeys(candidates)
        if resource_type in allowed_parents
        and _RESOURCE_ID_PATTERN.fullmatch(resource_id)
    ]
    if not normalized_candidates:
        return None

    normalized_unit = _normalize_required(unidade, "unidade", 100)
    normalized_environment = _normalize_environment(environment)
    normalized_wallet = _normalize_required(
        account_wallet_id,
        "account_wallet_id",
        100,
    )
    cursor.execute(
        """
        SELECT id, integration_id, resource_type, asaas_resource_id
        FROM asaas_sale_resources
        WHERE unidade = %s
          AND environment = %s
          AND account_wallet_id = %s
          AND (resource_type, asaas_resource_id) IN (
              SELECT * FROM unnest(%s::text[], %s::text[])
          )
        ORDER BY id
        """,
        (
            normalized_unit,
            normalized_environment,
            normalized_wallet,
            [item[0] for item in normalized_candidates],
            [item[1] for item in normalized_candidates],
        ),
    )
    matches = cursor.fetchall()
    integration_ids = {
        int(row[1] if not isinstance(row, Mapping) else row["integration_id"])
        for row in matches
    }
    if not matches:
        return None
    if len(integration_ids) != 1:
        raise RuntimeError("Conflito de escopo em recurso relacionado Asaas")
    row = matches[0]
    if isinstance(row, Mapping):
        return AsaasSaleResourceMatch(
            id=row["id"],
            integration_id=row["integration_id"],
            resource_type=row["resource_type"],
            asaas_resource_id=row["asaas_resource_id"],
        )
    return AsaasSaleResourceMatch(*row)


def find_integration_by_external_reference(
    cursor: Any,
    *,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    external_reference: Optional[str],
) -> Optional[int]:
    if not external_reference or not _EXTERNAL_REFERENCE_PATTERN.fullmatch(
        external_reference
    ):
        return None
    cursor.execute(
        """
        SELECT id
        FROM asaas_sale_integrations
        WHERE unidade = %s
          AND environment = %s
          AND account_wallet_id = %s
          AND external_reference = %s
        LIMIT 2
        """,
        (
            _normalize_required(unidade, "unidade", 100),
            _normalize_environment(environment),
            _normalize_required(account_wallet_id, "account_wallet_id", 100),
            external_reference,
        ),
    )
    rows = cursor.fetchall()
    if len(rows) > 1:
        raise RuntimeError("Referencia Asaas corresponde a integracoes ambiguas")
    if not rows:
        return None
    row = rows[0]
    return int(row["id"] if isinstance(row, Mapping) else row[0])


def update_resource_from_event(
    cursor: Any,
    *,
    resource_id: int,
    event_type: str,
    remote_status: Optional[str],
    event_created_at: Optional[datetime],
) -> AsaasSaleResourceEventUpdate:
    _validate_positive_id(resource_id, "resource_id")
    if not _EVENT_TYPE_PATTERN.fullmatch(str(event_type or "")):
        raise ValueError("event_type invalido")
    normalized_status = _normalize_remote_status(remote_status)
    normalized_event_at = _normalize_optional_datetime(event_created_at)
    cursor.execute(
        """
        UPDATE asaas_sale_resources AS resource
        SET remote_status = CASE
                WHEN incoming.occurred_at = resource.last_event_at
                THEN NULL
                WHEN resource.last_event_at IS NULL
                  OR (
                    incoming.occurred_at IS NOT NULL
                    AND incoming.occurred_at > resource.last_event_at
                  )
                THEN COALESCE(%s, resource.remote_status)
                ELSE resource.remote_status
            END,
            last_event_type = CASE
                WHEN incoming.occurred_at = resource.last_event_at
                THEN 'ORDER_AMBIGUOUS'
                WHEN resource.last_event_at IS NULL
                  OR (
                    incoming.occurred_at IS NOT NULL
                    AND incoming.occurred_at > resource.last_event_at
                  )
                THEN %s
                ELSE resource.last_event_type
            END,
            last_event_at = CASE
                WHEN resource.last_event_at IS NULL
                  OR (
                    incoming.occurred_at IS NOT NULL
                    AND incoming.occurred_at > resource.last_event_at
                  )
                THEN COALESCE(incoming.occurred_at, NOW())
                ELSE resource.last_event_at
            END,
            needs_reconciliation = CASE
                WHEN incoming.occurred_at = resource.last_event_at
                THEN TRUE
                WHEN resource.last_event_at IS NULL
                  OR (
                    incoming.occurred_at IS NOT NULL
                    AND incoming.occurred_at > resource.last_event_at
                  )
                THEN FALSE
                ELSE resource.needs_reconciliation
            END,
            updated_at = NOW()
        FROM (SELECT %s::timestamptz AS occurred_at) AS incoming
        WHERE resource.id = %s
        RETURNING
            resource.needs_reconciliation,
            resource.last_event_type,
            resource.last_event_at
        """,
        (normalized_status, event_type, normalized_event_at, resource_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Recurso Asaas nao localizado para atualizar evento")
    needs_reconciliation = (
        row.get("needs_reconciliation") if isinstance(row, Mapping) else row[0]
    )
    last_event_type = (
        row.get("last_event_type") if isinstance(row, Mapping) else row[1]
    )
    last_event_at = (
        row.get("last_event_at") if isinstance(row, Mapping) else row[2]
    )
    if not isinstance(needs_reconciliation, bool):
        raise RuntimeError("Estado de reconciliacao do recurso Asaas invalido")
    return AsaasSaleResourceEventUpdate(
        needs_reconciliation=needs_reconciliation,
        event_applied=(
            not needs_reconciliation
            and last_event_type == event_type
            and last_event_at == normalized_event_at
        ),
    )


def mark_webhook_processed(
    cursor: Any,
    *,
    event_id: int,
    claim_attempt: int,
    resource_id: int,
) -> AsaasSaleWebhookEventRecord:
    return _finish_webhook(
        cursor,
        event_id=event_id,
        claim_attempt=claim_attempt,
        status="processado",
        resource_id=resource_id,
        error_code=None,
        next_retry_at=None,
    )


def mark_webhook_processed_without_sale_resource(
    cursor: Any,
    *,
    event_id: int,
    claim_attempt: int,
) -> AsaasSaleWebhookEventRecord:
    """Finaliza evento reconhecido por um fluxo que nao usa sale_resources."""
    return _finish_webhook(
        cursor,
        event_id=event_id,
        claim_attempt=claim_attempt,
        status="processado",
        resource_id=None,
        error_code=None,
        next_retry_at=None,
    )


def mark_webhook_ignored(
    cursor: Any,
    *,
    event_id: int,
    claim_attempt: int,
) -> AsaasSaleWebhookEventRecord:
    return _finish_webhook(
        cursor,
        event_id=event_id,
        claim_attempt=claim_attempt,
        status="ignorado",
        resource_id=None,
        error_code=None,
        next_retry_at=None,
    )


def mark_webhook_retry(
    cursor: Any,
    *,
    event_id: int,
    claim_attempt: int,
    next_retry_at: datetime,
    error_code: str,
) -> AsaasSaleWebhookEventRecord:
    return _finish_webhook(
        cursor,
        event_id=event_id,
        claim_attempt=claim_attempt,
        status="retry",
        resource_id=None,
        error_code=_normalize_error_code(error_code),
        next_retry_at=next_retry_at,
    )


def extract_resource_candidates(
    technical_data: dict[str, Any],
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    def visit(mapping: Mapping[str, Any], *, depth: int) -> None:
        if depth > 6:
            return
        for key, value in mapping.items():
            resource_type = _RESOURCE_KEYS.get(key)
            candidate = None
            if resource_type is not None:
                if isinstance(value, str):
                    candidate = value
                elif isinstance(value, Mapping):
                    raw_id = value.get("id")
                    if isinstance(raw_id, str):
                        candidate = raw_id
                if candidate and _RESOURCE_ID_PATTERN.fullmatch(candidate):
                    candidates.append((resource_type, candidate))

            if isinstance(value, Mapping):
                visit(value, depth=depth + 1)

    visit(technical_data, depth=0)
    return list(dict.fromkeys(candidates))


def link_related_resources_from_event(
    cursor: Any,
    *,
    integration_id: int,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    candidates: list[tuple[str, str]],
) -> None:
    """Vincula IDs tecnicos secundarios sem reter o restante do webhook."""
    _validate_positive_id(integration_id, "integration_id")
    normalized_unit = _normalize_required(unidade, "unidade", 100)
    normalized_environment = _normalize_environment(environment)
    normalized_wallet = _normalize_required(
        account_wallet_id,
        "account_wallet_id",
        100,
    )
    cursor.execute(
        """
        SELECT external_reference
        FROM asaas_sale_integrations
        WHERE id = %s
          AND unidade = %s
          AND environment = %s
          AND account_wallet_id = %s
        LIMIT 1
        """,
        (
            integration_id,
            normalized_unit,
            normalized_environment,
            normalized_wallet,
        ),
    )
    integration_row = cursor.fetchone()
    if integration_row is None:
        raise RuntimeError("Integracao do webhook Asaas nao localizada")
    external_reference = (
        integration_row["external_reference"]
        if isinstance(integration_row, Mapping)
        else integration_row[0]
    )
    for resource_type, resource_id in dict.fromkeys(candidates):
        if (
            resource_type not in set(_RESOURCE_KEYS.values())
            or not _RESOURCE_ID_PATTERN.fullmatch(resource_id)
        ):
            continue
        cursor.execute(
            """
            INSERT INTO asaas_sale_resources (
                integration_id,
                unidade,
                environment,
                account_wallet_id,
                resource_type,
                asaas_resource_id,
                external_reference,
                remote_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'CREATED')
            ON CONFLICT (
                environment,
                account_wallet_id,
                resource_type,
                asaas_resource_id
            ) DO NOTHING
            RETURNING id
            """,
            (
                integration_id,
                normalized_unit,
                normalized_environment,
                normalized_wallet,
                resource_type,
                resource_id,
                external_reference,
            ),
        )
        if cursor.fetchone() is not None:
            continue
        cursor.execute(
            """
            SELECT integration_id, unidade, environment, account_wallet_id
            FROM asaas_sale_resources
            WHERE environment = %s
              AND account_wallet_id = %s
              AND resource_type = %s
              AND asaas_resource_id = %s
            LIMIT 1
            """,
            (
                normalized_environment,
                normalized_wallet,
                resource_type,
                resource_id,
            ),
        )
        existing = cursor.fetchone()
        if existing is None:
            raise RuntimeError("Recurso secundario Asaas nao persistido")
        existing_values = (
            (
                existing["integration_id"],
                existing["unidade"],
                existing["environment"],
                existing["account_wallet_id"],
            )
            if isinstance(existing, Mapping)
            else tuple(existing)
        )
        if existing_values != (
            integration_id,
            normalized_unit,
            normalized_environment,
            normalized_wallet,
        ):
            raise RuntimeError("Conflito de escopo em recurso secundario Asaas")


def _expected_resource_type(event_type: str) -> Optional[str]:
    normalized = str(event_type or "").strip().upper()
    if normalized.startswith("PAYMENT_"):
        return "payment"
    if normalized.startswith("SUBSCRIPTION_"):
        return "subscription"
    if normalized.startswith("CHECKOUT_"):
        return "checkout"
    if "PAYMENT_INSTRUCTION_" in normalized:
        return "pix_instruction"
    if "AUTHORIZATION_" in normalized:
        return "pix_authorization"
    return None


def extract_remote_status(technical_data: dict[str, Any]) -> Optional[str]:
    for key in _RESOURCE_KEYS:
        value = technical_data.get(key)
        if isinstance(value, Mapping):
            status = value.get("status")
            if isinstance(status, str):
                return _normalize_remote_status(status)
    status = technical_data.get("status")
    if isinstance(status, str):
        return _normalize_remote_status(status)
    return None


def extract_payment_projection(
    technical_data: dict[str, Any],
) -> Optional[AsaasSalePaymentProjection]:
    payment = _find_mapping(technical_data, "payment")
    instruction = _find_mapping(technical_data, "paymentInstruction")
    raw_payment_id: Any = None
    if payment is not None:
        raw_payment_id = payment.get("id")
    if raw_payment_id is None and instruction is not None:
        nested_payment = instruction.get("payment")
        if isinstance(nested_payment, Mapping):
            raw_payment_id = nested_payment.get("id")
        else:
            raw_payment_id = nested_payment
    if not isinstance(raw_payment_id, str) or not _RESOURCE_ID_PATTERN.fullmatch(
        raw_payment_id
    ):
        return None

    source = payment or instruction or {}
    raw_due_date = source.get("dueDate")
    due_date = None
    if isinstance(raw_due_date, str):
        try:
            due_date = date.fromisoformat(raw_due_date)
        except ValueError:
            due_date = None

    paid_at = None
    for key in ("paymentDate", "confirmedDate", "clientPaymentDate"):
        raw_paid_at = source.get(key)
        if isinstance(raw_paid_at, str):
            paid_at = _parse_provider_datetime(raw_paid_at)
            if paid_at is not None:
                break

    raw_reference = source.get("externalReference")
    external_reference = (
        raw_reference
        if isinstance(raw_reference, str)
        and _EXTERNAL_REFERENCE_PATTERN.fullmatch(raw_reference)
        else None
    )
    raw_status = source.get("status")
    return AsaasSalePaymentProjection(
        payment_id=raw_payment_id,
        remote_status=_normalize_remote_status(raw_status),
        due_date=due_date,
        paid_at=paid_at,
        external_reference=external_reference,
    )


def extract_safe_external_reference(
    technical_data: dict[str, Any],
) -> Optional[str]:
    def visit(value: Mapping[str, Any], *, depth: int) -> Optional[str]:
        if depth > 6:
            return None
        raw_reference = value.get("externalReference")
        if isinstance(raw_reference, str) and _EXTERNAL_REFERENCE_PATTERN.fullmatch(
            raw_reference
        ):
            return raw_reference
        for nested in value.values():
            if isinstance(nested, Mapping):
                found = visit(nested, depth=depth + 1)
                if found is not None:
                    return found
        return None

    return visit(technical_data, depth=0)


def link_payment_to_local_installment(
    cursor: Any,
    *,
    integration_id: int,
    projection: AsaasSalePaymentProjection,
) -> Optional[int]:
    """Vincula uma cobranca recorrente a uma unica parcela por vencimento."""
    _validate_positive_id(integration_id, "integration_id")
    cursor.execute(
        """
        SELECT link.numero_parcela, installment.data_vencimento
        FROM asaas_sale_payment_links AS link
        JOIN asaas_sale_resources AS resource
          ON resource.id = link.resource_id
        JOIN venda_parcelas AS installment
          ON installment.venda_id = link.venda_id
         AND installment.numero_parcela = link.numero_parcela
        WHERE link.integration_id = %s
          AND resource.resource_type = 'payment'
          AND resource.asaas_resource_id = %s
        LIMIT 1
        """,
        (integration_id, projection.payment_id),
    )
    existing = cursor.fetchone()
    if existing is not None:
        number = int(
            existing["numero_parcela"]
            if isinstance(existing, Mapping)
            else existing[0]
        )
        stored_due_date = (
            existing["data_vencimento"]
            if isinstance(existing, Mapping)
            else existing[1]
        )
        if projection.due_date is not None and stored_due_date != projection.due_date:
            raise RuntimeError("Conflito de vencimento em cobranca Asaas")
        return number
    if projection.due_date is None:
        return None

    cursor.execute(
        """
        SELECT
            integration.venda_id,
            integration.unidade,
            integration.environment,
            integration.account_wallet_id,
            integration.external_reference,
            installment.numero_parcela,
            resource.id
        FROM asaas_sale_integrations AS integration
        JOIN venda_parcelas AS installment
          ON installment.venda_id = integration.venda_id
         AND installment.data_vencimento = %s
        JOIN asaas_sale_resources AS resource
          ON resource.integration_id = integration.id
         AND resource.resource_type = 'payment'
         AND resource.asaas_resource_id = %s
        WHERE integration.id = %s
        ORDER BY installment.numero_parcela
        """,
        (projection.due_date, projection.payment_id, integration_id),
    )
    matches = cursor.fetchall()
    if len(matches) != 1:
        if matches:
            raise RuntimeError("Cobranca Asaas corresponde a parcelas ambiguas")
        return None
    row = matches[0]
    value = lambda name, index: row[name] if isinstance(row, Mapping) else row[index]
    venda_id = int(value("venda_id", 0))
    unidade = str(value("unidade", 1))
    environment = str(value("environment", 2))
    account_wallet_id = str(value("account_wallet_id", 3))
    external_reference = str(value("external_reference", 4))
    numero_parcela = int(value("numero_parcela", 5))
    resource_id = int(value("id", 6))
    if (
        projection.external_reference is not None
        and projection.external_reference != external_reference
    ):
        raise RuntimeError("Conflito de referencia em cobranca Asaas")

    cursor.execute(
        """
        INSERT INTO asaas_sale_payment_links (
            integration_id,
            venda_id,
            resource_id,
            numero_parcela,
            unidade,
            environment,
            account_wallet_id,
            resource_type
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'payment')
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (
            integration_id,
            venda_id,
            resource_id,
            numero_parcela,
            unidade,
            environment,
            account_wallet_id,
        ),
    )
    if cursor.fetchone() is None:
        cursor.execute(
            """
            SELECT resource_id, numero_parcela
            FROM asaas_sale_payment_links
            WHERE integration_id = %s
              AND (resource_id = %s OR numero_parcela = %s)
            LIMIT 2
            """,
            (integration_id, resource_id, numero_parcela),
        )
        links = cursor.fetchall()
        if len(links) != 1:
            raise RuntimeError("Conflito de vinculo em cobranca Asaas")
        link = links[0]
        linked_resource = int(
            link["resource_id"] if isinstance(link, Mapping) else link[0]
        )
        linked_number = int(
            link["numero_parcela"] if isinstance(link, Mapping) else link[1]
        )
        if linked_resource != resource_id or linked_number != numero_parcela:
            raise RuntimeError("Conflito de vinculo em cobranca Asaas")
    return numero_parcela


def project_payment_event_to_installment(
    cursor: Any,
    *,
    integration_id: int,
    event_type: str,
    projection: AsaasSalePaymentProjection,
) -> bool:
    numero_parcela = link_payment_to_local_installment(
        cursor,
        integration_id=integration_id,
        projection=projection,
    )
    if numero_parcela is None:
        return False
    if not event_type.startswith("PAYMENT_"):
        return True

    # O cronograma de venda_parcelas e imutavel por trigger. O estado efetivo
    # fica no recurso remoto e e projetado pelo portal por meio deste vinculo.
    return _local_installment_status(event_type, projection.remote_status) is not None


def project_recurring_sale_state(
    cursor: Any,
    *,
    integration_id: int,
    event_type: str,
    remote_status: Optional[str],
) -> None:
    cursor.execute(
        """
        SELECT venda_id, payment_method
        FROM asaas_sale_integrations
        WHERE id = %s
        LIMIT 1
        """,
        (integration_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Integracao recorrente Asaas nao localizada")
    venda_id = int(row["venda_id"] if isinstance(row, Mapping) else row[0])
    payment_method = str(
        row["payment_method"] if isinstance(row, Mapping) else row[1]
    )
    activate = (
        payment_method == "ASAAS_PIX_AUTOMATIC"
        and "AUTHORIZATION" in event_type
        and remote_status == "ACTIVE"
    ) or (
        payment_method == "ASAAS_CREDIT_CARD_RECURRENT"
        and event_type == "CHECKOUT_PAID"
        and remote_status == "PAID"
    )
    terminal = (
        payment_method == "ASAAS_PIX_AUTOMATIC"
        and remote_status in {"CANCELLED", "CANCELED", "EXPIRED", "REFUSED"}
        and "AUTHORIZATION" in event_type
    ) or (
        payment_method == "ASAAS_CREDIT_CARD_RECURRENT"
        and remote_status in {"CANCELLED", "CANCELED", "EXPIRED"}
        and event_type.startswith("CHECKOUT_")
    )
    if activate:
        cursor.execute(
            """
            UPDATE vendas
            SET status_venda = 'Efetuada'
            WHERE id = %s
              AND status_venda IN ('Pendente Asaas', 'Efetuada')
            """,
            (venda_id,),
        )
    elif terminal:
        cursor.execute(
            """
            UPDATE asaas_sale_integrations
            SET status = 'cancelado',
                remote_creation_state = 'falha_terminal',
                remote_confirmed_at = NULL,
                reconciliation_required = FALSE,
                updated_at = NOW()
            WHERE id = %s
              AND status = 'integrado'
            RETURNING id
            """,
            (integration_id,),
        )
        if cursor.fetchone() is not None:
            cursor.execute(
                """
                UPDATE vendas
                SET status_venda = 'Cancelada'
                WHERE id = %s
                  AND status_venda = 'Pendente Asaas'
                """,
                (venda_id,),
            )


def _local_installment_status(
    event_type: str,
    remote_status: Optional[str],
) -> Optional[str]:
    if event_type in {
        "PAYMENT_CONFIRMED",
        "PAYMENT_RECEIVED",
        "PAYMENT_RECEIVED_IN_CASH",
    } or remote_status in {"CONFIRMED", "RECEIVED", "RECEIVED_IN_CASH"}:
        return "Pago"
    if "CHARGEBACK" in event_type or remote_status in {
        "CHARGEBACK_REQUESTED",
        "CHARGEBACK_DISPUTE",
        "AWAITING_CHARGEBACK_REVERSAL",
    }:
        return "Disputa"
    if "REFUND" in event_type or remote_status in {
        "REFUNDED",
        "PARTIALLY_REFUNDED",
        "REFUND_REQUESTED",
        "REFUND_IN_PROGRESS",
    }:
        return "Estornado"
    if event_type == "PAYMENT_OVERDUE" or remote_status == "OVERDUE":
        return "Vencido"
    if event_type in {"PAYMENT_DELETED", "PAYMENT_BANK_SLIP_CANCELLED"}:
        return "Cancelada"
    if event_type == "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED":
        return "Falha"
    if event_type in {"PAYMENT_CREATED", "PAYMENT_UPDATED"} or remote_status in {
        "CREATED",
        "PENDING",
        "AWAITING_RISK_ANALYSIS",
    }:
        return "Pendente"
    return None


def _find_mapping(
    value: Mapping[str, Any],
    key: str,
    *,
    depth: int = 0,
) -> Optional[Mapping[str, Any]]:
    if depth > 6:
        return None
    direct = value.get(key)
    if isinstance(direct, Mapping):
        return direct
    for nested in value.values():
        if isinstance(nested, Mapping):
            found = _find_mapping(nested, key, depth=depth + 1)
            if found is not None:
                return found
    return None


def extract_event_created_at(
    technical_data: dict[str, Any],
) -> Optional[datetime]:
    value = technical_data.get("dateCreated")
    if not isinstance(value, str):
        return None
    return _parse_provider_datetime(value)


def extract_account_id(technical_data: dict[str, Any]) -> Optional[str]:
    account = technical_data.get("account")
    value = account.get("id") if isinstance(account, Mapping) else None
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        return None


def _finish_webhook(
    cursor: Any,
    *,
    event_id: int,
    claim_attempt: int,
    status: str,
    resource_id: Optional[int],
    error_code: Optional[str],
    next_retry_at: Optional[datetime],
) -> AsaasSaleWebhookEventRecord:
    _validate_positive_id(event_id, "event_id")
    _validate_positive_id(claim_attempt, "claim_attempt")
    if resource_id is not None:
        _validate_positive_id(resource_id, "resource_id")
    cursor.execute(
        f"""
        UPDATE asaas_sale_webhook_events
        SET status = %s,
            resource_id = COALESCE(%s, resource_id),
            last_error_code = %s,
            next_retry_at = %s,
            processed_at = CASE
                WHEN %s IN ('processado', 'ignorado', 'erro_terminal')
                THEN NOW()
                ELSE NULL
            END,
            updated_at = NOW()
        WHERE id = %s
          AND status = 'processando'
          AND attempt_count = %s
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            status,
            resource_id,
            error_code,
            next_retry_at,
            status,
            event_id,
            claim_attempt,
        ),
    )
    return _required_record(
        cursor.fetchone(),
        "Evento Asaas ausente ou claim perdido",
    )


def _sanitize_mapping(value: Mapping[str, Any], *, depth: int) -> dict[str, Any]:
    if depth > 5:
        return {}
    sanitized: dict[str, Any] = {}
    for key, raw_value in value.items():
        if key not in _ALLOWED_TECHNICAL_KEYS:
            continue
        clean_value = _sanitize_value(key, raw_value, depth=depth + 1)
        if clean_value is not None:
            sanitized[key] = clean_value
    return sanitized


def _sanitize_value(key: str, value: Any, *, depth: int) -> Any:
    if isinstance(value, Mapping):
        return _sanitize_mapping(value, depth=depth)
    if not isinstance(value, str):
        return None
    if key == "dateCreated":
        parsed = _parse_provider_datetime(value)
        return parsed.isoformat() if parsed is not None else None
    if key == "event":
        return value if _EVENT_TYPE_PATTERN.fullmatch(value) else None
    if key == "id" or key in _RESOURCE_KEYS:
        return value if _RESOURCE_ID_PATTERN.fullmatch(value) else None
    if key == "status":
        return value if value in _ALLOWED_REMOTE_STATUSES else None
    if key == "dueDate":
        return _sanitize_date(value)
    if key in {"paymentDate", "confirmedDate", "clientPaymentDate"}:
        parsed = _parse_provider_datetime(value)
        return parsed.isoformat() if parsed is not None else None
    if key == "externalReference":
        return value if _EXTERNAL_REFERENCE_PATTERN.fullmatch(value) else None
    return None


def _sanitize_date(value: Any) -> Optional[str]:
    try:
        normalized = date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None
    return normalized.isoformat()


def _record_from_row(row: Any) -> AsaasSaleWebhookEventRecord:
    if isinstance(row, Mapping):
        values = {column: row[column] for column in _column_names()}
    else:
        values = dict(zip(_column_names(), row))
    technical_data = values["technical_data"]
    if isinstance(technical_data, str):
        technical_data = json.loads(technical_data)
    if not isinstance(technical_data, dict):
        raise RuntimeError("Envelope tecnico do webhook Asaas invalido")
    values["technical_data"] = technical_data
    return AsaasSaleWebhookEventRecord(**values)


def _required_record(row: Any, message: str) -> AsaasSaleWebhookEventRecord:
    if row is None:
        raise RuntimeError(message)
    return _record_from_row(row)


def _column_names() -> tuple[str, ...]:
    return tuple(
        line.strip().rstrip(",")
        for line in RETURNING_COLUMNS.strip().splitlines()
    )


def _normalize_required(value: Any, name: str, max_length: int) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > max_length:
        raise ValueError(f"{name} invalido")
    return normalized


def _normalize_environment(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized not in {"sandbox", "production"}:
        raise ValueError("environment invalido")
    return normalized


def _normalize_remote_status(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    if normalized not in _ALLOWED_REMOTE_STATUSES:
        return None
    return normalized


def _parse_provider_datetime(value: str) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw or len(raw) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_ASAAS_TIMEZONE)
    return parsed.astimezone(timezone.utc)


def _normalize_optional_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("event_created_at deve possuir timezone")
    return value.astimezone(timezone.utc)


def _normalize_error_code(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    return (
        normalized
        if _ERROR_CODE_PATTERN.fullmatch(normalized)
        and not re.search(r"\d{4,}", normalized)
        and len(re.sub(r"\D", "", normalized)) <= 3
        else "integration_error"
    )


def _validate_positive_id(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} deve ser inteiro positivo")
    return value
