"""Contratos do snapshot imutavel anterior ao POST Asaas."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import asaas_carne_provisioning_service as worker
from app.services import asaas_split_service as splits
from test_asaas_carne_provisioning_service import make_snapshot


ROOT_WALLET = "wallet-sjm"
SELLER_WALLET = "wallet-comercial"


def _plan() -> splits.AsaasSplitPlan:
    return splits.AsaasSplitPlan(
        contexto="carne",
        items=[
            splits.AsaasSplitItem(
                wallet_id=SELLER_WALLET,
                kind="percentual",
                cargo_id=3,
                user_id=10,
                percentual_value=Decimal("60"),
            )
        ],
        absorber=splits.AsaasBalanceAbsorber(
            wallet_id=ROOT_WALLET,
            absorbed_value=Decimal("40.00"),
            cargo_id=4,
            user_id=11,
        ),
    )


def _sealed(
    *,
    plan: splits.AsaasSplitPlan | None = None,
    payload: list[dict] | None = None,
) -> splits.AsaasSealedSplitSnapshot:
    return splits.AsaasSealedSplitSnapshot(
        integration_id=10,
        plan=plan or _plan(),
        payload=payload
        or [{"walletId": SELLER_WALLET, "percentualValue": 60.0}],
        plan_sha256="a" * 64,
        payload_sha256="b" * 64,
        lifecycle_state="sealed",
    )


def _v2_plan() -> splits.AsaasSplitPlan:
    identity = splits.AsaasReceiverIdentity(
        kind="pf",
        local_id=10,
        unidade="São João de Meriti",
        environment="sandbox",
        account_id="account-recipient",
        wallet_id=SELLER_WALLET,
        credential_ref="env:ASAAS_RECEIVER_SELLER",
    )
    return splits.AsaasSplitPlan(
        contexto="carne",
        schema_version=2,
        items=[
            splits.AsaasSplitItem(
                wallet_id=SELLER_WALLET,
                kind="percentual",
                cargo_id=3,
                user_id=10,
                percentual_value=Decimal("60"),
                receiver_identity=identity,
            )
        ],
        absorber=splits.AsaasBalanceAbsorber(
            wallet_id=ROOT_WALLET,
            absorbed_value=Decimal("40.00"),
            cargo_id=4,
            user_id=11,
        ),
    )


class _Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.executions = []

    def execute(self, query, params):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return next(self.rows)


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return SimpleNamespace(cursor=lambda: self._cursor)

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_snapshot_hash_tamper_is_rejected():
    plan_json = splits._plan_to_json(_plan())
    payload_json = [{"walletId": SELLER_WALLET, "percentualValue": 60.0}]
    row = (
        20,
        "ASAAS_BOLETO_INSTALLMENT",
        "carne",
        "São João de Meriti",
        "sandbox",
        ROOT_WALLET,
        Decimal("100.00"),
        plan_json,
        payload_json,
        "0" * 64,
        splits._sha256_json(payload_json),
        "sealed",
    )

    with pytest.raises(
        splits.AsaasSplitValidationError,
        match="snapshot_split_hash_divergente",
    ):
        splits._snapshot_from_row(
            row,
            integration_id=10,
            expected_venda_id=20,
            expected_payment_method="ASAAS_BOLETO_INSTALLMENT",
            expected_context="carne",
            expected_unidade="São João de Meriti",
            expected_environment="sandbox",
            expected_account_wallet_id=ROOT_WALLET,
            expected_charge_value=Decimal("100.00"),
        )


def test_v2_snapshot_binds_receiver_identity_without_changing_remote_payload():
    identity = splits.AsaasReceiverIdentity(
        kind="pf",
        local_id=10,
        unidade="São João de Meriti",
        environment="sandbox",
        account_id="account-recipient",
        wallet_id=SELLER_WALLET,
        credential_ref="env:ASAAS_RECEIVER_SELLER",
    )
    plan = splits.AsaasSplitPlan(
        contexto="carne",
        schema_version=2,
        items=[
            splits.AsaasSplitItem(
                wallet_id=SELLER_WALLET,
                kind="percentual",
                user_id=10,
                percentual_value=Decimal("60"),
                receiver_identity=identity,
            )
        ],
    )

    plan_json = splits._plan_to_json(plan)
    payload = splits.to_asaas_payload(plan)

    assert plan_json["schema_version"] == 2
    assert plan_json["items"][0]["receiver_identity"]["credential_ref"] == identity.credential_ref
    assert "receiver_identity" not in payload[0]
    assert splits._json_to_plan(plan_json) == plan


def test_concurrent_seal_reuses_and_verifies_winning_snapshot():
    plan = _v2_plan()
    plan_json = splits._plan_to_json(plan)
    payload_json = splits.to_asaas_payload(plan)
    winning_row = (
        20,
        "ASAAS_BOLETO_INSTALLMENT",
        "carne",
        "São João de Meriti",
        "sandbox",
        ROOT_WALLET,
        Decimal("100.00"),
        plan_json,
        payload_json,
        splits._sha256_json(plan_json),
        splits._sha256_json(payload_json),
        "sealed",
    )
    cursor = _Cursor([None, winning_row])

    result = splits.seal_asaas_split_snapshot(
        cursor,
        integration_id=10,
        venda_id=20,
        payment_method="ASAAS_BOLETO_INSTALLMENT",
        unidade="São João de Meriti",
        environment="sandbox",
        account_wallet_id=ROOT_WALLET,
        charge_value=Decimal("100.00"),
        plan=plan,
        payload=payload_json,
    )

    assert result.plan == plan
    assert result.payload == payload_json
    assert "ON CONFLICT (integration_id) DO NOTHING" in cursor.executions[0][0]
    assert "FROM asaas_sale_split_plans" in cursor.executions[1][0]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("expected_venda_id", 21),
        ("expected_payment_method", "ASAAS_PIX_AUTOMATIC"),
        ("expected_charge_value", Decimal("99.99")),
    ],
)
def test_snapshot_rejects_divergent_sale_payment_or_charge(field, value):
    plan = _plan()
    plan_json = splits._plan_to_json(plan)
    payload_json = splits.to_asaas_payload(plan)
    row = (
        20,
        "ASAAS_BOLETO_INSTALLMENT",
        "carne",
        "São João de Meriti",
        "sandbox",
        ROOT_WALLET,
        Decimal("100.00"),
        plan_json,
        payload_json,
        splits._sha256_json(plan_json),
        splits._sha256_json(payload_json),
        "sealed",
    )
    expected = {
        "expected_venda_id": 20,
        "expected_payment_method": "ASAAS_BOLETO_INSTALLMENT",
        "expected_context": "carne",
        "expected_unidade": "São João de Meriti",
        "expected_environment": "sandbox",
        "expected_account_wallet_id": ROOT_WALLET,
        "expected_charge_value": Decimal("100.00"),
    }
    expected[field] = value

    with pytest.raises(
        splits.AsaasSplitValidationError,
        match="snapshot_split_escopo_divergente",
    ):
        splits._snapshot_from_row(row, integration_id=10, **expected)


def test_prepare_refuses_snapshot_after_remote_start():
    snapshot = make_snapshot()
    started = splits.AsaasSealedSplitSnapshot(
        **{
            **_sealed().__dict__,
            "lifecycle_state": "started",
        }
    )
    cursor = _Cursor([])

    with (
        patch.object(
            worker,
            "DatabaseConnection",
            return_value=_Connection(cursor),
        ),
        patch.object(
            worker,
            "load_asaas_split_snapshot",
            return_value=started,
        ),
    ):
        with pytest.raises(
            splits.AsaasSplitValidationError,
            match="snapshot_split_lifecycle_invalido",
        ):
            worker._prepare_asaas_split_snapshot(snapshot)


def test_prepare_reuses_existing_snapshot_without_rebuilding_rules():
    snapshot = make_snapshot()
    existing = _sealed()
    cursor = _Cursor([])

    with (
        patch.object(
            worker,
            "DatabaseConnection",
            return_value=_Connection(cursor),
        ),
        patch.object(
            worker,
            "load_asaas_split_snapshot",
            return_value=existing,
        ),
        patch.object(worker, "build_asaas_split_for_sale") as build,
        patch.object(worker, "seal_asaas_split_snapshot") as seal,
    ):
        payload, plan = worker._prepare_asaas_split_snapshot(
            snapshot,
            contexto="carne",
        )

    assert payload == existing.payload
    assert plan == existing.plan
    build.assert_not_called()
    seal.assert_not_called()


def test_split_preparation_failure_happens_before_remote_reservation():
    snapshot = make_snapshot()
    sdk = SimpleNamespace(
        account=SimpleNamespace(
            environment="sandbox",
            account_wallet_id=ROOT_WALLET,
        ),
        installments=SimpleNamespace(
            find_payments=lambda *_args: [],
            get_customer=lambda *_args: {
                "notificationDisabled": True,
            },
            create_installment=lambda *_args: pytest.fail(
                "POST remoto nao deveria ocorrer"
            ),
        ),
        __enter__=lambda self: self,
        __exit__=lambda *_args: None,
    )

    class _SDKContext:
        def __enter__(self):
            return sdk

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    with (
        patch.object(worker, "_claim_snapshot", return_value=snapshot),
        patch.object(
            worker.AsaasSalesSDK,
            "for_unit",
            return_value=_SDKContext(),
        ),
        patch.object(
            worker,
            "_prepare_asaas_split_snapshot",
            side_effect=splits.AsaasSplitValidationError(
                "configuracao_split_asaas_ausente"
            ),
        ),
        patch.object(
            worker,
            "is_asaas_sales_payment_method_environment_enabled",
            return_value=True,
        ),
        patch.object(worker, "_record_remote_attempt") as reserve,
        patch.object(worker, "_finish_safe_read_retry") as retry,
    ):
        worker.process_asaas_carne_job(snapshot.job_id)

    reserve.assert_not_called()
    retry.assert_called_once_with(
        snapshot,
        "asaas_split_plan_invalid",
    )


def test_sale_split_inputs_use_canonical_entry_signals():
    cursor = _Cursor(
        [
            (
                7,
                8,
                9,
                "Ortodontia",
                10,
                True,
            )
        ]
    )

    inputs = worker._load_sale_split_inputs(cursor, venda_id=20)

    query = cursor.executions[0][0]
    assert "LEFT JOIN pre_vendas_entradas AS pve" in query
    assert "pve.pre_venda_id = v.pre_venda_id" in query
    assert "v.valor_taxa_adesao IS NOT NULL" in query
    assert "v.valor_taxa_adesao > 0" in query
    assert "pve.valor_solicitado IS NOT NULL" in query
    assert "pve.valor_solicitado > 0" in query
    assert inputs["tem_entrada"] is True
