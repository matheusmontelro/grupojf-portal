"""Operacoes isoladas de parcelamento para o fluxo de vendas Asaas."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, NotRequired, TypedDict

from app.asaas_sdk.exceptions import AsaasAPIError, AsaasValidationError
from app.asaas_sdk.http_client import AsaasHttpClient


_RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
_EXTERNAL_REFERENCE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,254}$"
)
_STATUS_PATTERN = re.compile(r"^[A-Z][A-Z_]{0,63}$")
_PAYMENT_STATUSES = frozenset(
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
        "AWAITING_RISK_ANALYSIS",
    }
)
_PAYMENT_BOOK_ACCEPTS = frozenset({"application/json", "application/pdf"})
_INSTALLMENT_PAYLOAD_FIELDS = frozenset(
    {
        "billingType",
        "customer",
        "daysAfterDueDateToRegistrationCancellation",
        "description",
        "dueDate",
        "installmentCount",
        "paymentExternalReference",
        "postalService",
        "split",
        "totalValue",
        "value",
    }
)
_PAGE_LIMIT = 100
_MAX_REMOTE_ITEMS = 1000
_MAX_PDF_BYTES = 50 * 1024 * 1024


class AsaasCustomerPreflight(TypedDict):
    """Campos nao pessoais necessarios antes de provisionar uma venda."""

    id: str
    notificationDisabled: bool


class AsaasPaymentSummary(TypedDict):
    """Recorte seguro de uma cobranca pertencente ao parcelamento."""

    id: str
    installment: str
    customer: str
    billingType: str
    dueDate: str
    value: float
    status: str
    externalReference: str


class AsaasCreatedInstallment(TypedDict):
    """Identidade segura retornada ao criar um parcelamento."""

    id: str
    installment: str
    customer: str
    billingType: str
    dueDate: str
    value: float
    status: NotRequired[str]
    externalReference: str


class AsaasPaymentBookJSON(TypedDict):
    """Representacao JSON saneada do carnê."""

    installment: str
    payments: list[AsaasPaymentSummary]


def _invalid_remote_response(detail: str = "invalid_response") -> None:
    raise AsaasAPIError(
        status_code=502,
        response_body=None,
        detail=detail,
    )


def _decode_mapping(response: Any) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except (TypeError, ValueError):
        _invalid_remote_response()
    if not isinstance(payload, Mapping):
        _invalid_remote_response()
    return payload


def _normalize_request_identifier(value: Any, error_code: str) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not _RESOURCE_ID_PATTERN.fullmatch(value)
    ):
        raise AsaasValidationError([error_code])
    return value


def _normalize_remote_identifier(value: Any) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not _RESOURCE_ID_PATTERN.fullmatch(value)
    ):
        _invalid_remote_response()
    return value


def _normalize_request_external_reference(value: Any) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not _EXTERNAL_REFERENCE_PATTERN.fullmatch(value)
        or (value.isdigit() and len(value) in {11, 14})
    ):
        raise AsaasValidationError(["external_reference_invalid"])
    return value


def _normalize_remote_external_reference(value: Any) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not _EXTERNAL_REFERENCE_PATTERN.fullmatch(value)
    ):
        _invalid_remote_response()
    return value


def _normalize_request_date(value: Any) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise AsaasValidationError(["installment_due_date_invalid"])
    try:
        normalized = date.fromisoformat(value).isoformat()
    except ValueError:
        raise AsaasValidationError(["installment_due_date_invalid"]) from None
    if normalized != value:
        raise AsaasValidationError(["installment_due_date_invalid"])
    return normalized


def _normalize_remote_date(value: Any) -> str:
    if not isinstance(value, str):
        _invalid_remote_response()
    try:
        normalized = date.fromisoformat(value).isoformat()
    except ValueError:
        _invalid_remote_response()
    if normalized != value:
        _invalid_remote_response()
    return normalized


def _normalize_money(value: Any, *, request_error: str | None = None) -> float:
    if isinstance(value, bool):
        normalized = None
    else:
        try:
            normalized = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            normalized = None
    if normalized is None or not normalized.is_finite() or normalized <= 0:
        if request_error:
            raise AsaasValidationError([request_error])
        _invalid_remote_response()
    try:
        quantized = normalized.quantize(Decimal("0.01"))
    except InvalidOperation:
        if request_error:
            raise AsaasValidationError([request_error]) from None
        _invalid_remote_response()
    if normalized != quantized:
        if request_error:
            raise AsaasValidationError([request_error])
        _invalid_remote_response()
    return float(quantized)


def _normalize_remote_status(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not _STATUS_PATTERN.fullmatch(value)
        or value not in _PAYMENT_STATUSES
    ):
        _invalid_remote_response("invalid_payment_status")
    return value


def _normalize_split_payload(
    value: Any,
    *,
    allowed_value_keys: tuple[str, ...],
    error_code: str,
) -> list[dict[str, Any]]:
    """Valida o campo ``split`` (lista de {walletId, valor}) do payload.

    O Asaas exige um ``walletId`` e exatamente uma chave de valor por
    item. O caller escolhe as chaves permitidas por contexto (carnê:
    ``totalFixedValue``; entrada: ``fixedValue``; pix/cartao:
    ``percentualValue``).
    """
    if not isinstance(value, list) or not value:
        raise AsaasValidationError([error_code])
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise AsaasValidationError([error_code])
        wallet = item.get("walletId")
        if (
            not isinstance(wallet, str)
            or wallet != wallet.strip()
            or not _RESOURCE_ID_PATTERN.fullmatch(wallet)
        ):
            raise AsaasValidationError([error_code])
        # Rejeitar ambiguidade: o Asaas exige EXATAMENTE uma chave de valor
        # por item. Se houver mais de uma chave permitida presente, o item e
        # ambiguo e seria interpretado de forma incerta pelo Asaas — area de
        # dinheiro exige fail-closed.
        present_value_keys = [key for key in allowed_value_keys if key in item]
        if len(present_value_keys) != 1:
            raise AsaasValidationError([error_code])
        key = present_value_keys[0]
        raw_value = item[key]
        try:
            numeric = float(raw_value)
        except (TypeError, ValueError):
            raise AsaasValidationError([error_code]) from None
        if numeric <= 0:
            raise AsaasValidationError([error_code])
        normalized.append({"walletId": wallet, key: round(numeric, 2)})
    return normalized


def _sanitize_payment(
    payload: Any,
    *,
    expected_customer: str | None = None,
    expected_external_reference: str | None = None,
    expected_installment: str | None = None,
) -> AsaasPaymentSummary:
    if not isinstance(payload, Mapping):
        _invalid_remote_response()

    payment_id = _normalize_remote_identifier(payload.get("id"))
    installment_id = _normalize_remote_identifier(payload.get("installment"))
    customer_id = _normalize_remote_identifier(payload.get("customer"))
    external_reference = _normalize_remote_external_reference(
        payload.get("externalReference")
    )
    billing_type = payload.get("billingType")
    if billing_type != "BOLETO":
        _invalid_remote_response("invalid_payment_response")
    if expected_customer is not None and customer_id != expected_customer:
        _invalid_remote_response("payment_customer_mismatch")
    if (
        expected_external_reference is not None
        and external_reference != expected_external_reference
    ):
        _invalid_remote_response("payment_reference_mismatch")
    if expected_installment is not None and installment_id != expected_installment:
        _invalid_remote_response("payment_installment_mismatch")

    return {
        "id": payment_id,
        "installment": installment_id,
        "customer": customer_id,
        "billingType": billing_type,
        "dueDate": _normalize_remote_date(payload.get("dueDate")),
        "value": _normalize_money(payload.get("value")),
        "status": _normalize_remote_status(payload.get("status")),
        "externalReference": external_reference,
    }


def _decode_page(response: Any) -> tuple[list[Any], int]:
    page = _decode_mapping(response)
    items = page.get("data")
    total_count = page.get("totalCount")
    if (
        not isinstance(items, list)
        or isinstance(total_count, bool)
        or not isinstance(total_count, int)
        or total_count < 0
        or total_count > _MAX_REMOTE_ITEMS
        or len(items) > _PAGE_LIMIT
    ):
        _invalid_remote_response()
    return items, total_count


class AsaasSalesInstallmentManager:
    """Cliente minimo e defensivo para o Carnê Asaas."""

    def __init__(self, http_client: AsaasHttpClient):
        self._http_client = http_client

    def get_customer(self, customer_id: str) -> AsaasCustomerPreflight:
        """Confirma a identidade e o bloqueio global de notificacoes do cliente."""
        normalized_id = _normalize_request_identifier(
            customer_id,
            "customer_id_invalid",
        )
        customer = _decode_mapping(
            self._http_client.get(f"/customers/{normalized_id}")
        )
        returned_id = _normalize_remote_identifier(customer.get("id"))
        notification_disabled = customer.get("notificationDisabled")
        if returned_id != normalized_id or not isinstance(
            notification_disabled, bool
        ):
            _invalid_remote_response("invalid_customer_response")
        return {
            "id": returned_id,
            "notificationDisabled": notification_disabled,
        }

    def find_payments(
        self,
        customer_id: str,
        external_reference: str,
    ) -> list[AsaasPaymentSummary]:
        """Localiza cobrancas usando os dois identificadores de conciliacao."""
        normalized_customer = _normalize_request_identifier(
            customer_id,
            "customer_id_invalid",
        )
        normalized_reference = _normalize_request_external_reference(
            external_reference
        )
        return self._fetch_payment_pages(
            endpoint="/payments",
            filters={
                "customer": normalized_customer,
                "externalReference": normalized_reference,
            },
            sanitizer=lambda payment: _sanitize_payment(
                payment,
                expected_customer=normalized_customer,
                expected_external_reference=normalized_reference,
            ),
        )

    def create_installment(
        self,
        installment_data: Mapping[str, Any],
    ) -> AsaasCreatedInstallment:
        """Cria um parcelamento de boleto sem split ou envio postal."""
        payload = self._normalize_installment_payload(installment_data)
        response = self._http_client.post("/installments", json=payload)
        remote = _decode_mapping(response)

        customer_id = _normalize_remote_identifier(remote.get("customer"))
        if customer_id != payload["customer"]:
            _invalid_remote_response("payment_customer_mismatch")
        billing_type = remote.get("billingType")
        if billing_type != "BOLETO":
            _invalid_remote_response("invalid_installment_response")
        external_reference = _normalize_remote_external_reference(
            remote.get("externalReference", remote.get("paymentExternalReference"))
        )
        if external_reference != payload["paymentExternalReference"]:
            _invalid_remote_response("payment_reference_mismatch")

        remote_id = _normalize_remote_identifier(remote.get("id"))
        installment_id = _normalize_remote_identifier(remote.get("installment"))
        result: AsaasCreatedInstallment = {
            "id": remote_id,
            "installment": installment_id,
            "customer": customer_id,
            "billingType": billing_type,
            "dueDate": _normalize_remote_date(remote.get("dueDate")),
            "value": _normalize_money(remote.get("value")),
            "externalReference": external_reference,
        }
        if "status" in remote:
            result["status"] = _normalize_remote_status(remote.get("status"))
        return result

    def list_installment_payments(
        self,
        installment_id: str,
    ) -> list[AsaasPaymentSummary]:
        normalized_id = _normalize_request_identifier(
            installment_id,
            "installment_id_invalid",
        )
        return self._fetch_payment_pages(
            endpoint=f"/installments/{normalized_id}/payments",
            filters={},
            sanitizer=lambda payment: _sanitize_payment(
                payment,
                expected_installment=normalized_id,
            ),
        )

    def get_payment_book(
        self,
        installment_id: str,
        *,
        accept: str = "application/pdf",
    ) -> bytes | AsaasPaymentBookJSON:
        normalized_id = _normalize_request_identifier(
            installment_id,
            "installment_id_invalid",
        )
        if accept not in _PAYMENT_BOOK_ACCEPTS:
            raise AsaasValidationError(["payment_book_accept_invalid"])

        response = self._http_client.request(
            "GET",
            f"/installments/{normalized_id}/paymentBook",
            headers={"Accept": accept},
        )
        self._validate_content_type(response, accept)
        if accept == "application/pdf":
            content = getattr(response, "content", None)
            if (
                not isinstance(content, (bytes, bytearray))
                or not content.startswith(b"%PDF-")
                or len(content) > _MAX_PDF_BYTES
            ):
                _invalid_remote_response("invalid_payment_book_response")
            return bytes(content)

        payload = _decode_mapping(response)
        raw_payments = payload.get("payments", payload.get("data"))
        if not isinstance(raw_payments, list) or len(raw_payments) > _MAX_REMOTE_ITEMS:
            _invalid_remote_response("invalid_payment_book_response")
        return {
            "installment": normalized_id,
            "payments": [
                _sanitize_payment(
                    payment,
                    expected_installment=normalized_id,
                )
                for payment in raw_payments
            ],
        }

    def _fetch_payment_pages(
        self,
        *,
        endpoint: str,
        filters: Mapping[str, Any],
        sanitizer: Callable[[Any], AsaasPaymentSummary],
    ) -> list[AsaasPaymentSummary]:
        offset = 0
        expected_total: int | None = None
        payments: list[AsaasPaymentSummary] = []
        seen_ids: set[str] = set()

        while True:
            response = self._http_client.get(
                endpoint,
                params={
                    **filters,
                    "limit": _PAGE_LIMIT,
                    "offset": offset,
                },
            )
            items, total_count = _decode_page(response)
            if expected_total is None:
                expected_total = total_count
            elif total_count != expected_total:
                _invalid_remote_response()
            if offset + len(items) > total_count:
                _invalid_remote_response()

            for item in items:
                payment = sanitizer(item)
                if payment["id"] in seen_ids:
                    _invalid_remote_response()
                seen_ids.add(payment["id"])
                payments.append(payment)

            offset += len(items)
            if offset == total_count:
                return payments
            if not items or offset > total_count:
                _invalid_remote_response()

    @staticmethod
    def _normalize_installment_payload(
        installment_data: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(installment_data, Mapping):
            raise AsaasValidationError(["installment_payload_invalid"])
        if any(not isinstance(key, str) for key in installment_data):
            raise AsaasValidationError(["installment_payload_invalid"])
        if set(installment_data) - _INSTALLMENT_PAYLOAD_FIELDS:
            raise AsaasValidationError(["installment_payload_invalid"])

        customer_id = _normalize_request_identifier(
            installment_data.get("customer"),
            "customer_id_invalid",
        )
        if installment_data.get("billingType") != "BOLETO":
            raise AsaasValidationError(["installment_billing_type_invalid"])
        installment_count = installment_data.get("installmentCount")
        if (
            isinstance(installment_count, bool)
            or not isinstance(installment_count, int)
            or not 2 <= installment_count <= _MAX_REMOTE_ITEMS
        ):
            raise AsaasValidationError(["installment_count_invalid"])

        payload: dict[str, Any] = {
            "customer": customer_id,
            "billingType": "BOLETO",
            "installmentCount": installment_count,
            "value": _normalize_money(
                installment_data.get("value"),
                request_error="installment_value_invalid",
            ),
            "dueDate": _normalize_request_date(installment_data.get("dueDate")),
            "paymentExternalReference": _normalize_request_external_reference(
                installment_data.get("paymentExternalReference")
            ),
        }

        if "totalValue" in installment_data:
            payload["totalValue"] = _normalize_money(
                installment_data.get("totalValue"),
                request_error="installment_total_value_invalid",
            )
        if "description" in installment_data:
            description = installment_data.get("description")
            if (
                not isinstance(description, str)
                or description != description.strip()
                or not description
                or len(description) > 500
            ):
                raise AsaasValidationError(["installment_description_invalid"])
            payload["description"] = description
        if "postalService" in installment_data:
            if installment_data.get("postalService") is not False:
                raise AsaasValidationError(["postal_service_forbidden"])
            payload["postalService"] = False
        if "daysAfterDueDateToRegistrationCancellation" in installment_data:
            days = installment_data.get(
                "daysAfterDueDateToRegistrationCancellation"
            )
            if (
                isinstance(days, bool)
                or not isinstance(days, int)
                or not 0 <= days <= 3650
            ):
                raise AsaasValidationError(
                    ["registration_cancellation_days_invalid"]
                )
            payload["daysAfterDueDateToRegistrationCancellation"] = days
        if "split" in installment_data:
            payload["split"] = _normalize_split_payload(
                installment_data.get("split"),
                allowed_value_keys=("totalFixedValue", "percentualValue"),
                error_code="installment_split_invalid",
            )
        return payload

    @staticmethod
    def _validate_content_type(response: Any, expected: str) -> None:
        headers = getattr(response, "headers", None)
        if not isinstance(headers, Mapping):
            _invalid_remote_response("invalid_payment_book_response")
        raw_content_type = headers.get("content-type", headers.get("Content-Type"))
        if not isinstance(raw_content_type, str):
            _invalid_remote_response("invalid_payment_book_response")
        content_type = raw_content_type.partition(";")[0].strip().casefold()
        if content_type != expected:
            _invalid_remote_response("invalid_payment_book_response")
