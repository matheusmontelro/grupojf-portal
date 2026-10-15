"""Cobranças avulsas estritas para a entrada do Carnê Asaas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping, Optional, TypedDict
from urllib.parse import urlparse

from app.asaas_sdk.exceptions import AsaasAPIError, AsaasValidationError
from app.asaas_sdk.http_client import AsaasHttpClient


_RESOURCE_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9:_-]{1,120}$")
_METHODS = frozenset({"PIX", "BOLETO", "CREDIT_CARD"})
_STATUSES = frozenset(
    {
        "PENDING", "RECEIVED", "CONFIRMED", "OVERDUE", "REFUNDED",
        "RECEIVED_IN_CASH", "REFUND_REQUESTED", "REFUND_IN_PROGRESS",
        "CHARGEBACK_REQUESTED", "CHARGEBACK_DISPUTE",
        "AWAITING_CHARGEBACK_REVERSAL", "DUNNING_REQUESTED",
        "DUNNING_RECEIVED", "AWAITING_RISK_ANALYSIS",
    }
)
_SANDBOX_HOSTS = frozenset({"sandbox.asaas.com"})


class AsaasEntryPayment(TypedDict):
    id: str
    customer: str
    billingType: str
    status: str
    externalReference: str
    invoiceUrl: str
    value: float
    netValue: float


def _invalid(detail: str = "invalid_entry_response") -> None:
    raise AsaasAPIError(status_code=502, response_body=None, detail=detail)


def _id(value: Any, *, request: bool = False) -> str:
    normalized = str(value or "").strip()
    if not _RESOURCE_ID.fullmatch(normalized):
        if request:
            raise AsaasValidationError(["entry_identifier_invalid"])
        _invalid()
    return normalized


def _reference(value: Any, *, request: bool = False) -> str:
    normalized = str(value or "").strip()
    if not _REFERENCE.fullmatch(normalized):
        if request:
            raise AsaasValidationError(["entry_reference_invalid"])
        _invalid()
    return normalized


def _money(value: Any) -> float:
    try:
        raw = Decimal(str(value))
        normalized = raw.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise AsaasValidationError(["entry_amount_invalid"]) from None
    if not normalized.is_finite() or normalized <= 0 or raw != normalized:
        raise AsaasValidationError(["entry_amount_invalid"])
    return float(normalized)


def _invoice_url(value: Any) -> str:
    normalized = str(value or "").strip()
    parsed = urlparse(normalized)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _SANDBOX_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        _invalid("invalid_entry_checkout_url")
    return normalized


def _sanitize(
    payload: Any,
    *,
    customer: str,
    billing_type: str,
    external_reference: str,
    expected_amount: Any | None = None,
    expected_split: Optional[list[dict[str, Any]]] = None,
    expected_payment_id: Optional[str] = None,
) -> AsaasEntryPayment:
    if not isinstance(payload, Mapping):
        _invalid()
    returned_customer = _id(payload.get("customer"))
    returned_type = str(payload.get("billingType") or "").strip().upper()
    returned_reference = _reference(payload.get("externalReference"))
    status = str(payload.get("status") or "").strip().upper()
    returned_amount: float | None = None
    returned_net_amount: float | None = None
    if expected_amount is not None:
        try:
            returned_amount = _money(payload.get("value"))
            returned_net_amount = _money(payload.get("netValue"))
            expected = _money(expected_amount)
        except AsaasValidationError:
            _invalid("entry_amount_mismatch")
        # value is the contracted gross amount. netValue legitimately differs
        # after provider fees, but can never exceed it or be non-positive.
        if returned_amount != expected or returned_net_amount > returned_amount:
            _invalid("entry_amount_mismatch")
        if expected_split is not None:
            _validate_remote_split(
                payload.get("split"), expected_split, Decimal(str(returned_net_amount))
            )
    if (
        returned_customer != customer
        or returned_type != billing_type
        or returned_reference != external_reference
        or status not in _STATUSES
    ):
        _invalid("entry_identity_mismatch")
    returned_id = _id(payload.get("id"))
    if expected_payment_id is not None and returned_id != expected_payment_id:
        _invalid("entry_identity_mismatch")
    return {
        "id": returned_id,
        "customer": returned_customer,
        "billingType": returned_type,
        "status": status,
        "externalReference": returned_reference,
        "invoiceUrl": _invoice_url(payload.get("invoiceUrl")),
        **({"value": returned_amount, "netValue": returned_net_amount}
           if returned_amount is not None and returned_net_amount is not None else {}),
    }


def _normalize_split(
    value: Any,
    *,
    allowed_value_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Valida o ``split`` (lista de {walletId, valor}) do payload de entrada.

    A entrada e um pagamento unico: aceitamos ``fixedValue`` ou
    ``percentualValue`` por item, conforme o contexto (caller decide).
    """
    if not isinstance(value, list) or not value:
        raise AsaasValidationError(["entry_split_invalid"])
    normalized: list[dict[str, Any]] = []
    wallets: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise AsaasValidationError(["entry_split_invalid"])
        wallet = str(item.get("walletId") or "").strip()
        if not wallet or not _RESOURCE_ID.fullmatch(wallet):
            raise AsaasValidationError(["entry_split_invalid"])
        if wallet in wallets:
            raise AsaasValidationError(["entry_split_invalid"])
        wallets.add(wallet)
        # A resposta do Asaas pode materializar a outra variante como ``null``.
        # Para cobrança avulsa, porém, há exatamente um valor não-nulo; a
        # variante ``totalFixedValue`` pertence a parcelamentos e não pode
        # entrar silenciosamente nesta prova.
        if item.get("totalFixedValue") is not None:
            raise AsaasValidationError(["entry_split_invalid"])
        present_value_keys = [
            key for key in allowed_value_keys if item.get(key) is not None
        ]
        if len(present_value_keys) != 1:
            raise AsaasValidationError(["entry_split_invalid"])
        key = present_value_keys[0]
        raw = item[key]
        try:
            numeric = Decimal(str(raw))
            precision = Decimal("0.0001") if key == "percentualValue" else Decimal("0.01")
            rounded = numeric.quantize(precision)
        except (InvalidOperation, TypeError, ValueError):
            raise AsaasValidationError(["entry_split_invalid"]) from None
        if not numeric.is_finite() or numeric <= 0 or numeric != rounded:
            raise AsaasValidationError(["entry_split_invalid"])
        if key == "percentualValue" and numeric > Decimal("100"):
            raise AsaasValidationError(["entry_split_invalid"])
        normalized.append({"walletId": wallet, key: float(rounded)})
    return normalized


