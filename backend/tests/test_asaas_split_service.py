"""Contratos economicos e SQL do alocador exclusivo do Asaas."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services import asaas_split_service as service


ROOT_WALLET = "wallet-conta-emissora"
SELLER_WALLET = "wallet-comercial"
MANAGER_WALLET = "wallet-gerente"


class RecordingCursor:
    def __init__(self, responses=()):
        self.responses = iter(responses)
        self.current = None
        self.executions: list[tuple[str, tuple]] = []

    def execute(self, query, params):
        normalized = " ".join(query.split())
        self.executions.append((normalized, tuple(params)))
        self.current = next(self.responses, None)

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current[0] if self.current else None
        return self.current

    def fetchall(self):
        if isinstance(self.current, list):
            return self.current
        return [] if self.current is None else [self.current]


def _rule(
    wallet_id,
    *,
    percentage=None,
    fixed=None,
    cargo_id=3,
    user_id=10,
    cycles=None,
    absorber=False,
):
    return service.AsaasDomainSplitRule(
        wallet_id=wallet_id,
        cargo_id=cargo_id,
        user_id=user_id,
        percentual_value=(
            Decimal(str(percentage)) if percentage is not None else None
        ),
        fixed_value=Decimal(str(fixed)) if fixed is not None else None,
        cycles_to_participate=cycles,
        absorbs_balance=absorber,
    )


def _build(monkeypatch, rules, **overrides):
    monkeypatch.setattr(
        service,
        "_load_asaas_domain_rules",
        lambda _cursor, **_kwargs: list(rules),
    )
    kwargs = {
        "venda_id": 42,
        "unidade": "São João de Meriti",
        "environment": "sandbox",
        "tipo_odontograma_id": 7,
        "dentista_id": None,
        "usuario_venda_id": 10,
        "valor_liquido_total": Decimal("1000.00"),
        "tem_entrada": False,
        "contexto": "carne",
        "account_wallet_id": ROOT_WALLET,
        "remaining_installments": 4,
    }
    kwargs.update(overrides)
    return service.build_asaas_split_for_sale(object(), **kwargs)


@pytest.mark.parametrize("tipo_odontograma_id", (1, 2))
def test_sandbox_ni_rejects_blocked_type_before_loading_split_rules(
    tipo_odontograma_id,
):
    cursor = RecordingCursor()

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="asaas_sandbox_ni_odontogram_type_unavailable",
    ):
        service.build_asaas_split_for_sale(
            cursor,
            venda_id=42,
            unidade="NI1",
            environment="sandbox",
            tipo_odontograma_id=tipo_odontograma_id,
            dentista_id=None,
            usuario_venda_id=10,
            valor_liquido_total=Decimal("1000.00"),
            tem_entrada=False,
            account_wallet_id=ROOT_WALLET,
        )

    assert cursor.executions == []


def test_mixed_percentage_and_fixed_are_allocated_without_redistribution(
    monkeypatch,
):
    plan = _build(
        monkeypatch,
        [
            _rule(SELLER_WALLET, percentage=50),
            _rule(
                MANAGER_WALLET,
                fixed=25,
                cargo_id=4,
                user_id=11,
                cycles=2,
            ),
            _rule(
                ROOT_WALLET,
                cargo_id=4,
                user_id=12,
                absorber=True,
            ),
        ],
    )

    assert service.to_asaas_payload(plan) == [
        {"walletId": SELLER_WALLET, "percentualValue": 50.0},
        {"walletId": MANAGER_WALLET, "totalFixedValue": 50.0},
    ]
    assert plan.absorber is not None
    assert plan.absorber.absorbed_value == Decimal("450.00")
    assert all("absorbBalance" not in item for item in service.to_asaas_payload(plan))


def test_sandbox_binds_pf_from_new_identity_not_legacy_wallet(monkeypatch):
    # The loader intentionally supplies no sandbox wallet.  A stale value in
    # users.asaas_wallet_id therefore cannot influence the resulting split.
    plan = _build(
        monkeypatch,
        [_rule(None, percentage=100)],
        receiver_identity_for_new_sale_resolver=lambda kind, local_id, unidade, environment: service.AsaasReceiverIdentity(
            kind, local_id, unidade, environment, "account-sandbox", "wallet-link", "sandbox-link:7"
        ),
        receiver_identity_resolver=lambda kind, local_id, unidade, environment, wallet: service.AsaasReceiverIdentity(
            kind, local_id, unidade, environment, "account-sandbox", wallet, "sandbox-link:7"
        ),
    )
    assert service.to_asaas_payload(plan) == [{"walletId": "wallet-link", "percentualValue": 100.0}]


def test_entry_uses_fixed_value_and_carne_uses_total_fixed_value(monkeypatch):
    rules = [
        _rule(SELLER_WALLET, fixed=25),
        _rule(ROOT_WALLET, cargo_id=4, user_id=11, absorber=True),
    ]

    entry = _build(
        monkeypatch,
        rules,
        contexto="entrada",
        remaining_installments=1,
    )
    carne = _build(monkeypatch, rules, contexto="carne")

    assert service.to_asaas_payload(entry) == [
        {"walletId": SELLER_WALLET, "fixedValue": 25.0}
    ]
    assert service.to_asaas_payload(carne) == [
        {"walletId": SELLER_WALLET, "totalFixedValue": 100.0}
    ]


def test_persisted_receivers_are_append_only_and_keep_value_kind():
    cursor = RecordingCursor()
    plan = service.AsaasSplitPlan(
        contexto="carne",
        items=[
            service.AsaasSplitItem(
                wallet_id=SELLER_WALLET,
                kind="percentual",
                cargo_id=3,
                user_id=10,
                percentual_value=Decimal("35"),
            ),
            service.AsaasSplitItem(
                wallet_id=MANAGER_WALLET,
                kind="total_fixed",
                cargo_id=4,
                user_id=11,
                total_fixed_value=Decimal("125.50"),
            ),
        ],
    )

    service.persist_asaas_sale_splits(
        cursor,
        plan,
        venda_id=42,
        unidade="São João de Meriti",
        environment="sandbox",
        account_wallet_id=ROOT_WALLET,
    )

    assert len(cursor.executions) == 2
    assert all(
        "ON CONFLICT (venda_id, wallet_id) DO NOTHING" in query
        and "DO UPDATE" not in query
        for query, _params in cursor.executions
    )
    assert cursor.executions[0][1][8:10] == (35.0, None)
    assert cursor.executions[1][1][8:10] == (None, 125.5)


def test_expected_seller_rule_missing_blocks_domain_resolution():
    cursor = RecordingCursor(
        [
            (10, 4, SELLER_WALLET),
            (1, 0),
            None,
        ]
    )

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="regra_split_asaas_obrigatoria_ausente",
    ):
        service._load_asaas_domain_rules(
            cursor,
            venda_id=42,
            unidade="São João de Meriti",
            environment="sandbox",
            tipo_odontograma_id=7,
            dentista_id=None,
            usuario_venda_id=10,
        )


def test_expected_manager_rule_missing_blocks_domain_resolution():
    cursor = RecordingCursor(
        [
            (10, 3, SELLER_WALLET),
            (3, 0),
            (60, "percentual", None, None, False),
            None,
        ]
    )

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="regra_split_asaas_obrigatoria_ausente",
    ):
        service._load_asaas_domain_rules(
            cursor,
            venda_id=42,
            unidade="São João de Meriti",
            environment="sandbox",
            tipo_odontograma_id=7,
            dentista_id=None,
            usuario_venda_id=10,
        )


def test_explicit_zero_limits_select_no_receivers():
    cursor = RecordingCursor(
        [
            (10, 3, SELLER_WALLET),
            (0, 0),
        ]
    )

    rules = service._load_asaas_domain_rules(
        cursor,
        venda_id=42,
        unidade="São João de Meriti",
        environment="sandbox",
        tipo_odontograma_id=7,
        dentista_id=None,
        usuario_venda_id=10,
    )

    assert rules == []
    assert len(cursor.executions) == 2


def test_zero_company_limit_keeps_only_person_receiver():
    cursor = RecordingCursor(
        [
            (10, 4, SELLER_WALLET),
            (1, 0),
            (60, "percentual", None, None, False),
        ]
    )

    rules = service._load_asaas_domain_rules(
        cursor,
        venda_id=42,
        unidade="São João de Meriti",
        environment="sandbox",
        tipo_odontograma_id=7,
        dentista_id=None,
        usuario_venda_id=10,
    )

    # Sandbox never reads users.asaas_wallet_id; identity is bound later.
    assert [rule.wallet_id for rule in rules] == [None]
    assert all(
        "empresa_regras_split" not in query
        for query, _params in cursor.executions
    )


@pytest.mark.parametrize("limits", [(-1, 0), (0, -1)])
def test_negative_receiver_limits_fail_closed(limits):
    cursor = RecordingCursor(
        [
            (10, 4, SELLER_WALLET),
            limits,
        ]
    )

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="limite_split_asaas_invalido",
    ):
        service._load_asaas_domain_rules(
            cursor,
            venda_id=42,
            unidade="São João de Meriti",
            environment="sandbox",
            tipo_odontograma_id=7,
            dentista_id=None,
            usuario_venda_id=10,
        )


def test_production_rules_do_not_read_legacy_user_wallet_or_integration_status():
    cursor = RecordingCursor(
        [
            (10, 3, "stale-wallet"),
            (1, 0),
            (Decimal("10"), "percentual", None, None, False),
        ]
    )
    rules = service._load_asaas_domain_rules(
        cursor, venda_id=1, unidade="U", environment="production",
        tipo_odontograma_id=7, dentista_id=None, usuario_venda_id=10,
    )
    assert rules[0].wallet_id is None
    first_query = cursor.executions[0][0].casefold()
    assert "asaas_wallet_id" not in first_query
    assert "asaas_integration_status" not in first_query


def test_production_new_sale_requires_approved_identity_provider(monkeypatch):
    with pytest.raises(service.AsaasSplitValidationError, match="identidade_recebedor_asaas_ausente"):
        _build(
            monkeypatch,
            [_rule("legacy-wallet", percentage=10)],
            environment="production",
        )


def test_company_rules_are_deduplicated_before_limit_with_unit_priority(
    monkeypatch,
):
    monkeypatch.setenv(
        "ASAAS_SANDBOX_WALLET_ID_AKIMAIS",
        "wallet-akimais",
    )
    cursor = RecordingCursor(
        [
            (10, 4, SELLER_WALLET),
            (1, 1),
            (60, "percentual", None, None, False),
            [
                (
                    service.AKIMAIS_EMPRESA_ID,
                    40,
                    "percentual",
                    None,
                    None,
                    False,
                )
            ],
        ]
    )

    rules = service._load_asaas_domain_rules(
        cursor,
        venda_id=42,
        unidade="São João de Meriti",
        environment="sandbox",
        tipo_odontograma_id=7,
        dentista_id=None,
        usuario_venda_id=10,
    )

    company_query, company_params = cursor.executions[-1]
    assert "SELECT DISTINCT ON (ers.empresa_id)" in company_query
    assert "ORDER BY ers.empresa_id" in company_query
    assert "WHEN ers.unidade = %s THEN 0" in company_query
    assert "ORDER BY selecionada.prioridade_unidade" in company_query
    assert company_params == (
        "São João de Meriti",
        7,
        "São João de Meriti",
        "São João de Meriti",
        1,
    )
    assert rules[-1].wallet_id is None


def test_audit_metadata_contains_only_non_sensitive_split_fields(monkeypatch):
    plan = _build(
        monkeypatch,
        [
            _rule(SELLER_WALLET, percentage=100),
        ],
    )

    assert plan.raw_metadata == [
        {
            "cargo_id": 3,
            "user_id": 10,
            "empresa_id": None,
            "wallet_id": SELLER_WALLET,
            "percentual_value": "100",
            "fixed_value": None,
            "cycles_to_participate": None,
            "absorbs_balance": False,
        }
    ]
    serialized = service._canonical_json(plan.raw_metadata).casefold()
    for forbidden in ("nome", "cpf", "email", "telefone", "api_key", "token"):
        assert forbidden not in serialized
