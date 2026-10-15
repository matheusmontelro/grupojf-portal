"""Contratos offline do cadastro administrativo de vínculos por ambiente."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy

import pytest

from app.services import asaas_receiver_environment_links as links


def candidate(user_id: int, *, unit: str = "São João de Meriti", credential: str | None = None):
    return links.ReceiverEnvironmentLink(
        user_id=user_id, unidade=unit, environment="sandbox", account_id=f"account-{user_id}",
        wallet_id=f"wallet-{user_id}", credential_ciphertext=credential,
        credential_state="verified" if credential else "pending", cpf_digest=links.cpf_digest("12345678901"),
    )


class MemoryStore:
    def __init__(self, rows=None, *, fail_on_insert=None):
        self.rows = deepcopy(rows or {})
        self.events: list[object] = []
        self.fail_on_insert = fail_on_insert

    @contextmanager
    def transaction(self):
        snapshot = deepcopy(self.rows)
        self.events.append("begin")
        try:
            yield self
        except Exception:
            self.rows = snapshot
            self.events.append("rollback")
            raise
        else:
            self.events.append("commit")

    def lock_user(self, user_id):
        self.events.append(("lock_user", user_id))
        return {"id": user_id, "unidade": links.TARGET_UNITS[user_id], "cargo_id": 3,
                "status_aprovacao": "aprovado", "cpf": "12345678901"}

    def lock_link(self, user_id, unit, environment):
        self.events.append(("lock_link", user_id, unit, environment))
        return self.rows.get((user_id, unit, environment))

    def insert(self, item):
        if item.user_id == self.fail_on_insert:
            raise links.ReceiverEnvironmentLinkError("insert_failed")
        self.rows[(item.user_id, item.unidade, item.environment)] = item

    def promote_pending(self, current, desired):
        self.events.append(("promote", current.user_id))
        key = (current.user_id, current.unidade, current.environment)
        if self.rows.get(key) != current:
            return False
        self.rows[key] = desired
        return True


def test_exact_allowlist_persists_verified_and_pending_links_atomically_without_users_updates():
    entries = (candidate(45, credential="ciphertext-a"), candidate(54))
    store = MemoryStore()

    result = links.execute_import(
        entries, store=store, execute=True, confirmed_admin_database=True,
        allowed_user_ids=(45, 54), refresh=lambda ids: entries,
    )

    assert result == "imported"
    assert set(store.rows) == {(45, "São João de Meriti", "sandbox"), (54, "São João de Meriti", "sandbox")}
    assert store.rows[(45, "São João de Meriti", "sandbox")].credential_state == "verified"
    assert store.rows[(54, "São João de Meriti", "sandbox")].credential_state == "pending"
    assert store.events == ["begin", ("lock_user", 45), ("lock_link", 45, "São João de Meriti", "sandbox"),
                            ("lock_user", 54), ("lock_link", 54, "São João de Meriti", "sandbox"), "commit"]


def test_singleton_134_verified_link_uses_the_existing_atomic_import_contract():
    entry = candidate(134, unit="Nova Iguaçu 1", credential="ciphertext-134")
    store = MemoryStore()

    assert links.execute_import(
        (entry,), store=store, execute=True, confirmed_admin_database=True,
        allowed_user_ids=(134,), refresh=lambda _ids: (entry,),
    ) == "imported"
    assert set(store.rows) == {(134, "Nova Iguaçu 1", "sandbox")}
    assert store.rows[(134, "Nova Iguaçu 1", "sandbox")].credential_state == "verified"


def test_singleton_134_refresh_identity_drift_fails_before_any_database_lock():
    initial = candidate(134, unit="Nova Iguaçu 1", credential="ciphertext-134")
    drifted = links.ReceiverEnvironmentLink(
        134, "Nova Iguaçu 1", "sandbox", "account-134", "wallet-134", "other-ciphertext",
        "verified", links.cpf_digest("00000000000"),
    )
    store = MemoryStore()

    with pytest.raises(links.ReceiverEnvironmentLinkError, match="^execution_refresh_invalid$"):
        links.execute_import(
            (initial,), store=store, execute=True, confirmed_admin_database=True,
            allowed_user_ids=(134,), refresh=lambda _ids: (drifted,),
        )
    assert store.rows == {}
    assert store.events == []


@pytest.mark.parametrize("locked_user", [
    {"id": 134, "unidade": "Nova Iguaçu 1", "cargo_id": 4, "status_aprovacao": "APPROVED", "cpf": "12345678901"},
    {"id": 134, "unidade": "Nova Iguaçu 1", "cargo_id": 4, "status_aprovacao": "aprovado", "cpf": "00000000000"},
    {"id": 134, "unidade": "Nova Iguaçu 1", "cargo_id": 2, "status_aprovacao": "aprovado", "cpf": "12345678901"},
])
def test_singleton_134_locked_profile_or_cpf_mismatch_rolls_back_without_overwrite(locked_user):
    entry = candidate(134, unit="Nova Iguaçu 1", credential="ciphertext-134")
    current = candidate(134, unit="Nova Iguaçu 1", credential="existing-ciphertext")
    store = MemoryStore({(134, "Nova Iguaçu 1", "sandbox"): current})
    store.lock_user = lambda _user_id: locked_user

    with pytest.raises(links.ReceiverEnvironmentLinkError, match="^target_missing$"):
        links.execute_import(
            (entry,), store=store, execute=True, confirmed_admin_database=True,
            allowed_user_ids=(134,), refresh=lambda _ids: (entry,),
        )
    assert store.rows[(134, "Nova Iguaçu 1", "sandbox")] == current
    assert store.events[-1] == "rollback"


def test_same_plaintext_credential_is_a_noop_even_when_fernet_ciphertext_differs():
    existing = candidate(45, credential="ciphertext-old")
    refreshed = candidate(45, credential="ciphertext-new")
    store = MemoryStore({(45, "São João de Meriti", "sandbox"): existing})

    assert links.execute_import(
        (refreshed,), store=store, execute=True, confirmed_admin_database=True, allowed_user_ids=(45,),
        refresh=lambda ids: (refreshed,), credential_matches=lambda old, new: old == "ciphertext-old" and new == "ciphertext-new",
    ) == "no_op"
    assert store.rows[(45, "São João de Meriti", "sandbox")].credential_ciphertext == "ciphertext-old"


def test_ni_pending_lot_promotes_all_nine_atomically_and_never_inserts():
    pending = tuple(candidate(user_id, unit="Nova Iguaçu 1") for user_id in links.NI_PENDING_USER_IDS)
    desired = tuple(candidate(user_id, unit="Nova Iguaçu 1", credential=f"cipher-{user_id}") for user_id in links.NI_PENDING_USER_IDS)
    store = MemoryStore({(item.user_id, item.unidade, item.environment): item for item in pending})

    assert links.execute_pending_verification(
        desired, store=store, execute=True, confirmed_admin_database=True,
        refresh=lambda ids: desired,
    ) == "verified"
    assert [event for event in store.events if isinstance(event, tuple) and event[0] == "promote"] == [
        ("promote", user_id) for user_id in links.NI_PENDING_USER_IDS
    ]
    assert all(item.credential_state == "verified" for item in store.rows.values())


def test_ni_pending_lot_conflict_rolls_back_all_promotions():
    pending = tuple(candidate(user_id, unit="Nova Iguaçu 1") for user_id in links.NI_PENDING_USER_IDS)
    desired = tuple(candidate(user_id, unit="Nova Iguaçu 1", credential=f"cipher-{user_id}") for user_id in links.NI_PENDING_USER_IDS)
    conflict = candidate(44, unit="Nova Iguaçu 1")
    conflict = links.ReceiverEnvironmentLink(44, conflict.unidade, conflict.environment, "other", conflict.wallet_id, None, "pending", conflict.cpf_digest)
    store = MemoryStore({(item.user_id, item.unidade, item.environment): item for item in pending} | {(44, "Nova Iguaçu 1", "sandbox"): conflict})

    with pytest.raises(links.ReceiverEnvironmentLinkError, match="pending_link_conflict"):
        links.execute_pending_verification(desired, store=store, execute=True, confirmed_admin_database=True, refresh=lambda ids: desired)
    assert all(item.credential_state == "pending" for item in store.rows.values())
    assert store.events[-1] == "rollback"


def test_ni_pending_cas_returning_no_row_rolls_back_prior_promotions():
    """A late CAS miss must not commit the earlier eight (or first) updates."""
    pending = tuple(candidate(user_id, unit="Nova Iguaçu 1") for user_id in links.NI_PENDING_USER_IDS)
    desired = tuple(candidate(user_id, unit="Nova Iguaçu 1", credential=f"cipher-{user_id}") for user_id in links.NI_PENDING_USER_IDS)

    class CasMissStore(MemoryStore):
        def promote_pending(self, current, item):
            self.events.append(("promote", current.user_id))
            if current.user_id == 44:
                return False
            self.rows[(current.user_id, current.unidade, current.environment)] = item
            return True

    store = CasMissStore({(item.user_id, item.unidade, item.environment): item for item in pending})
    with pytest.raises(links.ReceiverEnvironmentLinkError, match="pending_link_conflict"):
        links.execute_pending_verification(
            desired, store=store, execute=True, confirmed_admin_database=True,
            refresh=lambda _ids: desired,
        )
    assert all(item.credential_state == "pending" for item in store.rows.values())
    assert store.events[-1] == "rollback"


def test_postgres_pending_promotion_sql_is_conditional_and_no_row_is_conflict():
    """Exercise the SQL CAS result, rather than only the in-memory precheck."""
    class Cursor:
        def __init__(self): self.executed = []
        def execute(self, query, params): self.executed.append((query, params))
        def fetchone(self): return None

    current = candidate(27, unit="Nova Iguaçu 1")
    desired = candidate(27, unit="Nova Iguaçu 1", credential="cipher")
    store = object.__new__(links.PostgresLinkStore)
    store._cursor = cursor = Cursor()
    assert store.promote_pending(current, desired) is False
    query, params = cursor.executed[0]
    assert "credential_state='pending'" in query
    assert "credential_ciphertext IS NULL" in query
    assert "account_id=%s AND wallet_id=%s" in query
    assert "RETURNING user_id" in query
    assert params == ("cipher", 27, "Nova Iguaçu 1", "account-27", "wallet-27")


@pytest.mark.parametrize("execute, confirmed", [(False, True), (True, False), (False, False)])
def test_execution_guards_fail_before_refresh_or_transaction(execute, confirmed):
    store, calls = MemoryStore(), []
    with pytest.raises(links.ReceiverEnvironmentLinkError, match="execution_not_confirmed"):
        links.execute_import((candidate(45),), store=store, execute=execute,
                             confirmed_admin_database=confirmed, allowed_user_ids=(45,),
                             refresh=lambda _ids: calls.append("refresh"))
    assert calls == []
    assert store.events == []


def test_refresh_scope_change_fails_before_any_database_lock_or_write():
    initial = candidate(45)
    refreshed = links.ReceiverEnvironmentLink(45, "São João de Meriti", "production", "account-45",
                                              "wallet-45", None, "pending", initial.cpf_digest)
    store = MemoryStore()
    with pytest.raises(links.ReceiverEnvironmentLinkError, match="link_scope_invalid"):
        links.execute_import((initial,), store=store, execute=True, confirmed_admin_database=True,
                             allowed_user_ids=(45,), refresh=lambda _ids: (refreshed,))
    assert store.events == []
    assert store.rows == {}


@pytest.mark.parametrize("entries, allowed", [
    ((candidate(45),), (45, 54)),
    ((candidate(45, unit="Outra unidade"),), (45,)),
    ((candidate(45, credential=""),), (45,)),
    ((candidate(45), candidate(45)), (45,)),
])
def test_invalid_scope_or_conflict_fails_before_any_write(entries, allowed):
    store = MemoryStore()
    with pytest.raises(links.ReceiverEnvironmentLinkError):
        links.execute_import(entries, store=store, execute=True, confirmed_admin_database=True,
                             allowed_user_ids=allowed, refresh=lambda ids: entries)
    assert store.rows == {}
    assert store.events == []


def test_insert_failure_rolls_back_whole_lot():
    entries = (candidate(45), candidate(54))
    store = MemoryStore(fail_on_insert=54)
    with pytest.raises(links.ReceiverEnvironmentLinkError, match="insert_failed"):
        links.execute_import(entries, store=store, execute=True, confirmed_admin_database=True,
                             allowed_user_ids=(45, 54), refresh=lambda ids: entries)
    assert store.rows == {}
    assert store.events[-1] == "rollback"


def test_existing_different_identity_or_state_fails_closed_without_replacement():
    current = candidate(45)
    store = MemoryStore({(45, "São João de Meriti", "sandbox"): current})
    conflicting = links.ReceiverEnvironmentLink(45, "São João de Meriti", "sandbox", "other-account", "other-wallet", None, "pending", links.cpf_digest("12345678901"))
    with pytest.raises(links.ReceiverEnvironmentLinkError, match="existing_link_conflict"):
        links.execute_import((conflicting,), store=store, execute=True, confirmed_admin_database=True,
                             allowed_user_ids=(45,), refresh=lambda ids: (conflicting,))
    assert store.rows[(45, "São João de Meriti", "sandbox")] == current


def test_late_existing_conflict_rolls_back_prior_insert_and_preserves_existing_link():
    first, conflicting = candidate(45), candidate(54)
    existing = links.ReceiverEnvironmentLink(54, "São João de Meriti", "sandbox", "old-account",
                                             "old-wallet", None, "pending", conflicting.cpf_digest)
    store = MemoryStore({(54, "São João de Meriti", "sandbox"): existing})
    with pytest.raises(links.ReceiverEnvironmentLinkError, match="existing_link_conflict"):
        links.execute_import((first, conflicting), store=store, execute=True, confirmed_admin_database=True,
                             allowed_user_ids=(45, 54), refresh=lambda _ids: (first, conflicting))
    assert store.rows == {(54, "São João de Meriti", "sandbox"): existing}
    assert store.events[-1] == "rollback"


def test_verified_cipher_matcher_exception_fails_closed_without_replacement():
    existing, desired = candidate(45, credential="old"), candidate(45, credential="new")
    store = MemoryStore({(45, "São João de Meriti", "sandbox"): existing})
    with pytest.raises(links.ReceiverEnvironmentLinkError, match="existing_link_conflict"):
        links.execute_import((desired,), store=store, execute=True, confirmed_admin_database=True,
                             allowed_user_ids=(45,), refresh=lambda _ids: (desired,),
                             credential_matches=lambda _old, _new: (_ for _ in ()).throw(ValueError("bad cipher")))
    assert store.rows[(45, "São João de Meriti", "sandbox")] == existing


def test_production_and_sandbox_are_isolated_by_identity_key():
    production = links.ReceiverEnvironmentLink(45, "São João de Meriti", "production", "prod-account", "prod-wallet", "prod-cipher", "verified")
    sandbox = candidate(45)
    store = MemoryStore({(45, "São João de Meriti", "production"): production})
    assert links.execute_import((sandbox,), store=store, execute=True, confirmed_admin_database=True,
                                allowed_user_ids=(45,), refresh=lambda ids: (sandbox,)) == "imported"
    assert store.rows[(45, "São João de Meriti", "production")] == production


def test_local_target_unit_change_under_lock_rolls_back():
    entries = (candidate(45),)
    store = MemoryStore()
    store.lock_user = lambda _user_id: {"id": 45, "unidade": "Outra unidade"}
    with pytest.raises(links.ReceiverEnvironmentLinkError, match="target_missing"):
        links.execute_import(entries, store=store, execute=True, confirmed_admin_database=True,
                             allowed_user_ids=(45,), refresh=lambda _ids: entries)
    assert store.rows == {}


def test_local_target_role_or_cpf_change_under_lock_rolls_back():
    entries, store = (candidate(45),), MemoryStore()
    store.lock_user = lambda _user_id: {"id": 45, "unidade": "São João de Meriti", "cargo_id": 2,
                                        "status_aprovacao": "aprovado", "cpf": "different"}
    with pytest.raises(links.ReceiverEnvironmentLinkError, match="target_missing"):
        links.execute_import(entries, store=store, execute=True, confirmed_admin_database=True,
                             allowed_user_ids=(45,), refresh=lambda _ids: entries)
    assert store.rows == {}


def test_postgres_store_hides_database_exception_details(monkeypatch):
    class FailingConnection:
        def close(self): pass

    def fail_connect(**_config):
        raise RuntimeError("ciphertext must satisfy receiver_environment_link_ciphertext_check")

    monkeypatch.setattr(links.psycopg2, "connect", fail_connect)
    store = links.PostgresLinkStore({"host": "host", "port": "5432", "dbname": "database", "user": "user", "password": "password"})
    with pytest.raises(links.ReceiverEnvironmentLinkError, match="^database_operation_failed$") as error:
        with store.transaction():
            pass
    assert error.value.__cause__ is None
