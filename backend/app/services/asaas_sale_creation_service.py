"""Criacao local e consulta do primeiro fluxo independente de Carnê Asaas."""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from typing import Any, Callable, Optional
from uuid import UUID

from app.models.vendas_asaas import AsaasRecurringSaleCreateBase
from app.services.asaas_sale_integration_service import (
    prepare_sale_integration,
)
from app.services.asaas_split_service import (
    AsaasSplitPlan,
    AsaasSplitValidationError,
    persist_asaas_sale_splits,
    seal_asaas_split_snapshot,
    validate_asaas_new_split_preview,
)
from app.services.asaas_sales_config import (
    canonicalize_asaas_sales_unit,
    is_asaas_sandbox_ni_odontogram_type_available,
    is_asaas_sales_payment_method_environment_enabled,
    is_asaas_sales_pix_automatic_split_policy_approved,
)


PAYMENT_METHOD_CODE = "ASAAS_BOLETO_INSTALLMENT"
PIX_AUTOMATIC_PAYMENT_METHOD_CODE = "ASAAS_PIX_AUTOMATIC"
CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE = "ASAAS_CREDIT_CARD_RECURRENT"
PAYMENT_METHOD_CODES = frozenset(
    {
        PAYMENT_METHOD_CODE,
        PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
        CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
    }
)
LOCAL_SALE_PENDING_STATUS = "Pendente Asaas"
MAX_DATABASE_MONEY = Decimal("9999999999.99")
CONTRACT_ODONTOGRAM_TYPES = frozenset(
    {
        "Contrato Odontológico + Akimais",
        "Contrato Ortodôntico",
        "Combo Orto + ODC",
    }
)
ENTRY_REQUIRED_ODONTOGRAM_TYPES = frozenset(
    {
        *CONTRACT_ODONTOGRAM_TYPES,
        "Particular",
        "Ortodontia",
    }
)


