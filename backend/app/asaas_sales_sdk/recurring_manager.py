"""Managers estritos dos produtos recorrentes do fluxo isolado de vendas."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Optional, TypedDict
from urllib.parse import urlparse

from app.asaas_sdk.exceptions import AsaasIntegrationError, AsaasValidationError
from app.asaas_sdk.http_client import AsaasHttpClient


_RESOURCE_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
_EXTERNAL_REFERENCE = re.compile(r"^[A-Za-z0-9:_-]{1,120}$")
_PIX_STATUSES = frozenset(
    {"CREATED", "PENDING", "ACTIVE", "REFUSED", "CANCELLED", "EXPIRED"}
)
_CHECKOUT_STATUSES = frozenset(
    {"ACTIVE", "PAID", "CANCELLED", "CANCELED", "EXPIRED", "INACTIVE"}
)
_SANDBOX_CHECKOUT_HOSTS = frozenset({"sandbox.asaas.com"})


class AsaasPixAuthorization(TypedDict):
    id: str
    status: str
    qr_payload: Optional[str]
    expires_at: Optional[str]


class AsaasRecurringCheckout(TypedDict):
    id: str
    status: str
    link: str


def _required_id(value: Any, name: str) -> str:
    normalized = str(value or "").strip()
    if not _RESOURCE_ID.fullmatch(normalized):
        raise AsaasValidationError([f"{name}_invalid"])
    return normalized


def _required_reference(value: Any, *, max_length: int = 120) -> str:
    normalized = str(value or "").strip()
    if (
        not _EXTERNAL_REFERENCE.fullmatch(normalized)
        or len(normalized) > max_length
    ):
        raise AsaasValidationError(["external_reference_invalid"])
    return normalized


def _date_string(value: Any, name: str) -> str:
    normalized = str(value or "").strip()
    try:
        datetime.fromisoformat(normalized)
    except (TypeError, ValueError):
        raise AsaasValidationError([f"{name}_invalid"]) from None
    return normalized


def _optional_datetime_string(value: Any, name: str) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    try:
        datetime.fromisoformat(normalized)
    except (TypeError, ValueError):
        raise AsaasIntegrationError(f"invalid_{name}") from None
    return normalized


def _checkout_datetime(value: Any, name: str) -> str:
    normalized = _date_string(value, name)
    if len(normalized) == 10:
        return f"{normalized} 00:00:00"
    return normalized


def _money(value: Any, name: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        raise AsaasValidationError([f"{name}_invalid"]) from None
    if normalized <= 0 or normalized > 9_999_999_999.99:
        raise AsaasValidationError([f"{name}_invalid"])
    return round(normalized, 2)


def _sanitize_pix_authorization(payload: Any) -> AsaasPixAuthorization:
    if not isinstance(payload, dict):
        raise AsaasIntegrationError("invalid_pix_authorization_response")
    resource_id = _required_id(payload.get("id"), "pix_authorization_id")
    status = str(payload.get("status") or "CREATED").strip().upper()
    if status not in _PIX_STATUSES:
        raise AsaasIntegrationError("invalid_pix_authorization_status")
    raw_qr = payload.get("immediateQrCode") or payload.get("qrCode") or {}
    qr_payload = None
    expires_at = None
    if isinstance(raw_qr, dict):
        # `encodedImage` e uma imagem base64, nao o Pix copia e cola. Nunca a
        # devolvemos ao frontend como payload de pagamento.
        raw_payload = raw_qr.get("payload")
        if isinstance(raw_payload, str) and 1 <= len(raw_payload.strip()) <= 2048:
            qr_payload = raw_payload.strip()
        raw_expiration = (
            raw_qr.get("expirationDate")
            or raw_qr.get("expiresAt")
            or raw_qr.get("expiration")
        )
        if isinstance(raw_expiration, str) and raw_expiration.strip():
            expires_at = _optional_datetime_string(
                raw_expiration,
                "pix_expiration",
            )
    if qr_payload is None:
        raw_payload = payload.get("payload")
        if isinstance(raw_payload, str) and 1 <= len(raw_payload.strip()) <= 2048:
            qr_payload = raw_payload.strip()
    return {
        "id": resource_id,
        "status": status,
        "qr_payload": qr_payload,
        "expires_at": expires_at,
    }


def _sanitize_checkout(payload: Any) -> AsaasRecurringCheckout:
    if not isinstance(payload, dict):
        raise AsaasIntegrationError("invalid_checkout_response")
    resource_id = _required_id(payload.get("id"), "checkout_id")
    status = str(payload.get("status") or "").strip().upper()
    if status not in _CHECKOUT_STATUSES:
        raise AsaasIntegrationError("invalid_checkout_status")
    raw_link = str(payload.get("link") or "").strip()
    if not raw_link:
        raise AsaasIntegrationError("invalid_checkout_link")
    parsed = urlparse(raw_link)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _SANDBOX_CHECKOUT_HOSTS
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise AsaasIntegrationError("invalid_checkout_link")
    return {"id": resource_id, "status": status, "link": raw_link}


def _normalize_split(
    value: Any,
    *,
    error_code: str,
) -> list[dict[str, Any]]:
    """Valida o ``split`` (lista de {walletId, percentualValue}).

    Para Pix automatico e checkout recorrente o Asaas aceita apenas
    ``percentualValue`` por item. ``walletId`` e obrigatorio.
    """
    if not isinstance(value, list) or not value:
        raise AsaasValidationError([error_code])
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AsaasValidationError([error_code])
        wallet = str(item.get("walletId") or "").strip()
        if not wallet or not _RESOURCE_ID.fullmatch(wallet):
            raise AsaasValidationError([error_code])
        # Rejeitar ambiguidade: para pix/cartao o Asaas aceita apenas
        # percentualValue. Se houver outra chave de valor (fixedValue/
        # totalFixedValue) presente, o item e ambiguo — fail-closed.
        if "percentualValue" not in item:
            raise AsaasValidationError([error_code])
        if any(
            extra in item
            for extra in ("fixedValue", "totalFixedValue")
        ):
            raise AsaasValidationError([error_code])
        try:
            numeric = float(item["percentualValue"])
        except (TypeError, ValueError):
            raise AsaasValidationError([error_code]) from None
        if numeric <= 0 or numeric > 100:
            raise AsaasValidationError([error_code])
        normalized.append(
            {"walletId": wallet, "percentualValue": round(numeric, 4)}
        )
    return normalized


class AsaasSalesRecurringManager:
    def __init__(self, http_client: AsaasHttpClient):
        self.http_client = http_client

    def create_pix_authorization(
        self,
        *,
        customer_id: str,
        contract_id: str,
        start_date: str,
        finish_date: str,
        value: Any,
        split: Optional[list] = None,
    ) -> AsaasPixAuthorization:
        payload = {
            "customerId": _required_id(customer_id, "customer_id"),
            "frequency": "MONTHLY",
            "contractId": _required_reference(contract_id, max_length=35),
            "startDate": _date_string(start_date, "start_date"),
            "finishDate": _date_string(finish_date, "finish_date"),
            "value": _money(value, "value"),
            "description": "Tratamento odontologico",
            "immediateQrCode": {},
            "paymentCreationMode": "SUBSCRIPTION",
            "retryPolicy": "NOT_ALLOWED",
        }
        if split:
            payload["split"] = _normalize_split(
                split,
                error_code="pix_split_invalid",
            )
        response = self.http_client.post(
            "/pix/automatic/authorizations",
            json=payload,
        )
        return _sanitize_pix_authorization(response.json())

    def get_pix_authorization(
        self,
        authorization_id: str,
    ) -> AsaasPixAuthorization:
        normalized = _required_id(authorization_id, "pix_authorization_id")
        response = self.http_client.get(
            f"/pix/automatic/authorizations/{normalized}"
        )
        return _sanitize_pix_authorization(response.json())

    def create_recurring_card_checkout(
        self,
        *,
        customer_id: str,
        external_reference: str,
        item_name: str,
        quantity: int,
        value: Any,
        next_due_date: str,
        end_date: str,
        callback_url: str,
        split: Optional[list] = None,
    ) -> AsaasRecurringCheckout:
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise AsaasValidationError(["quantity_invalid"])
        normalized_name = str(item_name or "").strip()
        if not normalized_name or len(normalized_name) > 100:
            raise AsaasValidationError(["item_name_invalid"])
        normalized_callback = str(callback_url or "").strip()
        parsed_callback = urlparse(normalized_callback)
        if (
            parsed_callback.scheme != "https"
            or not parsed_callback.hostname
            or parsed_callback.username is not None
            or parsed_callback.password is not None
            or parsed_callback.query
            or parsed_callback.fragment
        ):
            raise AsaasValidationError(["callback_url_invalid"])
        payload = {
            "billingTypes": ["CREDIT_CARD"],
            "chargeTypes": ["RECURRENT"],
            "minutesToExpire": 60,
            "externalReference": _required_reference(
                external_reference,
                max_length=200,
            ),
            "customer": _required_id(customer_id, "customer_id"),
            "callback": {
                "successUrl": f"{normalized_callback}?resultado=sucesso",
                "cancelUrl": f"{normalized_callback}?resultado=cancelado",
                "expiredUrl": f"{normalized_callback}?resultado=expirado",
            },
            "items": [
                {
                    "name": normalized_name,
                    "quantity": quantity,
                    "value": _money(value, "value"),
                }
            ],
            "subscription": {
                "cycle": "MONTHLY",
                "nextDueDate": _checkout_datetime(
                    next_due_date,
                    "next_due_date",
                ),
                "endDate": _checkout_datetime(end_date, "end_date"),
            },
        }
        if split:
            payload["split"] = _normalize_split(
                split,
                error_code="checkout_split_invalid",
            )
        response = self.http_client.post("/checkouts", json=payload)
        return _sanitize_checkout(response.json())

    def get_checkout(self, checkout_id: str) -> AsaasRecurringCheckout:
        _required_id(checkout_id, "checkout_id")
        # O contrato publico nao disponibiliza consulta de Checkout por ID.
        # Sem resposta do POST original ou webhook CHECKOUT_PAID, qualquer
        # status/link seria uma inferencia insegura.
        raise AsaasIntegrationError("checkout_status_unavailable")
