"""Composição offline de produção: gates reais, persistência/transporte fictícios.

Não é homologação Asaas nem E2E com banco. Exercita o loader compartilhado,
builder canônico e evidência autenticada juntos antes da reserva/POST do worker.
"""

from contextlib import ExitStack
from dataclasses import replace
import json
from unittest.mock import MagicMock, patch

import pytest

from app.asaas_sales_sdk.approval_evidence import AsaasSalesApprovalEvidenceReader
from app.services.asaas_account_approval_service import AsaasApprovalTarget
from app.services.asaas_receiver_identity_provider import AsaasReceiverIdentityProvider
from app.services import asaas_carne_provisioning_service as carne
from app.services import asaas_recurring_provisioning_service as recurring
from app.services import asaas_sales_config as config
from app.services import asaas_sales_preflight as preflight
from app.services import asaas_split_service as splits
from test_asaas_carne_provisioning_service import DatabaseContext, FakeCursor, remote_payments
from test_asaas_recurring_provisioning_service import SDKContext, make_snapshot


UNIT = "São João de Meriti"
METHODS = (carne.PAYMENT_METHOD_CODE, recurring.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE)
UNITS = ("Nova Iguaçu 1", "Vilar dos Teles", UNIT)


def _enable_production(monkeypatch):
    for name, value in {
        "ENVIRONMENT": "production", "ASAAS_ENVIRONMENT": "production",
        "ASAAS_SALES_ENABLED_UNITS": UNIT,
        "ASAAS_SALES_PRODUCTION_PROFILE_ENABLED": "true",
        "ASAAS_SALES_PRODUCTION_ENABLED_UNITS": UNIT,
        "ASAAS_SALES_PRODUCTION_CARNE_ENABLED_UNITS": UNIT,
        "ASAAS_SALES_PRODUCTION_CREDIT_CARD_RECURRENT_ENABLED_UNITS": UNIT,
        "ASAAS_SALES_CHECKOUT_CALLBACK_URL": "https://example.invalid/asaas/return",
    }.items():
        monkeypatch.setenv(name, value)


def _provider(tmp_path, monkeypatch):
    receivers = []
    for kind, local_id, wallet in (("pf", 10, "wallet-pf"), ("empresa", 1, "wallet-sjm")):
        name = f"ASAAS_SALES_RECEIVER_SECRET_COMPOSITION_{local_id}_{kind.upper()}"
        receivers.append({
            "kind": kind, "local_id": local_id, "unidade": UNIT,
            "environment": "production", "account_id": f"account-{kind}",
            "wallet_id": wallet, "credential_ref": f"env:{name}",
        })
        monkeypatch.setenv(name, f"offline-only-{kind}")
    path = tmp_path / "metadata-only.json"
    path.write_text(json.dumps({"schema_version": 1, "receivers": receivers}), encoding="utf-8")
    return AsaasReceiverIdentityProvider(str(path)), receivers


def _build_plan(provider, method):
    # A wallet legada de Sandbox e deliberadamente incompatível; produção
    # deve selecionar a identidade canônica, inclusive para o absorvedor PJ.
    cursor = FakeCursor(
        one=[(10, 3, "legacy-sandbox-wallet"), (1, 1), (60, "percentual", None, None, False)],
        many=[[(1, 0, "percentual", None, None, True)]],
    )
    with patch.object(splits, "_resolve_company_wallet", side_effect=AssertionError("legacy lookup forbidden")):
        plan = splits.build_asaas_split_for_sale(
            cursor, venda_id=20, unidade=UNIT, environment="production",
            tipo_odontograma_id=1, dentista_id=None, usuario_venda_id=10,
            valor_liquido_total=300, tem_entrada=False,
            contexto="carne" if method == carne.PAYMENT_METHOD_CODE else "cartao",
            account_wallet_id="wallet-sjm", remaining_installments=3,
            receiver_identity_resolver=lambda kind, local_id, unit, env, wallet: provider.resolve(
                kind=kind, local_id=local_id, unidade=unit, environment=env, wallet_id=wallet,
            ),
            receiver_identity_for_new_sale_resolver=lambda kind, local_id, unit, env: provider.resolve_for_new_sale(
                kind=kind, local_id=local_id, unidade=unit, environment=env,
            ),
        )
    assert plan.schema_version == 2
    assert plan.items[0].wallet_id == "wallet-pf"
    assert plan.items[0].receiver_identity.environment == "production"
    # A produção não lê wallet/estado legado por ambiente: a elegibilidade
    # continua limitada ao vendedor e à unidade, e a identidade vem do manifesto.
    seller_queries = [params for query, params in cursor.executions if "SELECT id, cargo_id" in query]
    assert seller_queries == [(10, UNIT)]
    return plan


