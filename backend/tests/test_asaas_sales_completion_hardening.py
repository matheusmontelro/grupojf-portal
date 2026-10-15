"""Casos negativos independentes da preparação Asaas, sem rede nem banco."""

from dataclasses import replace
from decimal import Decimal
import json
from unittest.mock import MagicMock

import pytest

from app.asaas_sales_sdk.approval_evidence import AsaasSalesApprovalEvidenceReader
from app.services.asaas_account_approval_service import AsaasApprovalTarget
from app.services.asaas_receiver_identity_provider import AsaasReceiverIdentityProvider
from app.services import asaas_split_service as splits
from test_asaas_split_snapshot import _plan, _v2_plan, ROOT_WALLET


TARGET = AsaasApprovalTarget(
    unidade="São João de Meriti", environment="sandbox",
    account_id="account-test", wallet_id="wallet-test",
)


def _evidence_client(*, commercial_info=None, wallets=None):
    if commercial_info is None:
        commercial_info = {"commercialInfoExpiration": {"isExpired": False}}
    if wallets is None:
        wallets = {
            "object": "list", "hasMore": False, "totalCount": 1,
            "limit": 10, "offset": 0,
            "data": [{"object": "wallet", "id": TARGET.wallet_id}],
        }
    client = MagicMock()
    client.get.side_effect = [
        MagicMock(json=lambda: {"id": TARGET.account_id, "general": "APPROVED"}),
        MagicMock(json=lambda: commercial_info),
        MagicMock(json=lambda: wallets),
    ]
    return client


@pytest.mark.parametrize("expiration", [
    {}, None, [], "current", {"isExpired": None}, {"isExpired": 0},
    {"isExpired": 1}, {"isExpired": "false"}, {"isExpired": "False"},
    {"isExpired": True},
])
def test_commercial_expiration_requires_exact_boolean_false(expiration):
    client = _evidence_client(commercial_info={"commercialInfoExpiration": expiration})
    assert AsaasSalesApprovalEvidenceReader(client, TARGET)(TARGET) is None


@pytest.mark.parametrize("field,value", [
    ("hasMore", 0), ("totalCount", True), ("totalCount", 2),
    ("limit", 0), ("offset", 1), ("offset", False), ("data", {}),
])
def test_wallet_proof_rejects_ambiguous_pagination(field, value):
    wallets = {
        "object": "list", "hasMore": False, "totalCount": 1,
        "limit": 10, "offset": 0,
        "data": [{"object": "wallet", "id": TARGET.wallet_id}],
    }
    wallets[field] = value
    client = _evidence_client(wallets=wallets)
    assert AsaasSalesApprovalEvidenceReader(client, TARGET)(TARGET) is None


@pytest.mark.parametrize("field,value", [
    ("unidade", "Nova Iguaçu 1"), ("environment", "production"),
    ("account_id", "other-account"), ("wallet_id", "other-wallet"),
])
def test_reader_never_uses_bound_credential_for_another_target(field, value):
    client = _evidence_client()
    assert AsaasSalesApprovalEvidenceReader(client, TARGET)(replace(TARGET, **{field: value})) is None
    client.get.assert_not_called()


@pytest.mark.parametrize("response_index", [0, 1, 2])
def test_invalid_json_blocks_evidence(response_index):
    client = _evidence_client()
    responses = list(client.get.side_effect)
    responses[response_index] = MagicMock(json=MagicMock(side_effect=ValueError("invalid response")))
    client.get.side_effect = responses
    assert AsaasSalesApprovalEvidenceReader(client, TARGET)(TARGET) is None


def _provider(tmp_path):
    receiver = {
        "kind": "pf", "local_id": 10, "unidade": TARGET.unidade,
        "environment": TARGET.environment, "account_id": TARGET.account_id,
        "wallet_id": TARGET.wallet_id,
        "credential_ref": "env:ASAAS_SALES_RECEIVER_SECRET_HARDENING",
    }
    path = tmp_path / "metadata-only.json"
    path.write_text(json.dumps({"schema_version": 1, "receivers": [receiver]}), encoding="utf-8")
    provider = AsaasReceiverIdentityProvider(str(path))
    return provider, provider.resolve_for_new_sale(
        kind="pf", local_id=10, unidade=TARGET.unidade, environment=TARGET.environment,
    )


