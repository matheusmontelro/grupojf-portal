"""Cadastro administrativo, isolado do runtime, de recebedores Asaas por ambiente.

Esta unidade nao e um provider de vendas: nao consulta ``users.asaas_*``, nao
altera o runtime e nao exibe cifras.  A escrita e propositalmente limitada ao
novo cadastro e precisa de uma transacao administrativa escolhida pelo operador.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import re
from typing import Literal, Protocol

import psycopg2
from psycopg2.extras import RealDictCursor

SANDBOX = "sandbox"
TARGET_UNITS: dict[int, str] = {
    **{user_id: "Nova Iguaçu 1" for user_id in (27, 44, 47, 48, 55, 96, 118, 123, 125, 134)},
    **{user_id: "São João de Meriti" for user_id in (45, 54, 122, 127, 130)},
    **{user_id: "Vilar dos Teles" for user_id in (107, 120, 132, 133)},
}
_REMOTE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


class ReceiverEnvironmentLinkError(RuntimeError):
    """Erro publico estavel; nunca inclui conta, wallet, documento ou cifra."""


@dataclass(frozen=True, repr=False)
class ReceiverEnvironmentLink:
    user_id: int
    unidade: str
    environment: str
    account_id: str
    wallet_id: str
    credential_ciphertext: str | None = field(repr=False)
    credential_state: Literal["verified", "pending"]
    cpf_digest: str = field(default="", repr=False)

    def __repr__(self) -> str:
        return ("ReceiverEnvironmentLink(user_id=%r, unidade=%r, environment=%r, "
                "credential_state=%r)" % (self.user_id, self.unidade, self.environment, self.credential_state))


class LinkStore(Protocol):
    def transaction(self): ...
    def lock_user(self, user_id: int) -> Mapping[str, object] | None: ...
    def lock_link(self, user_id: int, unidade: str, environment: str) -> ReceiverEnvironmentLink | None: ...
    def insert(self, item: ReceiverEnvironmentLink) -> None: ...
    def promote_pending(self, current: ReceiverEnvironmentLink, desired: ReceiverEnvironmentLink) -> bool: ...


NI_PENDING_USER_IDS = (27, 44, 47, 48, 55, 96, 118, 123, 125)


def execute_pending_verification(
    entries: Iterable[ReceiverEnvironmentLink], *, store: LinkStore, execute: bool,
    confirmed_admin_database: bool,
    refresh: Callable[[tuple[int, ...]], Iterable[ReceiverEnvironmentLink]],
    credential_matches: Callable[[str, str], bool] | None = None,
) -> Literal["verified", "no_op"]:
    """Promove exclusivamente o lote NI pending após prova remota atual.

    A prova remota é concluída antes da transação. Qualquer diferença local,
    corrida CAS ou resultado remoto incompleto faz rollback integral.
    """
    allowed = NI_PENDING_USER_IDS
    desired = tuple(entries)
    if not execute or not confirmed_admin_database:
        raise ReceiverEnvironmentLinkError("execution_not_confirmed")
    _validate_lot(desired, allowed)
    if any(item.credential_state != "verified" for item in desired):
        raise ReceiverEnvironmentLinkError("credential_state_invalid")
    refreshed = tuple(refresh(allowed))
    _validate_lot(refreshed, allowed)
    if (any(item.credential_state != "verified" for item in refreshed)
            or tuple(_identity(item) for item in desired) != tuple(_identity(item) for item in refreshed)):
        raise ReceiverEnvironmentLinkError("execution_refresh_invalid")
    matcher = credential_matches or _same_credential_plaintext
    promoted = False
    with store.transaction():
        for item in refreshed:
            user = store.lock_user(item.user_id)
            if not _matches_target_user(user, item):
                raise ReceiverEnvironmentLinkError("target_missing")
            current = store.lock_link(item.user_id, item.unidade, item.environment)
            if current is None:
                raise ReceiverEnvironmentLinkError("pending_link_missing")
            if _same_link(current, item, matcher):
                continue
            if not _pending_matches(current, item):
                raise ReceiverEnvironmentLinkError("pending_link_conflict")
            if not store.promote_pending(current, item):
                raise ReceiverEnvironmentLinkError("pending_link_conflict")
            promoted = True
    return "verified" if promoted else "no_op"


def execute_import(entries: Iterable[ReceiverEnvironmentLink], *, store: LinkStore, execute: bool,
                   confirmed_admin_database: bool, allowed_user_ids: Iterable[int],
                   refresh: Callable[[tuple[int, ...]], Iterable[ReceiverEnvironmentLink]],
                   credential_matches: Callable[[str, str], bool] | None = None) -> Literal["imported", "no_op"]:
    """Persiste o lote revalidado ou falha antes de substituir qualquer vínculo.

    ``refresh`` deve realizar a prova remota imediatamente antes da escrita. A
    igualdade de cifras e deliberadamente por plaintext, pois Fernet gera um
    token novo a cada cifra.
    """
    items, allowed = tuple(entries), tuple(allowed_user_ids)
    if not execute or not confirmed_admin_database:
        raise ReceiverEnvironmentLinkError("execution_not_confirmed")
    _validate_lot(items, allowed)
    refreshed = tuple(refresh(allowed))
    _validate_lot(refreshed, allowed)
    if tuple(_identity(item) for item in items) != tuple(_identity(item) for item in refreshed):
        raise ReceiverEnvironmentLinkError("execution_refresh_invalid")
    matcher = credential_matches or _same_credential_plaintext
    inserted = False
    with store.transaction():
        for item in refreshed:
            user = store.lock_user(item.user_id)
            if not _matches_target_user(user, item):
                raise ReceiverEnvironmentLinkError("target_missing")
            current = store.lock_link(item.user_id, item.unidade, item.environment)
            if current is None:
                store.insert(item)
                inserted = True
            elif not _same_link(current, item, matcher):
                raise ReceiverEnvironmentLinkError("existing_link_conflict")
    return "imported" if inserted else "no_op"


def _validate_lot(items: tuple[ReceiverEnvironmentLink, ...], allowed: tuple[int, ...]) -> None:
    if (not items or not allowed or len(set(allowed)) != len(allowed)
            or any(type(value) is not int or value <= 0 for value in allowed)
            or {item.user_id for item in items} != set(allowed) or len({item.user_id for item in items}) != len(items)):
        raise ReceiverEnvironmentLinkError("execution_allowlist_invalid")
    for item in items:
        if (type(item.user_id) is not int or TARGET_UNITS.get(item.user_id) != item.unidade
                or item.environment != SANDBOX or not _valid_remote_id(item.account_id)
                or not _valid_remote_id(item.wallet_id) or not re.fullmatch(r"[0-9a-f]{64}", item.cpf_digest)):
            raise ReceiverEnvironmentLinkError("link_scope_invalid")
        if item.credential_state == "verified":
            if not isinstance(item.credential_ciphertext, str) or not item.credential_ciphertext:
                raise ReceiverEnvironmentLinkError("credential_invalid")
        elif item.credential_state == "pending":
            if item.credential_ciphertext is not None:
                raise ReceiverEnvironmentLinkError("credential_invalid")
        else:
            raise ReceiverEnvironmentLinkError("credential_state_invalid")


def _identity(item: ReceiverEnvironmentLink) -> tuple[object, ...]:
    return (item.user_id, item.unidade, item.environment, item.account_id, item.wallet_id,
            item.credential_state, item.cpf_digest)


def _same_link(current: ReceiverEnvironmentLink, desired: ReceiverEnvironmentLink,
               matcher: Callable[[str, str], bool]) -> bool:
    if (current.user_id, current.unidade, current.environment, current.account_id, current.wallet_id,
            current.credential_state) != (desired.user_id, desired.unidade, desired.environment,
                                           desired.account_id, desired.wallet_id, desired.credential_state):
        return False
    if current.credential_state == "pending":
        return current.credential_ciphertext is None and desired.credential_ciphertext is None
    if not isinstance(current.credential_ciphertext, str) or not isinstance(desired.credential_ciphertext, str):
        return False
    try:
        return matcher(current.credential_ciphertext, desired.credential_ciphertext)
    except Exception:
        return False


def _pending_matches(current: ReceiverEnvironmentLink, desired: ReceiverEnvironmentLink) -> bool:
    return (
        current.credential_state == "pending"
        and current.credential_ciphertext is None
        and desired.credential_state == "verified"
        and isinstance(desired.credential_ciphertext, str)
        and bool(desired.credential_ciphertext)
        # The new table intentionally does not persist CPF material.  The
        # locked users row above proves its current digest before this CAS.
        and (current.user_id, current.unidade, current.environment,
             current.account_id, current.wallet_id)
        == (desired.user_id, desired.unidade, desired.environment,
            desired.account_id, desired.wallet_id)
    )
def _same_credential_plaintext(current: str, desired: str) -> bool:
    from app.security.asaas_account_secret import decrypt_api_key
    return decrypt_api_key(current) == decrypt_api_key(desired)


def _valid_remote_id(value: object) -> bool:
    return isinstance(value, str) and bool(_REMOTE_ID.fullmatch(value))


def _matches_target_user(user: Mapping[str, object] | None, item: ReceiverEnvironmentLink) -> bool:
    """Checks the mutable local target again while holding its row lock."""
    return bool(user and user.get("id") == item.user_id and user.get("unidade") == item.unidade
                and user.get("cargo_id") in (3, 4) and user.get("status_aprovacao") == "aprovado"
                and isinstance(user.get("cpf"), str) and cpf_digest(user["cpf"]) == item.cpf_digest)


def cpf_digest(cpf: str) -> str:
    """Keeps only an ephemeral comparison fingerprint outside the new table."""
    return hashlib.sha256(cpf.encode("ascii")).hexdigest()


class PostgresLinkStore:
    """Store administrativo novo; nao importa ``db.py`` nem atualiza ``users``."""
    def __init__(self, config: Mapping[str, str]) -> None:
        required = ("host", "port", "dbname", "user", "password")
        if any(not isinstance(config.get(key), str) or not config[key].strip() for key in required):
            raise ReceiverEnvironmentLinkError("admin_database_config_invalid")
        self._config = {key: config[key].strip() for key in required}
        self._config.update({"connect_timeout": "10", "options": "-c lock_timeout=5000 -c statement_timeout=30000"})
        self._connection = self._cursor = None

    @contextmanager
    def transaction(self):
        try:
            self._connection = psycopg2.connect(**self._config)
            self._connection.autocommit = False
            self._cursor = self._connection.cursor(cursor_factory=RealDictCursor)
            self._cursor.execute("SET LOCAL search_path TO pg_catalog, public")
            yield self
            self._connection.commit()
        except ReceiverEnvironmentLinkError:
            self._rollback()
            raise
        except Exception:
            self._rollback()
            raise ReceiverEnvironmentLinkError("database_operation_failed") from None
        finally:
            if self._cursor is not None:
                self._cursor.close()
            if self._connection is not None:
                self._connection.close()
            self._connection = self._cursor = None

    def _rollback(self) -> None:
        if self._connection is not None:
            self._connection.rollback()

    def lock_user(self, user_id: int) -> Mapping[str, object] | None:
        self._cursor.execute("""SELECT id, unidade, cargo_id, status_aprovacao,
            REGEXP_REPLACE(COALESCE(cpf,''), '[^0-9]', '', 'g') AS cpf
            FROM public.users WHERE id=%s FOR UPDATE""", (user_id,))
        return self._cursor.fetchone()

    def lock_link(self, user_id: int, unidade: str, environment: str) -> ReceiverEnvironmentLink | None:
        self._cursor.execute("""SELECT user_id, unidade, environment, account_id, wallet_id,
            credential_ciphertext, credential_state FROM public.asaas_receiver_environment_links
            WHERE user_id=%s AND unidade=%s AND environment=%s FOR UPDATE""", (user_id, unidade, environment))
        row = self._cursor.fetchone()
        return ReceiverEnvironmentLink(**row) if row else None

    def insert(self, item: ReceiverEnvironmentLink) -> None:
        self._cursor.execute("""INSERT INTO public.asaas_receiver_environment_links
            (user_id, unidade, environment, account_id, wallet_id, credential_ciphertext, credential_state)
            VALUES (%s,%s,%s,%s,%s,%s,%s)""", (item.user_id, item.unidade, item.environment, item.account_id,
                                                  item.wallet_id, item.credential_ciphertext, item.credential_state))

    def promote_pending(self, current: ReceiverEnvironmentLink, desired: ReceiverEnvironmentLink) -> bool:
        self._cursor.execute("""UPDATE public.asaas_receiver_environment_links
            SET credential_ciphertext=%s, credential_state='verified'
            WHERE user_id=%s AND unidade=%s AND environment='sandbox'
              AND account_id=%s AND wallet_id=%s AND credential_state='pending'
              AND credential_ciphertext IS NULL
            RETURNING user_id""", (
                desired.credential_ciphertext, current.user_id, current.unidade,
                current.account_id, current.wallet_id,
            ))
        return self._cursor.fetchone() is not None