def _load_production_snapshot(method):
    expected = make_snapshot(method, environment="production")
    fingerprint = carne.build_sale_financial_fingerprint(
        payment_method=method, total_value=expected.total_value,
        installment_count=len(expected.installments),
        installments=[(item.number, item.value, item.due_date) for item in expected.installments],
    )
    row = (
        10, 20, UNIT, "production", "wallet-sjm", "cus_technical", "integrado",
        expected.external_reference, "pendente", method, "nao_iniciado", 0,
        carne.LOCAL_SALE_PENDING_STATUS, expected.total_value, 3, fingerprint,
        10, UNIT, 10, None, None, 0,
    )
    cursor = FakeCursor(one=[row], many=[[
        (item.id, item.number, item.value, item.due_date, "Pendente", None, None)
        for item in expected.installments
    ], []])
    return carne._load_snapshot(
        cursor, job_id=5, claim_attempt=1, operation="provisionar_venda",
        integration_id=10, payment_method=method,
        resource_type="installment" if method == carne.PAYMENT_METHOD_CODE else "checkout",
    )


def _evidence_client(target, *, expired=False, wrong_wallet=False):
    client = MagicMock()
    responses = {
        "/myAccount/status/": {"id": target.account_id, "general": "APPROVED"},
        "/myAccount/commercialInfo/": {"commercialInfoExpiration": {"isExpired": expired}},
        "/wallets/": {
            "object": "list", "hasMore": False, "totalCount": 1, "limit": 10, "offset": 0,
            "data": [{"object": "wallet", "id": "wrong-wallet" if wrong_wallet else target.wallet_id}],
        },
    }
    client.get.side_effect = lambda path: MagicMock(json=lambda: responses[path])
    return client


def _worker_patches(stack, method, snapshot, sdk, plan):
    service = carne if method == carne.PAYMENT_METHOD_CODE else recurring
    stack.enter_context(patch.object(service, "_claim_snapshot", return_value=snapshot))
    stack.enter_context(patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk))
    # Somente fronteira de persistência do plano já selado; não mocka gates.
    stack.enter_context(patch.object(service, "_prepare_asaas_split_snapshot", return_value=(splits.to_asaas_payload(plan), plan)))
    mocks = {}
    for name in ("_record_remote_attempt", "_finish_safe_read_retry", "_finish_terminal", "_handoff_to_reconciliation", "_finish_existing_confirmation"):
        mocks[name] = stack.enter_context(patch.object(service, name))
    mocks["_record_remote_attempt"].return_value = "reserved"
    confirm = "_confirm_remote_payments" if service is carne else "_confirm_resource"
    mocks[confirm] = stack.enter_context(patch.object(service, confirm))
    return mocks


def _run(method):
    if method == carne.PAYMENT_METHOD_CODE:
        carne.process_asaas_carne_job(5)
    else:
        recurring.process_asaas_recurring_job(5, method)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("failure", [None, "expired", "wallet", "credential", "profile_off"])