def test_missing_jit_secret_does_not_open_a_client(tmp_path, monkeypatch):
    provider, identity = _provider(tmp_path)
    monkeypatch.delenv("ASAAS_SALES_RECEIVER_SECRET_HARDENING", raising=False)
    factory = MagicMock()
    monkeypatch.setattr("app.services.asaas_receiver_identity_provider.AsaasHttpClient", factory)
    with pytest.raises(splits.AsaasSplitValidationError, match="credencial_recebedor_asaas_ausente"):
        with provider.approval_reader(identity):
            pytest.fail("missing credential accepted")
    factory.assert_not_called()


def test_jit_rotation_reads_fresh_secret_and_closes_even_on_failure(tmp_path, monkeypatch):
    provider, identity = _provider(tmp_path)
    captured_headers = []
    clients = []

    def factory(**kwargs):
        captured_headers.append(kwargs["headers"])
        client = MagicMock()
        clients.append(client)
        return client

    monkeypatch.setattr("app.services.asaas_receiver_identity_provider.AsaasHttpClient", factory)
    for secret in ("offline-key-before", "offline-key-after"):
        monkeypatch.setenv("ASAAS_SALES_RECEIVER_SECRET_HARDENING", secret)
        with pytest.raises(RuntimeError, match="consumer failure"):
            with provider.approval_reader(identity):
                raise RuntimeError("consumer failure")
    assert captured_headers[0]["access_token"] == "offline-key-before"
    assert captured_headers[1]["access_token"] == "offline-key-after"
    assert identity.credential_ref == "env:ASAAS_SALES_RECEIVER_SECRET_HARDENING"
    assert all(client.close.call_count == 1 for client in clients)
    assert "offline-key" not in repr(identity)


@pytest.mark.parametrize("field,value", [
    ("account_id", "another-account"), ("credential_ref", "env:ASAAS_SALES_RECEIVER_SECRET_OTHER"),
])
def test_jit_declared_tuple_cannot_be_substituted(tmp_path, monkeypatch, field, value):
    provider, identity = _provider(tmp_path)
    factory = MagicMock()
    monkeypatch.setattr("app.services.asaas_receiver_identity_provider.AsaasHttpClient", factory)
    with pytest.raises(splits.AsaasSplitValidationError, match="identidade_recebedor_asaas_divergente"):
        with provider.approval_reader(replace(identity, **{field: value})):
            pytest.fail("substituted credential accepted")
    factory.assert_not_called()


@pytest.mark.parametrize("local_id", [0, -1])
def test_new_preview_rejects_nonpositive_local_id_before_any_write(local_id):
    plan = _v2_plan()
    item = plan.items[0]
    item = replace(item, user_id=local_id, receiver_identity=replace(item.receiver_identity, local_id=local_id))
    plan = replace(plan, items=[item])
    with pytest.raises(splits.AsaasSplitValidationError):
        splits.validate_asaas_new_split_preview(
            plan, splits.to_asaas_payload(plan), unidade=TARGET.unidade,
            environment=TARGET.environment, account_wallet_id=ROOT_WALLET,
            charge_value=Decimal("100"), contexto="carne",
        )


def test_new_preview_rejects_boolean_identity_id_even_if_equal_to_integer():
    plan = _v2_plan()
    item = plan.items[0]
    item = replace(item, user_id=1, receiver_identity=replace(item.receiver_identity, local_id=True))
    plan = replace(plan, items=[item])
    with pytest.raises(splits.AsaasSplitValidationError):
        splits.validate_asaas_new_split_preview(
            plan, splits.to_asaas_payload(plan), unidade=TARGET.unidade,
            environment=TARGET.environment, account_wallet_id=ROOT_WALLET,
            charge_value=Decimal("100"), contexto="carne",
        )


def test_v1_roundtrip_keeps_exact_historical_document_and_hash():
    historical = splits._plan_to_json(_plan())
    before = splits._sha256_json(historical)
    assert "schema_version" not in historical
    assert "receiver_identity" not in historical["items"][0]
    loaded = splits._json_to_plan(historical)
    assert loaded.schema_version == 1
    assert splits._plan_to_json(loaded) == historical
    assert splits._sha256_json(splits._plan_to_json(loaded)) == before


@pytest.mark.parametrize("field,value", [("walletId", "wallet-substituted"), ("percentualValue", 59.0)])
def test_new_preview_rejects_payload_wallet_or_value_substitution(field, value):
    plan = _v2_plan()
    payload = splits.to_asaas_payload(plan)
    payload[0][field] = value
    with pytest.raises(splits.AsaasSplitValidationError, match="snapshot_payload_split_divergente"):
        splits.validate_asaas_new_split_preview(
            plan, payload, unidade=TARGET.unidade,
            environment=TARGET.environment, account_wallet_id=ROOT_WALLET,
            charge_value=Decimal("100"), contexto="carne",
        )