class AsaasSaleCreationError(ValueError):
    """Erro controlado do contrato local de criacao da venda."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AsaasSaleCreationNotFoundError(AsaasSaleCreationError):
    """Uma referencia local obrigatoria nao existe no escopo da venda."""


class AsaasSaleCreationConflictError(AsaasSaleCreationError):
    """A operacao colide com outra venda ou chave idempotente."""


@dataclass(frozen=True)
class AsaasCarneSaleRecord:
    venda_id: int
    documento_venda: str
    integration_id: int
    status: str
    valor_liquido_total: Decimal
    qtd_parcelas: int
    created_at: datetime


@dataclass(frozen=True)
class AsaasSaleStatusRecord:
    integration_id: int
    venda_id: int
    unidade: str
    payment_method: str
    status: str
    remote_creation_state: str
    reconciliation_required: bool
    payment_book_available: bool
    last_error_code: Optional[str]
    created_at: datetime
    updated_at: datetime
    pix_qr_available: bool = False
    checkout_available: bool = False


@dataclass(frozen=True)
class AsaasPaymentBookTarget:
    integration_id: int
    unidade: str
    environment: str
    account_wallet_id: str
    installment_id: str


@dataclass(frozen=True)
class AsaasRemoteActionTarget:
    integration_id: int
    unidade: str
    environment: str
    account_wallet_id: str
    resource_id: str


@dataclass(frozen=True)
class AsaasSaleItemSnapshot:
    item_number: int
    product_id: int
    quantity: int
    unit_value: Decimal
    total_value: Decimal


@dataclass(frozen=True)
class _FrozenPaidEntry:
    """Intenção selada que pode gerar exatamente um Carnê restante."""

    entry_id: int
    pre_venda_id: str
    amount: Decimal
    gross_total: Decimal
    discount_total: Decimal
    net_total: Decimal
    remaining_values: tuple[Decimal, ...]
    items: tuple[AsaasSaleItemSnapshot, ...]
    carne_plan: AsaasSplitPlan
    carne_payload: list[dict[str, Any]]
    snapshot_sha256: str


def build_sale_request_fingerprint(
    sale: AsaasRecurringSaleCreateBase,
    *,
    unidade: str,
    user_id: int,
    payment_method: str = PAYMENT_METHOD_CODE,
) -> str:
    canonical_items = sorted(
        (
            {
                "produto_id": item.produto_id,
                "quantidade": item.quantidade,
                "valor_unitario_registrado": _money_string(
                    item.valor_unitario_registrado,
                    "item_value",
                ),
                "observacao": str(item.observacao or "").strip(),
            }
            for item in (sale.itens_avulsos or [])
        ),
        key=lambda item: (
            item["produto_id"],
            item["quantidade"],
            item["valor_unitario_registrado"],
            item["observacao"],
        ),
    )
    canonical = json.dumps(
        {
            "client_request_id": str(sale.client_request_id),
            "paciente_id": sale.paciente_id,
            "dentista_orcamentista_id": sale.dentista_orcamentista_id,
            "unidade": unidade,
            "qtd_parcelas": sale.qtd_parcelas,
            "data_vencimento_primeira_parcela": (
                sale.data_vencimento_primeira_parcela.isoformat()
            ),
            "odontograma_id": sale.odontograma_id,
            "itens_avulsos": canonical_items,
            "dependente_id": sale.dependente_id,
            "user_id": user_id,
            "payment_method": payment_method,
            "entry_id": getattr(sale, "entry_id", None),
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_asaas_carne_sale(
    cursor: Any,
    *,
    sale: AsaasRecurringSaleCreateBase,
    unidade: str,
    user_id: int,
    environment: str,
    account_wallet_id: str,
    payment_method: str = PAYMENT_METHOD_CODE,
    approval_guard: Optional[Callable[[], bool]] = None,
    split_preview: Optional[Callable[[Mapping[str, Any]], tuple[AsaasSplitPlan, list[dict[str, Any]]]]] = None,
) -> AsaasCarneSaleRecord:
    """Grava venda, parcelas, integracao e outbox na mesma transacao."""
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    if not canonical_unit:
        raise AsaasSaleCreationError("asaas_sale_unit_invalid")
    normalized_payment_method = str(payment_method or "").strip().upper()
    if normalized_payment_method not in PAYMENT_METHOD_CODES:
        raise AsaasSaleCreationError("asaas_sale_payment_method_invalid")
    if (
        normalized_payment_method == PIX_AUTOMATIC_PAYMENT_METHOD_CODE
        and not is_asaas_sales_pix_automatic_split_policy_approved()
    ):
        raise AsaasSaleCreationError("asaas_pix_split_nao_suportado")
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise AsaasSaleCreationError("asaas_sale_user_invalid")
    if sale.data_vencimento_primeira_parcela < date.today():
        raise AsaasSaleCreationError("asaas_sale_due_date_in_past")
    # Evita comportamento mensal divergente entre meses com 29, 30 e 31 dias.
    if sale.data_vencimento_primeira_parcela.day > 28:
        raise AsaasSaleCreationError("asaas_sale_due_day_unsupported")

    request_id = str(sale.client_request_id)
    request_fingerprint = build_sale_request_fingerprint(
        sale,
        unidade=canonical_unit,
        user_id=user_id,
        payment_method=normalized_payment_method,
    )
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (
            "asaas-sale-request:"
            f"{environment}:{account_wallet_id}:{request_id}",
        ),
    )
    replay = _find_request_replay(
        cursor,
        environment=environment,
        account_wallet_id=account_wallet_id,
        request_id=request_id,
    )
    if replay is not None:
        stored_value = _row_value(replay, "request_fingerprint", 7)
        stored_fingerprint = (
            str(stored_value).strip() if stored_value is not None else None
        )
        if stored_fingerprint != request_fingerprint:
            raise AsaasSaleCreationConflictError(
                "asaas_sale_idempotency_conflict"
            )
        return _sale_record_from_replay(replay)

    if not is_asaas_sales_payment_method_environment_enabled(
        canonical_unit, environment, normalized_payment_method
    ):
        raise AsaasSaleCreationError(
            "asaas_carne_sandbox_only"
            if normalized_payment_method == PAYMENT_METHOD_CODE
            else "asaas_sale_sandbox_only"
        )

    sandbox_ni = (
        canonical_unit == "Nova Iguaçu 1"
        and str(environment or "").strip().casefold() == "sandbox"
    )
    if sandbox_ni:
        # Confirma a posse local antes de consultar o tipo. Sem isso, a
        # mensagem de indisponibilidade revelaria o tipo de um odontograma
        # de outro paciente ou unidade.
        _validate_authenticated_user(cursor, user_id=user_id, unidade=canonical_unit)
        _validate_patient(cursor, paciente_id=sale.paciente_id, unidade=canonical_unit)
        _validate_dentist(cursor, dentista_id=sale.dentista_orcamentista_id)
        dependent_id = _validate_sale_source(
            cursor,
            sale=sale,
            unidade=canonical_unit,
        )
        odontogram_type_id = _get_odontogram_type_id(cursor, sale.odontograma_id)
        if not is_asaas_sandbox_ni_odontogram_type_available(
            canonical_unit, environment, odontogram_type_id
        ):
            raise AsaasSaleCreationError(
                "asaas_sandbox_ni_odontogram_type_unavailable"
            )

    # A deduplicação é anterior à prova remota: retries não podem ser
    # convertidos em nova venda nem falhar porque o KYC mudou depois do POST.
    if approval_guard is None or approval_guard() is not True:
        raise AsaasSaleCreationError("asaas_sale_account_not_approved")

    if not sandbox_ni:
        _validate_authenticated_user(cursor, user_id=user_id, unidade=canonical_unit)
        _validate_patient(cursor, paciente_id=sale.paciente_id, unidade=canonical_unit)
        _validate_dentist(cursor, dentista_id=sale.dentista_orcamentista_id)
        dependent_id = _validate_sale_source(
            cursor,
            sale=sale,
            unidade=canonical_unit,
        )
    odontogram_type = _get_odontogram_type(cursor, sale.odontograma_id)
    requested_entry_id = getattr(sale, "entry_id", None)
    if (
        normalized_payment_method == PAYMENT_METHOD_CODE
        and odontogram_type in ENTRY_REQUIRED_ODONTOGRAM_TYPES
        and requested_entry_id is None
    ):
        raise AsaasSaleCreationConflictError("asaas_sale_paid_entry_required")
    entry_amount: Optional[Decimal] = None
    pre_venda_id: Optional[str] = None
    frozen_entry: Optional[_FrozenPaidEntry] = None
    if requested_entry_id is not None:
        if normalized_payment_method != PAYMENT_METHOD_CODE:
            raise AsaasSaleCreationError("asaas_sale_entry_method_invalid")
        frozen_entry = _validate_paid_entry(
            cursor,
            entry_id=requested_entry_id,
            sale=sale,
            unidade=canonical_unit,
            user_id=user_id,
            environment=environment,
            account_wallet_id=account_wallet_id,
        )
    if frozen_entry is not None:
        # Uma entrada versionada não pode ser afetada por mutação posterior de
        # produtos, descontos, regras de split ou carteiras. Só seus dados
        # selados participam da criação do restante.
        entry_amount = frozen_entry.amount
        pre_venda_id = frozen_entry.pre_venda_id
        gross_value = frozen_entry.gross_total
        rule_discount = frozen_entry.discount_total
        full_net_value = frozen_entry.net_total
        item_snapshots = frozen_entry.items
        remote_value = _money(full_net_value - entry_amount, "remaining_value")
        installment_values = list(frozen_entry.remaining_values)
        if len(installment_values) != sale.qtd_parcelas or sum(installment_values, Decimal("0.00")) != remote_value:
            raise AsaasSaleCreationConflictError("asaas_sale_entry_snapshot_invalid")
    else:
        gross_value, item_snapshots = _calculate_gross_value(
            cursor,
            sale=sale,
            contract_installment_count=None,
        )
        rule_discount = _calculate_rule_discount(
            cursor,
            unidade=canonical_unit,
            installment_count=sale.qtd_parcelas,
            gross_value=gross_value,
            payment_method=normalized_payment_method,
        )
        full_net_value = _money(gross_value - rule_discount, "net_value")
        remote_value = full_net_value
        installment_values = calculate_asaas_installment_values(remote_value, sale.qtd_parcelas)
    if (
        normalized_payment_method != PAYMENT_METHOD_CODE
        and len(set(installment_values)) != 1
    ):
        raise AsaasSaleCreationError("asaas_sale_recurring_value_mismatch")
    due_dates = calculate_monthly_due_dates(
        sale.data_vencimento_primeira_parcela,
        sale.qtd_parcelas,
    )

    # Build and authenticate the exact sealed plan before the first write.
    if frozen_entry is not None:
        split_plan, split_payload = frozen_entry.carne_plan, frozen_entry.carne_payload
    else:
        if split_preview is None:
            raise AsaasSaleCreationError("asaas_split_preview_required")
        try:
            split_plan, split_payload = split_preview({
            "cursor": cursor,
            "unidade": canonical_unit,
            "environment": environment,
            "account_wallet_id": account_wallet_id,
            "usuario_venda_id": user_id,
            "odontograma_id": sale.odontograma_id,
            "valor_liquido_total": remote_value,
            "tem_entrada": entry_amount is not None,
            "contexto": (
                "carne" if normalized_payment_method == PAYMENT_METHOD_CODE
                else "pix" if normalized_payment_method == PIX_AUTOMATIC_PAYMENT_METHOD_CODE
                else "cartao"
            ),
            "remaining_installments": len(installment_values),
            })
        except (AsaasSplitValidationError, ValueError, TypeError):
            raise AsaasSaleCreationError("asaas_split_preview_invalid") from None
    try:
        validate_asaas_new_split_preview(
            split_plan,
            split_payload,
            unidade=canonical_unit,
            environment=environment,
            account_wallet_id=account_wallet_id,
            charge_value=remote_value,
            contexto=(
                "carne" if normalized_payment_method == PAYMENT_METHOD_CODE
                else "pix" if normalized_payment_method == PIX_AUTOMATIC_PAYMENT_METHOD_CODE
                else "cartao"
            ),
        )
    except (AsaasSplitValidationError, ValueError, TypeError):
        raise AsaasSaleCreationError("asaas_split_preview_invalid")

    document = f"VA-{sale.client_request_id.hex}"
    now = datetime.now(timezone.utc)
    cursor.execute(
        "SELECT set_config('app.asaas_sale_creation', 'enabled', TRUE)"
    )
    cursor.execute(
        """
        INSERT INTO vendas (
            documento_venda,
            paciente_id,
            dentista_orcamentista_id,
            odontograma_id,
            unidade,
            data_venda,
            valor_bruto_total,
            valor_desconto_regra,
            valor_desconto_solicitado,
            valor_desconto_aprovado,
            valor_liquido_total,
            qtd_parcelas,
            usuario_venda_id,
            status_venda,
            dependente_id,
            valor_entrada,
            tipo_cobranca_inicial,
            entrada_automatica,
            pre_venda_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            0.00, 0.00, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING id
        """,
        (
            document,
            sale.paciente_id,
            sale.dentista_orcamentista_id,
            sale.odontograma_id,
            canonical_unit,
            now,
            gross_value,
            rule_discount,
            full_net_value,
            sale.qtd_parcelas,
            user_id,
            LOCAL_SALE_PENDING_STATUS,
            dependent_id,
            entry_amount,
            "entrada" if entry_amount is not None else None,
            entry_amount is not None,
            pre_venda_id,
        ),
    )
    sale_row = cursor.fetchone()
    if sale_row is None:
        raise RuntimeError("Venda Asaas nao retornada")
    venda_id = int(_row_value(sale_row, "id", 0))
    if frozen_entry is not None:
        cursor.execute(
            """
            SELECT public.asaas_consume_entry_snapshot(%s, %s)
            """,
            (frozen_entry.entry_id, venda_id),
        )
        consumed_row = cursor.fetchone()
        if (
            consumed_row is None
            or int(_row_value(consumed_row, "asaas_consume_entry_snapshot", 0) or 0)
            != venda_id
        ):
            raise AsaasSaleCreationConflictError("asaas_sale_entry_already_used")

    for number, (value, due_date) in enumerate(
        zip(installment_values, due_dates),
        start=1,
    ):
        cursor.execute(
            """
            INSERT INTO venda_parcelas (
                venda_id,
                numero_parcela,
                valor_parcela,
                data_vencimento,
                status_parcela,
                documento_referencia
            ) VALUES (%s, %s, %s, %s, 'Pendente', %s)
            """,
            (
                venda_id,
                number,
                value,
                due_date,
                f"{document}/{number:02d}",
            ),
        )

    integration = prepare_sale_integration(
        cursor,
        venda_id=venda_id,
        unidade=canonical_unit,
        environment=environment,
        account_wallet_id=account_wallet_id,
        payment_method=normalized_payment_method,
        client_request_id=request_id,
    )
    try:
        seal_asaas_split_snapshot(
            cursor,
            integration_id=integration.id,
            venda_id=venda_id,
            payment_method=normalized_payment_method,
            unidade=canonical_unit,
            environment=environment,
            account_wallet_id=account_wallet_id,
            charge_value=remote_value,
            plan=split_plan,
            payload=split_payload,
        )
    except AsaasSplitValidationError:
        raise AsaasSaleCreationError("asaas_split_snapshot_not_sealed") from None
    persist_asaas_sale_splits(
        cursor,
        split_plan,
        venda_id=venda_id,
        unidade=canonical_unit,
        environment=environment,
        account_wallet_id=account_wallet_id,
    )
    _insert_sale_item_snapshots(
        cursor,
        integration_id=integration.id,
        venda_id=venda_id,
        snapshots=item_snapshots,
    )
    cursor.execute(
        """
        UPDATE asaas_sale_integrations
        SET request_fingerprint = %s,
            updated_at = NOW()
        WHERE id = %s
          AND request_fingerprint IS NULL
        RETURNING id
        """,
        (request_fingerprint, integration.id),
    )
    if cursor.fetchone() is None:
        raise AsaasSaleCreationConflictError(
            "asaas_sale_idempotency_conflict"
        )
    return AsaasCarneSaleRecord(
        venda_id=venda_id,
        documento_venda=document,
        integration_id=integration.id,
        status=_public_status(integration.status, "nao_iniciado"),
        valor_liquido_total=full_net_value,
        qtd_parcelas=sale.qtd_parcelas,
        created_at=integration.created_at,
    )


def get_asaas_sale_status(
    cursor: Any,
    *,
    integration_id: int,
    unidade: str,
) -> Optional[AsaasSaleStatusRecord]:
    _validate_positive_id(integration_id, "integration_id")
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    if not canonical_unit:
        raise AsaasSaleCreationError("asaas_sale_unit_invalid")
    cursor.execute(
        """
        SELECT
            integration.id,
            integration.venda_id,
            integration.unidade,
            integration.payment_method,
            integration.status,
            integration.remote_creation_state,
            integration.reconciliation_required,
            integration.last_error_code,
            integration.created_at,
            integration.updated_at,
            EXISTS (
                SELECT 1
                FROM asaas_sale_resources AS resource
                WHERE resource.integration_id = integration.id
                  AND resource.resource_type = 'installment'
            ) AS payment_book_available,
            EXISTS (
                SELECT 1
                FROM asaas_sale_resources AS resource
                WHERE resource.integration_id = integration.id
                  AND resource.resource_type = 'pix_authorization'
            ) AS pix_qr_available,
            EXISTS (
                SELECT 1
                FROM asaas_sale_resources AS resource
                WHERE resource.integration_id = integration.id
                  AND resource.resource_type = 'checkout'
            ) AS checkout_available
        FROM asaas_sale_integrations AS integration
        WHERE integration.id = %s
          AND integration.unidade = %s
        LIMIT 1
        """,
        (integration_id, canonical_unit),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    remote_state = str(_row_value(row, "remote_creation_state", 5))
    return AsaasSaleStatusRecord(
        integration_id=int(_row_value(row, "id", 0)),
        venda_id=int(_row_value(row, "venda_id", 1)),
        unidade=str(_row_value(row, "unidade", 2)),
        payment_method=str(_row_value(row, "payment_method", 3)),
        status=_public_status(
            str(_row_value(row, "status", 4)),
            remote_state,
        ),
        remote_creation_state=remote_state,
        reconciliation_required=bool(
            _row_value(row, "reconciliation_required", 6)
        ),
        payment_book_available=bool(
            _row_value(row, "payment_book_available", 10)
        ),
        pix_qr_available=bool(_row_value(row, "pix_qr_available", 11)),
        checkout_available=bool(_row_value(row, "checkout_available", 12)),
        last_error_code=_optional_string(
            _row_value(row, "last_error_code", 7)
        ),
        created_at=_row_value(row, "created_at", 8),
        updated_at=_row_value(row, "updated_at", 9),
    )


def get_payment_book_target(
    cursor: Any,
    *,
    integration_id: int,
    unidade: str,
) -> Optional[AsaasPaymentBookTarget]:
    _validate_positive_id(integration_id, "integration_id")
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    if not canonical_unit:
        raise AsaasSaleCreationError("asaas_sale_unit_invalid")
    cursor.execute(
        """
        SELECT
            integration.id,
            integration.unidade,
            integration.environment,
            integration.account_wallet_id,
            resource.asaas_resource_id
        FROM asaas_sale_integrations AS integration
        JOIN asaas_sale_resources AS resource
          ON resource.integration_id = integration.id
         AND resource.unidade = integration.unidade
         AND resource.environment = integration.environment
         AND resource.account_wallet_id = integration.account_wallet_id
        WHERE integration.id = %s
          AND integration.unidade = %s
          AND integration.status = 'integrado'
          AND integration.remote_creation_state = 'confirmado'
          AND resource.resource_type = 'installment'
        LIMIT 1
        """,
        (integration_id, canonical_unit),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return AsaasPaymentBookTarget(
        integration_id=int(_row_value(row, "id", 0)),
        unidade=str(_row_value(row, "unidade", 1)),
        environment=str(_row_value(row, "environment", 2)),
        account_wallet_id=str(_row_value(row, "account_wallet_id", 3)),
        installment_id=str(_row_value(row, "asaas_resource_id", 4)),
    )


def get_remote_action_target(
    cursor: Any,
    *,
    integration_id: int,
    unidade: str,
    payment_method: str,
    resource_type: str,
) -> Optional[AsaasRemoteActionTarget]:
    _validate_positive_id(integration_id, "integration_id")
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    if not canonical_unit:
        raise AsaasSaleCreationError("asaas_sale_unit_invalid")
    if payment_method not in PAYMENT_METHOD_CODES:
        raise AsaasSaleCreationError("asaas_sale_payment_method_invalid")
    if resource_type not in {"pix_authorization", "checkout"}:
        raise AsaasSaleCreationError("asaas_sale_resource_type_invalid")
    cursor.execute(
        """
        SELECT
            integration.id,
            integration.unidade,
            integration.environment,
            integration.account_wallet_id,
            resource.asaas_resource_id
        FROM asaas_sale_integrations AS integration
        JOIN asaas_sale_resources AS resource
          ON resource.integration_id = integration.id
         AND resource.unidade = integration.unidade
         AND resource.environment = integration.environment
         AND resource.account_wallet_id = integration.account_wallet_id
        WHERE integration.id = %s
          AND integration.unidade = %s
          AND integration.payment_method = %s
          AND integration.status = 'integrado'
          AND integration.remote_creation_state = 'confirmado'
          AND resource.resource_type = %s
        LIMIT 1
        """,
        (
            integration_id,
            canonical_unit,
            payment_method,
            resource_type,
        ),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return AsaasRemoteActionTarget(
        integration_id=int(_row_value(row, "id", 0)),
        unidade=str(_row_value(row, "unidade", 1)),
        environment=str(_row_value(row, "environment", 2)),
        account_wallet_id=str(_row_value(row, "account_wallet_id", 3)),
        resource_id=str(_row_value(row, "asaas_resource_id", 4)),
    )


def calculate_asaas_installment_values(
    total: Decimal,
    installment_count: int,
) -> list[Decimal]:
    normalized_total = _money(total, "total_value")
    if installment_count < 2:
        raise AsaasSaleCreationError("asaas_sale_installment_count_invalid")
    total_cents = int(normalized_total * 100)
    base_cents, remainder = divmod(total_cents, installment_count)
    if base_cents <= 0:
        raise AsaasSaleCreationError("asaas_sale_installment_value_invalid")
    values = [Decimal(base_cents) / 100 for _ in range(installment_count)]
    values[-1] += Decimal(remainder) / 100
    if sum(values, Decimal("0.00")) != normalized_total:
        raise RuntimeError("Agenda financeira Asaas inconsistente")
    return [value.quantize(Decimal("0.01")) for value in values]


def calculate_monthly_due_dates(first_due_date: date, count: int) -> list[date]:
    if count < 2:
        raise AsaasSaleCreationError("asaas_sale_installment_count_invalid")
    dates: list[date] = []
    for offset in range(count):
        raw_month = first_due_date.month - 1 + offset
        year = first_due_date.year + raw_month // 12
        month = raw_month % 12 + 1
        day = min(first_due_date.day, calendar.monthrange(year, month)[1])
        dates.append(date(year, month, day))
    return dates


def _find_request_replay(
    cursor: Any,
    *,
    environment: str,
    account_wallet_id: str,
    request_id: str,
) -> Optional[Any]:
    cursor.execute(
        """
        SELECT
            integration.id,
            integration.venda_id,
            integration.status,
            integration.remote_creation_state,
            integration.created_at,
            sale.documento_venda,
            sale.valor_liquido_total,
            integration.request_fingerprint,
            sale.qtd_parcelas
        FROM asaas_sale_integrations AS integration
        JOIN vendas AS sale ON sale.id = integration.venda_id
        WHERE integration.environment = %s
          AND integration.account_wallet_id = %s
          AND integration.idempotency_key = %s
        LIMIT 1
        FOR UPDATE OF integration
        """,
        (environment, account_wallet_id, request_id),
    )
    return cursor.fetchone()


def _sale_record_from_replay(row: Any) -> AsaasCarneSaleRecord:
    return AsaasCarneSaleRecord(
        venda_id=int(_row_value(row, "venda_id", 1)),
        documento_venda=str(_row_value(row, "documento_venda", 5)),
        integration_id=int(_row_value(row, "id", 0)),
        status=_public_status(
            str(_row_value(row, "status", 2)),
            str(_row_value(row, "remote_creation_state", 3)),
        ),
        valor_liquido_total=_money(
            _row_value(row, "valor_liquido_total", 6),
            "net_value",
        ),
        qtd_parcelas=int(_row_value(row, "qtd_parcelas", 8)),
        created_at=_row_value(row, "created_at", 4),
    )


def _validate_authenticated_user(cursor: Any, *, user_id: int, unidade: str) -> None:
    cursor.execute(
        "SELECT id, unidade FROM users WHERE id = %s LIMIT 1",
        (user_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise AsaasSaleCreationNotFoundError("asaas_sale_user_not_found")
    stored_unit = canonicalize_asaas_sales_unit(_row_value(row, "unidade", 1))
    if stored_unit and stored_unit != unidade:
        raise AsaasSaleCreationError("asaas_sale_user_unit_mismatch")


def _validate_patient(cursor: Any, *, paciente_id: int, unidade: str) -> None:
    cursor.execute(
        """
        SELECT paciente_id, unidade
        FROM pacientes
        WHERE paciente_id = %s
        LIMIT 1
        """,
        (paciente_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise AsaasSaleCreationNotFoundError("asaas_sale_patient_not_found")
    if canonicalize_asaas_sales_unit(_row_value(row, "unidade", 1)) != unidade:
        raise AsaasSaleCreationError("asaas_sale_patient_unit_mismatch")


def _validate_dentist(cursor: Any, *, dentista_id: int) -> None:
    cursor.execute(
        "SELECT id, ativo FROM dentistas WHERE id = %s LIMIT 1",
        (dentista_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise AsaasSaleCreationNotFoundError("asaas_sale_dentist_not_found")
    if not bool(_row_value(row, "ativo", 1)):
        raise AsaasSaleCreationError("asaas_sale_dentist_inactive")


def _validate_sale_source(
    cursor: Any,
    *,
    sale: AsaasCarneSaleCreate,
    unidade: str,
) -> Optional[int]:
    dependent_id = sale.dependente_id
    if sale.odontograma_id is not None:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"asaas-sale-odontograma:{sale.odontograma_id}",),
        )
        cursor.execute(
            """
            SELECT id, paciente_id, unidade, tipo, dependente_id, ativo
            FROM odontogramas
            WHERE id = %s
            LIMIT 1
            """,
            (sale.odontograma_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise AsaasSaleCreationNotFoundError(
                "asaas_sale_odontogram_not_found"
            )
        if int(_row_value(row, "paciente_id", 1)) != sale.paciente_id:
            raise AsaasSaleCreationError("asaas_sale_odontogram_patient_mismatch")
        if canonicalize_asaas_sales_unit(_row_value(row, "unidade", 2)) != unidade:
            raise AsaasSaleCreationError("asaas_sale_odontogram_unit_mismatch")
        if not bool(_row_value(row, "ativo", 5)):
            raise AsaasSaleCreationError("asaas_sale_odontogram_inactive")
        odontogram_dependent = _row_value(row, "dependente_id", 4)
        if odontogram_dependent is not None:
            odontogram_dependent = int(odontogram_dependent)
            if dependent_id is not None and dependent_id != odontogram_dependent:
                raise AsaasSaleCreationError(
                    "asaas_sale_dependent_odontogram_mismatch"
                )
            dependent_id = odontogram_dependent
        cursor.execute(
            """
            SELECT id
            FROM vendas
            WHERE odontograma_id = %s
              AND status_venda <> 'Cancelada'
            LIMIT 1
            """,
            (sale.odontograma_id,),
        )
        if cursor.fetchone() is not None:
            raise AsaasSaleCreationConflictError(
                "asaas_sale_odontogram_already_sold"
            )

    if dependent_id is not None:
        cursor.execute(
            """
            SELECT dependente_id, responsavel_paciente_id, ativo
            FROM dependentes
            WHERE dependente_id = %s
            LIMIT 1
            """,
            (dependent_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise AsaasSaleCreationNotFoundError(
                "asaas_sale_dependent_not_found"
            )
        if int(_row_value(row, "responsavel_paciente_id", 1)) != sale.paciente_id:
            raise AsaasSaleCreationError("asaas_sale_dependent_patient_mismatch")
        if not bool(_row_value(row, "ativo", 2)):
            raise AsaasSaleCreationError("asaas_sale_dependent_inactive")
    return dependent_id


def _get_odontogram_type(cursor: Any, odontograma_id: Optional[int]) -> Optional[str]:
    if odontograma_id is None:
        return None
    cursor.execute(
        "SELECT tipo FROM odontogramas WHERE id = %s LIMIT 1",
        (odontograma_id,),
    )
    row = cursor.fetchone()
    return str(_row_value(row, "tipo", 0)) if row is not None else None


def _get_odontogram_type_id(cursor: Any, odontograma_id: Optional[int]) -> Optional[int]:
    if odontograma_id is None:
        return None
    cursor.execute(
        """
        SELECT t.id
        FROM odontogramas AS o
        LEFT JOIN tipos_odontograma AS t
          ON LOWER(t.nome) = LOWER(o.tipo) AND t.ativo = TRUE
        WHERE o.id = %s
        LIMIT 1
        """,
        (odontograma_id,),
    )
    row = cursor.fetchone()
    value = _row_value(row, "id", 0) if row is not None else None
    return int(value) if type(value) is int else None


def _validate_paid_entry(
    cursor: Any,
    *,
    entry_id: int,
    sale: AsaasRecurringSaleCreateBase,
    unidade: str,
    user_id: int,
    environment: str,
    account_wallet_id: str,
) -> _FrozenPaidEntry:
    cursor.execute(
        """
        SELECT entry.status AS entry_status, entry.amount, entry.odontograma_id,
               entry.unidade, pre.pre_venda_id, pre.paciente_id,
               pre.dependente_id, pre.dentista_id, pre.status AS pre_status,
               pre.valor_pago,
               (pre.metadata_json->>'qtd_parcelas_total')::INTEGER,
               snapshot.snapshot_json, snapshot.entry_plan_json,
               snapshot.entry_split_json, snapshot.carne_plan_json,
               snapshot.carne_split_json, snapshot.intent_version,
               snapshot.intent_sha256, snapshot.consumed_venda_id
        FROM asaas_entry_integrations AS entry
        JOIN pre_vendas_entradas AS pre
          ON pre.pre_venda_id = entry.pre_venda_id
        JOIN asaas_entry_financial_snapshots AS snapshot
          ON snapshot.entry_integration_id = entry.id
        WHERE entry.id = %s AND entry.environment = 'sandbox'
        LIMIT 1
        FOR UPDATE OF entry, pre, snapshot
        """,
        (entry_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise AsaasSaleCreationNotFoundError("asaas_sale_entry_not_found")
    if (
        _row_value(row, "entry_status", 0) != "pago"
        or _row_value(row, "pre_status", 8) != "pago"
    ):
        raise AsaasSaleCreationConflictError("asaas_sale_entry_not_paid")
    if int(_row_value(row, "odontograma_id", 2)) != sale.odontograma_id:
        raise AsaasSaleCreationConflictError("asaas_sale_entry_source_mismatch")
    if canonicalize_asaas_sales_unit(_row_value(row, "unidade", 3)) != unidade:
        raise AsaasSaleCreationConflictError("asaas_sale_entry_unit_mismatch")
    if int(_row_value(row, "paciente_id", 5)) != sale.paciente_id:
        raise AsaasSaleCreationConflictError("asaas_sale_entry_patient_mismatch")
    stored_dependent = _row_value(row, "dependente_id", 6)
    if stored_dependent is not None:
        stored_dependent = int(stored_dependent)
    if stored_dependent != sale.dependente_id:
        raise AsaasSaleCreationConflictError("asaas_sale_entry_dependent_mismatch")
    if int(_row_value(row, "dentista_id", 7)) != sale.dentista_orcamentista_id:
        raise AsaasSaleCreationConflictError("asaas_sale_entry_dentist_mismatch")
    if int(_row_value(row, "qtd_parcelas_total", 10)) != sale.qtd_parcelas + 1:
        raise AsaasSaleCreationConflictError("asaas_sale_entry_installments_mismatch")
    requested = _money(_row_value(row, "amount", 1), "entry_amount")
    paid = _money(_row_value(row, "valor_pago", 9), "entry_paid_amount")
    if requested != paid:
        raise AsaasSaleCreationConflictError("asaas_sale_entry_amount_mismatch")
    if _row_value(row, "consumed_venda_id", 18) is not None:
        raise AsaasSaleCreationConflictError("asaas_sale_entry_already_used")
    snapshot = _json_object(_row_value(row, "snapshot_json", 11))
    entry_plan_json = _json_object(_row_value(row, "entry_plan_json", 12))
    entry_split = _json_array(_row_value(row, "entry_split_json", 13))
    carne_plan_json = _json_object(_row_value(row, "carne_plan_json", 14))
    carne_split = _json_array(_row_value(row, "carne_split_json", 15))
    if (
        snapshot is None or entry_plan_json is None or entry_split is None
        or carne_plan_json is None or carne_split is None
        or int(_row_value(row, "intent_version", 16)) != 1
        or snapshot.get("version") != 1
        or snapshot.get("actor_user_id") != user_id
        or snapshot.get("unidade") != unidade
        or snapshot.get("environment") != environment
        or snapshot.get("account_wallet_id") != account_wallet_id
        or snapshot.get("paciente_id") != sale.paciente_id
        or snapshot.get("dentista_id") != sale.dentista_orcamentista_id
        or snapshot.get("dependente_id") != sale.dependente_id
        or snapshot.get("odontograma_id") != sale.odontograma_id
        or snapshot.get("qtd_parcelas_total") != sale.qtd_parcelas + 1
        or snapshot.get("first_due_date") != sale.data_vencimento_primeira_parcela.isoformat()
        or snapshot.get("intent_sha256") != _row_value(row, "intent_sha256", 17)
        or snapshot.get("intent_sha256") != _intent_hash(snapshot)
        or snapshot.get("snapshot_sha256") != _snapshot_hash(snapshot)
        or snapshot.get("entry_amount") != format(requested, ".2f")
        or not snapshot.get("issuer_account_id")
    ):
        raise AsaasSaleCreationConflictError("asaas_sale_entry_snapshot_invalid")
    try:
        from app.services.asaas_split_service import _json_to_plan

        entry_plan = _json_to_plan(entry_plan_json)
        carne_plan = _json_to_plan(carne_plan_json)
        gross = _money(snapshot.get("gross_total"), "gross_value")
        discount = _nonnegative_money(snapshot.get("discount_total"), "discount_value")
        net = _money(snapshot.get("net_total"), "net_value")
        remaining_values = tuple(
            _money(value, "remaining_value") for value in snapshot.get("remaining_values", [])
        )
        items = tuple(
            AsaasSaleItemSnapshot(
                item_number=int(item["item_number"]), product_id=int(item["product_id"]),
                quantity=int(item["quantity"]), unit_value=_money(item["unit_value"], "item_value"),
                total_value=_money(item["total_value"], "item_total"),
            )
            for item in snapshot.get("items", [])
        )
        if not items or len(remaining_values) != sale.qtd_parcelas:
            raise ValueError
        validate_asaas_new_split_preview(
            entry_plan, entry_split, unidade=unidade, environment=environment,
            account_wallet_id=account_wallet_id, charge_value=requested,
            contexto="entrada",
        )
        validate_asaas_new_split_preview(
            carne_plan, carne_split, unidade=unidade, environment=environment,
            account_wallet_id=account_wallet_id, charge_value=net - requested,
            contexto="carne",
        )
    except (AsaasSplitValidationError, KeyError, TypeError, ValueError, InvalidOperation):
        raise AsaasSaleCreationConflictError("asaas_sale_entry_snapshot_invalid") from None
    artifact_hashes = {
        "entry_plan_sha256": entry_plan_json,
        "entry_payload_sha256": entry_split,
        "carne_plan_sha256": carne_plan_json,
        "carne_payload_sha256": carne_split,
    }
    if any(
        snapshot.get(key) != hashlib.sha256(
            json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        for key, value in artifact_hashes.items()
    ):
        raise AsaasSaleCreationConflictError("asaas_sale_entry_snapshot_invalid")
    if (
        gross - discount != net
        or sum(remaining_values, Decimal("0.00")) != net - requested
        or sum((item.total_value for item in items), Decimal("0.00")) != gross
        or any(item.quantity <= 0 or item.unit_value <= 0 or item.total_value <= 0 for item in items)
    ):
        raise AsaasSaleCreationConflictError("asaas_sale_entry_snapshot_invalid")
    return _FrozenPaidEntry(
        entry_id=entry_id,
        pre_venda_id=str(_row_value(row, "pre_venda_id", 4)), amount=paid,
        gross_total=gross, discount_total=discount, net_total=net,
        remaining_values=remaining_values, items=items, carne_plan=carne_plan,
        carne_payload=carne_split, snapshot_sha256=str(snapshot["snapshot_sha256"]),
    )


def _calculate_gross_value(
    cursor: Any,
    *,
    sale: AsaasCarneSaleCreate,
    contract_installment_count: Optional[int] = None,
) -> tuple[Decimal, tuple[AsaasSaleItemSnapshot, ...]]:
    if sale.odontograma_id is not None:
        cursor.execute(
            """
            SELECT produto_id, valor_registrado
            FROM odontograma_itens
            WHERE odontograma_id = %s
            ORDER BY id
            """,
            (sale.odontograma_id,),
        )
        rows = cursor.fetchall()
        if not rows:
            raise AsaasSaleCreationError("asaas_sale_odontogram_without_items")
        if contract_installment_count is not None:
            cursor.execute(
                """
                SELECT t.valor_base
                FROM odontogramas AS o
                JOIN tipos_odontograma AS t
                  ON LOWER(t.nome) = LOWER(o.tipo) AND t.ativo = TRUE
                WHERE o.id = %s
                LIMIT 1
                """,
                (sale.odontograma_id,),
            )
            config = cursor.fetchone()
            if config is None:
                raise AsaasSaleCreationNotFoundError(
                    "asaas_sale_contract_config_not_found"
                )
            base_value = _money(
                _row_value(config, "valor_base", 0),
                "contract_base_value",
            )
            total = _money(
                base_value * contract_installment_count,
                "gross_value",
            )
            snapshots = _build_contract_item_snapshots(rows, total)
            return total, snapshots

        snapshots = tuple(
            AsaasSaleItemSnapshot(
                item_number=item_number,
                product_id=int(_row_value(row, "produto_id", 0)),
                quantity=1,
                unit_value=_money(
                    _row_value(row, "valor_registrado", 1),
                    "item_value",
                ),
                total_value=_money(
                    _row_value(row, "valor_registrado", 1),
                    "item_value",
                ),
            )
            for item_number, row in enumerate(rows, start=1)
        )
        total = sum(
            (snapshot.total_value for snapshot in snapshots),
            Decimal("0.00"),
        )
        return _money(total, "gross_value"), snapshots

    items = sale.itens_avulsos or []
    product_ids = sorted({item.produto_id for item in items})
    cursor.execute(
        "SELECT id, ativo, valor FROM produtos WHERE id = ANY(%s)",
        (product_ids,),
    )
    product_rows = cursor.fetchall()
    catalog_values = {
        int(_row_value(row, "id", 0)): _money(
            _row_value(row, "valor", 2),
            "catalog_value",
        )
        for row in product_rows
        if bool(_row_value(row, "ativo", 1))
    }
    if set(catalog_values) != set(product_ids):
        raise AsaasSaleCreationNotFoundError(
            "asaas_sale_product_unavailable"
        )
    snapshots: list[AsaasSaleItemSnapshot] = []
    for item_number, item in enumerate(items, start=1):
        requested_value = _money(
            item.valor_unitario_registrado,
            "item_value",
        )
        catalog_value = catalog_values[item.produto_id]
        if requested_value != catalog_value:
            raise AsaasSaleCreationConflictError(
                "asaas_sale_product_price_changed"
            )
        snapshots.append(
            AsaasSaleItemSnapshot(
                item_number=item_number,
                product_id=item.produto_id,
                quantity=item.quantidade,
                unit_value=catalog_value,
                total_value=_money(
                    catalog_value * item.quantidade,
                    "item_total",
                ),
            )
        )
    total = sum(
        (snapshot.total_value for snapshot in snapshots),
        Decimal("0.00"),
    )
    return _money(total, "gross_value"), tuple(snapshots)


def _build_contract_item_snapshots(
    rows: list[Any],
    gross_value: Decimal,
) -> tuple[AsaasSaleItemSnapshot, ...]:
    total_cents = int(gross_value * 100)
    item_count = len(rows)
    base_cents, remainder = divmod(total_cents, item_count)
    if base_cents <= 0:
        raise AsaasSaleCreationError(
            "asaas_sale_contract_item_allocation_invalid"
        )

    snapshots = []
    for index, row in enumerate(rows):
        allocated_cents = base_cents + (1 if index < remainder else 0)
        allocated_value = _money(
            Decimal(allocated_cents) / Decimal("100"),
            "item_value",
        )
        snapshots.append(
            AsaasSaleItemSnapshot(
                item_number=index + 1,
                product_id=int(_row_value(row, "produto_id", 0)),
                quantity=1,
                unit_value=allocated_value,
                total_value=allocated_value,
            )
        )
    return tuple(snapshots)


def _insert_sale_item_snapshots(
    cursor: Any,
    *,
    integration_id: int,
    venda_id: int,
    snapshots: tuple[AsaasSaleItemSnapshot, ...],
) -> None:
    if not snapshots:
        raise AsaasSaleCreationError("asaas_sale_items_required")
    for snapshot in snapshots:
        cursor.execute(
            """
            INSERT INTO asaas_sale_items (
                integration_id,
                venda_id,
                item_number,
                product_id,
                quantity,
                unit_value,
                total_value
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                integration_id,
                venda_id,
                snapshot.item_number,
                snapshot.product_id,
                snapshot.quantity,
                snapshot.unit_value,
                snapshot.total_value,
            ),
        )


