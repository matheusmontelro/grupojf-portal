"""Provisionamento administrativo, único e fail-closed da Karen (id 63)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
import re
from typing import Any, Callable, Mapping
from uuid import uuid4
from psycopg2.extras import RealDictCursor

from app.asaas_sdk.environment import Environment
from app.asaas_sdk.http_client import AsaasHttpClient
from app.asaas_sales_sdk.account_manager import prepare_account_payload
from app.security.asaas_account_secret import encrypt_api_key
from app.services.asaas_sale_database import DatabaseConnection

TARGET_USER_ID = 63
TARGET_UNIT = "Nova Iguaçu 1"
TARGET_ENVIRONMENT = "production"
TARGET_WALLET_ENV = "ASAAS_WALLET_ID_NOVA_IGUACU_1"
TARGET_KEY_ENV = "ASAAS_PRODUCTION_API_KEY_NOVA_IGUACU_1"


class KarenProductionProvisionError(RuntimeError):
    """Erro seguro: não inclui PII, documentos ou segredos."""


@dataclass(frozen=True)
class KarenProvisionResult:
    code: str
    account_id: str | None = None
    wallet_id: str | None = None


def parse_income(value: str) -> Decimal:
    try:
        income = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise KarenProductionProvisionError("income_invalid") from exc
    if not income.is_finite() or income <= 0 or income.as_tuple().exponent < -2:
        raise KarenProductionProvisionError("income_invalid")
    return income.quantize(Decimal("0.01"))


def check_only(*, income: Decimal) -> KarenProvisionResult:
    """Valida o alvo sob lock, sem escrita nem chamada HTTP."""
    with DatabaseConnection(read_only=True) as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        state = _attempt_state(cursor)
        if state == "confirmed":
            _confirmed_target(cursor)
            return KarenProvisionResult("confirmed")
        if state is not None:
            raise KarenProductionProvisionError("attempt_already_active")
        user = _target(cursor, lock=False)
        prepare_account_payload(_payload(user, income))
    return KarenProvisionResult("check_ok")


def execute(
    *,
    income: Decimal,
    receipt_dir: Path,
    parent_wallet_id: str,
    parent_api_key: str,
    http_client_factory: Callable[..., AsaasHttpClient] = AsaasHttpClient,
) -> KarenProvisionResult:
    """Executa uma única criação remota depois de todos os gates duráveis."""
    if not parent_wallet_id or not parent_api_key:
        raise KarenProductionProvisionError("parent_configuration_invalid")
    _validate_receipt_dir(receipt_dir)
    # Valida a disponibilidade da Fernet sem usar uma credencial real.
    encrypt_api_key("preflight")
    # Primeiro as verificacoes remotas sem qualquer tentativa duravel: uma
    # configuracao/CPF invalida nao pode consumir o unico POST permitido.
    with DatabaseConnection(read_only=True) as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        state = _attempt_state(cursor)
        if state == "confirmed":
            _confirmed_target(cursor)
            return KarenProvisionResult("confirmed")
        if state is not None:
            raise KarenProductionProvisionError("attempt_already_active")
        user = _target(cursor, lock=False)
        payload = prepare_account_payload(_payload(user, income))
    client = http_client_factory(
        base_url=Environment.PRODUCTION.value,
        headers={"Content-Type": "application/json", "Accept": "application/json", "access_token": parent_api_key},
    )
    try:
        _validate_parent(client, parent_wallet_id)
        checked_cpf = user["cpf"]
        _validate_absent_cpf(client, checked_cpf)
    except Exception:
        _close_safely(client)
        return KarenProvisionResult("remote_precheck_failed")
    with DatabaseConnection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        state = _attempt_state(cursor)
        if state == "confirmed":
            _confirmed_target(cursor)
            _close_safely(client)
            return KarenProvisionResult("confirmed")
        if state is not None:
            _close_safely(client)
            raise KarenProductionProvisionError("attempt_already_active")
        user = _target(cursor, lock=True)
        if user["cpf"] != checked_cpf:
            _close_safely(client)
            raise KarenProductionProvisionError("target_cpf_changed")
        payload = prepare_account_payload(_payload(user, income))
        token = str(uuid4())
        cursor.execute(
            """INSERT INTO asaas_account_provision_attempts
                (user_id, unidade, environment, attempt_token, lifecycle_state, remote_attempt_count)
                VALUES (%s, %s, %s, %s, 'reserved', 0) RETURNING id""",
            (TARGET_USER_ID, TARGET_UNIT, TARGET_ENVIRONMENT, token),
        )
        if cursor.fetchone() is None:
            raise KarenProductionProvisionError("attempt_reservation_failed")
        cursor.execute(
            """UPDATE asaas_account_provision_attempts SET lifecycle_state='started',
                remote_attempt_count=1, remote_started_at=NOW(), updated_at=NOW()
                WHERE user_id=%s AND environment=%s AND attempt_token=%s
                AND lifecycle_state='reserved' RETURNING id""",
            (TARGET_USER_ID, TARGET_ENVIRONMENT, token),
        )
        if cursor.fetchone() is None:
            raise KarenProductionProvisionError("attempt_start_failed")

    try:
        response = client.post("/accounts", json=payload)
        if not 200 <= response.status_code < 300:
            raise KarenProductionProvisionError("provider_response_invalid")
        created = response.json()
    except Exception:
        _uncertain(token, "provider_result_uncertain")
        return KarenProvisionResult("provider_result_uncertain")
    finally:
        _close_safely(client)

    api_key = created.get("apiKey") if isinstance(created, Mapping) else None
    if not isinstance(api_key, str) or not api_key:
        _uncertain(token, "provider_response_invalid")
        return KarenProvisionResult("provider_response_invalid")
    try:
        encrypted = encrypt_api_key(api_key)
        _write_escrow(receipt_dir, token, encrypted)
    except Exception:
        _uncertain(token, "provider_result_uncertain")
        return KarenProvisionResult("provider_result_uncertain")
    account_id, wallet_id = created.get("id"), created.get("walletId")
    if not all(_valid_remote_id(value) for value in (account_id, wallet_id)):
        _uncertain(token, "provider_response_invalid")
        return KarenProvisionResult("provider_response_invalid")
    with DatabaseConnection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        confirmed_user = _target(cursor, lock=True)
        if confirmed_user["cpf"] != checked_cpf:
            raise KarenProductionProvisionError("confirmation_target_changed")
        cursor.execute(
            """UPDATE users SET asaas_wallet_id=%s, asaas_account_id=%s,
                asaas_account_api_key_enc=%s, asaas_integration_status='integrado',
                asaas_account_updated_at=NOW() WHERE id=%s AND unidade=%s
                AND cargo_id=3 AND status_aprovacao='aprovado'
                AND asaas_wallet_id IS NULL AND asaas_account_id IS NULL
                AND asaas_account_api_key_enc IS NULL RETURNING id""",
            (wallet_id, account_id, encrypted, TARGET_USER_ID, TARGET_UNIT),
        )
        if cursor.fetchone() is None:
            raise KarenProductionProvisionError("confirmation_target_changed")
        cursor.execute(
            """UPDATE asaas_account_provision_attempts SET lifecycle_state='confirmed',
                remote_confirmed_at=NOW(), updated_at=NOW(), last_error_code=NULL
                WHERE user_id=%s AND environment=%s AND attempt_token=%s
                AND lifecycle_state='started' RETURNING id""",
            (TARGET_USER_ID, TARGET_ENVIRONMENT, token),
        )
        if cursor.fetchone() is None:
            raise KarenProductionProvisionError("confirmation_attempt_changed")
    return KarenProvisionResult("confirmed", account_id, wallet_id)


def _target(cursor: Any, *, lock: bool) -> Mapping[str, str]:
    cursor.execute(
        """SELECT id, unidade, cargo_id, status_aprovacao,
            REGEXP_REPLACE(COALESCE(cpf,''), '[^0-9]', '', 'g') AS cpf, nome, email,
            phone_country_code, phone_area_code, phone_number, street, street_number,
            neighborhood, zip_code, birthdate, asaas_wallet_id, asaas_account_id,
            asaas_account_api_key_enc
            FROM users WHERE id=%s AND unidade=%s AND cargo_id=3
            AND status_aprovacao='aprovado'""" + (" FOR UPDATE" if lock else ""),
        (TARGET_USER_ID, TARGET_UNIT),
    )
    row = cursor.fetchone()
    if not isinstance(row, Mapping) or len(str(row.get("cpf", ""))) != 11:
        raise KarenProductionProvisionError("target_invalid")
    if (row.get("asaas_wallet_id") or row.get("asaas_account_id")
            or row.get("asaas_account_api_key_enc")):
        raise KarenProductionProvisionError("target_already_integrated")
    cursor.execute("SELECT id FROM users WHERE REGEXP_REPLACE(COALESCE(cpf,''), '[^0-9]', '', 'g')=%s AND id<>%s LIMIT 1", (row["cpf"], TARGET_USER_ID))
    if cursor.fetchone() is not None:
        raise KarenProductionProvisionError("target_cpf_not_unique")
    return row


def _attempt_state(cursor: Any) -> str | None:
    cursor.execute("SELECT lifecycle_state FROM asaas_account_provision_attempts WHERE user_id=%s AND environment=%s AND lifecycle_state<>'rejected' LIMIT 1", (TARGET_USER_ID, TARGET_ENVIRONMENT))
    row = cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, Mapping):
        state = row.get("lifecycle_state")
    else:
        state = row[0]
    return state if isinstance(state, str) else "invalid"


def _confirmed_target(cursor: Any) -> None:
    cursor.execute(
        """SELECT asaas_wallet_id, asaas_account_id, asaas_account_api_key_enc
            FROM users WHERE id=%s AND unidade=%s AND cargo_id=3
            AND status_aprovacao='aprovado' AND asaas_integration_status='integrado'""",
        (TARGET_USER_ID, TARGET_UNIT),
    )
    row = cursor.fetchone()
    if not isinstance(row, Mapping) or not all((
        _valid_remote_id(row.get("asaas_wallet_id")),
        _valid_remote_id(row.get("asaas_account_id")),
        isinstance(row.get("asaas_account_api_key_enc"), str)
        and bool(row["asaas_account_api_key_enc"]),
    )):
        raise KarenProductionProvisionError("confirmed_target_inconsistent")


def _close_safely(client: AsaasHttpClient) -> None:
    try:
        client.close()
    except Exception:
        pass


def _response_json(response: Any) -> Mapping[str, Any]:
    if not 200 <= response.status_code < 300:
        raise KarenProductionProvisionError("remote_precheck_invalid")
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise KarenProductionProvisionError("remote_precheck_invalid")
    return payload


def _validate_parent(client: AsaasHttpClient, wallet_id: str) -> None:
    status = _response_json(client.get("/myAccount/status/"))
    commercial = _response_json(client.get("/myAccount/commercialInfo/"))
    wallets = _response_json(client.get("/wallets/", params={"limit": 100, "offset": 0}))
    if (not isinstance(status, Mapping) or status.get("general") != "APPROVED"
            or status.get("commercialInfo") != "APPROVED"
            or not _valid_remote_id(status.get("id"))):
        raise KarenProductionProvisionError("parent_not_approved")
    expiration = commercial.get("commercialInfoExpiration")
    if ("commercialInfoExpiration" not in commercial
            or commercial.get("status") != "APPROVED"
            or commercial.get("personType") != "JURIDICA"
            or (expiration is not None and
                (not isinstance(expiration, Mapping) or expiration.get("isExpired") is not False))):
        raise KarenProductionProvisionError("parent_commercial_expired")
    data = wallets.get("data")
    if (wallets.get("object") != "list" or wallets.get("hasMore") is not False
            or wallets.get("offset") != 0 or not isinstance(data, list)
            or wallets.get("totalCount") != len(data)
            or sum(1 for item in data if isinstance(item, Mapping) and item.get("id") == wallet_id) != 1):
        raise KarenProductionProvisionError("parent_wallet_invalid")


def _validate_absent_cpf(client: AsaasHttpClient, cpf: str) -> None:
    accounts = _response_json(client.get("/accounts", params={"cpfCnpj": cpf, "limit": 100, "offset": 0}))
    data = accounts.get("data")
    if (accounts.get("object") != "list" or accounts.get("hasMore") is not False
            or accounts.get("offset") != 0 or not isinstance(data, list)
            or accounts.get("totalCount") != len(data) or data):
        raise KarenProductionProvisionError("remote_cpf_not_absent")


def _valid_remote_id(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value))


def _validate_receipt_dir(directory: Path) -> None:
    if not directory.is_dir() or (directory.stat().st_mode & 0o077):
        raise KarenProductionProvisionError("receipt_dir_invalid")


def _payload(user: Mapping[str, Any], income: Decimal) -> dict[str, Any]:
    return {"name": user["nome"], "email": user["email"], "cpfCnpj": user["cpf"], "mobilePhone": f"{user['phone_country_code']}{user['phone_area_code']}{user['phone_number']}", "incomeValue": income, "address": user["street"], "addressNumber": user["street_number"], "province": user["neighborhood"], "postalCode": user["zip_code"], "birthDate": str(user["birthdate"])}


def _uncertain(token: str, code: str) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE asaas_account_provision_attempts SET lifecycle_state='uncertain', last_error_code=%s, remote_uncertain_at=NOW(), updated_at=NOW() WHERE user_id=%s AND environment=%s AND attempt_token=%s AND lifecycle_state='started'", (code, TARGET_USER_ID, TARGET_ENVIRONMENT, token))


def _write_escrow(directory: Path, token: str, encrypted: str) -> None:
    if not directory.is_dir() or (directory.stat().st_mode & 0o077):
        raise KarenProductionProvisionError("receipt_dir_invalid")
    path = directory / f"asaas-karen-production-{token}.receipt"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        data = encrypted.encode("utf-8")
        offset = 0
        while offset < len(data):
            written = os.write(descriptor, data[offset:])
            if written <= 0:
                raise OSError("escrow_write_incomplete")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
