"""Entrada avulsa Sandbox que antecede o Carnê Asaas."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re
from typing import Any, Callable, Optional
from uuid import UUID

from app.asaas_sdk.exceptions import (
    AsaasAPIError,
    AsaasConfigurationError,
    AsaasConnectionError,
    AsaasIntegrationError,
    AsaasValidationError,
)
from app.asaas_sales_sdk import AsaasSalesSDK
from app.services.asaas_sale_database import DatabaseConnection
from app.models.vendas_asaas import AsaasCarneSaleCreate
from app.services.asaas_sale_creation_service import (
    CONTRACT_ODONTOGRAM_TYPES,
    PAYMENT_METHOD_CODE,
    _calculate_gross_value,
    _calculate_rule_discount,
    calculate_asaas_installment_values,
)
from app.services.asaas_sales_config import (
    canonicalize_asaas_sales_unit,
    is_asaas_sandbox_ni_odontogram_type_available,
    is_asaas_sales_carne_enabled,
    is_asaas_sales_entry_split_policy_approved,
)
from app.services.asaas_account_approval_service import AsaasApprovalTarget, require_approved_targets
from app.services.asaas_receiver_identity_provider import receiver_identity_provider_for_environment
from app.services.asaas_split_service import (
    AsaasSplitPlan,
    AsaasSplitValidationError,
    _json_to_plan,
    _plan_to_json,
    validate_asaas_new_split_preview,
)


ENTRY_METHODS = frozenset({"ASAAS_ENTRY_PIX"})
_BILLING_TYPES = {
    "ASAAS_ENTRY_PIX": "PIX",
}
# Cash receipt does not prove an Asaas split transfer for the versioned Pix
# entry, so it remains non-paid and requires an explicit reconciliation path.
_PAID_REMOTE_STATUSES = frozenset({"RECEIVED", "CONFIRMED"})
_TERMINAL_REMOTE_STATUSES = frozenset(
    {
        "OVERDUE", "REFUNDED", "REFUND_REQUESTED", "REFUND_IN_PROGRESS",
        "CHARGEBACK_REQUESTED", "CHARGEBACK_DISPUTE",
        "AWAITING_CHARGEBACK_REVERSAL", "DUNNING_REQUESTED", "DUNNING_RECEIVED",
    }
)
_RETRY_DELAY = timedelta(seconds=15)
_STALE_AFTER = timedelta(minutes=5)
_REMOTE_PAYMENT_ID_PATTERN = re.compile(
    r"^(?=.{1,120}$)(?=.*[0-9])(?=.*[_-])[A-Za-z0-9_-]+$"
)
_WEBHOOK_RECONCILABLE_STATUSES = frozenset(
    {
        "pendente",
        "processando",
        "aguardando_pagamento",
        "retry",
        "resultado_incerto",
    }
)


class AsaasEntryError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AsaasEntryNotFoundError(AsaasEntryError):
    pass


class AsaasEntryConflictError(AsaasEntryError):
    pass


@dataclass(frozen=True)
class AsaasEntryCreatedRecord:
    entry_id: int
    status: str
    payment_method: str
    amount: Decimal
    card_installments: int
    created_at: datetime


@dataclass(frozen=True)
class AsaasEntryStatusRecord:
    entry_id: int
    status: str
    payment_method: str
    amount: Decimal
    card_installments: int
    checkout_available: bool
    last_error_code: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AsaasEntryWebhookMatch:
    entry_id: int
    status: str


@dataclass(frozen=True)
class _EntrySnapshot:
    job_id: int
    claim_attempt: int
    entry_id: int
    unidade: str
    environment: str
    account_wallet_id: str
    customer_id: str
    payment_method: str
    card_installments: int
    amount: Decimal
    external_reference: str
    remote_creation_state: str
    remote_attempt_count: int
    remote_payment_id: Optional[str]
    entry_split: list[dict[str, Any]] = field(default_factory=list)
    entry_plan: Optional[AsaasSplitPlan] = None
    issuer_account_id: str = ""
    snapshot_sha256: str = ""
    entry_due_date: str = ""


def create_asaas_entry(
    cursor: Any,
    *,
    client_request_id: UUID,
    intent_version: int,
    first_due_date: Optional[date],
    user_id: int,
    paciente_id: int,
    dentista_id: int,
    odontograma_id: int,
    dependente_id: Optional[int],
    unidade: str,
    total_installments: int,
    payment_method: str,
    card_installments: int,
    environment: str,
    account_wallet_id: str,
    issuer_account_id: Optional[str] = None,
    approval_guard: Optional[Callable[[], bool]] = None,
    split_preview: Optional[Callable[[Mapping[str, Any]], tuple[Any, list[dict[str, Any]]]]] = None,
) -> AsaasEntryCreatedRecord:
    """Cria pré-venda, integração e outbox na mesma transação local."""
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    normalized_method = str(payment_method or "").strip().upper()
    if not canonical_unit:
        raise AsaasEntryError("asaas_entry_unit_invalid")
    if not is_asaas_sales_entry_split_policy_approved():
        raise AsaasEntryError("asaas_entry_split_policy_unavailable")
    if environment != "sandbox":
        raise AsaasEntryError("asaas_entry_sandbox_only")
    if normalized_method not in ENTRY_METHODS:
        raise AsaasEntryError("asaas_entry_method_invalid")
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise AsaasEntryError("asaas_entry_user_invalid")
    if (
        isinstance(total_installments, bool)
        or not isinstance(total_installments, int)
        or not 3 <= total_installments <= 60
    ):
        raise AsaasEntryError("asaas_entry_total_installments_invalid")
    if (
        isinstance(card_installments, bool)
        or not isinstance(card_installments, int)
        or card_installments != 1
    ):
        raise AsaasEntryError("asaas_entry_card_installments_invalid")

    request_id = str(client_request_id)
    fingerprint = _request_fingerprint(
        request_id=request_id,
        intent_version=intent_version,
        first_due_date=first_due_date.isoformat() if isinstance(first_due_date, date) else None,
        user_id=user_id,
        paciente_id=paciente_id,
        dentista_id=dentista_id,
        odontograma_id=odontograma_id,
        dependente_id=dependente_id,
        unidade=canonical_unit,
        total_installments=total_installments,
        payment_method=normalized_method,
        card_installments=card_installments,
    )
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"asaas-entry:{environment}:{account_wallet_id}:{request_id}",),
    )
    cursor.execute(
        """
        SELECT id, status, payment_method, amount, card_installments,
               created_at, request_fingerprint
        FROM asaas_entry_integrations
        WHERE environment = %s
          AND account_wallet_id = %s
          AND idempotency_key = %s
        LIMIT 1
        """,
        (environment, account_wallet_id, request_id),
    )
    replay = cursor.fetchone()
    if replay is not None:
        if str(_value(replay, "request_fingerprint", 6)) != fingerprint:
            raise AsaasEntryConflictError("asaas_entry_idempotency_conflict")
        return _created_record(replay)

    # Date validation deliberately happens only after an idempotent replay so
    # a request made yesterday remains readable after midnight.
    if intent_version != 1:
        raise AsaasEntryError("asaas_entry_intent_version_invalid")
    if not isinstance(first_due_date, date) or first_due_date < date.today() or first_due_date.day > 28:
        raise AsaasEntryError("asaas_entry_due_date_invalid")

    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"asaas-sale-odontograma:{odontograma_id}",),
    )
    cursor.execute(
        """
        SELECT o.paciente_id, o.unidade, o.tipo, o.dependente_id, o.ativo,
               t.valor_base, t.qtd_parcelas, t.id AS tipo_odontograma_id
        FROM odontogramas AS o
        LEFT JOIN tipos_odontograma AS t
          ON LOWER(t.nome) = LOWER(o.tipo) AND t.ativo = TRUE
        WHERE o.id = %s
        LIMIT 1
        """,
        (odontograma_id,),
    )
    source = cursor.fetchone()
    if source is None:
        raise AsaasEntryNotFoundError("asaas_entry_odontogram_not_found")
    if int(_value(source, "paciente_id", 0)) != paciente_id:
        raise AsaasEntryConflictError("asaas_entry_patient_mismatch")
    if canonicalize_asaas_sales_unit(_value(source, "unidade", 1)) != canonical_unit:
        raise AsaasEntryConflictError("asaas_entry_unit_mismatch")
    if not bool(_value(source, "ativo", 4)):
        raise AsaasEntryError("asaas_entry_odontogram_inactive")
    source_dependent = _value(source, "dependente_id", 3)
    if source_dependent is not None:
        source_dependent = int(source_dependent)
    if source_dependent != dependente_id:
        raise AsaasEntryConflictError("asaas_entry_dependent_mismatch")
    odontogram_type_id = _value(source, "tipo_odontograma_id", 7)
    if not is_asaas_sandbox_ni_odontogram_type_available(
        canonical_unit, environment, odontogram_type_id
    ):
        raise AsaasEntryError("asaas_sandbox_ni_odontogram_type_unavailable")

    cursor.execute(
        "SELECT id, ativo FROM dentistas WHERE id = %s LIMIT 1",
        (dentista_id,),
    )
    dentist = cursor.fetchone()
    if dentist is None:
        raise AsaasEntryNotFoundError("asaas_entry_dentist_not_found")
    if not bool(_value(dentist, "ativo", 1)):
        raise AsaasEntryError("asaas_entry_dentist_inactive")

    odontogram_type = str(_value(source, "tipo", 2)).strip().upper()
    configured_installments = _value(source, "qtd_parcelas", 6)
    if (
        odontogram_type in CONTRACT_ODONTOGRAM_TYPES
        and configured_installments and int(configured_installments) != total_installments
    ):
        raise AsaasEntryConflictError("asaas_entry_contract_installments_changed")
    # Keep calculation aligned with the dedicated Carnê source of truth.  The
    # client never supplies values, discounts, products or receivers.
    sale_input = AsaasCarneSaleCreate(
        client_request_id=client_request_id, paciente_id=paciente_id,
        dentista_orcamentista_id=dentista_id, unidade=canonical_unit,
        qtd_parcelas=total_installments, data_vencimento_primeira_parcela=first_due_date,
        odontograma_id=odontograma_id, dependente_id=dependente_id,
    )
    gross, items = _calculate_gross_value(
        cursor, sale=sale_input,
        contract_installment_count=(total_installments if odontogram_type in CONTRACT_ODONTOGRAM_TYPES else None),
    )
    discount = _calculate_rule_discount(
        cursor, unidade=canonical_unit, installment_count=total_installments - 1,
        gross_value=gross, payment_method=PAYMENT_METHOD_CODE,
    )
    net_total = _money(gross - discount)
    if net_total <= 0:
        raise AsaasEntryError("asaas_entry_amount_invalid")
    # The first cycle is the entry; the remaining booklet always owns N-1.
    amount = calculate_asaas_installment_values(net_total, total_installments)[0]
    remaining_values = calculate_asaas_installment_values(
        _money(net_total - amount), total_installments - 1
    )

    cursor.execute(
        """
        SELECT id, status, asaas_customer_id
        FROM asaas_patient_customers
        WHERE paciente_id = %s AND unidade = %s AND environment = %s
          AND account_wallet_id = %s
        LIMIT 1
        """,
        (paciente_id, canonical_unit, environment, account_wallet_id),
    )
    customer = cursor.fetchone()
    if (
        customer is None
        or _value(customer, "status", 1) != "integrado"
        or not _value(customer, "asaas_customer_id", 2)
    ):
        raise AsaasEntryConflictError("asaas_customer_not_ready")

    if approval_guard is None or not approval_guard():
        raise AsaasEntryError("asaas_account_approval_unverified")
    if not isinstance(issuer_account_id, str) or not issuer_account_id.strip():
        raise AsaasEntryError("asaas_entry_issuer_invalid")
    if split_preview is None:
        raise AsaasEntryError("asaas_entry_split_preview_required")
    split_context = {
        "cursor": cursor, "unidade": canonical_unit, "environment": environment,
        "account_wallet_id": account_wallet_id, "odontograma_id": odontograma_id,
        "usuario_venda_id": user_id, "valor_liquido_total": amount,
        "tem_entrada": True, "contexto": "entrada", "remaining_installments": total_installments,
        "dentista_id": dentista_id,
    }
    carne_context = dict(split_context, valor_liquido_total=_money(net_total - amount),
                         contexto="carne", remaining_installments=total_installments - 1,
                         )
    # The complete, authenticated artefacts are checked before any local sale
    # row is written; a malformed callback cannot leave an entry/outbox behind.
    try:
        entry_plan, entry_split = split_preview(split_context)
        if not isinstance(entry_split, list):
            raise AsaasSplitValidationError("asaas_entry_split_invalid")
        carne_plan, carne_split = split_preview(carne_context)
        if not isinstance(carne_split, list):
            raise AsaasSplitValidationError("asaas_entry_split_invalid")
        validate_asaas_new_split_preview(entry_plan, entry_split, unidade=canonical_unit,
            environment=environment, account_wallet_id=account_wallet_id, charge_value=amount, contexto="entrada")
        validate_asaas_new_split_preview(carne_plan, carne_split, unidade=canonical_unit,
            environment=environment, account_wallet_id=account_wallet_id, charge_value=_money(net_total - amount), contexto="carne")
        entry_plan_json = _plan_to_json(entry_plan)
        carne_plan_json = _plan_to_json(carne_plan)
    except AsaasSplitValidationError as exc:
        raise AsaasEntryError(exc.args[0]) from None

    pre_venda_id = f"PV-AS-{client_request_id.hex}"
    cursor.execute(
        """
        INSERT INTO pre_vendas_entradas (
            pre_venda_id, tipo_odontograma, paciente_id, dependente_id,
            dentista_id, unidade, valor_solicitado, valor_pago,
            checkout_id, checkout_url, forma_pagamento_id, status,
            expires_at, metadata_json
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, NULL,
            NULL, NULL, NULL, 'pendente', NOW() + INTERVAL '24 hours',
            jsonb_build_object(
                'odontograma_id', %s,
                'qtd_parcelas_total', %s,
                'actor_user_id', %s,
                'provider', 'asaas'
            )
        )
        """,
        (
            pre_venda_id,
            str(_value(source, "tipo", 2)),
            paciente_id,
            dependente_id,
            dentista_id,
            canonical_unit,
            amount,
            odontograma_id,
            total_installments,
            user_id,
        ),
    )
    external_reference = f"grupojf:entrada:{client_request_id.hex}"
    cursor.execute(
        """
        INSERT INTO asaas_entry_integrations (
            pre_venda_id, asaas_patient_customer_id, odontograma_id,
            unidade, environment, account_wallet_id, payment_method,
            card_installments, amount, idempotency_key, request_fingerprint,
            external_reference
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, status, payment_method, amount, card_installments,
                  created_at, request_fingerprint
        """,
        (
            pre_venda_id,
            int(_value(customer, "id", 0)),
            odontograma_id,
            canonical_unit,
            environment,
            account_wallet_id,
            normalized_method,
            card_installments,
            amount,
            request_id,
            fingerprint,
            external_reference,
        ),
    )
    integration = cursor.fetchone()
    if integration is None:
        raise RuntimeError("Entrada Asaas nao retornada")
    entry_id = int(_value(integration, "id", 0))
    item_snapshot = [
        {"item_number": item.item_number, "product_id": item.product_id,
         "quantity": item.quantity, "unit_value": format(item.unit_value, ".2f"),
         "total_value": format(item.total_value, ".2f")}
        for item in items
    ]
    entry_due_date = date.today().isoformat()
    intent_payload = {
        "version": intent_version, "actor_user_id": user_id,
        "contexto": "entrada",
        "unidade": canonical_unit, "environment": environment,
        "account_wallet_id": account_wallet_id, "paciente_id": paciente_id,
        "issuer_account_id": str(issuer_account_id or ""),
        "dependente_id": dependente_id, "dentista_id": dentista_id,
        "odontograma_id": odontograma_id,
        "qtd_parcelas_total": total_installments,
        "first_due_date": first_due_date.isoformat(),
        "entry_due_date": entry_due_date,
        "gross_total": format(gross, ".2f"), "discount_total": format(discount, ".2f"),
        "net_total": format(net_total, ".2f"), "entry_amount": format(amount, ".2f"),
        "remaining_values": [format(value, ".2f") for value in remaining_values],
        "items": item_snapshot,
    }
    intent_json = json.dumps(intent_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    entry_plan_json_text = json.dumps(entry_plan_json, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    carne_plan_json_text = json.dumps(carne_plan_json, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    snapshot_payload = dict(intent_payload,
        intent_sha256=hashlib.sha256(intent_json.encode("utf-8")).hexdigest(),
        entry_plan_sha256=hashlib.sha256(entry_plan_json_text.encode("utf-8")).hexdigest(),
        entry_payload_sha256=hashlib.sha256(json.dumps(entry_split, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        carne_plan_sha256=hashlib.sha256(carne_plan_json_text.encode("utf-8")).hexdigest(),
        carne_payload_sha256=hashlib.sha256(json.dumps(carne_split, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
    )
    snapshot_payload["snapshot_sha256"] = _snapshot_hash(snapshot_payload)
    snapshot_json = json.dumps(snapshot_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    cursor.execute(
        """
        INSERT INTO asaas_entry_financial_snapshots (
            entry_integration_id, intent_version, intent_sha256, snapshot_json,
            entry_plan_json, entry_split_json, carne_plan_json, carne_split_json
        ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
        """,
        (entry_id, intent_version, hashlib.sha256(intent_json.encode("utf-8")).hexdigest(), snapshot_json,
         entry_plan_json_text, json.dumps(entry_split, separators=(",", ":")), carne_plan_json_text,
         json.dumps(carne_split, separators=(",", ":"))),
    )
    cursor.execute(
        """
        INSERT INTO asaas_entry_jobs (entry_integration_id, operation)
        VALUES (%s, 'provisionar_entrada')
        """,
        (entry_id,),
    )
    return _created_record(integration)


def get_asaas_entry_status(
    cursor: Any, *, entry_id: int, unidade: str
) -> Optional[AsaasEntryStatusRecord]:
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    if not canonical_unit or entry_id <= 0:
        raise AsaasEntryError("asaas_entry_scope_invalid")
    cursor.execute(
        """
        SELECT id, status, payment_method, amount, card_installments,
               checkout_url IS NOT NULL AS checkout_available,
               last_error_code, created_at, updated_at
        FROM asaas_entry_integrations
        WHERE id = %s AND unidade = %s AND environment = 'sandbox'
        LIMIT 1
        """,
        (entry_id, canonical_unit),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return AsaasEntryStatusRecord(
        entry_id=int(_value(row, "id", 0)),
        status=str(_value(row, "status", 1)),
        payment_method=str(_value(row, "payment_method", 2)),
        amount=_money(_value(row, "amount", 3)),
        card_installments=int(_value(row, "card_installments", 4)),
        checkout_available=bool(_value(row, "checkout_available", 5)),
        last_error_code=(
            str(_value(row, "last_error_code", 6))
            if _value(row, "last_error_code", 6) is not None else None
        ),
        created_at=_value(row, "created_at", 7),
        updated_at=_value(row, "updated_at", 8),
    )


def get_asaas_entry_checkout_url(
    cursor: Any, *, entry_id: int, unidade: str
) -> Optional[str]:
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    if not canonical_unit or entry_id <= 0:
        raise AsaasEntryError("asaas_entry_scope_invalid")
    cursor.execute(
        """
        SELECT checkout_url
        FROM asaas_entry_integrations
        WHERE id = %s AND unidade = %s AND environment = 'sandbox'
          AND status IN ('aguardando_pagamento', 'pago', 'retry')
        LIMIT 1
        """,
        (entry_id, canonical_unit),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    value = _value(row, "checkout_url", 0)
    return str(value) if value else None


def list_dispatchable_entry_job_ids(
    cursor: Any, *, unidades: tuple[str, ...], limit: int = 100
) -> list[int]:
    if not unidades:
        return []
    cursor.execute(
        """
        SELECT job.id
        FROM asaas_entry_jobs AS job
        JOIN asaas_entry_integrations AS entry
          ON entry.id = job.entry_integration_id
        WHERE entry.unidade = ANY(%s)
          AND (
            (
                job.status = 'pendente'
                AND (
                    job.last_dispatched_at IS NULL
                    OR job.last_dispatched_at <= NOW() - INTERVAL '5 minutes'
                )
            )
            OR (
                job.status = 'retry'
                AND job.next_retry_at <= NOW()
                AND (
                    job.last_dispatched_at IS NULL
                    OR job.last_dispatched_at < job.next_retry_at
                )
            )
            OR (
                job.status = 'processando'
                AND job.last_attempt_at <= NOW() - INTERVAL '5 minutes'
                AND (
                    job.last_dispatched_at IS NULL
                    OR job.last_dispatched_at <= NOW() - INTERVAL '5 minutes'
                )
            )
          )
        ORDER BY COALESCE(job.next_retry_at, job.created_at), job.id
        LIMIT %s
        """,
        (list(unidades), max(1, min(limit, 100))),
    )
    return [int(_value(row, "id", 0)) for row in cursor.fetchall()]


def find_asaas_entry_for_webhook(
    cursor: Any,
    *,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    event_type: str,
    candidates: list[tuple[str, str]],
) -> Optional[AsaasEntryWebhookMatch]:
    """Localiza somente a entrada tecnica no mesmo alvo Sandbox do evento."""
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    normalized_wallet = str(account_wallet_id or "").strip()
    if not canonical_unit or not normalized_wallet or len(normalized_wallet) > 100:
        raise AsaasEntryError("asaas_entry_webhook_scope_invalid")
    if environment != "sandbox" or not str(event_type or "").startswith("PAYMENT_"):
        return None
    payment_ids = list(
        dict.fromkeys(
            resource_id
            for resource_type, resource_id in candidates
            if resource_type == "payment"
            and isinstance(resource_id, str)
            and _REMOTE_PAYMENT_ID_PATTERN.fullmatch(resource_id)
        )
    )
    if not payment_ids:
        return None
    cursor.execute(
        """
        SELECT id, status
        FROM asaas_entry_integrations
        WHERE unidade = %s
          AND environment = 'sandbox'
          AND account_wallet_id = %s
          AND remote_payment_id = ANY(%s)
        ORDER BY id
        """,
        (canonical_unit, normalized_wallet, payment_ids),
    )
    rows = cursor.fetchall()
    if not rows:
        return None
    if len(rows) != 1:
        raise AsaasEntryConflictError("asaas_entry_webhook_ambiguous")
    row = rows[0]
    return AsaasEntryWebhookMatch(
        entry_id=int(_value(row, "id", 0)),
        status=str(_value(row, "status", 1)),
    )


def wake_asaas_entry_reconciliation(
    cursor: Any, *, match: AsaasEntryWebhookMatch
) -> None:
    """Torna a reconciliacao elegivel sem criar ou alterar cobranca remota."""
    if match.status == "pago":
        return
    if match.status not in _WEBHOOK_RECONCILABLE_STATUSES:
        raise AsaasEntryConflictError("asaas_entry_webhook_status_conflict")
    cursor.execute(
        """
        UPDATE asaas_entry_jobs
        SET status = 'retry', next_retry_at = NOW(),
            last_dispatched_at = NULL, completed_at = NULL,
            last_error_code = 'asaas_entry_webhook_reconciliation',
            updated_at = NOW()
        WHERE entry_integration_id = %s
          AND status IN ('pendente', 'retry')
        RETURNING id
        """,
        (match.entry_id,),
    )
    if cursor.fetchone() is not None:
        return
    cursor.execute(
        """
        SELECT id
        FROM asaas_entry_jobs
        WHERE entry_integration_id = %s
          AND status = 'processando'
        ORDER BY id
        """,
        (match.entry_id,),
    )
    processing = cursor.fetchall()
    if len(processing) > 1:
        raise AsaasEntryConflictError("asaas_entry_webhook_jobs_ambiguous")
    if processing:
        return
    cursor.execute(
        """
        INSERT INTO asaas_entry_jobs (
            entry_integration_id, operation, status, next_retry_at
        ) VALUES (%s, 'reconciliar_entrada', 'pendente', NULL)
        ON CONFLICT (entry_integration_id, operation)
            WHERE status IN ('pendente', 'processando', 'retry')
        DO NOTHING
        RETURNING id
        """,
        (match.entry_id,),
    )
    cursor.fetchone()


def mark_entry_job_dispatched(cursor: Any, *, job_id: int) -> None:
    cursor.execute(
        "UPDATE asaas_entry_jobs SET last_dispatched_at = NOW(), updated_at = NOW() WHERE id = %s",
        (job_id,),
    )


def process_asaas_entry_job(job_id: int) -> None:
    snapshot = _claim_entry_job(job_id)
    if snapshot is None:
        return
    if snapshot.payment_method not in ENTRY_METHODS or snapshot.card_installments != 1:
        _finish_terminal(snapshot, "asaas_entry_method_invalid")
        return
    if (
        snapshot.remote_creation_state == "nao_iniciado"
        and snapshot.remote_attempt_count == 0
        and snapshot.remote_payment_id is None
        and not is_asaas_sales_entry_split_policy_approved()
    ):
        _finish_retry(
            snapshot,
            "asaas_entry_split_policy_unavailable",
            uncertain=False,
        )
        return
    billing_type = _BILLING_TYPES[snapshot.payment_method]
    remote_attempt_reserved = False
    try:
        with AsaasSalesSDK.for_unit(snapshot.unidade) as sdk:
            if (
                snapshot.environment != "sandbox"
                or sdk.account.environment != snapshot.environment
                or sdk.account.account_wallet_id != snapshot.account_wallet_id
                or (snapshot.issuer_account_id and getattr(sdk.account, "account_id", None) != snapshot.issuer_account_id)
            ):
                _finish_terminal(snapshot, "asaas_entry_target_mismatch")
                return

            # Revalidate the exact frozen issuer and receiver identities.  No
            # split/domain lookup is allowed here: changed rules must not
            # change an already accepted financial intention.
            if snapshot.entry_plan is not None and not _frozen_entry_targets_are_approved(sdk, snapshot):
                _finish_terminal(snapshot, "asaas_entry_identity_unverified")
                return

            payment = None
            if snapshot.remote_payment_id:
                payment = sdk.entries.get_payment(
                    snapshot.remote_payment_id,
                    customer_id=snapshot.customer_id,
                    billing_type=billing_type,
                    external_reference=snapshot.external_reference,
                    expected_amount=snapshot.amount,
                    expected_split=snapshot.entry_split,
                )
            else:
                found = sdk.entries.find_payments(
                    customer_id=snapshot.customer_id,
                    billing_type=billing_type,
                    external_reference=snapshot.external_reference,
                    expected_amount=snapshot.amount,
                    expected_split=snapshot.entry_split,
                )
                if found:
                    # A list response is discovery only.  Reconcile the one
                    # returned resource before any paid/local transition.
                    payment = sdk.entries.get_payment(
                        found[0]["id"], customer_id=snapshot.customer_id,
                        billing_type=billing_type, external_reference=snapshot.external_reference,
                        expected_amount=snapshot.amount, expected_split=snapshot.entry_split,
                    )
                elif (
                    snapshot.remote_creation_state != "nao_iniciado"
                    or snapshot.remote_attempt_count > 0
                ):
                    _finish_retry(snapshot, "asaas_entry_result_unknown", uncertain=True)
                    return
                else:
                    if not is_asaas_sales_entry_split_policy_approved():
                        _finish_retry(
                            snapshot,
                            "asaas_entry_split_policy_unavailable",
                            uncertain=False,
                        )
                        return
                    if not _reserve_remote_attempt(snapshot):
                        return
                    remote_attempt_reserved = True
                    payment = sdk.entries.create_payment(
                        customer_id=snapshot.customer_id,
                        billing_type=billing_type,
                        amount=snapshot.amount,
                        due_date=snapshot.entry_due_date or date.today().isoformat(),
                        external_reference=snapshot.external_reference,
                        installments=snapshot.card_installments,
                        split=snapshot.entry_split,
                    )
                    # POST does not prove the split; reconcile the canonical
                    # payment resource before any local paid transition.
                    payment = sdk.entries.get_payment(
                        payment["id"],
                        customer_id=snapshot.customer_id,
                        billing_type=billing_type,
                        external_reference=snapshot.external_reference,
                        expected_amount=snapshot.amount,
                        expected_split=snapshot.entry_split,
                    )
            _store_remote_result(snapshot, payment)
    except AsaasAPIError as exc:
        # Once POST was reserved, even a malformed response can denote a
        # remote charge.  Preserve reconciliation by external reference.
        if (
            not remote_attempt_reserved
            and snapshot.remote_creation_state == "nao_iniciado"
            and snapshot.remote_attempt_count == 0
            and snapshot.remote_payment_id is None
            and exc.detail in {
            "entry_remote_conflict",
            "entry_identity_mismatch",
            "entry_amount_mismatch",
            "entry_split_mismatch",
            "entry_split_exceeds_net_value",
            "invalid_entry_response",
            "invalid_entry_checkout_url",
            }
        ):
            _finish_conflict(snapshot, exc.detail)
            return
        _finish_retry(
            snapshot,
            "asaas_entry_remote_unavailable",
            uncertain=(
                remote_attempt_reserved
                or snapshot.remote_creation_state != "nao_iniciado"
                or snapshot.remote_attempt_count > 0
                or snapshot.remote_payment_id is not None
            ),
        )
    except AsaasConnectionError:
        _finish_retry(
            snapshot,
            "asaas_entry_remote_unavailable",
            uncertain=(
                remote_attempt_reserved
                or snapshot.remote_creation_state != "nao_iniciado"
                or snapshot.remote_attempt_count > 0
                or snapshot.remote_payment_id is not None
            ),
        )
    except (AsaasValidationError, AsaasIntegrationError, AsaasConfigurationError):
        if (
            remote_attempt_reserved
            or snapshot.remote_creation_state != "nao_iniciado"
            or snapshot.remote_attempt_count > 0
            or snapshot.remote_payment_id
        ):
            _finish_retry(snapshot, "asaas_entry_reconciliation_required", uncertain=True)
        else:
            _finish_terminal(snapshot, "asaas_entry_remote_rejected")


def _frozen_entry_targets_are_approved(sdk: AsaasSalesSDK, snapshot: _EntrySnapshot) -> bool:
    plan = snapshot.entry_plan
    if plan is None or not require_approved_targets((AsaasApprovalTarget(
        unidade=snapshot.unidade, environment=snapshot.environment,
        account_id=snapshot.issuer_account_id, wallet_id=snapshot.account_wallet_id,
    ),), getattr(sdk, "approval_evidence_reader", None)):
        return False
    try:
        provider = receiver_identity_provider_for_environment(snapshot.environment)
        for item in plan.items:
            identity = item.receiver_identity
            if identity is None:
                return False
            with provider.approval_reader(identity) as reader:
                if not require_approved_targets((AsaasApprovalTarget(
                    unidade=identity.unidade, environment=identity.environment,
                    account_id=identity.account_id, wallet_id=identity.wallet_id,
                ),), reader):
                    return False
    except Exception:
        return False
    return True


def _claim_entry_job(job_id: int) -> Optional[_EntrySnapshot]:
    if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0:
        raise ValueError("entry_job_id deve ser inteiro positivo")
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_entry_jobs
            SET status = 'processando', attempt_count = attempt_count + 1,
                last_attempt_at = NOW(), next_retry_at = NULL, updated_at = NOW()
            WHERE id = %s
              AND (
                status IN ('pendente', 'retry')
                OR (status = 'processando' AND last_attempt_at <= %s)
              )
            RETURNING entry_integration_id, attempt_count
            """,
            (job_id, datetime.now(timezone.utc) - _STALE_AFTER),
        )
        claimed = cursor.fetchone()
        if claimed is None:
            return None
        entry_id = int(_value(claimed, "entry_integration_id", 0))
        attempt = int(_value(claimed, "attempt_count", 1))
        cursor.execute(
            """
            SELECT entry.id, entry.unidade, entry.environment,
                   entry.account_wallet_id, customer.asaas_customer_id,
                   customer.status, entry.payment_method,
                   entry.card_installments, entry.amount,
                   entry.external_reference, entry.remote_creation_state,
                   entry.remote_attempt_count, entry.remote_payment_id,
                   entry.odontograma_id, pre.paciente_id, pre.dependente_id,
                   pre.dentista_id, pre.status, pre.expires_at, snapshot.snapshot_json,
                   snapshot.entry_plan_json, snapshot.entry_split_json,
                   snapshot.carne_plan_json, snapshot.carne_split_json,
                   snapshot.intent_version, snapshot.intent_sha256
            FROM asaas_entry_integrations AS entry
            JOIN asaas_patient_customers AS customer
              ON customer.id = entry.asaas_patient_customer_id
             AND customer.unidade = entry.unidade
             AND customer.environment = entry.environment
             AND customer.account_wallet_id = entry.account_wallet_id
            JOIN pre_vendas_entradas AS pre
              ON pre.pre_venda_id = entry.pre_venda_id
            JOIN asaas_entry_financial_snapshots AS snapshot
              ON snapshot.entry_integration_id = entry.id
            WHERE entry.id = %s
            LIMIT 1
            FOR UPDATE OF entry, pre
            """,
            (entry_id,),
        )
        row = cursor.fetchone()
        if row is None:
            _mark_job_terminal(cursor, job_id, attempt, "asaas_entry_not_found")
            return None
        if not is_asaas_sales_carne_enabled(str(_value(row, "unidade", 1))):
            _mark_job_retry(cursor, job_id, attempt, "asaas_entry_unit_disabled")
            return None
        if _value(row, "status", 5) != "integrado":
            _mark_job_retry(cursor, job_id, attempt, "asaas_customer_not_ready")
            return None
        # pre-venda paga não prova a cobrança remota desta entrada; somente o
        # GET canônico pode encerrar a outbox.
        if (
            _value(row, "expires_at", 18) <= datetime.now(timezone.utc)
            and _value(row, "remote_creation_state", 10) == "nao_iniciado"
            and int(_value(row, "remote_attempt_count", 11) or 0) == 0
            and _value(row, "remote_payment_id", 12) is None
        ):
            cursor.execute(
                """
                UPDATE asaas_entry_integrations
                SET status = 'expirado', updated_at = NOW()
                WHERE id = %s
                  AND remote_creation_state = 'nao_iniciado'
                  AND remote_attempt_count = 0
                  AND remote_payment_id IS NULL
                """,
                (entry_id,),
            )
            cursor.execute(
                "UPDATE pre_vendas_entradas SET status = 'expirado' WHERE pre_venda_id = (SELECT pre_venda_id FROM asaas_entry_integrations WHERE id = %s)",
                (entry_id,),
            )
            _mark_job_terminal(cursor, job_id, attempt, "asaas_entry_expired")
            return None
        snapshot_json = _json_object(_value(row, "snapshot_json", 19))
        entry_plan_json = _json_object(_value(row, "entry_plan_json", 20))
        entry_split = _json_array(_value(row, "entry_split_json", 21))
        carne_plan_json = _json_object(_value(row, "carne_plan_json", 22))
        carne_split = _json_array(_value(row, "carne_split_json", 23))
        try:
            entry_plan = _json_to_plan(entry_plan_json) if entry_plan_json else None
            carne_plan = _json_to_plan(carne_plan_json) if carne_plan_json else None
            if entry_plan is not None and entry_split is not None:
                validate_asaas_new_split_preview(entry_plan, entry_split,
                    unidade=str(_value(row, "unidade", 1)), environment=str(_value(row, "environment", 2)),
                    account_wallet_id=str(_value(row, "account_wallet_id", 3)), charge_value=_value(row, "amount", 8), contexto="entrada")
            if carne_plan is not None and carne_split is not None:
                validate_asaas_new_split_preview(carne_plan, carne_split,
                    unidade=str(_value(row, "unidade", 1)), environment=str(_value(row, "environment", 2)),
                    account_wallet_id=str(_value(row, "account_wallet_id", 3)),
                    charge_value=_money(Decimal(str((snapshot_json or {}).get("net_total", "0"))) - _money(_value(row, "amount", 8))), contexto="carne")
        except (AsaasSplitValidationError, InvalidOperation, ValueError, TypeError):
            entry_plan = None
            carne_plan = None
        if (
            snapshot_json is None
            or entry_plan_json is None
            or entry_split is None
            or carne_plan_json is None
            or carne_split is None
            or entry_plan is None
            or carne_plan is None
            or int(_value(row, "intent_version", 24)) != 1
            or snapshot_json.get("version") != 1
            or not isinstance(snapshot_json.get("actor_user_id"), int)
            or snapshot_json.get("unidade") != _value(row, "unidade", 1)
            or snapshot_json.get("contexto") != "entrada"
            or snapshot_json.get("odontograma_id") != _value(row, "odontograma_id", 13)
            or snapshot_json.get("paciente_id") != _value(row, "paciente_id", 14)
            or snapshot_json.get("dependente_id") != _value(row, "dependente_id", 15)
            or snapshot_json.get("dentista_id") != _value(row, "dentista_id", 16)
            or not snapshot_json.get("issuer_account_id")
            or not snapshot_json.get("entry_due_date")
            or snapshot_json.get("intent_sha256") != _value(row, "intent_sha256", 25)
            or snapshot_json.get("intent_sha256") != _intent_hash(snapshot_json)
            or snapshot_json.get("snapshot_sha256") != _snapshot_hash(snapshot_json)
            or snapshot_json.get("environment") != _value(row, "environment", 2)
            or snapshot_json.get("account_wallet_id") != _value(row, "account_wallet_id", 3)
            or snapshot_json.get("entry_amount") != format(_money(_value(row, "amount", 8)), ".2f")
            or snapshot_json.get("entry_payload_sha256") != hashlib.sha256(
                json.dumps(entry_split, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            or snapshot_json.get("entry_plan_sha256") != hashlib.sha256(
                json.dumps(entry_plan_json, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            or snapshot_json.get("carne_plan_sha256") != hashlib.sha256(
                json.dumps(carne_plan_json, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            or snapshot_json.get("carne_payload_sha256") != hashlib.sha256(
                json.dumps(carne_split, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
        ):
            _mark_job_terminal(cursor, job_id, attempt, "asaas_entry_snapshot_invalid")
            return None
        return _EntrySnapshot(
            job_id=job_id,
            claim_attempt=attempt,
            entry_id=entry_id,
            unidade=str(_value(row, "unidade", 1)),
            environment=str(_value(row, "environment", 2)),
            account_wallet_id=str(_value(row, "account_wallet_id", 3)),
            customer_id=str(_value(row, "asaas_customer_id", 4)),
            payment_method=str(_value(row, "payment_method", 6)),
            card_installments=int(_value(row, "card_installments", 7)),
            amount=_money(_value(row, "amount", 8)),
            external_reference=str(_value(row, "external_reference", 9)),
            remote_creation_state=str(_value(row, "remote_creation_state", 10)),
            remote_attempt_count=int(_value(row, "remote_attempt_count", 11)),
            remote_payment_id=(
                str(_value(row, "remote_payment_id", 12))
                if _value(row, "remote_payment_id", 12) else None
            ),
            entry_split=entry_split,
            entry_plan=entry_plan,
            issuer_account_id=str(snapshot_json.get("issuer_account_id") or ""),
            snapshot_sha256=str(snapshot_json["snapshot_sha256"]),
            entry_due_date=str(snapshot_json.get("entry_due_date") or ""),
        )


def _reserve_remote_attempt(snapshot: _EntrySnapshot) -> bool:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_entry_integrations
            SET status = 'processando', remote_creation_state = 'requisicao_iniciada',
                remote_attempt_count = remote_attempt_count + 1,
                last_attempt_at = NOW(), updated_at = NOW()
            WHERE id = %s AND remote_attempt_count = %s
              AND remote_payment_id IS NULL
              AND remote_creation_state = 'nao_iniciado'
            RETURNING id
            """,
            (snapshot.entry_id, snapshot.remote_attempt_count),
        )
        return cursor.fetchone() is not None


def _store_remote_result(snapshot: _EntrySnapshot, payment: Mapping[str, Any]) -> None:
    remote_status = str(payment["status"])
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_entry_integrations
            SET remote_payment_id = COALESCE(remote_payment_id, %s),
                checkout_url = COALESCE(checkout_url, %s),
                remote_status = %s, remote_creation_state = 'confirmado',
                status = %s, last_error_code = NULL,
                paid_at = CASE WHEN %s THEN NOW() ELSE paid_at END,
                updated_at = NOW()
            WHERE id = %s
              AND (remote_payment_id IS NULL OR remote_payment_id = %s)
            RETURNING pre_venda_id
            """,
            (
                payment["id"], payment["invoiceUrl"], remote_status,
                "pago" if remote_status in _PAID_REMOTE_STATUSES else "aguardando_pagamento",
                remote_status in _PAID_REMOTE_STATUSES,
                snapshot.entry_id, payment["id"],
            ),
        )
        updated = cursor.fetchone()
        if updated is None:
            cursor.execute(
                """
                UPDATE asaas_entry_integrations
                SET status = 'conflito',
                    remote_creation_state = 'resultado_incerto',
                    last_error_code = 'asaas_entry_remote_conflict',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (snapshot.entry_id,),
            )
            _mark_job_conflict(
                cursor,
                snapshot.job_id,
                snapshot.claim_attempt,
                "asaas_entry_remote_conflict",
            )
            return
        pre_venda_id = str(_value(updated, "pre_venda_id", 0))
        if remote_status in _PAID_REMOTE_STATUSES:
            cursor.execute(
                """
                UPDATE pre_vendas_entradas
                SET status = 'pago', valor_pago = valor_solicitado,
                    checkout_url = NULL, checkout_id = NULL
                WHERE pre_venda_id = %s AND status = 'pendente'
                """,
                (pre_venda_id,),
            )
            _mark_job_integrated(cursor, snapshot.job_id, snapshot.claim_attempt)
        elif remote_status in _TERMINAL_REMOTE_STATUSES:
            cursor.execute(
                "UPDATE asaas_entry_integrations SET status = 'cancelado', remote_creation_state = 'falha_terminal', updated_at = NOW() WHERE id = %s",
                (snapshot.entry_id,),
            )
            cursor.execute(
                "UPDATE pre_vendas_entradas SET status = 'cancelado' WHERE pre_venda_id = %s",
                (pre_venda_id,),
            )
            _mark_job_terminal(cursor, snapshot.job_id, snapshot.claim_attempt, "asaas_entry_payment_terminal")
        else:
            _mark_job_retry(cursor, snapshot.job_id, snapshot.claim_attempt, "asaas_entry_payment_pending")


def _finish_retry(snapshot: _EntrySnapshot, code: str, *, uncertain: bool = False) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_entry_integrations
            SET status = %s, remote_creation_state = %s,
                last_error_code = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (
                "resultado_incerto" if uncertain else "retry",
                "resultado_incerto" if uncertain else "nao_iniciado",
                code,
                snapshot.entry_id,
            ),
        )
        _mark_job_retry(cursor, snapshot.job_id, snapshot.claim_attempt, code)


def _finish_terminal(snapshot: _EntrySnapshot, code: str) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE asaas_entry_integrations SET status = 'erro_terminal', remote_creation_state = 'falha_terminal', last_error_code = %s, updated_at = NOW() WHERE id = %s",
            (code, snapshot.entry_id),
        )
        _mark_job_terminal(cursor, snapshot.job_id, snapshot.claim_attempt, code)


def _finish_conflict(snapshot: _EntrySnapshot, code: str) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_entry_integrations
            SET status = 'conflito', remote_creation_state = 'resultado_incerto',
                last_error_code = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (code, snapshot.entry_id),
        )
        _mark_job_conflict(cursor, snapshot.job_id, snapshot.claim_attempt, code)


def _mark_job_retry(cursor: Any, job_id: int, attempt: int, code: str) -> None:
    cursor.execute(
        """
        UPDATE asaas_entry_jobs
        SET status = 'retry', last_error_code = %s,
            next_retry_at = NOW() + CASE
                WHEN %s = 'asaas_entry_payment_pending'
                THEN INTERVAL '5 minutes'
                ELSE INTERVAL '15 seconds'
            END,
            updated_at = NOW()
        WHERE id = %s AND attempt_count = %s AND status = 'processando'
        """,
        (code, code, job_id, attempt),
    )


def _mark_job_terminal(cursor: Any, job_id: int, attempt: int, code: str) -> None:
    cursor.execute(
        """
        UPDATE asaas_entry_jobs
        SET status = 'erro_terminal', last_error_code = %s,
            next_retry_at = NULL, completed_at = NOW(), updated_at = NOW()
        WHERE id = %s AND attempt_count = %s AND status = 'processando'
        """,
        (code, job_id, attempt),
    )


def _mark_job_conflict(cursor: Any, job_id: int, attempt: int, code: str) -> None:
    cursor.execute(
        """
        UPDATE asaas_entry_jobs
        SET status = 'conflito', last_error_code = %s,
            next_retry_at = NULL, completed_at = NOW(), updated_at = NOW()
        WHERE id = %s AND attempt_count = %s AND status = 'processando'
        """,
        (code, job_id, attempt),
    )


def _mark_job_integrated(cursor: Any, job_id: int, attempt: int) -> None:
    cursor.execute(
        """
        UPDATE asaas_entry_jobs
        SET status = 'integrado', last_error_code = NULL,
            next_retry_at = NULL, completed_at = NOW(), updated_at = NOW()
        WHERE id = %s AND attempt_count = %s AND status = 'processando'
        """,
        (job_id, attempt),
    )


def _request_fingerprint(**values: Any) -> str:
    canonical = json.dumps(values, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _created_record(row: Any) -> AsaasEntryCreatedRecord:
    return AsaasEntryCreatedRecord(
        entry_id=int(_value(row, "id", 0)),
        status=str(_value(row, "status", 1)),
        payment_method=str(_value(row, "payment_method", 2)),
        amount=_money(_value(row, "amount", 3)),
        card_installments=int(_value(row, "card_installments", 4)),
        created_at=_value(row, "created_at", 5),
    )


def _money(value: Any) -> Decimal:
    try:
        normalized = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise AsaasEntryError("asaas_entry_amount_invalid") from None
    if not normalized.is_finite() or normalized <= 0:
        raise AsaasEntryError("asaas_entry_amount_invalid")
    return normalized


def _snapshot_hash(snapshot: Mapping[str, Any]) -> str:
    """Hashes the immutable snapshot without recursively hashing itself."""
    body = dict(snapshot)
    body.pop("snapshot_sha256", None)
    encoded = json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _intent_hash(snapshot: Mapping[str, Any]) -> str:
    """Reproduz o hash da intenção, sem hashes de artefatos derivados."""
    derived = {
        "intent_sha256", "entry_plan_sha256", "entry_payload_sha256",
        "carne_plan_sha256", "carne_payload_sha256", "snapshot_sha256",
    }
    body = {key: value for key, value in snapshot.items() if key not in derived}
    encoded = json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_object(value: Any) -> Optional[dict[str, Any]]:
    if isinstance(value, Mapping):
        return dict(value)
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _json_array(value: Any) -> Optional[list[dict[str, Any]]]:
    if isinstance(value, list) and all(isinstance(item, Mapping) for item in value):
        return [dict(item) for item in value]
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError):
        return None
    return [dict(item) for item in decoded] if isinstance(decoded, list) and all(isinstance(item, Mapping) for item in decoded) else None


def _value(row: Any, name: str, index: int) -> Any:
    return row[name] if isinstance(row, Mapping) else row[index]