def _calculate_rule_discount(
    cursor: Any,
    *,
    unidade: str,
    installment_count: int,
    gross_value: Decimal,
    payment_method: str = PAYMENT_METHOD_CODE,
) -> Decimal:
    cursor.execute(
        """
        SELECT percentage
        FROM asaas_sale_discount_rules
        WHERE unidade = %s
          AND payment_method = %s
          AND active = TRUE
          AND installment_min <= %s
          AND installment_max >= %s
        ORDER BY id
        """,
        (
            unidade,
            payment_method,
            installment_count,
            installment_count,
        ),
    )
    rows = cursor.fetchall()
    if len(rows) > 1:
        raise AsaasSaleCreationConflictError(
            "asaas_sale_overlapping_discount_rules"
        )
    if not rows:
        return Decimal("0.00")
    percentage = Decimal(str(_row_value(rows[0], "percentage", 0)))
    if not Decimal("0.00") <= percentage < Decimal("100.00"):
        raise AsaasSaleCreationError("asaas_sale_discount_rule_invalid")
    return (gross_value * percentage / Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _public_status(status: str, remote_creation_state: str) -> str:
    if remote_creation_state == "resultado_incerto":
        return "resultado_incerto"
    return status


def _money(value: Any, name: str) -> Decimal:
    try:
        normalized = Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, TypeError, ValueError):
        raise AsaasSaleCreationError(f"asaas_sale_{name}_invalid") from None
    if (
        not normalized.is_finite()
        or normalized <= 0
        or normalized > MAX_DATABASE_MONEY
    ):
        raise AsaasSaleCreationError(f"asaas_sale_{name}_invalid")
    return normalized


