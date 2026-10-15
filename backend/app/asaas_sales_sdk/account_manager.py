"""Gerenciamento isolado de subcontas Asaas (PF) para o fluxo de vendas.

Cuida da criacao, listagem e consulta de subcontas via ``POST/GET /accounts``.
A ``base_url`` do ``AsaasHttpClient`` ja inclui ``/v3`` (ver
``app/asaas_sdk/environment.py``), portanto os endpoints sao referenciados sem
o prefixo de versao.

Seguranca:
  * O payload de criacao e restrito a uma whitelist estrita de campos; nenhum
    campo fora dela atravessa para o Asaas.
  * Qualquer URL remota retornada (``invoiceUrl``/``callback``) deve apontar
    para o host Sandbox; do contrario a resposta e rejeitada.
  * A ``apiKey`` retornada pelo Asaas NUNCA e logada aqui. Ela trafega apenas
    no dict devolvido a quem chamou, para ser imediatamente cifrada e
    persistida pelo servico de provisioning.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.parse import urlparse

from app.asaas_sdk.exceptions import AsaasAPIError, AsaasValidationError
from app.asaas_sdk.http_client import AsaasHttpClient


_ACCOUNT_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
_CPF_CNPJ = re.compile(r"^\d{11}$|^\d{14}$")
_NON_DIGIT = re.compile(r"\D")
_EMAIL = re.compile(r"^[^@\s]{1,254}@[^@\s]{1,254}\.[^@\s]{2,254}$")
_MOBILE_PHONE = re.compile(r"^\+?\d{10,15}$")
_POSTAL_CODE = re.compile(r"^\d{5,9}$|^\d{5}-\d{3}$")
_BIRTH_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SANDBOX_HOSTS = frozenset({"sandbox.asaas.com"})
_ACCOUNT_PAYLOAD_FIELDS = frozenset(
    {
        "name",
        "email",
        "cpfCnpj",
        "mobilePhone",
        "incomeValue",
        "address",
        "addressNumber",
        "province",
        "postalCode",
        "birthDate",
        "complement",
    }
)
_LIST_LIMIT_MAX = 100


def _invalid(detail: str = "invalid_account_response") -> None:
    raise AsaasAPIError(status_code=502, response_body=None, detail=detail)


def _required_str(value: Any, *, name: str, max_length: int = 200) -> str:
    if not isinstance(value, str):
        raise AsaasValidationError([f"account_{name}_invalid"])
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise AsaasValidationError([f"account_{name}_invalid"])
    return normalized


def _optional_str(value: Any, *, name: str, max_length: int = 200) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AsaasValidationError([f"account_{name}_invalid"])
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise AsaasValidationError([f"account_{name}_invalid"])
    return normalized


def _cpf_cnpj(value: Any) -> str:
    if not isinstance(value, str):
        raise AsaasValidationError(["account_cpf_cnpj_invalid"])
    digits = _NON_DIGIT.sub("", value)
    if not _CPF_CNPJ.fullmatch(digits):
        raise AsaasValidationError(["account_cpf_cnpj_invalid"])
    return digits


def _email(value: Any) -> str:
    normalized = _required_str(value, name="email", max_length=254)
    if not _EMAIL.fullmatch(normalized):
        raise AsaasValidationError(["account_email_invalid"])
    return normalized


def _mobile_phone(value: Any) -> str:
    normalized = _required_str(value, name="mobile_phone", max_length=20)
    cleaned = normalized.removeprefix("+")
    if not _MOBILE_PHONE.fullmatch(f"+{cleaned}") or not cleaned.isdigit():
        raise AsaasValidationError(["account_mobile_phone_invalid"])
    return cleaned


def _postal_code(value: Any) -> str:
    normalized = _required_str(value, name="postal_code", max_length=9)
    if not _POSTAL_CODE.fullmatch(normalized):
        raise AsaasValidationError(["account_postal_code_invalid"])
    return normalized


def _birth_date(value: Any) -> str:
    if not isinstance(value, str) or not _BIRTH_DATE.fullmatch(value.strip()):
        raise AsaasValidationError(["account_birth_date_invalid"])
    try:
        date.fromisoformat(value)
    except ValueError:
        raise AsaasValidationError(["account_birth_date_invalid"]) from None
    return value


def _income_value(value: Any) -> float:
    if isinstance(value, bool):
        raise AsaasValidationError(["account_income_value_invalid"])
    try:
        normalized = Decimal(str(value))
        quantized = normalized.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise AsaasValidationError(["account_income_value_invalid"]) from None
    if (
        not normalized.is_finite()
        or not quantized.is_finite()
        or normalized != quantized
        or normalized <= 0
        or normalized > 9_999_999_999.99
    ):
        raise AsaasValidationError(["account_income_value_invalid"])
    return float(quantized)


def prepare_account_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Aplica whitelist estrita e valida cada campo antes do envio ao Asaas."""
    if not isinstance(payload, Mapping):
        raise AsaasValidationError(["account_payload_invalid"])
    if any(not isinstance(key, str) for key in payload):
        raise AsaasValidationError(["account_payload_invalid"])
    if set(payload) - _ACCOUNT_PAYLOAD_FIELDS:
        raise AsaasValidationError(["account_payload_invalid"])

    normalized: dict[str, Any] = {
        "name": _required_str(payload.get("name"), name="name", max_length=120),
        "email": _email(payload.get("email")),
        "cpfCnpj": _cpf_cnpj(payload.get("cpfCnpj")),
        "mobilePhone": _mobile_phone(payload.get("mobilePhone")),
        "incomeValue": _income_value(payload.get("incomeValue")),
        "address": _required_str(
            payload.get("address"), name="address", max_length=150
        ),
        "addressNumber": _required_str(
            payload.get("addressNumber"), name="address_number", max_length=20
        ),
        "province": _required_str(
            payload.get("province"), name="province", max_length=150
        ),
        "postalCode": _postal_code(payload.get("postalCode")),
        "birthDate": _birth_date(payload.get("birthDate")),
    }

    complement = _optional_str(
        payload.get("complement"), name="complement", max_length=200
    )
    if complement is not None:
        normalized["complement"] = complement
    return normalized