def test_production_composition_real_guards_before_simulated_post(tmp_path, monkeypatch, method, failure):
    _enable_production(monkeypatch)
    provider, receivers = _provider(tmp_path, monkeypatch)
    plan = _build_plan(provider, method)
    snapshot = _load_production_snapshot(method)
    sdk = SDKContext()
    sdk.account.environment = "production"
    target = AsaasApprovalTarget(unidade=UNIT, environment="production", account_id=sdk.account.account_id, wallet_id="wallet-sjm")
    sdk.approval_evidence_reader = AsaasSalesApprovalEvidenceReader(_evidence_client(target), target)
    sdk.installments.get_customer.return_value = {"id": snapshot.customer_id, "notificationDisabled": False}
    sdk.installments.find_payments.return_value = []
    sdk.installments.create_installment.return_value = {"installment": "ins_technical"}
    sdk.installments.list_installment_payments.return_value = remote_payments()
    sdk.recurring.create_recurring_card_checkout.return_value = {"id": "checkout_offline", "status": "ACTIVE"}
    opened = []

    def client_factory(*, base_url, headers):
        receiver = next(row for row in receivers if headers["access_token"] == f"offline-only-{row['kind']}")
        receiver_target = AsaasApprovalTarget(unidade=UNIT, environment="production", account_id=receiver["account_id"], wallet_id=receiver["wallet_id"])
        client = _evidence_client(receiver_target, expired=failure == "expired", wrong_wallet=failure == "wallet")
        opened.append(client)
        return client

    if failure == "credential":
        monkeypatch.delenv(receivers[0]["credential_ref"].split(":", 1)[1])
    elif failure == "profile_off":
        monkeypatch.setenv("ASAAS_SALES_PRODUCTION_PROFILE_ENABLED", "false")
    with ExitStack() as stack:
        stack.enter_context(patch.object(carne, "_receiver_identity_provider", return_value=provider))
        stack.enter_context(patch("app.services.asaas_receiver_identity_provider.AsaasHttpClient", side_effect=client_factory))
        mocks = _worker_patches(stack, method, snapshot, sdk, plan)
        _run(method)
        create = sdk.installments.create_installment if method == carne.PAYMENT_METHOD_CODE else sdk.recurring.create_recurring_card_checkout
        if failure:
            mocks["_record_remote_attempt"].assert_not_called()
            create.assert_not_called()
            mocks["_finish_safe_read_retry"].assert_called_once()
        else:
            mocks["_record_remote_attempt"].assert_called_once_with(snapshot)
            create.assert_called_once()
            payload = create.call_args.args[0] if method == carne.PAYMENT_METHOD_CODE else create.call_args.kwargs
            assert payload["split"] == splits.to_asaas_payload(plan)
            confirm_name = "_confirm_remote_payments" if method == carne.PAYMENT_METHOD_CODE else "_confirm_resource"
            mocks[confirm_name].assert_called_once()
            # Replay confirmado continua sem novo POST após desligar rollout
            # e retirar credenciais, sem reescrever identidade histórica.
            monkeypatch.setenv("ASAAS_SALES_PRODUCTION_PROFILE_ENABLED", "false")
            monkeypatch.delenv(receivers[0]["credential_ref"].split(":", 1)[1])
            confirmed = replace(snapshot, remote_creation_state="confirmado", remote_attempt_count=1, remote_installment_id="remote_offline")
            with patch.object(carne if method == carne.PAYMENT_METHOD_CODE else recurring, "_claim_snapshot", return_value=confirmed):
                _run(method)
            create.assert_called_once()
            mocks["_record_remote_attempt"].assert_called_once()
            mocks["_finish_existing_confirmation"].assert_called_once_with(confirmed)
    assert all(client.close.call_count == 1 for client in opened)
    assert not sdk.recurring.create_pix_authorization.called


