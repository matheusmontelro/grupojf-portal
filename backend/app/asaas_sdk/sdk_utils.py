"""Funcoes utilitarias do SDK do Asaas."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any, Dict, Iterable, List, Optional

from .exceptions import AsaasValidationError


TWOPLACES = Decimal("0.01")
FOURPLACES = Decimal("0.0001")


def _only_digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def cents_to_decimal(amount_cents: int | Decimal | float) -> Decimal:
    if isinstance(amount_cents, Decimal):
        value = amount_cents / Decimal("100")
    else:
        value = Decimal(str(amount_cents)) / Decimal("100")
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def normalize_money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def normalize_percentage(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(FOURPLACES, rounding=ROUND_HALF_UP)


def normalize_billing_type(value: str) -> str:
    raw = (value or "").strip().upper()
    mapping = {
        "BANK_SLIP": "BOLETO",
        "BOLETO": "BOLETO",
        "PIX": "PIX",
        "CREDIT_CARD": "CREDIT_CARD",
        "CARTAO": "CREDIT_CARD",
        "CARTAO_CREDITO": "CREDIT_CARD",
        "UNDEFINED": "UNDEFINED",
        "PIX AVULSO DELTA": "PIX",
        "BOLETO AVULSO DELTA": "BOLETO",
        "CARTAO CREDITO AVULSO DELTA": "CREDIT_CARD",
        "CARTÃO CRÉDITO AVULSO DELTA": "CREDIT_CARD",
    }
    normalized = mapping.get(raw, raw)
    allowed = {"BOLETO", "PIX", "CREDIT_CARD", "UNDEFINED"}
    if normalized not in allowed:
        raise AsaasValidationError([f"billingType invalido: {value}"])
    return normalized


def format_due_date(value: Optional[Any] = None) -> str:
    if value is None:
        return (date.today() + timedelta(days=1)).isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def build_callback(success_url: Optional[str], auto_redirect: bool = False) -> Optional[Dict[str, Any]]:
    if not success_url:
        return None
    payload = {"successUrl": success_url}
    if auto_redirect is not None:
        payload["autoRedirect"] = auto_redirect
    return payload


def build_customer_payload(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "name": customer_data.get("name"),
        "cpfCnpj": _only_digits(customer_data.get("document") or customer_data.get("cpfCnpj")),
        "email": customer_data.get("email"),
        "externalReference": (
            customer_data.get("externalReference")
            or customer_data.get("external_reference")
        ),
    }

    if not payload["name"]:
        raise AsaasValidationError(["name is required"])
    if not payload["cpfCnpj"]:
        raise AsaasValidationError(["document/cpfCnpj is required"])

    if "notificationDisabled" in customer_data:
        notification_disabled = customer_data["notificationDisabled"]
        if not isinstance(notification_disabled, bool):
            raise AsaasValidationError(["notification_disabled_invalid"])
        payload["notificationDisabled"] = notification_disabled

    phone = customer_data.get("phone")
    if isinstance(phone, dict):
        mobile_phone = (
            f"{_only_digits(phone.get('areaCode'))}{_only_digits(phone.get('number'))}"
            if phone.get("areaCode") or phone.get("number")
            else ""
        )
        if mobile_phone:
            payload["mobilePhone"] = mobile_phone
    elif phone:
        payload["mobilePhone"] = _only_digits(phone)

    address = customer_data.get("address") or {}
    if address:
        payload.update(
            {
                "address": address.get("street") or address.get("address"),
                "addressNumber": str(address.get("streetNumber") or address.get("addressNumber") or "S/N"),
                "complement": address.get("complement"),
                "province": address.get("neighborhood") or address.get("province"),
                "postalCode": _only_digits(address.get("zipCode") or address.get("postalCode")),
            }
        )

    return {key: value for key, value in payload.items() if value not in (None, "", {})}


def transform_splits_to_asaas(splits: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    transformed: List[Dict[str, Any]] = []
    if not splits:
        return transformed

    for index, split in enumerate(splits):
        if split.get("absorbBalance"):
            continue

        metadata = split.get("metadata") or {}
        wallet_id = split.get("walletId") or metadata.get("walletId")
        if not wallet_id:
            raise AsaasValidationError(
                [f"Split item {index} precisa de walletId para uso no Asaas"]
            )

        asaas_split: Dict[str, Any] = {"walletId": wallet_id}

        if split.get("fixedValue") is not None:
            asaas_split["fixedValue"] = float(normalize_money(split["fixedValue"]))
        elif split.get("totalFixedValue") is not None:
            asaas_split["totalFixedValue"] = float(normalize_money(split["totalFixedValue"]))
        elif split.get("percentualValue") is not None:
            asaas_split["percentualValue"] = float(normalize_percentage(split["percentualValue"]))
        elif split.get("percentage") is not None:
            asaas_split["percentualValue"] = float(normalize_percentage(split["percentage"]))
        else:
            raise AsaasValidationError(
                [f"Split item {index} precisa de fixedValue, totalFixedValue ou percentage"]
            )

        transformed.append(asaas_split)

    return transformed