def _validate_remote_split(value: Any, expected: list[dict[str, Any]], net: Decimal) -> None:
    """Require the remote split to be exactly the frozen plan and affordable.

    Percentages are intentionally assessed against ``netValue``; no fee is
    inferred and no participant is silently resized to make a split fit.
    """
    try:
        actual = _normalize_split(value, allowed_value_keys=("fixedValue", "percentualValue"))
        frozen = _normalize_split(expected, allowed_value_keys=("fixedValue", "percentualValue"))
        def canonical(items: list[dict[str, Any]]) -> dict[str, tuple[str, Decimal]]:
            return {
                item["walletId"]: (
                    "fixedValue" if "fixedValue" in item else "percentualValue",
                    Decimal(str(item.get("fixedValue", item.get("percentualValue")))),
                ) for item in items
            }
        if canonical(actual) != canonical(frozen):
            _invalid("entry_split_mismatch")
        total = Decimal("0")
        for item in frozen:
            if "fixedValue" in item:
                total += Decimal(str(item["fixedValue"]))
            else:
                total += net * Decimal(str(item["percentualValue"])) / Decimal("100")
        if total > net:
            _invalid("entry_split_exceeds_net_value")
    except AsaasValidationError:
        _invalid("entry_split_mismatch")


class AsaasSalesEntryManager:
    """Cria e consulta apenas cobranças de entrada no Sandbox."""

    def __init__(self, http_client: AsaasHttpClient):
        self._http_client = http_client

    def create_payment(
        self,
        *,
        customer_id: str,
        billing_type: str,
        amount: Any,
        due_date: str,
        external_reference: str,
        installments: int = 1,
        split: Optional[list] = None,
    ) -> AsaasEntryPayment:
        customer = _id(customer_id, request=True)
        method = str(billing_type or "").strip().upper()
        reference = _reference(external_reference, request=True)
        if method not in _METHODS:
            raise AsaasValidationError(["entry_method_invalid"])
        try:
            normalized_due_date = date.fromisoformat(due_date).isoformat()
        except (TypeError, ValueError):
            raise AsaasValidationError(["entry_due_date_invalid"]) from None
        if (
            isinstance(installments, bool)
            or not isinstance(installments, int)
            or not 1 <= installments <= 12
            or (method != "CREDIT_CARD" and installments != 1)
        ):
            raise AsaasValidationError(["entry_installments_invalid"])

        payload: dict[str, Any] = {
            "customer": customer,
            "billingType": method,
            "dueDate": normalized_due_date,
            "description": "Entrada de tratamento odontologico",
            "externalReference": reference,
        }
        normalized_amount = _money(amount)
        if installments > 1:
            payload.update(
                {"installmentCount": installments, "totalValue": normalized_amount}
            )
        else:
            payload["value"] = normalized_amount
        if method == "BOLETO":
            payload["postalService"] = False
        if split:
            payload["split"] = _normalize_split(
                split,
                allowed_value_keys=("fixedValue", "percentualValue"),
            )

        response = self._http_client.post("/payments", json=payload)
        return _sanitize(
            response.json(),
            customer=customer,
            billing_type=method,
            external_reference=reference,
            # The POST response is not the reconciliation proof: Asaas returns
            # the complete split on GET /payments/{id}. The caller that uses a
            # frozen plan must read it back before accepting payment.
            expected_amount=None,
        )

    def get_payment(
        self,
        payment_id: str,
        *,
        customer_id: str,
        billing_type: str,
        external_reference: str,
        expected_amount: Any | None = None,
        expected_split: Optional[list[dict[str, Any]]] = None,
    ) -> AsaasEntryPayment:
        payment = _id(payment_id, request=True)
        customer = _id(customer_id, request=True)
        method = str(billing_type or "").strip().upper()
        reference = _reference(external_reference, request=True)
        if method not in _METHODS:
            raise AsaasValidationError(["entry_method_invalid"])
        response = self._http_client.get(f"/payments/{payment}")
        return _sanitize(
            response.json(),
            customer=customer,
            billing_type=method,
            external_reference=reference,
            expected_amount=expected_amount,
            expected_split=expected_split,
            expected_payment_id=payment,
        )

    def find_payments(
        self,
        *,
        customer_id: str,
        billing_type: str,
        external_reference: str,
        expected_amount: Any | None = None,
        expected_split: Optional[list[dict[str, Any]]] = None,
    ) -> list[AsaasEntryPayment]:
        customer = _id(customer_id, request=True)
        method = str(billing_type or "").strip().upper()
        reference = _reference(external_reference, request=True)
        if method not in _METHODS:
            raise AsaasValidationError(["entry_method_invalid"])
        response = self._http_client.get(
            "/payments",
            params={
                "customer": customer,
                "externalReference": reference,
                "limit": 10,
                "offset": 0,
            },
        )
        payload = response.json()
        if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), list):
            _invalid()
        items = payload["data"]
        if len(items) > 1:
            _invalid("entry_remote_conflict")
        return [
            _sanitize(
                item,
                customer=customer,
                billing_type=method,
                external_reference=reference,
                expected_amount=expected_amount,
                expected_split=expected_split,
            )
            for item in items
        ]
