"""Contratos fail-closed do provisionamento de subcontas Asaas.

Os testes exercitam o fluxo duravel ``reserved -> started -> confirmed |
rejected | uncertain``, a elegibilidade PF por unidade/cargo e o recorte
defensivo do manager HTTP. Nenhum teste abre conexao real com banco ou Asaas.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.asaas_sdk.exceptions import (
    AsaasAPIError,
    AsaasConnectionError,
    AsaasValidationError,
)
from app.asaas_sales_sdk.account_manager import AsaasSalesAccountManager
from app.services import asaas_account_provisioning_service as service


USER_ID = 700
UNIT = "São João de Meriti"


class FakeCursor:
    def __init__(self, fetches=()):
        self._fetches = list(fetches)
        self.executions: list[tuple[str, object]] = []

    def execute(self, query, params=None):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return self._fetches.pop(0) if self._fetches else None


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self._cursor


def _tuple_user_row(
    *,
    unidade=UNIT,
    cargo_id=3,
    cpf="111.111.111-11",
    email="maria@example.com",
    wallet=None,
    account=None,
    status=None,
):
    """Linha realista na ordem exata do SELECT de ``_load_eligible_user``."""
    return (
        USER_ID,
        unidade,
        cargo_id,
        "Maria Comercial",
        cpf,
        email,
        "55",
        "21",
        "988887766",
        "Rua das Flores",
        "100",
        "Centro",
        "25555000",
        date(1990, 1, 15),
        wallet,
        account,
        status,
    )


def _user(**overrides):
    values = {
        "user_id": USER_ID,
        "unidade": UNIT,
        "cargo_id": 3,
        "nome": "Maria Comercial",
        "cpf": "11111111111",
        "email": "maria@example.com",
        "mobile_phone": "+5521988887766",
        "address": "Rua das Flores",
        "address_number": "100",
        "province": "Centro",
        "postal_code": "25555000",
        "birth_date": "1990-01-15",
        "wallet_id": None,
        "account_id": None,
        "integration_status": None,
    }
    values.update(overrides)
    return service._UserData(**values)


def _patch_enabled_unit(monkeypatch):
    monkeypatch.setattr(
        service,
        "canonicalize_asaas_sales_unit",
        lambda value: UNIT if str(value or "").strip() else None,
    )
    monkeypatch.setattr(
        service,
        "is_asaas_sales_subaccount_provisioning_enabled",
        lambda unidade: True,
    )
    monkeypatch.setattr(
        service,
        "is_asaas_sales_pf_user_excluded",
        lambda user_id, unidade: False,
    )


class StatefulSDKContext:
    """Contexto que falha o teste se o POST ocorrer depois do fechamento."""

    def __init__(self, *, created=None, error=None, environment="sandbox"):
        self.created = created or {
            "id": "acc_new",
            "walletId": "wallet_new",
            "apiKey": "test-api-key",
        }
        self.error = error
        self.open = False
        self.enter_count = 0
        self.exit_count = 0
        self.create_count = 0
        self.account = SimpleNamespace(
            environment=environment,
            unidade=UNIT,
        )
        self.accounts = SimpleNamespace(create_account=self.create_account)

    def __enter__(self):
        assert not self.open
        self.open = True
        self.enter_count += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        assert self.open
        self.open = False
        self.exit_count += 1
        return False

    def create_account(self, payload):
        assert self.open, "POST /accounts ocorreu com SDK fechado"
        assert payload["cpfCnpj"] == "11111111111"
        self.create_count += 1
        if self.error is not None:
            raise self.error
        return self.created


def _patch_happy_path_dependencies(monkeypatch, context):
    events: list[str] = []
    reservation = service._Reservation(
        user=_user(),
        attempt_token="4e637349-5383-44b0-bab1-32a69a3aac1d",
        payload=service.prepare_account_payload(
            service._build_account_payload(_user())
        ),
    )
    _patch_enabled_unit(monkeypatch)
    monkeypatch.setattr(service, "_precheck_target", lambda **kwargs: None)
    monkeypatch.setattr(
        service,
        "_reserve_attempt",
        lambda **kwargs: events.append("reserved") or reservation,
    )
    monkeypatch.setattr(
        service,
        "_transition_attempt_to_started",
        lambda **kwargs: events.append("started"),
    )
    monkeypatch.setattr(
        service,
        "encrypt_api_key",
        lambda value: events.append("encrypted") or "ciphertext",
    )
    monkeypatch.setattr(
        service,
        "_confirm_attempt",
        lambda **kwargs: events.append("confirmed"),
    )
    monkeypatch.setattr(
        service,
        "AsaasSalesSDK",
        SimpleNamespace(for_unit=lambda unidade: context),
    )
    return events


def test_load_eligible_user_tuple_preserves_select_cardinality_and_order():
    cursor = FakeCursor([_tuple_user_row()])

    user = service._load_eligible_user(
        cursor,
        user_id=USER_ID,
        expected_unit=UNIT,
        lock=True,
    )

    assert user == _user()
    query, params = cursor.executions[0]
    selected_columns = query.split("SELECT", 1)[1].split("FROM users", 1)[0]
    assert selected_columns.count("phone_country_code") == 1
    assert len(_tuple_user_row()) == 17
    assert "unidade = %s" in query
    assert "cargo_id IN %s" in query
    assert "status_aprovacao = 'aprovado'" in query
    assert "REGEXP_REPLACE" in query
    assert ") = 11" in query
    assert query.endswith("FOR UPDATE")
    assert params == (USER_ID, UNIT, (3, 4))


def test_precheck_inelegivel_happens_before_sdk(monkeypatch):
    _patch_enabled_unit(monkeypatch)
    monkeypatch.setattr(
        service,
        "_precheck_target",
        lambda **kwargs: service.ProvisionResult(
            status="erro_validacao",
            mensagem="Usuário não encontrado ou inelegível para subconta PF.",
        ),
    )
    monkeypatch.setattr(
        service,
        "AsaasSalesSDK",
        SimpleNamespace(
            for_unit=lambda unidade: pytest.fail("SDK não deve ser instanciado")
        ),
    )

    result = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert result.status == "erro_validacao"


@pytest.mark.parametrize("lifecycle_state", ["started", "uncertain"])
def test_existing_attempt_blocks_retry_during_read_only_precheck(
    monkeypatch,
    lifecycle_state,
):
    cursor = FakeCursor([_tuple_user_row(), (lifecycle_state, False)])
    calls = []

    def factory(*args, **kwargs):
        calls.append(kwargs)
        return FakeConnection(cursor)

    monkeypatch.setattr(service, "DatabaseConnection", factory)

    result = service._precheck_target(user_id=USER_ID, expected_unit=UNIT)

    assert result is not None
    assert result.status == "erro_integracao"
    assert "reconciliação manual" in (result.mensagem or "")
    assert calls == [{"read_only": True}]
    assert "FROM asaas_account_provision_attempts" in cursor.executions[-1][0]


def test_stale_reserved_attempt_can_continue_after_read_only_precheck(
    monkeypatch,
):
    cursor = FakeCursor([_tuple_user_row(), ("reserved", True)])
    monkeypatch.setattr(
        service,
        "DatabaseConnection",
        lambda *args, **kwargs: FakeConnection(cursor),
    )

    result = service._precheck_target(user_id=USER_ID, expected_unit=UNIT)

    assert result is None
    query, params = cursor.executions[-1]
    assert "lifecycle_state <> 'rejected'" in query
    assert "reusable_stale_reservation" in query
    assert params == (UNIT, service._RESERVED_STALE_AFTER_SECONDS, USER_ID)


def test_manifest_exclusion_blocks_before_database_and_sdk(monkeypatch):
    _patch_enabled_unit(monkeypatch)
    monkeypatch.setattr(
        service,
        "is_asaas_sales_pf_user_excluded",
        lambda user_id, unidade: True,
    )
    monkeypatch.setattr(
        service,
        "DatabaseConnection",
        lambda *args, **kwargs: pytest.fail("Banco não deve ser acessado"),
    )
    monkeypatch.setattr(
        service,
        "AsaasSalesSDK",
        SimpleNamespace(
            for_unit=lambda unidade: pytest.fail("SDK não deve ser instanciado")
        ),
    )

    result = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert result.status == "erro_validacao"
    assert "excluído" in (result.mensagem or "")


def test_success_keeps_sdk_open_for_post_and_closes_exactly_once(monkeypatch):
    context = StatefulSDKContext()
    events = _patch_happy_path_dependencies(monkeypatch, context)

    result = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert result == service.ProvisionResult(
        status="sucesso",
        wallet_id="wallet_new",
        account_id="acc_new",
        integration_status="integrado",
    )
    assert events == ["reserved", "started", "encrypted", "confirmed"]
    assert context.create_count == 1
    assert context.enter_count == 1
    assert context.exit_count == 1
    assert context.open is False
    assert "api_key" not in result.__dict__


def test_post_exception_closes_once_marks_uncertain_and_retry_is_fail_closed(
    monkeypatch,
    caplog,
):
    sensitive_remote_text = "timeout cpf=11111111111 key=test-secret"
    context = StatefulSDKContext(
        error=AsaasConnectionError(sensitive_remote_text)
    )
    _patch_happy_path_dependencies(monkeypatch, context)
    uncertain = []
    monkeypatch.setattr(
        service,
        "_mark_uncertain_safely",
        lambda **kwargs: uncertain.append(kwargs),
    )

    first = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert first.status == "erro_integracao"
    assert context.create_count == 1
    assert context.enter_count == context.exit_count == 1
    assert uncertain == [
        {
            "user_id": USER_ID,
            "expected_unit": UNIT,
            "attempt_token": "4e637349-5383-44b0-bab1-32a69a3aac1d",
            "user_status": "erro_integracao",
            "error_code": "provider_connection_error",
        }
    ]
    assert sensitive_remote_text not in caplog.text

    monkeypatch.setattr(
        service,
        "_precheck_target",
        lambda **kwargs: service.ProvisionResult(
            status="erro_integracao",
            mensagem=service._MANUAL_RECONCILIATION_MESSAGE,
        ),
    )
    second = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert second.status == "erro_integracao"
    assert "reconciliação manual" in (second.mensagem or "")
    assert context.create_count == 1
    assert context.enter_count == context.exit_count == 1


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (
            AsaasAPIError(400, detail="request_rejected"),
            "erro_validacao",
            "provider_rejection_400",
        ),
        (
            AsaasAPIError(422, detail="request_rejected"),
            "erro_validacao",
            "provider_rejection_422",
        ),
        (
            AsaasAPIError(429, detail="request_rejected"),
            "erro_integracao",
            "provider_rate_limit_429",
        ),
    ],
)
def test_definitive_remote_http_rejection_releases_explicit_retry(
    monkeypatch,
    error,
    expected_status,
    expected_code,
):
    context = StatefulSDKContext(error=error)
    _patch_happy_path_dependencies(monkeypatch, context)
    rejected = []
    uncertain = []
    monkeypatch.setattr(
        service,
        "_mark_rejected_safely",
        lambda **kwargs: rejected.append(kwargs),
    )
    monkeypatch.setattr(
        service,
        "_mark_uncertain_safely",
        lambda **kwargs: uncertain.append(kwargs),
    )

    result = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert result.status == "erro_integracao"
    assert context.create_count == 1
    assert uncertain == []
    assert rejected == [
        {
            "user_id": USER_ID,
            "expected_unit": UNIT,
            "attempt_token": "4e637349-5383-44b0-bab1-32a69a3aac1d",
            "user_status": expected_status,
            "error_code": expected_code,
        }
    ]


def test_remote_validation_422_is_rejected_but_local_validation_is_uncertain(
    monkeypatch,
):
    remote_error = AsaasValidationError(["invalid_cpf_cnpj"])
    remote_error.status_code = 422
    remote_context = StatefulSDKContext(error=remote_error)
    _patch_happy_path_dependencies(monkeypatch, remote_context)
    rejected = []
    uncertain = []
    monkeypatch.setattr(
        service,
        "_mark_rejected_safely",
        lambda **kwargs: rejected.append(kwargs),
    )
    monkeypatch.setattr(
        service,
        "_mark_uncertain_safely",
        lambda **kwargs: uncertain.append(kwargs),
    )

    remote_result = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert remote_result.status == "erro_kyc"
    assert rejected[0]["error_code"] == "provider_validation_422"
    assert uncertain == []

    local_context = StatefulSDKContext(
        error=AsaasValidationError(["account_payload_invalid"])
    )
    _patch_happy_path_dependencies(monkeypatch, local_context)
    rejected.clear()
    uncertain.clear()

    local_result = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert local_result.status == "erro_validacao"
    assert rejected == []
    assert uncertain[0]["error_code"] == "local_validation_after_start"


@pytest.mark.parametrize(
    ("created", "expected_error"),
    [
        (
            {"id": "acc_new", "walletId": "wallet_new"},
            "incomplete_provider_response",
        ),
        (
            {"id": "acc_new", "walletId": "wallet_new", "apiKey": ""},
            "incomplete_provider_response",
        ),
    ],
)
def test_incomplete_remote_response_is_uncertain(
    monkeypatch,
    created,
    expected_error,
):
    context = StatefulSDKContext(created=created)
    _patch_happy_path_dependencies(monkeypatch, context)
    uncertain = []
    monkeypatch.setattr(
        service,
        "_mark_uncertain_safely",
        lambda **kwargs: uncertain.append(kwargs),
    )

    result = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert result.status == "erro_integracao"
    assert uncertain[0]["expected_unit"] == UNIT
    assert uncertain[0]["error_code"] == expected_error
    assert context.enter_count == context.exit_count == 1


def test_encryption_or_confirmation_failure_never_authorizes_new_post(
    monkeypatch,
):
    context = StatefulSDKContext()
    _patch_happy_path_dependencies(monkeypatch, context)
    monkeypatch.setattr(
        service,
        "encrypt_api_key",
        lambda value: (_ for _ in ()).throw(RuntimeError("cipher unavailable")),
    )
    uncertain = []
    monkeypatch.setattr(
        service,
        "_mark_uncertain_safely",
        lambda **kwargs: uncertain.append(kwargs),
    )

    result = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert result.status == "erro_integracao"
    assert uncertain[0]["error_code"] == "secret_encryption_error"
    assert uncertain[0]["wallet_id"] == "wallet_new"
    assert uncertain[0]["account_id"] == "acc_new"
    assert context.create_count == 1
    assert context.enter_count == context.exit_count == 1


def test_confirmation_failure_marks_remote_ids_uncertain(monkeypatch):
    context = StatefulSDKContext()
    _patch_happy_path_dependencies(monkeypatch, context)
    monkeypatch.setattr(
        service,
        "_confirm_attempt",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("commit unknown")),
    )
    uncertain = []
    monkeypatch.setattr(
        service,
        "_mark_uncertain_safely",
        lambda **kwargs: uncertain.append(kwargs),
    )

    result = service.provision_asaas_account_for_user(
        USER_ID,
        expected_unit=UNIT,
    )

    assert result.status == "erro_integracao"
    assert uncertain[0]["error_code"] == "confirmation_persistence_error"
    assert uncertain[0]["wallet_id"] == "wallet_new"
    assert uncertain[0]["account_id"] == "acc_new"
    assert context.create_count == 1


def test_reservation_uses_lock_random_token_and_reserved_zero_attempts(
    monkeypatch,
):
    cursor = FakeCursor([_tuple_user_row(), None, (91,)])
    monkeypatch.setattr(
        service,
        "DatabaseConnection",
        lambda *args, **kwargs: FakeConnection(cursor),
    )

    result = service._reserve_attempt(
        user_id=USER_ID,
        expected_unit=UNIT,
        environment="sandbox",
    )

    assert isinstance(result, service._Reservation)
    UUID(result.attempt_token)
    assert "pg_advisory_xact_lock" in cursor.executions[0][0]
    assert cursor.executions[0][1] == (
        f"asaas-account-provisioning:{USER_ID}",
    )
    insert, params = cursor.executions[-1]
    assert "lifecycle_state" in insert
    assert "'reserved', 0" in insert
    assert "ON CONFLICT DO NOTHING" in insert
    assert params[:3] == (USER_ID, UNIT, "sandbox")
    assert params[3] == result.attempt_token
    assert result.payload["cpfCnpj"] == "11111111111"


def test_strict_payload_validation_happens_before_reservation(monkeypatch):
    cursor = FakeCursor([_tuple_user_row(email="maria@localhost")])
    monkeypatch.setattr(
        service,
        "DatabaseConnection",
        lambda *args, **kwargs: FakeConnection(cursor),
    )

    with pytest.raises(AsaasValidationError) as raised:
        service._reserve_attempt(
            user_id=USER_ID,
            expected_unit=UNIT,
            environment="sandbox",
        )

    assert "account_email_invalid" in raised.value.errors
    assert all(
        "INSERT INTO asaas_account_provision_attempts" not in query
        for query, _params in cursor.executions
    )
    assert all(
        "lifecycle_state = 'started'" not in query
        for query, _params in cursor.executions
    )


def test_stale_reserved_attempt_reuses_token_without_new_insert(monkeypatch):
    stale_token = "b4d6219a-e757-4fb5-a841-7729c6d37e90"
    cursor = FakeCursor(
        [_tuple_user_row(), (stale_token, "reserved", True), (91,)]
    )
    monkeypatch.setattr(
        service,
        "DatabaseConnection",
        lambda *args, **kwargs: FakeConnection(cursor),
    )

    result = service._reserve_attempt(
        user_id=USER_ID,
        expected_unit=UNIT,
        environment="sandbox",
    )

    assert isinstance(result, service._Reservation)
    assert result.attempt_token == stale_token
    assert any(
        "SET updated_at = NOW()" in query
        and "lifecycle_state = 'reserved'" in query
        for query, _params in cursor.executions
    )
    assert all(
        "INSERT INTO asaas_account_provision_attempts" not in query
        for query, _params in cursor.executions
    )


def test_rejected_history_does_not_block_new_explicit_attempt(monkeypatch):
    cursor = FakeCursor([_tuple_user_row(), None, (92,)])
    monkeypatch.setattr(
        service,
        "DatabaseConnection",
        lambda *args, **kwargs: FakeConnection(cursor),
    )

    result = service._reserve_attempt(
        user_id=USER_ID,
        expected_unit=UNIT,
        environment="sandbox",
    )

    assert isinstance(result, service._Reservation)
    active_query = cursor.executions[2][0]
    insert_query = cursor.executions[3][0]
    assert "lifecycle_state <> 'rejected'" in active_query
    assert "ON CONFLICT DO NOTHING" in insert_query


def test_started_uncertain_and_confirmed_transitions_are_guarded_and_scoped(
    monkeypatch,
):
    started_cursor = FakeCursor([(1,)])
    monkeypatch.setattr(
        service,
        "DatabaseConnection",
        lambda *args, **kwargs: FakeConnection(started_cursor),
    )
    service._transition_attempt_to_started(
        user_id=USER_ID,
        attempt_token="opaque-token",
    )
    started_sql, started_params = started_cursor.executions[0]
    assert "lifecycle_state = 'started'" in started_sql
    assert "remote_attempt_count = 1" in started_sql
    assert "lifecycle_state = 'reserved'" in started_sql
    assert "remote_attempt_count = 0" in started_sql
    assert started_params == (USER_ID, "opaque-token")

    uncertain_cursor = FakeCursor([(1,), (USER_ID,)])
    monkeypatch.setattr(
        service,
        "DatabaseConnection",
        lambda *args, **kwargs: FakeConnection(uncertain_cursor),
    )
    service._mark_attempt_uncertain(
        user_id=USER_ID,
        expected_unit=UNIT,
        attempt_token="opaque-token",
        user_status="erro_integracao",
        error_code="provider_connection_error",
        wallet_id="wallet_new",
        account_id="acc_new",
    )
    uncertain_sql, _ = uncertain_cursor.executions[0]
    user_sql, user_params = uncertain_cursor.executions[1]
    assert "lifecycle_state = 'uncertain'" in uncertain_sql
    assert "lifecycle_state = 'started'" in uncertain_sql
    assert "remote_attempt_count = 1" in uncertain_sql
    assert "unidade = %s" in user_sql
    assert "cargo_id IN %s" in user_sql
    assert "status_aprovacao = 'aprovado'" in user_sql
    assert "REGEXP_REPLACE" in user_sql
    assert user_params == (
        "wallet_new",
        "acc_new",
        "erro_integracao",
        USER_ID,
        UNIT,
        (3, 4),
    )

    confirmed_cursor = FakeCursor([(USER_ID,), (1,)])
    monkeypatch.setattr(
        service,
        "DatabaseConnection",
        lambda *args, **kwargs: FakeConnection(confirmed_cursor),
    )
    service._confirm_attempt(
        user_id=USER_ID,
        expected_unit=UNIT,
        attempt_token="opaque-token",
        wallet_id="wallet_new",
        account_id="acc_new",
        encrypted_api_key="ciphertext",
    )
    user_sql, user_params = confirmed_cursor.executions[0]
    confirmed_sql, confirmed_params = confirmed_cursor.executions[1]
    assert "unidade = %s" in user_sql
    assert "cargo_id IN %s" in user_sql
    assert "status_aprovacao = 'aprovado'" in user_sql
    assert "REGEXP_REPLACE" in user_sql
    assert user_params == (
        "wallet_new",
        "acc_new",
        "ciphertext",
        USER_ID,
        UNIT,
        (3, 4),
    )
    assert "lifecycle_state = 'confirmed'" in confirmed_sql
    assert "lifecycle_state = 'started'" in confirmed_sql
    assert "remote_attempt_count = 1" in confirmed_sql
    assert confirmed_params == (USER_ID, "opaque-token")

    rejected_cursor = FakeCursor([(1,), (USER_ID,)])
    monkeypatch.setattr(
        service,
        "DatabaseConnection",
        lambda *args, **kwargs: FakeConnection(rejected_cursor),
    )
    service._mark_attempt_rejected(
        user_id=USER_ID,
        expected_unit=UNIT,
        attempt_token="opaque-token",
        user_status="erro_validacao",
        error_code="provider_rejection_422",
    )
    rejected_sql, rejected_params = rejected_cursor.executions[0]
    rejected_user_sql, rejected_user_params = rejected_cursor.executions[1]
    assert "lifecycle_state = 'rejected'" in rejected_sql
    assert "remote_rejected_at = NOW()" in rejected_sql
    assert "lifecycle_state = 'started'" in rejected_sql
    assert rejected_params == (
        "provider_rejection_422",
        USER_ID,
        "opaque-token",
    )
    assert "asaas_wallet_id" in rejected_user_sql
    assert "asaas_account_id" in rejected_user_sql
    assert rejected_user_params == (
        "erro_validacao",
        USER_ID,
        UNIT,
        (3, 4),
    )


@pytest.mark.parametrize(
    ("wallet", "account", "status", "expected_status"),
    [
        ("wallet_old", "account_old", "integrado", "existente"),
        ("wallet_partial", None, None, "erro_integracao"),
        (None, "account_partial", "erro_validacao", "erro_integracao"),
    ],
)
def test_existing_or_partial_remote_identity_is_fail_closed(
    wallet,
    account,
    status,
    expected_status,
):
    result = service._existing_or_partial_result(
        _user(
            wallet_id=wallet,
            account_id=account,
            integration_status=status,
        )
    )

    assert result is not None
    assert result.status == expected_status
    if expected_status == "erro_integracao":
        assert "reconciliação manual" in (result.mensagem or "")


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _valid_create_payload(**overrides):
    payload = {
        "name": "Maria Comercial",
        "email": "maria@example.com",
        "cpfCnpj": "11111111111",
        "mobilePhone": "5521988887766",
        "incomeValue": 5000.00,
        "address": "Rua das Flores",
        "addressNumber": "100",
        "province": "Centro",
        "postalCode": "25555000",
        "birthDate": "1990-01-15",
    }
    payload.update(overrides)
    return payload


def _no_http_client():
    return SimpleNamespace(
        post=lambda *args, **kwargs: pytest.fail("HTTP não deveria ser chamado"),
        get=lambda *args, **kwargs: pytest.fail("HTTP não deveria ser chamado"),
    )


def test_account_manager_rejects_extra_field_and_invalid_document():
    manager = AsaasSalesAccountManager(_no_http_client())

    with pytest.raises(AsaasValidationError) as extra:
        manager.create_account(
            _valid_create_payload(
                creditCard={"number": "4111111111111111"}
            )
        )
    assert "account_payload_invalid" in extra.value.errors

    with pytest.raises(AsaasValidationError) as invalid_cpf:
        manager.create_account(_valid_create_payload(cpfCnpj="1234567890"))
    assert "account_cpf_cnpj_invalid" in invalid_cpf.value.errors


def test_account_manager_normalizes_document_and_sanitizes_created_response():
    captured = {}
    client = SimpleNamespace()

    def post(path, **kwargs):
        captured["path"] = path
        captured["json"] = kwargs["json"]
        return FakeResponse(
            {
                "id": "acc_new",
                "walletId": "wallet_new",
                "apiKey": "test-key",
                "password": "must-not-leak",
                "customer": {"cpf": "must-not-leak"},
            }
        )

    client.post = post
    manager = AsaasSalesAccountManager(client)

    result = manager.create_account(
        _valid_create_payload(cpfCnpj="111.111.111-11")
    )

    assert captured["path"] == "/accounts"
    assert captured["json"]["cpfCnpj"] == "11111111111"
    assert result == {
        "id": "acc_new",
        "walletId": "wallet_new",
        "apiKey": "test-key",
    }


def test_account_manager_rejects_non_sandbox_url_and_missing_key():
    client = SimpleNamespace(
        post=lambda *args, **kwargs: FakeResponse(
            {
                "id": "acc_new",
                "walletId": "wallet_new",
                "apiKey": "test-key",
                "invoiceUrl": "https://www.asaas.com/checkout/production",
            }
        )
    )
    manager = AsaasSalesAccountManager(client)

    with pytest.raises(AsaasAPIError) as invalid_url:
        manager.create_account(_valid_create_payload())
    assert invalid_url.value.status_code == 502
    assert invalid_url.value.detail == "invalid_account_url"

    client.post = lambda *args, **kwargs: FakeResponse(
        {"id": "acc_new", "walletId": "wallet_new"}
    )
    with pytest.raises(AsaasAPIError) as missing_key:
        manager.create_account(_valid_create_payload())
    assert missing_key.value.status_code == 502
    assert "api_key" in missing_key.value.detail


@pytest.mark.parametrize(
    ("kwargs", "error_code"),
    [
        ({"limit": 0}, "account_list_limit_invalid"),
        ({"limit": 101}, "account_list_limit_invalid"),
        ({"limit": True}, "account_list_limit_invalid"),
        ({"offset": -1}, "account_list_offset_invalid"),
        ({"offset": True}, "account_list_offset_invalid"),
    ],
)
def test_account_manager_rejects_invalid_pagination(kwargs, error_code):
    manager = AsaasSalesAccountManager(_no_http_client())

    with pytest.raises(AsaasValidationError) as raised:
        manager.list_accounts(**kwargs)

    assert error_code in raised.value.errors


def test_account_manager_list_and_get_return_only_safe_summary():
    client = SimpleNamespace()

    def get(path, **kwargs):
        if path == "/accounts":
            assert kwargs["params"] == {"limit": 20, "offset": 0}
            return FakeResponse(
                {
                    "data": [
                        {
                            "id": "acc_1",
                            "walletId": "wallet_1",
                            "status": "ACTIVE",
                            "email": "must-not-leak@example.com",
                            "cpf": "must-not-leak",
                        }
                    ],
                    "totalCount": 1,
                }
            )
        return FakeResponse(
            {
                "id": "acc_1",
                "walletId": "wallet_1",
                "status": "ACTIVE",
                "apiKey": "must-not-leak",
            }
        )

    client.get = get
    manager = AsaasSalesAccountManager(client)

    assert manager.list_accounts() == {
        "data": [
            {"id": "acc_1", "walletId": "wallet_1", "status": "ACTIVE"}
        ],
        "totalCount": 1,
    }
    assert manager.get_account("acc_1") == {
        "id": "acc_1",
        "walletId": "wallet_1",
        "status": "ACTIVE",
    }


def test_account_manager_rejects_invalid_account_id_before_get():
    manager = AsaasSalesAccountManager(_no_http_client())

    with pytest.raises(AsaasValidationError) as raised:
        manager.get_account("acc com espaço!")

    assert "account_id_invalid" in raised.value.errors