def _money_string(value: Any, name: str) -> str:
    return format(_money(value, name), ".2f")


def _nonnegative_money(value: Any, name: str) -> Decimal:
    try:
        normalized = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise AsaasSaleCreationError(f"asaas_sale_{name}_invalid") from None
    if not normalized.is_finite() or normalized < 0 or normalized > MAX_DATABASE_MONEY:
        raise AsaasSaleCreationError(f"asaas_sale_{name}_invalid")
    return normalized


def _json_object(value: Any) -> Optional[dict[str, Any]]:
    if isinstance(value, Mapping):
        return dict(value)
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError):
        return None
    return dict(decoded) if isinstance(decoded, Mapping) else None


def _json_array(value: Any) -> Optional[list[dict[str, Any]]]:
    if isinstance(value, list) and all(isinstance(item, Mapping) for item in value):
        return [dict(item) for item in value]
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError):
        return None
    return [dict(item) for item in decoded] if isinstance(decoded, list) and all(isinstance(item, Mapping) for item in decoded) else None


def _snapshot_hash(snapshot: Mapping[str, Any]) -> str:
    body = dict(snapshot)
    body.pop("snapshot_sha256", None)
    encoded = json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _intent_hash(snapshot: Mapping[str, Any]) -> str:
    derived = {
        "intent_sha256", "entry_plan_sha256", "entry_payload_sha256",
        "carne_plan_sha256", "carne_payload_sha256", "snapshot_sha256",
    }
    body = {key: value for key, value in snapshot.items() if key not in derived}
    encoded = json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _row_value(row: Any, name: str, index: int) -> Any:
    return row[name] if isinstance(row, Mapping) else row[index]


def _optional_string(value: Any) -> Optional[str]:
    return str(value) if value is not None else None


def _validate_positive_id(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AsaasSaleCreationError(f"asaas_sale_{name}_invalid")
    return value