@pytest.mark.parametrize("unit", UNITS)
@pytest.mark.parametrize("method", METHODS + (recurring.PIX_AUTOMATIC_PAYMENT_METHOD_CODE, "ASAAS_ENTRY"))
def test_production_off_by_default_each_unit_and_method(monkeypatch, unit, method):
    for name in list(__import__("os").environ):
        if name.startswith("ASAAS_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert not config.is_asaas_sales_payment_method_environment_enabled(unit, "production", method)


def test_production_preflight_uses_canonical_pf_and_absorber_pj(tmp_path, monkeypatch):
    provider, _receivers = _provider(tmp_path, monkeypatch)
    cursor = FakeCursor(many=[[(10, UNIT, 3)], [(1,)]])
    rules = [
        splits.AsaasDomainSplitRule(wallet_id=None, user_id=10, cargo_id=3),
        splits.AsaasDomainSplitRule(wallet_id=None, empresa_id=1, absorbs_balance=True),
    ]
    with patch.object(preflight, "_load_asaas_domain_rules", return_value=rules):
        preflight._validate_production_receiver_identities(
            cursor, units=(UNIT,), account_targets=((UNIT, "production", "wallet-sjm"),),
            exclusions=(), provider=provider,
        )
    assert len(cursor.executions) == 2
    assert "asaas_wallet_id" not in cursor.executions[0][0]


def test_production_preflight_absorber_must_match_issuer(tmp_path, monkeypatch):
    provider, _receivers = _provider(tmp_path, monkeypatch)
    cursor = FakeCursor(many=[[(10, UNIT, 3)], [(1,)]])
    rules = [splits.AsaasDomainSplitRule(wallet_id=None, empresa_id=1, absorbs_balance=True)]
    with patch.object(preflight, "_load_asaas_domain_rules", return_value=rules):
        with pytest.raises(preflight.AsaasSalesPreflightError):
            preflight._validate_production_receiver_identities(
                cursor, units=(UNIT,), account_targets=((UNIT, "production", "another-root"),),
                exclusions=(), provider=provider,
            )


@pytest.mark.parametrize("company_absorbs,expected_reason", [
    (False, "absorvedor_externo_nao_suportado"),
    (True, "mais_de_um_absorvedor_de_saldo"),
])
def test_preflight_real_selector_rejects_pf_absorber_and_combined_absorbers(
    tmp_path, monkeypatch, company_absorbs, expected_reason,
):
    provider, _receivers = _provider(tmp_path, monkeypatch)
    cursor = FakeCursor(
        one=[(10, 3, "legacy-wallet"), (1, 1), (60, "percentual", None, None, True)],
        many=[[(10, UNIT, 3)], [(1,)], [(1, 0, "percentual", None, None, company_absorbs)]],
    )
    # No replacement of the runtime selector or shared absorber invariant.
    with pytest.raises(preflight.AsaasSalesPreflightError) as error:
        preflight._validate_production_receiver_identities(
            cursor, units=(UNIT,), account_targets=((UNIT, "production", "wallet-sjm"),),
            exclusions=(), provider=provider,
        )
    assert error.value.code == "account_configuration_invalid"
    assert str(error.value.__cause__) == expected_reason


def test_preflight_real_selector_preserves_effective_unit_precedence_and_limits(tmp_path, monkeypatch):
    provider, _receivers = _provider(tmp_path, monkeypatch)
    # The persistence boundary returns the specific-unit effective rules.
    # SQL assertions below guard the runtime selection of those rows; this
    # is not execution of PostgreSQL nor proof about production data.
    cursor = FakeCursor(
        one=[(10, 3, "legacy-wallet"), (1, 1), (60, "percentual", None, None, False)],
        many=[[(10, UNIT, 3)], [(1,)], [(1, 0, "percentual", None, None, True)]],
    )
    with patch.object(provider, "resolve_for_new_sale", wraps=provider.resolve_for_new_sale) as resolve:
        preflight._validate_production_receiver_identities(
            cursor, units=(UNIT,), account_targets=((UNIT, "production", "wallet-sjm"),),
            exclusions=(), provider=provider,
        )
    type_query, type_params = cursor.executions[1]
    assert "(r.unidade IS NULL OR r.unidade = %s)" in type_query
    assert type_params == (UNIT,)
    role_query, role_params = next((sql, params) for sql, params in cursor.executions if "FROM regras_split rs" in sql)
    assert "ORDER BY CASE WHEN rs.unidade = %s THEN 0 ELSE 1 END" in role_query
    assert "LIMIT 1" in role_query
    assert role_params == (1, 3, UNIT, UNIT)
    company_query, company_params = next((sql, params) for sql, params in cursor.executions if "FROM empresa_regras_split ers" in sql)
    assert "SELECT DISTINCT ON (ers.empresa_id)" in company_query
    assert "WHEN ers.unidade = %s THEN 0" in company_query
    assert "LIMIT %s" in company_query
    assert company_params == (UNIT, 1, UNIT, UNIT, 1)
    assert {call.kwargs["local_id"] for call in resolve.call_args_list} == {10, 1}


def _database_catalog_stubs(stack, cursor):
    # Database/catalog boundary only; production readiness remains real.
    database = stack.enter_context(patch.object(preflight, "DatabaseConnection", return_value=DatabaseContext(cursor)))
    for name in (
        "_validate_runtime_role", "_validate_tables_and_privileges", "_validate_sequences",
        "_validate_indexes", "_validate_functions", "_validate_sandbox_receiver_acl",
        "_validate_entry_snapshot_acl", "_validate_triggers", "_validate_constraints",
    ):
        stack.enter_context(patch.object(preflight, name))
    return database


def test_partial_production_readiness_keeps_only_selected_account_targets(tmp_path, monkeypatch):
    provider, _receivers = _provider(tmp_path, monkeypatch)
    cursor = FakeCursor(many=[[(10, UNIT, 3)], []])
    all_targets = tuple((unit, "production", "wallet-sjm" if unit == UNIT else f"wallet-offline-{index}") for index, unit in enumerate(UNITS))
    with ExitStack() as stack:
        database = _database_catalog_stubs(stack, cursor)
        preflight._validate_database(
            UNITS, readiness_units=(UNIT,), account_targets=all_targets,
            company_wallets={}, pf_exclusions=(), production_provider=provider,
        )
    database.assert_called_once_with(read_only=True)
    assert cursor.executions[0][1] == ([UNIT],)


@pytest.mark.parametrize("readiness_units", [(), (UNIT,)])
def test_production_exclusions_never_bypass_readiness_including_empty_health(
    tmp_path, monkeypatch, readiness_units,
):
    provider, _receivers = _provider(tmp_path, monkeypatch)
    cursor = FakeCursor()
    with ExitStack() as stack:
        _database_catalog_stubs(stack, cursor)
        readiness = stack.enter_context(patch.object(preflight, "_validate_production_receiver_identities"))
        with pytest.raises(preflight.AsaasSalesPreflightError) as error:
            preflight._validate_database(
                UNITS, readiness_units=readiness_units,
                account_targets=((UNIT, "production", "wallet-sjm"),), company_wallets={},
                pf_exclusions=(preflight._PfExclusion(user_id=10, unidade=UNIT),),
                production_provider=provider,
            )
    assert error.value.code == "pf_exclusion_configuration_invalid"
    readiness.assert_not_called()
    assert cursor.executions == []
