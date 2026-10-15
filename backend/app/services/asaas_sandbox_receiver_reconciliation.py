"""Reconciliação fail-closed de recebedores Asaas, apenas sandbox."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import stat
from typing import Literal, Protocol

from psycopg2.extras import RealDictCursor
from app.asaas_sdk.environment import AsaasConfig, Environment
from app.asaas_sdk.http_client import AsaasHttpClient
from app.security.asaas_account_secret import decrypt_api_key
from app.services.asaas_sale_database import DatabaseConnection
from app.services.asaas_sales_preflight import AsaasSalesPreflightError, is_asaas_sales_pf_user_excluded

SANDBOX_ENVIRONMENT = "sandbox"
SANDBOX_UNITS = frozenset({"Nova Iguaçu 1", "São João de Meriti", "Vilar dos Teles"})
_CPF_DIGITS = re.compile(r"\D+")
_REMOTE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


class ReconciliationError(RuntimeError):
    """Erro estável sem documento, cifra, chave ou resposta remota."""


@dataclass(frozen=True, repr=False)
class ReceiverTarget:
    user_id: int
    unidade: str
    cpf: str = field(repr=False)
    cargo_id: int = field(default=3, repr=False)
    approval_status: str = field(default="aprovado", repr=False)
    wallet_id: str | None = field(default=None, repr=False)
    account_id: str | None = field(default=None, repr=False)
    integration_status: str | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return f"ReceiverTarget(user_id={self.user_id!r}, unidade={self.unidade!r})"


@dataclass(frozen=True, repr=False)
class EncryptedCredentialReceipt:
    user_id: int
    unidade: str
    environment: str
    account_id: str
    wallet_id: str
    ciphertext: str = field(repr=False)

    def __repr__(self) -> str:
        return f"EncryptedCredentialReceipt(user_id={self.user_id!r}, unidade={self.unidade!r}, identity=<redacted>)"


@dataclass(frozen=True, repr=False)
class RemoteReceiverAccount:
    account_id: str
    wallet_id: str
    cpf: str = field(repr=False)
    approval_status: str | None = None

    def __repr__(self) -> str:
        return "RemoteReceiverAccount(identity=<redacted>)"


@dataclass(frozen=True)
class RemoteAccountInventory:
    accounts: tuple[RemoteReceiverAccount, ...]
    complete: bool

    def __init__(self, accounts: Iterable[RemoteReceiverAccount], complete: bool):
        object.__setattr__(self, "accounts", tuple(accounts))
        object.__setattr__(self, "complete", complete)


@dataclass(frozen=True, repr=False)
class RemoteWalletInventory:
    wallet_ids: tuple[str, ...]
    complete: bool

    def __init__(self, wallet_ids: Iterable[str], complete: bool):
        object.__setattr__(self, "wallet_ids", tuple(wallet_ids))
        object.__setattr__(self, "complete", complete)


class RemoteReceiverGateway(Protocol):
    def list_accounts_by_cpf(self, cpf: str) -> RemoteAccountInventory: ...
    def get_own_account(self, api_key: str) -> Mapping[str, object]: ...
    def get_own_commercial_identity(self, api_key: str) -> Mapping[str, object]: ...
    def get_own_wallets(self, api_key: str) -> RemoteWalletInventory: ...


@dataclass(frozen=True, repr=False)
class ReconciliationEntry:
    user_id: int
    unidade: str
    state: str
    account_id: str | None = field(default=None, repr=False)
    wallet_id: str | None = field(default=None, repr=False)
    ciphertext: str | None = field(default=None, repr=False)
    sales_ready: bool = False
    cpf_snapshot: str | None = field(default=None, repr=False)
    cargo_id_snapshot: int | None = field(default=None, repr=False)
    approval_status_snapshot: str | None = field(default=None, repr=False)
    integration_status_snapshot: str | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return f"ReconciliationEntry(user_id={self.user_id!r}, unidade={self.unidade!r}, state={self.state!r}, sales_ready={self.sales_ready!r})"


@dataclass(frozen=True, repr=False)
class ReconciliationReport:
    environment: str
    entries: tuple[ReconciliationEntry, ...]

    def __init__(self, environment: str, entries: Iterable[ReconciliationEntry]):
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "entries", tuple(entries))

    def as_public_dict(self) -> dict[str, object]:
        return {"environment": self.environment, "entries": [
            {"user_id": entry.user_id, "unidade": entry.unidade, "state": entry.state}
            for entry in self.entries]}

    def __repr__(self) -> str:
        return f"ReconciliationReport(environment={self.environment!r}, entries={self.entries!r})"


def plan_reconciliation(*, environment: str, targets: Iterable[ReceiverTarget],
                        receipts: Iterable[EncryptedCredentialReceipt], gateway: RemoteReceiverGateway,
                        excluded_user_ids: set[int] | frozenset[int] = frozenset()) -> ReconciliationReport:
    target_list = tuple(targets)
    _validate_scope(environment, target_list)
    _validate_exclusions(excluded_user_ids)
    receipt_index = _index_receipts(receipts)
    entries = []
    for target in target_list:
        entries.append(ReconciliationEntry(target.user_id, target.unidade, "excluded") if target.user_id in excluded_user_ids
                       else _plan_target(target, receipt_index.get(target.user_id), gateway))
    return ReconciliationReport(environment, entries)


def _plan_target(target: ReceiverTarget, receipt: EncryptedCredentialReceipt | None,
                 gateway: RemoteReceiverGateway) -> ReconciliationEntry:
    cpf = _canonical_cpf(target.cpf)
    if cpf is None:
        return _entry(target, "target_invalid")
    inventory = gateway.list_accounts_by_cpf(cpf)
    if not inventory.complete:
        return _entry(target, "remote_inventory_incomplete")
    matches = [account for account in inventory.accounts if _canonical_cpf(account.cpf) == cpf]
    if not matches:
        return _entry(target, "remote_match_missing")
    if len(matches) != 1:
        return _entry(target, "remote_match_ambiguous")
    account = matches[0]
    if not _valid_remote_id(account.account_id) or not _valid_remote_id(account.wallet_id):
        return _entry(target, "remote_identity_invalid")
    local_present = any(value is not None for value in (target.wallet_id, target.account_id))
    if target.integration_status == "integrado" and not all(value is not None for value in (target.wallet_id, target.account_id)):
        return _entry(target, "local_conflict")
    if receipt is None:
        return _entry(target, "credential_missing")
    if not _receipt_matches(receipt, target, account):
        return _entry(target, "credential_identity_invalid")
    try:
        api_key = decrypt_api_key(receipt.ciphertext)
        own = gateway.get_own_account(api_key)
        commercial = gateway.get_own_commercial_identity(api_key)
        wallets = gateway.get_own_wallets(api_key)
    except Exception:
        return _entry(target, "credential_identity_invalid")
    if not _own_identity_matches(own, commercial, wallets, account, cpf):
        return _entry(target, "credential_identity_invalid")
    if (own.get("general") not in (None, "APPROVED") or account.approval_status not in (None, "APPROVED")
            or commercial.get("status") not in (None, "APPROVED")):
        return _entry(target, "kyc_pending")
    if local_present:
        if (target.wallet_id, target.account_id) == (account.wallet_id, account.account_id) and target.integration_status == "integrado":
            return _entry(target, "already_consistent", account, receipt)
        return _entry(target, "local_conflict")
    return _entry(target, "eligible", account, receipt)


def _entry(target: ReceiverTarget, state: str, account: RemoteReceiverAccount | None = None,
           receipt: EncryptedCredentialReceipt | None = None) -> ReconciliationEntry:
    return ReconciliationEntry(target.user_id, target.unidade, state,
        account.account_id if account else None, account.wallet_id if account else None,
        receipt.ciphertext if receipt else None, False, _canonical_cpf(target.cpf),
        target.cargo_id, target.approval_status, target.integration_status)


def execute_local_links(report: ReconciliationReport, *, store: object, execute: bool,
                        confirmed_sandbox_database: bool, allowed_user_ids: Iterable[int], refresh_plan: object | None = None) -> Literal["linked", "no_op"]:
    """Executor local futuro: bloqueia/revalida todo lote antes de qualquer UPDATE."""
    _runtime_guard()
    allowed = tuple(allowed_user_ids)
    selected = tuple(entry for entry in report.entries if entry.user_id in allowed)
    entry_ids = tuple(entry.user_id for entry in selected)
    if not execute:
        raise ReconciliationError("execution_not_confirmed")
    if report.environment != SANDBOX_ENVIRONMENT or not confirmed_sandbox_database:
        raise ReconciliationError("sandbox_database_not_confirmed")
    if not entry_ids or not _valid_unique_ids(entry_ids) or not _valid_unique_ids(allowed) or set(entry_ids) != set(allowed):
        raise ReconciliationError("execution_allowlist_invalid")
    if any(entry.state not in {"eligible", "already_consistent"} for entry in selected):
        raise ReconciliationError("execution_entry_not_eligible")
    transaction = getattr(store, "transaction", None)
    if not callable(transaction):
        raise ReconciliationError("execution_store_invalid")
    pending: list[ReconciliationEntry] = []
    with transaction():
        for entry in selected:
            if _locked_action(store.lock_and_get(entry.user_id), entry) == "update":
                pending.append(entry)
        if not callable(refresh_plan):
            raise ReconciliationError("execution_refresh_required")
        refreshed = refresh_plan(allowed)
        if not isinstance(refreshed, ReconciliationReport) or refreshed.environment != SANDBOX_ENVIRONMENT:
            raise ReconciliationError("execution_refresh_invalid")
        refreshed_entries = tuple(entry for entry in refreshed.entries if entry.user_id in allowed)
        if len(refreshed_entries) != len(selected) or any(entry.state not in {"eligible", "already_consistent"} for entry in refreshed_entries):
            raise ReconciliationError("execution_refresh_invalid")
        for previous, refreshed_entry in zip(selected, refreshed_entries):
            if (previous.user_id, previous.account_id, previous.wallet_id, previous.ciphertext, previous.cpf_snapshot,
                    previous.cargo_id_snapshot, previous.approval_status_snapshot, previous.integration_status_snapshot) != (
                    refreshed_entry.user_id, refreshed_entry.account_id, refreshed_entry.wallet_id, refreshed_entry.ciphertext,
                    refreshed_entry.cpf_snapshot, refreshed_entry.cargo_id_snapshot, refreshed_entry.approval_status_snapshot,
                    refreshed_entry.integration_status_snapshot):
                raise ReconciliationError("execution_refresh_invalid")
        for entry in pending:
            store.update_if_empty(entry)
    return "linked" if pending else "no_op"


def _locked_action(existing: object, entry: ReconciliationEntry) -> Literal["update", "no_op"]:
    if not isinstance(existing, Mapping) or (existing.get("user_id") != entry.user_id
            or existing.get("unidade") != entry.unidade or _canonical_cpf(existing.get("cpf")) != entry.cpf_snapshot
            or existing.get("cargo_id") != entry.cargo_id_snapshot
            or existing.get("status_aprovacao") != entry.approval_status_snapshot
            or existing.get("integration_status") != entry.integration_status_snapshot):
        raise ReconciliationError("execution_target_changed")
    current, desired = (existing.get("wallet_id"), existing.get("account_id"), existing.get("ciphertext")), (entry.wallet_id, entry.account_id, entry.ciphertext)
    if current == desired and existing.get("integration_status") == "integrado":
        return "no_op"
    if any(value is not None for value in current) or entry.state != "eligible" or not all(isinstance(value, str) and value for value in desired):
        raise ReconciliationError("execution_local_conflict")
    return "update"


class _UnitGateway:
    """Adaptador HTTP oficial GET, limitado à conta-pai sandbox de uma unidade."""
    def __init__(self, unidade: str):
        if unidade not in SANDBOX_UNITS:
            raise ReconciliationError("sandbox_scope_invalid")
        config = AsaasConfig.from_env(unidade, strict=True)
        if config.environment is not Environment.SANDBOX:
            raise ReconciliationError("sandbox_scope_invalid")
        # strict=True binds env names to the unit, but it does not prove that a
        # copied key is the configured parent account.  Prove its own identity
        # and configured wallet before inventorying any receiver.
        parent = _key_client_get(config.api_key, "/myAccount/status")
        parent_wallets = _key_client_wallets(config.api_key)
        parent_wallet_ids = [item.get("id") for item in parent_wallets[0]
                             if isinstance(item, Mapping) and isinstance(item.get("id"), str)]
        if (not _valid_remote_id(parent.get("id")) or not config.account_wallet_id
                or not parent_wallets[1] or parent_wallet_ids.count(config.account_wallet_id) != 1):
            raise ReconciliationError("sandbox_parent_identity_invalid")
        self.client = AsaasHttpClient(config.base_url, config.headers)

    def close(self) -> None:
        self.client.close()

    def list_accounts_by_cpf(self, cpf: str) -> RemoteAccountInventory:
        items, complete = _paginate(lambda offset: self.client.get("/accounts", params={"cpfCnpj": cpf, "limit": 100, "offset": offset}))
        return RemoteAccountInventory(
            (RemoteReceiverAccount(str(raw.get("id", "")), str(raw.get("walletId", "")), str(raw.get("cpfCnpj", "")),
             raw.get("status") if isinstance(raw.get("status"), str) else None) for raw in items if isinstance(raw, Mapping)), complete)

    def get_own_account(self, api_key: str) -> Mapping[str, object]:
        return _key_client_get(api_key, "/myAccount/status")

    def get_own_commercial_identity(self, api_key: str) -> Mapping[str, object]:
        return _key_client_get(api_key, "/myAccount/commercialInfo")

    def get_own_wallets(self, api_key: str) -> RemoteWalletInventory:
        items, complete = _key_client_wallets(api_key)
        return RemoteWalletInventory((raw.get("id") for raw in items if isinstance(raw, Mapping) and isinstance(raw.get("id"), str)), complete)


def _paginate(get_page: object) -> tuple[list[object], bool]:
    offset, expected_total, items, pages = 0, None, [], 0
    while True:
        pages += 1
        if pages > 100:
            return [], False
        payload = get_page(offset).json()
        if not isinstance(payload, Mapping) or payload.get("object") != "list" or not isinstance(payload.get("data"), list):
            return [], False
        total, limit, response_offset, data = payload.get("totalCount"), payload.get("limit"), payload.get("offset"), payload["data"]
        if (type(total) is not int or total < 0 or type(limit) is not int or limit < 1
                or type(response_offset) is not int or response_offset != offset):
            return [], False
        if expected_total is None:
            expected_total = total
        if total != expected_total or len(data) > limit or len(items) + len(data) > total:
            return [], False
        items.extend(data)
        if payload.get("hasMore") is False:
            return items, len(items) == total
        if payload.get("hasMore") is not True or not data:
            return [], False
        offset += len(data)


def _key_client_get(api_key: str, endpoint: str) -> Mapping[str, object]:
    payload = _key_client_payload(api_key, endpoint)
    return payload if isinstance(payload, Mapping) else {}


def _key_client_wallets(api_key: str) -> tuple[list[object], bool]:
    # GET /wallets has no query parameters. A truncated list is blocked.
    payload = _key_client_payload(api_key, "/wallets")
    if not isinstance(payload, Mapping) or payload.get("hasMore") is not False:
        return [], False
    total, limit, offset, data = payload.get("totalCount"), payload.get("limit"), payload.get("offset"), payload.get("data")
    if (payload.get("object") != "list" or type(total) is not int or type(limit) is not int
            or type(offset) is not int or offset != 0 or not isinstance(data, list)
            or total != len(data) or len(data) > limit):
        return [], False
    return data, True


def _key_client_payload(api_key: str, endpoint: str) -> object:
    """Executa um único GET autenticado e sempre fecha o cliente efêmero."""
    client = AsaasHttpClient(
        Environment.SANDBOX.value,
        {"Accept": "application/json", "access_token": api_key},
    )
    try:
        return client.get(endpoint).json()
    finally:
        client.close()


def load_runtime_plan(*, receipt_dir: Path, explicit_excluded_user_ids: set[int],
                      allowed_user_ids: Iterable[int] | None = None) -> ReconciliationReport:
    _runtime_guard()
    _validate_exclusions(explicit_excluded_user_ids)
    allowed = None if allowed_user_ids is None else tuple(allowed_user_ids)
    if allowed is not None and not _valid_unique_ids(allowed):
        raise ReconciliationError("execution_allowlist_invalid")
    _validate_receipt_directory(receipt_dir)  # validates sandbox private source before any DB/network I/O
    receipts, targets = _load_private_receipts(receipt_dir), _load_runtime_targets(allowed)
    if allowed is not None and {target.user_id for target in targets} != set(allowed):
        raise ReconciliationError("runtime_targets_missing")
    exclusions = set(explicit_excluded_user_ids)
    for target in targets:
        try:
            if is_asaas_sales_pf_user_excluded(target.user_id, target.unidade):
                exclusions.add(target.user_id)
        except AsaasSalesPreflightError:
            raise ReconciliationError("operational_exclusions_invalid") from None
    entries: list[ReconciliationEntry] = []
    for unit in sorted(SANDBOX_UNITS):
        unit_targets = tuple(target for target in targets if target.unidade == unit)
        if unit_targets:
            gateway = _UnitGateway(unit)
            try:
                entries.extend(plan_reconciliation(environment=SANDBOX_ENVIRONMENT, targets=unit_targets, receipts=receipts, gateway=gateway, excluded_user_ids=exclusions).entries)
            finally:
                gateway.close()
    return ReconciliationReport(SANDBOX_ENVIRONMENT, entries)


class DatabaseLinkStore:
    """Store de execução administrativa; a role de leitura da cifra é pré-requisito explícito.

    A confirmação não concede grant: aprovação/role administrativa e sua leitura da
    cifra devem existir antes, em mudança separada. Não há fallback para .env.
    """
    def __init__(self, *, confirmed_admin_cipher_read: bool = False) -> None:
        _runtime_guard()
        if confirmed_admin_cipher_read is not True:
            raise ReconciliationError("admin_cipher_read_not_confirmed")
        self._connection_context = self._connection = self._cursor = None

    def transaction(self): return self
    def __enter__(self):
        self._connection_context = DatabaseConnection()
        self._connection = self._connection_context.__enter__()
        self._cursor = self._connection.cursor(cursor_factory=RealDictCursor)
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        try: return self._connection_context.__exit__(exc_type, exc_value, traceback)
        finally: self._connection_context = self._connection = self._cursor = None

    def lock_and_get(self, user_id: int) -> Mapping[str, object] | None:
        self._cursor.execute("""SELECT id AS user_id, unidade, cpf,
            cargo_id, status_aprovacao, asaas_wallet_id AS wallet_id, asaas_account_id AS account_id,
            asaas_account_api_key_enc AS ciphertext, asaas_integration_status AS integration_status
            FROM users WHERE id=%s FOR UPDATE""", (user_id,))
        return self._cursor.fetchone()

    def update_if_empty(self, entry: ReconciliationEntry) -> None:
        self._cursor.execute("""UPDATE users SET asaas_wallet_id=%s, asaas_account_id=%s, asaas_account_api_key_enc=%s,
            asaas_integration_status='integrado', asaas_account_updated_at=NOW() WHERE id=%s AND unidade=%s
            AND REGEXP_REPLACE(COALESCE(cpf,''), '[^0-9]', '', 'g')=%s AND cargo_id=%s AND status_aprovacao=%s
            AND asaas_integration_status IS NOT DISTINCT FROM %s
            AND asaas_wallet_id IS NULL AND asaas_account_id IS NULL AND asaas_account_api_key_enc IS NULL RETURNING id""",
            (entry.wallet_id, entry.account_id, entry.ciphertext, entry.user_id, entry.unidade, entry.cpf_snapshot,
             entry.cargo_id_snapshot, entry.approval_status_snapshot, entry.integration_status_snapshot))
        if self._cursor.fetchone() is None:
            raise ReconciliationError("execution_target_changed")


def _load_runtime_targets(allowed_user_ids: tuple[int, ...] | None = None) -> tuple[ReceiverTarget, ...]:
    with DatabaseConnection(read_only=True) as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        if allowed_user_ids is None:
            cursor.execute("""SELECT id, unidade, cpf,
                cargo_id, status_aprovacao, asaas_wallet_id, asaas_account_id, asaas_integration_status FROM users
                WHERE cargo_id IN (3, 4) AND status_aprovacao='aprovado' AND unidade = ANY(%s) ORDER BY id""",
                (sorted(SANDBOX_UNITS),))
        else:
            cursor.execute("""SELECT id, unidade, cpf,
                cargo_id, status_aprovacao, asaas_wallet_id, asaas_account_id, asaas_integration_status FROM users
                WHERE id = ANY(%s) AND cargo_id IN (3, 4) AND status_aprovacao='aprovado'
                AND unidade = ANY(%s) ORDER BY id""", (list(allowed_user_ids), sorted(SANDBOX_UNITS)))
        rows = cursor.fetchall()
    return tuple(ReceiverTarget(row["id"], row["unidade"], row["cpf"], row["cargo_id"], row["status_aprovacao"],
                 row["asaas_wallet_id"], row["asaas_account_id"], row["asaas_integration_status"])
                 for row in rows if isinstance(row, Mapping))


def _validate_receipt_directory(directory: Path) -> None:
    try:
        root, resolved, info = Path(__file__).resolve().parents[3], directory.resolve(strict=True), directory.lstat()
        inside_git_checkout = any(_is_git_checkout_marker(ancestor / ".git") for ancestor in (resolved, *resolved.parents))
        if (not directory.is_absolute() or directory.is_symlink() or resolved.is_relative_to(root) or inside_git_checkout
                or not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077):
            raise ReconciliationError("credential_receipt_directory_invalid")
    except (OSError, ValueError):
        raise ReconciliationError("credential_receipt_directory_invalid") from None


def _is_git_checkout_marker(marker: Path) -> bool:
    """Reconhece metadados Git sem abrir conteúdo nem aceitar `.git` vazio."""
    try:
        info = marker.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    if stat.S_ISLNK(info.st_mode) or stat.S_ISREG(info.st_mode):
        return True
    if not stat.S_ISDIR(info.st_mode):
        return True
    try:
        return next(marker.iterdir(), None) is not None
    except OSError:
        return True


def _load_private_receipts(directory: Path) -> tuple[EncryptedCredentialReceipt, ...]:
    _validate_receipt_directory(directory)
    receipts, seen = [], set()
    try: paths = sorted(directory.iterdir())
    except OSError: raise ReconciliationError("credential_receipt_directory_invalid") from None
    for path in paths:
        if path.suffix != ".json": continue
        try:
            info = path.lstat()
            if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise ValueError
            raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_json_keys)
            if not isinstance(raw, Mapping) or set(raw) != {"user_id", "unidade", "environment", "account_id", "wallet_id", "ciphertext"}:
                raise ValueError
            item = EncryptedCredentialReceipt(**raw)
            if type(item.user_id) is not int or item.user_id <= 0 or item.user_id in seen: raise ValueError
            seen.add(item.user_id); receipts.append(item)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            raise ReconciliationError("credential_receipt_invalid") from None
    return tuple(receipts)


def _validate_scope(environment: str, targets: tuple[ReceiverTarget, ...]) -> None:
    if environment != SANDBOX_ENVIRONMENT or not targets or any(type(t.user_id) is not int or t.user_id <= 0 or t.unidade not in SANDBOX_UNITS for t in targets):
        raise ReconciliationError("sandbox_scope_invalid")


def _runtime_guard() -> None:
    application_environment = os.getenv("ENVIRONMENT")
    asaas_environment = os.getenv("ASAAS_ENVIRONMENT", "").strip().lower()
    db_environment = os.getenv("ASAAS_SALES_DB_ENVIRONMENT", "").strip().lower()
    recognized_non_prod = {"sandbox", "development", "test", "testing"}
    if (application_environment is not None and application_environment.strip().lower() not in recognized_non_prod
            or asaas_environment not in recognized_non_prod or db_environment not in recognized_non_prod
            or asaas_environment != SANDBOX_ENVIRONMENT or db_environment != SANDBOX_ENVIRONMENT):
        raise ReconciliationError("sandbox_runtime_not_confirmed")


def _validate_exclusions(ids: Iterable[int]) -> None:
    values = tuple(ids)
    if values and not _valid_unique_ids(values): raise ReconciliationError("excluded_user_id_invalid")
def _valid_unique_ids(ids: tuple[int, ...]) -> bool:
    return bool(ids) and all(type(value) is int and value > 0 for value in ids) and len(set(ids)) == len(ids)
def _index_receipts(receipts: Iterable[EncryptedCredentialReceipt]) -> dict[int, EncryptedCredentialReceipt]:
    indexed = {}
    for receipt in receipts:
        if type(receipt.user_id) is not int or receipt.user_id in indexed: raise ReconciliationError("credential_receipt_ambiguous")
        indexed[receipt.user_id] = receipt
    return indexed
def _receipt_matches(receipt: EncryptedCredentialReceipt, target: ReceiverTarget, account: RemoteReceiverAccount) -> bool:
    return (receipt.environment == SANDBOX_ENVIRONMENT and receipt.user_id == target.user_id and receipt.unidade == target.unidade
            and receipt.account_id == account.account_id and receipt.wallet_id == account.wallet_id
            and isinstance(receipt.ciphertext, str) and bool(receipt.ciphertext))
def _own_identity_matches(own: Mapping[str, object], commercial: Mapping[str, object], wallets: RemoteWalletInventory,
                          account: RemoteReceiverAccount, cpf: str) -> bool:
    return (isinstance(own, Mapping) and isinstance(commercial, Mapping) and own.get("id") == account.account_id
            and _canonical_cpf(commercial.get("cpfCnpj")) == cpf and wallets.complete
            and wallets.wallet_ids.count(account.wallet_id) == 1 and len(wallets.wallet_ids) == 1)
def _canonical_cpf(value: object) -> str | None:
    if not isinstance(value, str): return None
    if re.search(r"[^0-9.\- /]", value): return None
    digits = _CPF_DIGITS.sub("", value)
    return digits if len(digits) == 11 else None
def _valid_remote_id(value: object) -> bool:
    return isinstance(value, str) and bool(_REMOTE_ID.fullmatch(value))


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result
