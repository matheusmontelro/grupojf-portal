"""Contratos offline da reconciliação administrativa de recebedores sandbox."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import socket

import dotenv
import psycopg2
import pytest
from cryptography.fernet import Fernet

from app.security.asaas_account_secret import encrypt_api_key
from app.services import asaas_sandbox_receiver_reconciliation as reconciliation


@pytest.fixture
def fernet_secret(monkeypatch):
    monkeypatch.setenv("ASAAS_ACCOUNT_API_KEY_SECRET", Fernet.generate_key().decode())


@pytest.fixture(autouse=True)
def sandbox_runtime(monkeypatch):
    monkeypatch.setenv("ASAAS_ENVIRONMENT", "sandbox")
    monkeypatch.setenv("ASAAS_SALES_DB_ENVIRONMENT", "sandbox")


@pytest.fixture(autouse=True)
def offline_harness(monkeypatch):
    """A suite não pode abrir socket, banco ou carregar dotenv operacional."""
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: pytest.fail("network disabled"))
    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: pytest.fail("network disabled"))
    monkeypatch.setattr(psycopg2, "connect", lambda *_args, **_kwargs: pytest.fail("database disabled"))
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(reconciliation, "DatabaseConnection", lambda *_args, **_kwargs: pytest.fail("database disabled"))


def target(user_id=101, unit="São João de Meriti"):
    return reconciliation.ReceiverTarget(user_id=user_id, unidade=unit, cpf="000.000.000-00")


def remote(account_id="account-101", wallet_id="wallet-101"):
    return reconciliation.RemoteReceiverAccount(
        account_id=account_id, wallet_id=wallet_id, cpf="00000000000", approval_status="APPROVED"
    )


def receipt(user_id=101, unit="São João de Meriti", ciphertext="cipher"):
    return reconciliation.EncryptedCredentialReceipt(
        user_id=user_id, unidade=unit, environment="sandbox", account_id="account-101",
        wallet_id="wallet-101", ciphertext=ciphertext,
    )


class FakeGateway:
    def __init__(self, accounts, *, complete=True, own=None, commercial=None, wallets=None):
        self.accounts, self.complete = accounts, complete
        self.own = own or {"id": "account-101", "general": "APPROVED"}
        self.commercial = commercial or {"cpfCnpj": "00000000000", "status": "APPROVED"}
        self.wallets = wallets if wallets is not None else reconciliation.RemoteWalletInventory(["wallet-101"], True)
        self.calls = []

    def list_accounts_by_cpf(self, cpf):
        self.calls.append(("GET", "accounts", cpf))
        return reconciliation.RemoteAccountInventory(accounts=self.accounts, complete=self.complete)

    def get_own_account(self, api_key):
        self.calls.append(("GET", "myAccount/status"))
        return self.own

    def get_own_commercial_identity(self, api_key):
        self.calls.append(("GET", "myAccount/commercialInfo"))
        return self.commercial

    def get_own_wallets(self, api_key):
        self.calls.append(("GET", "wallets"))
        return self.wallets


def test_plan_is_read_only_and_reports_only_safe_identifiers(fernet_secret):
    cipher = encrypt_api_key("api-key-101")
    gateway = FakeGateway([remote()])
    report = reconciliation.plan_reconciliation(
        environment="sandbox", targets=[target()], receipts=[receipt(ciphertext=cipher)], gateway=gateway
    )
    assert report.entries[0].state == "eligible"
    assert gateway.calls == [
        ("GET", "accounts", "00000000000"), ("GET", "myAccount/status"),
        ("GET", "myAccount/commercialInfo"), ("GET", "wallets"),
    ]
    public = report.as_public_dict()
    assert public == {"environment": "sandbox", "entries": [{"user_id": 101, "unidade": "São João de Meriti", "state": "eligible"}]}
    assert "00000000000" not in repr(report)
    assert cipher not in repr(report)


@pytest.mark.parametrize("environment, unit", [
    ("production", "São João de Meriti"), ("sandbox", "Outra unidade"),
])
def test_plan_rejects_non_sandbox_or_unit_outside_hard_boundary(environment, unit):
    with pytest.raises(reconciliation.ReconciliationError, match="sandbox_scope_invalid"):
        reconciliation.plan_reconciliation(environment=environment, targets=[target(unit=unit)], receipts=[], gateway=FakeGateway([]))


@pytest.mark.parametrize("accounts, complete, expected", [
    ([], True, "remote_match_missing"), ([remote(), remote("other", "other-wallet")], True, "remote_match_ambiguous"),
    ([remote()], False, "remote_inventory_incomplete"),
])
def test_plan_blocks_non_unique_or_incomplete_remote_inventory(accounts, complete, expected):
    report = reconciliation.plan_reconciliation(environment="sandbox", targets=[target()], receipts=[], gateway=FakeGateway(accounts, complete=complete))
    assert report.entries[0].state == expected


def test_exclusion_is_explicit_id_and_does_not_exclude_similarly_named_person():
    report = reconciliation.plan_reconciliation(
        environment="sandbox", targets=[target(100), target(101)], receipts=[], gateway=FakeGateway([]), excluded_user_ids={100}
    )
    assert [entry.state for entry in report.entries] == ["excluded", "remote_match_missing"]


def test_bad_receipt_or_authenticated_identity_mismatch_blocks_link(fernet_secret):
    cipher = encrypt_api_key("api-key-101")
    report = reconciliation.plan_reconciliation(
        environment="sandbox", targets=[target()], receipts=[receipt(ciphertext=cipher)],
        gateway=FakeGateway([remote()], own={"id": "other", "walletId": "wallet-101"}),
    )
    assert report.entries[0].state == "credential_identity_invalid"


def test_authenticated_commercial_cpf_must_match_target(fernet_secret):
    cipher = encrypt_api_key("api-key-101")
    report = reconciliation.plan_reconciliation(
        environment="sandbox", targets=[target()], receipts=[receipt(ciphertext=cipher)], gateway=FakeGateway(
            [remote()], commercial={"cpfCnpj": "00000000000", "status": "APPROVED"},
        ),
    )
    assert report.entries[0].state == "credential_identity_invalid"


def test_authenticated_wallet_requires_complete_exact_wallet_inventory(fernet_secret):
    cipher = encrypt_api_key("api-key-101")
    report = reconciliation.plan_reconciliation(
        environment="sandbox", targets=[target()], receipts=[receipt(ciphertext=cipher)], gateway=FakeGateway(
            [remote()], wallets=reconciliation.RemoteWalletInventory(["wallet-101", "wallet-other"], True),
        ),
    )
    assert report.entries[0].state == "credential_identity_invalid"


def test_pending_kyc_does_not_declare_sales_readiness(fernet_secret):
    cipher = encrypt_api_key("api-key-101")
    report = reconciliation.plan_reconciliation(
        environment="sandbox", targets=[target()], receipts=[receipt(ciphertext=cipher)],
        gateway=FakeGateway([remote()], own={"id": "account-101", "walletId": "wallet-101", "general": "PENDING"}),
    )
    assert report.entries[0].state == "kyc_pending"
    assert report.entries[0].sales_ready is False


class MemoryStore:
    def __init__(self, rows=None, *, fail_on_update=None):
        self.events, self.updates, self.update_calls = [], [], []
        self.rows = deepcopy(rows or {})
        self.fail_on_update = fail_on_update
        self.clock = 0
    @contextmanager
    def transaction(self):
        self.events.append("begin")
        snapshot = deepcopy((self.rows, self.updates, self.update_calls, self.clock))
        try:
            yield self
        except Exception:
            self.rows, self.updates, self.update_calls, self.clock = snapshot
            self.events.append("rollback")
            raise
        else:
            self.events.append("commit")
    def lock_and_get(self, user_id):
        self.events.append(("lock", user_id))
        return self.rows.setdefault(user_id, {"user_id": user_id, "unidade": "São João de Meriti", "cpf": "00000000000", "cargo_id": 3, "status_aprovacao": "aprovado", "wallet_id": None, "account_id": None, "ciphertext": None, "integration_status": None})
    def update_if_empty(self, entry):
        self.update_calls.append(entry.user_id)
        if entry.user_id == self.fail_on_update:
            raise reconciliation.ReconciliationError("simulated_update_failure")
        row = self.rows[entry.user_id]
        assert row["wallet_id"] is row["account_id"] is row["ciphertext"] is None
        self.clock += 1
        row.update(wallet_id=entry.wallet_id, account_id=entry.account_id, ciphertext=entry.ciphertext,
                   integration_status="integrado", updated_at=f"timestamp-{self.clock}")
        self.updates.append(entry.user_id)


def test_future_executor_updates_once_then_new_plan_is_noop_with_same_timestamp():
    entry = reconciliation.ReconciliationEntry(101, "São João de Meriti", "eligible", "account-101", "wallet-101", "cipher", cpf_snapshot="00000000000", cargo_id_snapshot=3, approval_status_snapshot="aprovado")
    report = reconciliation.ReconciliationReport("sandbox", (entry,))
    store = MemoryStore()
    with pytest.raises(reconciliation.ReconciliationError, match="execution_not_confirmed"):
        reconciliation.execute_local_links(report, store=store, execute=False, confirmed_sandbox_database=True, allowed_user_ids={101})
    assert store.events == []
    result = reconciliation.execute_local_links(report, store=store, execute=True, confirmed_sandbox_database=True, allowed_user_ids={101}, refresh_plan=lambda _ids: report)
    assert result == "linked"
    assert store.events == ["begin", ("lock", 101), "commit"]
    assert store.updates == [101]
    timestamp = store.rows[101]["updated_at"]
    new_plan = reconciliation.ReconciliationReport("sandbox", [
        reconciliation.ReconciliationEntry(101, "São João de Meriti", "already_consistent", "account-101", "wallet-101", "cipher", cpf_snapshot="00000000000", cargo_id_snapshot=3, approval_status_snapshot="aprovado", integration_status_snapshot="integrado")
    ])
    assert reconciliation.execute_local_links(new_plan, store=store, execute=True, confirmed_sandbox_database=True,
                                              allowed_user_ids={101}, refresh_plan=lambda _ids: new_plan) == "no_op"
    assert store.updates == [101]
    assert store.rows[101]["updated_at"] == timestamp


def test_executor_rolls_back_first_update_when_second_update_fails():
    entries = [
        reconciliation.ReconciliationEntry(user_id, "São João de Meriti", "eligible", f"account-{user_id}", f"wallet-{user_id}", f"cipher-{user_id}", cpf_snapshot="00000000000", cargo_id_snapshot=3, approval_status_snapshot="aprovado")
        for user_id in (101, 102)
    ]
    report = reconciliation.ReconciliationReport("sandbox", entries)
    store = MemoryStore({user_id: {"user_id": user_id, "unidade": "São João de Meriti", "cpf": "00000000000", "cargo_id": 3, "status_aprovacao": "aprovado", "wallet_id": None, "account_id": None, "ciphertext": None, "integration_status": None} for user_id in (101, 102)}, fail_on_update=102)
    with pytest.raises(reconciliation.ReconciliationError, match="simulated_update_failure"):
        reconciliation.execute_local_links(report, store=store, execute=True, confirmed_sandbox_database=True,
                                           allowed_user_ids=[101, 102], refresh_plan=lambda _ids: report)
    assert store.updates == []
    assert store.rows[101]["wallet_id"] is None
    assert "updated_at" not in store.rows[101]
    assert store.events == ["begin", ("lock", 101), ("lock", 102), "rollback"]


@pytest.mark.parametrize("changed", [
    {"cpf": "00000000000"}, {"cargo_id": 99}, {"unidade": "Vilar dos Teles"},
])
def test_executor_revalidates_sensitive_snapshot_under_lock_before_any_write(changed):
    entry = reconciliation.ReconciliationEntry(101, "São João de Meriti", "eligible", "account-101", "wallet-101", "cipher", cpf_snapshot="00000000000", cargo_id_snapshot=3, approval_status_snapshot="aprovado")
    row = {"user_id": 101, "unidade": "São João de Meriti", "cpf": "00000000000", "cargo_id": 3, "status_aprovacao": "aprovado", "wallet_id": None, "account_id": None, "ciphertext": None, "integration_status": None}
    row.update(changed)
    store = MemoryStore({101: row})
    with pytest.raises(reconciliation.ReconciliationError, match="execution_target_changed"):
        reconciliation.execute_local_links(reconciliation.ReconciliationReport("sandbox", [entry]), store=store, execute=True, confirmed_sandbox_database=True, allowed_user_ids=[101], refresh_plan=lambda _ids: reconciliation.ReconciliationReport("sandbox", [entry]))
    assert store.updates == []
    assert store.events == ["begin", ("lock", 101), "rollback"]


def test_executor_validates_entire_locked_batch_before_writing_and_noop_requires_integrated():
    first = reconciliation.ReconciliationEntry(101, "São João de Meriti", "eligible", "account-101", "wallet-101", "cipher", cpf_snapshot="00000000000", cargo_id_snapshot=3, approval_status_snapshot="aprovado")
    second = reconciliation.ReconciliationEntry(102, "São João de Meriti", "eligible", "account-102", "wallet-102", "cipher-2", cpf_snapshot="00000000000", cargo_id_snapshot=3, approval_status_snapshot="aprovado")
    store = MemoryStore({
        101: {"user_id": 101, "unidade": "São João de Meriti", "cpf": "00000000000", "cargo_id": 3, "status_aprovacao": "aprovado", "wallet_id": None, "account_id": None, "ciphertext": None, "integration_status": None},
        102: {"user_id": 102, "unidade": "São João de Meriti", "cpf": "00000000000", "cargo_id": 3, "status_aprovacao": "aprovado", "wallet_id": "different", "account_id": "different", "ciphertext": "cipher-2", "integration_status": "integrado"},
    })
    with pytest.raises(reconciliation.ReconciliationError, match="execution_target_changed"):
        reconciliation.execute_local_links(reconciliation.ReconciliationReport("sandbox", [first, second]), store=store, execute=True, confirmed_sandbox_database=True, allowed_user_ids=[101, 102])
    assert store.updates == []
    assert store.events == ["begin", ("lock", 101), ("lock", 102), "rollback"]


def test_executor_rejects_duplicate_or_boolean_ids_and_only_noops_when_integrated():
    entry = reconciliation.ReconciliationEntry(101, "São João de Meriti", "eligible", "account-101", "wallet-101", "cipher", cpf_snapshot="00000000000", cargo_id_snapshot=3, approval_status_snapshot="aprovado")
    report = reconciliation.ReconciliationReport("sandbox", [entry, entry])
    with pytest.raises(reconciliation.ReconciliationError, match="execution_allowlist_invalid"):
        reconciliation.execute_local_links(report, store=MemoryStore(), execute=True, confirmed_sandbox_database=True, allowed_user_ids=[101, 101])
    with pytest.raises(reconciliation.ReconciliationError, match="execution_allowlist_invalid"):
        reconciliation.execute_local_links(reconciliation.ReconciliationReport("sandbox", [entry]), store=MemoryStore(), execute=True, confirmed_sandbox_database=True, allowed_user_ids=[True])
    store = MemoryStore({101: {"user_id": 101, "unidade": "São João de Meriti", "cpf": "00000000000", "cargo_id": 3, "status_aprovacao": "aprovado", "wallet_id": "wallet-101", "account_id": "account-101", "ciphertext": "cipher", "integration_status": "pendente"}})
    with pytest.raises(reconciliation.ReconciliationError, match="execution_target_changed"):
        reconciliation.execute_local_links(reconciliation.ReconciliationReport("sandbox", [entry]), store=store, execute=True, confirmed_sandbox_database=True, allowed_user_ids=[101])


def test_official_list_pagination_rejects_offset_limit_or_total_inconsistency():
    class Response:
        def __init__(self, payload): self.payload = payload
        def json(self): return self.payload
    responses = iter([
        Response({"object": "list", "hasMore": True, "totalCount": 2, "limit": 1, "offset": 0, "data": [{"id": "one"}]}),
        Response({"object": "list", "hasMore": False, "totalCount": 2, "limit": 1, "offset": 0, "data": [{"id": "two"}]}),
    ])
    assert reconciliation._paginate(lambda _offset: next(responses)) == ([], False)


def test_official_list_pagination_stops_after_one_hundred_pages():
    class Response:
        def __init__(self, offset): self.offset = offset
        def json(self):
            return {"object": "list", "hasMore": True, "totalCount": 101, "limit": 1, "offset": self.offset, "data": [{"id": "one"}]}
    calls = []
    def get_page(offset):
        calls.append(offset)
        return Response(offset)
    assert reconciliation._paginate(get_page) == ([], False)
    assert calls == list(range(100))


def test_parent_gateway_rejects_copied_key_when_configured_wallet_is_not_owned(monkeypatch):
    class Config:
        environment = reconciliation.Environment.SANDBOX
        api_key = "test-parent-key"
        account_wallet_id = "configured-wallet"
        base_url = "sandbox"
        headers = {}
    monkeypatch.setattr(reconciliation.AsaasConfig, "from_env", lambda *_args, **_kwargs: Config())
    monkeypatch.setattr(reconciliation, "_key_client_get", lambda *_args: {"id": "parent-account"})
    monkeypatch.setattr(reconciliation, "_key_client_wallets", lambda *_args: ([{"id": "other-wallet"}], True))
    with pytest.raises(reconciliation.ReconciliationError, match="sandbox_parent_identity_invalid"):
        reconciliation._UnitGateway("São João de Meriti")


def test_parent_gateway_accepts_its_configured_wallet_before_inventory(monkeypatch):
    class Config:
        environment = reconciliation.Environment.SANDBOX
        api_key = "test-parent-key"
        account_wallet_id = "configured-wallet"
        base_url = "sandbox"
        headers = {}
    class Client:
        def __init__(self, *_args): pass
    monkeypatch.setattr(reconciliation.AsaasConfig, "from_env", lambda *_args, **_kwargs: Config())
    monkeypatch.setattr(reconciliation, "_key_client_get", lambda *_args: {"id": "parent-account"})
    monkeypatch.setattr(reconciliation, "_key_client_wallets", lambda *_args: ([{"id": "configured-wallet"}], True))
    monkeypatch.setattr(reconciliation, "AsaasHttpClient", Client)
    assert isinstance(reconciliation._UnitGateway("São João de Meriti"), reconciliation._UnitGateway)


def test_executor_accepts_exact_partial_allowlist_and_requires_refresh_before_write():
    entries = [
        reconciliation.ReconciliationEntry(101, "São João de Meriti", "eligible", "account-101", "wallet-101", "cipher", cpf_snapshot="00000000000", cargo_id_snapshot=3, approval_status_snapshot="aprovado"),
        reconciliation.ReconciliationEntry(102, "São João de Meriti", "excluded"),
    ]
    store = MemoryStore()
    with pytest.raises(reconciliation.ReconciliationError, match="execution_refresh_required"):
        reconciliation.execute_local_links(reconciliation.ReconciliationReport("sandbox", entries), store=store, execute=True, confirmed_sandbox_database=True, allowed_user_ids=[101])
    result = reconciliation.execute_local_links(reconciliation.ReconciliationReport("sandbox", entries), store=store, execute=True, confirmed_sandbox_database=True, allowed_user_ids=[101], refresh_plan=lambda ids: reconciliation.ReconciliationReport("sandbox", [entries[0]]))
    assert result == "linked"


def test_cpf_with_letters_never_normalizes():
    assert reconciliation._canonical_cpf("123.abc.789-09") is None


def test_receipt_directory_inside_any_git_checkout_is_rejected_before_runtime_io(tmp_path):
    checkout = tmp_path / "other-checkout"
    receipts = checkout / "private" / "receipts"
    receipts.mkdir(parents=True)
    (checkout / ".git").mkdir()
    (checkout / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    receipts.chmod(0o700)
    with pytest.raises(reconciliation.ReconciliationError, match="credential_receipt_directory_invalid"):
        reconciliation._validate_receipt_directory(receipts)


def test_private_external_receipt_directory_is_accepted_when_git_marker_is_empty(tmp_path):
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    receipts.chmod(0o700)
    marker = tmp_path / ".git"
    marker.mkdir()
    reconciliation._validate_receipt_directory(receipts)


def test_private_receipt_directory_with_worktree_git_file_is_rejected(tmp_path):
    checkout = tmp_path / "worktree"
    receipts = checkout / "receipts"
    receipts.mkdir(parents=True, mode=0o700)
    receipts.chmod(0o700)
    (checkout / ".git").write_text("gitdir: /metadata/worktree\n", encoding="utf-8")
    with pytest.raises(reconciliation.ReconciliationError, match="credential_receipt_directory_invalid"):
        reconciliation._validate_receipt_directory(receipts)


def test_private_receipt_directory_with_symlinked_git_marker_is_rejected(tmp_path):
    checkout = tmp_path / "worktree"
    receipts = checkout / "receipts"
    receipts.mkdir(parents=True, mode=0o700)
    receipts.chmod(0o700)
    marker_target = tmp_path / "git-metadata"
    marker_target.mkdir()
    (checkout / ".git").symlink_to(marker_target, target_is_directory=True)
    with pytest.raises(reconciliation.ReconciliationError, match="credential_receipt_directory_invalid"):
        reconciliation._validate_receipt_directory(receipts)


def test_private_receipt_symlink_is_rejected(tmp_path):
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    receipts.chmod(0o700)
    target_file = tmp_path / "receipt.json"
    target_file.write_text("{}", encoding="utf-8")
    target_file.chmod(0o600)
    (receipts / "linked.json").symlink_to(target_file)
    with pytest.raises(reconciliation.ReconciliationError, match="credential_receipt_invalid"):
        reconciliation._load_private_receipts(receipts)


@pytest.mark.parametrize("environment", [None, "sandbox", "development", "test", "testing"])
def test_runtime_guard_allows_absent_or_recognized_non_production_environment(monkeypatch, environment):
    if environment is None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("ENVIRONMENT", environment)
    reconciliation._runtime_guard()


def test_runtime_guard_rejects_production_environment_even_with_sandbox_markers(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ASAAS_ENVIRONMENT", "sandbox")
    monkeypatch.setenv("ASAAS_SALES_DB_ENVIRONMENT", "sandbox")
    with pytest.raises(reconciliation.ReconciliationError, match="sandbox_runtime_not_confirmed"):
        reconciliation._runtime_guard()


def test_runtime_guard_blocks_before_receipt_database_or_gateway_io(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(reconciliation, "_validate_receipt_directory", lambda _path: pytest.fail("receipt io"))
    monkeypatch.setattr(reconciliation, "_load_runtime_targets", lambda *_args: pytest.fail("database io"))
    with pytest.raises(reconciliation.ReconciliationError, match="sandbox_runtime_not_confirmed"):
        reconciliation.load_runtime_plan(receipt_dir=tmp_path, explicit_excluded_user_ids=set(), allowed_user_ids=[101])


def test_runtime_subset_uses_only_allowlisted_targets_and_gates(monkeypatch, tmp_path):
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    seen = []
    monkeypatch.setattr(reconciliation, "_validate_receipt_directory", lambda _path: None)
    monkeypatch.setattr(reconciliation, "_load_private_receipts", lambda _path: ())
    monkeypatch.setattr(reconciliation, "_load_runtime_targets", lambda allowed_user_ids=None: (
        reconciliation.ReceiverTarget(101, "São João de Meriti", "00000000000"),) if allowed_user_ids == (101,) else ())
    class Gateway:
        def __init__(self, unit): seen.append(unit)
        def close(self): pass
        def list_accounts_by_cpf(self, _cpf): return reconciliation.RemoteAccountInventory([], True)
    monkeypatch.setattr(reconciliation, "_UnitGateway", Gateway)
    report = reconciliation.load_runtime_plan(receipt_dir=receipts, explicit_excluded_user_ids=set(), allowed_user_ids=[101])
    assert [entry.user_id for entry in report.entries] == [101]
    assert seen == ["São João de Meriti"]


def test_runtime_subset_missing_requested_id_blocks_before_gateway(monkeypatch, tmp_path):
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    monkeypatch.setattr(reconciliation, "_validate_receipt_directory", lambda _path: None)
    monkeypatch.setattr(reconciliation, "_load_private_receipts", lambda _path: ())
    monkeypatch.setattr(reconciliation, "_load_runtime_targets", lambda allowed_user_ids=None: ())
    monkeypatch.setattr(reconciliation, "_UnitGateway", lambda _unit: pytest.fail("gateway should not be created"))
    with pytest.raises(reconciliation.ReconciliationError, match="runtime_targets_missing"):
        reconciliation.load_runtime_plan(receipt_dir=receipts, explicit_excluded_user_ids=set(), allowed_user_ids=[101])


def test_future_executor_aborts_entire_batch_on_revalidation_conflict():
    eligible = reconciliation.ReconciliationEntry(101, "São João de Meriti", "eligible", "account-101", "wallet-101", "cipher")
    blocked = reconciliation.ReconciliationEntry(102, "Vilar dos Teles", "remote_match_missing")
    store = MemoryStore()
    with pytest.raises(reconciliation.ReconciliationError, match="execution_entry_not_eligible"):
        reconciliation.execute_local_links(reconciliation.ReconciliationReport("sandbox", (eligible, blocked)), store=store, execute=True, confirmed_sandbox_database=True, allowed_user_ids={101, 102})
    assert store.events == []


@pytest.mark.parametrize("fresh_state", ["excluded", "credential_identity_invalid", "credential_missing", "kyc_pending"])
def test_executor_fresh_plan_blocks_exclusion_identity_receipt_or_kyc_before_update(fresh_state):
    entry = reconciliation.ReconciliationEntry(101, "São João de Meriti", "eligible", "account-101", "wallet-101", "cipher", cpf_snapshot="00000000000", cargo_id_snapshot=3, approval_status_snapshot="aprovado")
    store = MemoryStore()
    with pytest.raises(reconciliation.ReconciliationError, match="execution_refresh_invalid"):
        reconciliation.execute_local_links(reconciliation.ReconciliationReport("sandbox", [entry]), store=store,
                                           execute=True, confirmed_sandbox_database=True, allowed_user_ids=[101],
                                           refresh_plan=lambda _ids: reconciliation.ReconciliationReport("sandbox", [
                                               reconciliation.ReconciliationEntry(101, "São João de Meriti", fresh_state)
                                           ]))
    assert store.updates == []
    assert store.events == ["begin", ("lock", 101), "rollback"]
