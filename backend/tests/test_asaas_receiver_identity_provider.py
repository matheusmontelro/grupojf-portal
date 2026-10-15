"""Contratos da fonte estreita de identidades de recebedores Asaas."""

from __future__ import annotations

import json

import pytest

from app.services.asaas_receiver_identity_provider import (
    AsaasReceiverIdentityProvider,
)
from app.services.asaas_split_service import AsaasSplitValidationError


def _receiver(*, wallet_id: str, credential_ref: str) -> dict[str, object]:
    return {
        "kind": "pf",
        "local_id": 10,
        "unidade": "São João de Meriti",
        "environment": "sandbox",
        "account_id": "account-receiver",
        "wallet_id": wallet_id,
        "credential_ref": credential_ref,
    }


def _manifest(tmp_path, receivers, *, schema_version=1):
    path = tmp_path / "receivers.json"
    path.write_text(
        json.dumps({"schema_version": schema_version, "receivers": receivers}),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("schema_version", [True, 1.0, "1", 2])
def test_receiver_manifest_rejects_non_exact_schema_version(tmp_path, schema_version):
    path = _manifest(
        tmp_path,
        [_receiver(wallet_id="wallet-a", credential_ref="env:ASAAS_SALES_RECEIVER_SECRET_A")],
        schema_version=schema_version,
    )

    with pytest.raises(AsaasSplitValidationError, match="manifesto_recebedor_asaas_invalido"):
        AsaasReceiverIdentityProvider(str(path))


@pytest.mark.parametrize("local_id", [True, 0, -1, 1.0, "10"])
def test_receiver_manifest_requires_positive_integer_local_id(tmp_path, local_id):
    receiver = _receiver(
        wallet_id="wallet-a", credential_ref="env:ASAAS_SALES_RECEIVER_SECRET_A"
    )
    receiver["local_id"] = local_id
    path = _manifest(tmp_path, [receiver])

    with pytest.raises(AsaasSplitValidationError, match="manifesto_recebedor_asaas_invalido"):
        AsaasReceiverIdentityProvider(str(path))


def test_provider_requires_exact_wallet_but_allows_history_with_another_wallet(tmp_path):
    path = _manifest(
        tmp_path,
        [
            _receiver(wallet_id="wallet-old", credential_ref="env:ASAAS_SALES_RECEIVER_SECRET_OLD"),
            _receiver(wallet_id="wallet-new", credential_ref="env:ASAAS_SALES_RECEIVER_SECRET_NEW"),
        ],
    )
    provider = AsaasReceiverIdentityProvider(str(path))

    old = provider.resolve(
        kind="pf", local_id=10, unidade="São João de Meriti",
        environment="sandbox", wallet_id="wallet-old",
    )
    new = provider.resolve(
        kind="pf", local_id=10, unidade="São João de Meriti",
        environment="sandbox", wallet_id="wallet-new",
    )

    assert old.wallet_id == "wallet-old"
    assert new.wallet_id == "wallet-new"
    with pytest.raises(AsaasSplitValidationError, match="identidade_recebedor_asaas_ausente"):
        provider.resolve(
            kind="pf", local_id=10, unidade="São João de Meriti",
            environment="sandbox", wallet_id="wallet-unknown",
        )
    with pytest.raises(AsaasSplitValidationError, match="identidade_recebedor_asaas_ambigua"):
        provider.resolve_for_new_sale(
            kind="pf", local_id=10, unidade="São João de Meriti", environment="sandbox"
        )


def test_provider_factory_and_jit_reader_close_client_without_storing_secret(tmp_path, monkeypatch):
    path = _manifest(
        tmp_path,
        [_receiver(wallet_id="wallet-a", credential_ref="env:ASAAS_SALES_RECEIVER_SECRET_A")],
    )
    monkeypatch.setenv("ASAAS_SALES_RECEIVER_IDENTITIES_FILE", str(path))
    monkeypatch.setenv("ASAAS_SALES_RECEIVER_SECRET_A", "test-secret-only-in-environment")
    provider = AsaasReceiverIdentityProvider.from_environment()
    identity = provider.resolve(
        kind="pf", local_id=10, unidade="São João de Meriti",
        environment="sandbox", wallet_id="wallet-a",
    )

    class FakeClient:
        def __init__(self, **_kwargs):
            self.closed = False

        def close(self):
            self.closed = True

    clients = []

    def fake_client(**kwargs):
        client = FakeClient(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(
        "app.services.asaas_receiver_identity_provider.AsaasHttpClient", fake_client
    )

    with provider.approval_reader(identity) as reader:
        assert reader._bound_target.account_id == identity.account_id

    assert clients[0].closed is True
    assert "test-secret-only-in-environment" not in repr(identity)


def test_provider_factory_fails_closed_when_manifest_is_not_configured(monkeypatch):
    monkeypatch.delenv("ASAAS_SALES_RECEIVER_IDENTITIES_FILE", raising=False)

    with pytest.raises(AsaasSplitValidationError, match="manifesto_recebedor_asaas_ausente"):
        AsaasReceiverIdentityProvider.from_environment()