def _sandbox_url(value: Any) -> str | None:
    """Valida que uma URL retornada pelo Asaas aponta apenas para o Sandbox."""
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    parsed = urlparse(normalized)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _SANDBOX_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        _invalid("invalid_account_url")
    return normalized


def _sanitize_created_account(payload: Any) -> dict[str, Any]:
    """Recorta apenas os identificadores seguros da subconta recem-criada.

    A ``apiKey`` retorna no dict para que o servico de provisioning a cifre e
    persista imediatamente; ela nao deve ser logada em nenhum ponto.
    """
    if not isinstance(payload, Mapping):
        _invalid()
    account_id = str(payload.get("id") or "").strip()
    wallet_id = str(payload.get("walletId") or "").strip()
    api_key = payload.get("apiKey")
    if not _ACCOUNT_ID.fullmatch(account_id):
        _invalid("invalid_account_id")
    if not _ACCOUNT_ID.fullmatch(wallet_id):
        _invalid("invalid_account_wallet_id")
    if not isinstance(api_key, str) or not api_key.strip() or len(api_key) > 512:
        _invalid("invalid_account_api_key")
    api_key = api_key.strip()
    result: dict[str, Any] = {
        "id": account_id,
        "walletId": wallet_id,
        "apiKey": api_key,
    }
    invoice_url = _sandbox_url(payload.get("invoiceUrl"))
    if invoice_url is not None:
        result["invoiceUrl"] = invoice_url
    callback = _sandbox_url(payload.get("callback"))
    if callback is not None:
        result["callback"] = callback
    return result


def _sanitize_account_summary(payload: Any) -> dict[str, Any]:
    """Recorte de leitura de uma subconta, sem apiKey nem dados pessoais."""
    if not isinstance(payload, Mapping):
        _invalid()
    account_id = str(payload.get("id") or "").strip()
    if not _ACCOUNT_ID.fullmatch(account_id):
        _invalid("invalid_account_id")
    result: dict[str, Any] = {"id": account_id}
    wallet_id = payload.get("walletId")
    if wallet_id is not None:
        normalized_wallet = str(wallet_id).strip()
        if normalized_wallet and _ACCOUNT_ID.fullmatch(normalized_wallet):
            result["walletId"] = normalized_wallet
    status = payload.get("status")
    if isinstance(status, str):
        normalized_status = status.strip()
        if normalized_status and len(normalized_status) <= 50:
            result["status"] = normalized_status
    return result


class AsaasSalesAccountManager:
    """Cria e consulta subcontas PF apenas no Sandbox."""

    def __init__(self, http_client: AsaasHttpClient):
        self._http_client = http_client

    @staticmethod
    def prepare_account_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        """Valida o payload localmente, sem qualquer chamada ao provedor."""
        return prepare_account_payload(payload)

    def create_account(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Cria uma subconta via ``POST /accounts`` e devolve identificadores."""
        normalized = prepare_account_payload(payload)
        response = self._http_client.post("/accounts", json=normalized)
        return _sanitize_created_account(response.json())

    def list_accounts(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """Lista subcontas via ``GET /accounts`` com paginacao defensiva."""
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= _LIST_LIMIT_MAX
        ):
            raise AsaasValidationError(["account_list_limit_invalid"])
        if (
            isinstance(offset, bool)
            or not isinstance(offset, int)
            or offset < 0
        ):
            raise AsaasValidationError(["account_list_offset_invalid"])
        response = self._http_client.get(
            "/accounts",
            params={"limit": limit, "offset": offset},
        )
        body = response.json()
        if not isinstance(body, Mapping):
            _invalid()
        raw_data = body.get("data")
        if raw_data is not None and not isinstance(raw_data, list):
            _invalid("invalid_account_list_response")
        total = body.get("totalCount")
        if total is not None and (
            isinstance(total, bool)
            or not isinstance(total, int)
            or total < 0
            or total > 100_000
        ):
            _invalid("invalid_account_list_total")
        result: dict[str, Any] = {
            "data": (
                [_sanitize_account_summary(item) for item in raw_data]
                if isinstance(raw_data, list)
                else []
            )
        }
        if isinstance(total, int):
            result["totalCount"] = total
        return result

    def get_account(self, account_id: str) -> dict[str, Any]:
        """Consulta uma subconta via ``GET /accounts/{account_id}``."""
        normalized = str(account_id or "").strip()
        if not _ACCOUNT_ID.fullmatch(normalized):
            raise AsaasValidationError(["account_id_invalid"])
        response = self._http_client.get(f"/accounts/{normalized}")
        return _sanitize_account_summary(response.json())
