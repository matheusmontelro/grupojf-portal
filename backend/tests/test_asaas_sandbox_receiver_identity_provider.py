"""Contrato do provider PF sandbox sem banco ou segredo real."""

from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.services.asaas_receiver_identity_provider import AsaasSandboxReceiverIdentityProvider
from app.services.asaas_split_service import AsaasSplitValidationError


class _Cursor:
    def __init__(self, rows, cipher=None):
        self.rows, self.cipher, self.query = rows, cipher, ""
    def execute(self, query, params): self.query, self.params = query, params
    def fetchall(self): return self.rows
    def fetchone(self): return (self.cipher,) if "asaas_get_verified" in self.query and self.cipher else None


class _Connection:
    def __init__(self, cursor): self.cursor_value = cursor
    def cursor(self): return self.cursor_value


def _factory(cursor):
    @contextmanager
    def connect(**_kwargs): yield _Connection(cursor)
    return connect


def test_sandbox_pf_resolves_only_single_view_tuple_without_users_fields():
    cursor = _Cursor([(7, 12, "SJM", "sandbox", "account-1", "wallet-1")])
    provider = AsaasSandboxReceiverIdentityProvider(_factory(cursor))
    identity = provider.resolve_for_new_sale(kind="pf", local_id=12, unidade="SJM", environment="sandbox")
    assert identity.wallet_id == "wallet-1"
    assert identity.credential_ref == "sandbox-link:7"
    assert "asaas_sandbox_receiver_link_metadata" in cursor.query
    assert "credential_state = 'verified'" in cursor.query
    assert "users" not in cursor.query


@pytest.mark.parametrize("rows", [[], [(7, 12, "SJM", "sandbox", "a", "w"), (8, 12, "SJM", "sandbox", "b", "x")]])
def test_sandbox_pf_fails_closed_for_missing_or_ambiguous_link(rows):
    provider = AsaasSandboxReceiverIdentityProvider(_factory(_Cursor(rows)))
    with pytest.raises(AsaasSplitValidationError):
        provider.resolve_for_new_sale(kind="pf", local_id=12, unidade="SJM", environment="sandbox")


def test_sandbox_pf_rejects_production_before_query():
    provider = AsaasSandboxReceiverIdentityProvider(_factory(_Cursor([])))
    with pytest.raises(AsaasSplitValidationError):
        provider.resolve_for_new_sale(kind="pf", local_id=12, unidade="SJM", environment="production")


def test_sandbox_pf_approval_reader_uses_exact_frozen_tuple_and_hides_cipher_failure():
    cursor = _Cursor([(7, 12, "SJM", "sandbox", "account-1", "wallet-1")], cipher="cipher")
    provider = AsaasSandboxReceiverIdentityProvider(_factory(cursor))
    identity = provider.resolve_for_new_sale(kind="pf", local_id=12, unidade="SJM", environment="sandbox")
    with patch("app.services.asaas_receiver_identity_provider.decrypt_api_key", return_value="secret"), \
         patch("app.services.asaas_receiver_identity_provider.AsaasHttpClient") as client:
        client.return_value.close.return_value = None
        with provider.approval_reader(identity):
            pass
        assert cursor.params == (7, 12, "SJM", "account-1", "wallet-1")
        client.return_value.close.assert_called_once()
    with patch("app.services.asaas_receiver_identity_provider.decrypt_api_key", side_effect=RuntimeError("ciphertext leaked")):
        with pytest.raises(AsaasSplitValidationError) as caught:
            with provider.approval_reader(identity):
                pass
    assert "cipher" not in str(caught.value)


@pytest.mark.parametrize("field, value", [("account_id", "other-account"), ("wallet_id", "other-wallet"), ("local_id", 99)])
def test_sandbox_pf_approval_reader_rejects_any_divergent_frozen_tuple(field, value):
    cursor = _Cursor([(7, 12, "SJM", "sandbox", "account-1", "wallet-1")], cipher="cipher")
    provider = AsaasSandboxReceiverIdentityProvider(_factory(cursor))
    identity = provider.resolve_for_new_sale(kind="pf", local_id=12, unidade="SJM", environment="sandbox")
    changed = replace(identity, **{field: value})
    with pytest.raises(AsaasSplitValidationError):
        with provider.approval_reader(changed):
            pass
    assert "asaas_get_verified" not in cursor.query


def test_sandbox_pf_closes_client_when_reader_body_raises():
    cursor = _Cursor([(7, 12, "SJM", "sandbox", "account-1", "wallet-1")], cipher="cipher")
    provider = AsaasSandboxReceiverIdentityProvider(_factory(cursor))
    identity = provider.resolve_for_new_sale(kind="pf", local_id=12, unidade="SJM", environment="sandbox")
    with patch("app.services.asaas_receiver_identity_provider.decrypt_api_key", return_value="secret"), \
         patch("app.services.asaas_receiver_identity_provider.AsaasHttpClient") as client:
        with pytest.raises(RuntimeError, match="reader failure"):
            with provider.approval_reader(identity):
                raise RuntimeError("reader failure")
        client.return_value.close.assert_called_once()
