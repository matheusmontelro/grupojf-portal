"""Contratos de seguranca do alocador de split exclusivo do Asaas."""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from app.services import asaas_split_service as service


ROOT_WALLET = "wallet-conta-emissora"
SELLER_WALLET = "wallet-comercial"
MANAGER_WALLET = "wallet-gerente"


def _kwargs(**overrides):
    values = {
        "venda_id": 42,
        "unidade": "Unidade A",
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
    values.update(overrides)
    return values


def _rule(
    *,
    wallet_id: str | None,
    percentage: str | None = None,
    fixed: str | None = None,
    cargo_id: int | None = 3,
    user_id: int | None = 10,
    empresa_id: int | None = None,
    cycles: int | None = None,
    absorber: bool = False,
):
    return service.AsaasDomainSplitRule(
        wallet_id=wallet_id,
        cargo_id=cargo_id,
        user_id=user_id,
        empresa_id=empresa_id,
        percentual_value=Decimal(percentage) if percentage is not None else None,
        fixed_value=Decimal(fixed) if fixed is not None else None,
        cycles_to_participate=cycles,
        absorbs_balance=absorber,
    )


def _use_rules(monkeypatch, rules):
    monkeypatch.setattr(
        service,
        "_load_asaas_domain_rules",
        lambda cursor, **kwargs: list(rules),
    )


def test_allocator_is_independent_from_legacy_bempaggo_service():
    source = inspect.getsource(service).lower()

    assert "splitservice" not in source.replace("asaassplitservice", "")
    assert "bempaggo" not in source


def test_valid_pf_wallet_is_allocated_without_legacy_integration(monkeypatch):
    _use_rules(
        monkeypatch,
        [
            _rule(wallet_id=SELLER_WALLET, percentage="60"),
            _rule(
                wallet_id=ROOT_WALLET,
                cargo_id=4,
                user_id=11,
                absorber=True,
            ),
        ],
    )

    plan = service.build_asaas_split_for_sale(object(), **_kwargs())

    assert [item.wallet_id for item in plan.items] == [SELLER_WALLET]
    assert plan.absorber is not None
    assert plan.absorber.wallet_id == ROOT_WALLET
    assert plan.absorber.absorbed_value == Decimal("400.00")
    assert service.to_asaas_payload(plan) == [
        {"walletId": SELLER_WALLET, "percentualValue": 60.0}
    ]


def test_missing_wallet_for_selected_receiver_blocks_sale(monkeypatch):
    _use_rules(
        monkeypatch,
        [
            _rule(wallet_id=None, percentage="60"),
            _rule(
                wallet_id=ROOT_WALLET,
                cargo_id=4,
                user_id=11,
                absorber=True,
            ),
        ],
    )

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="identidade_recebedor_asaas_ausente",
    ):
        service.build_asaas_split_for_sale(object(), **_kwargs())


def test_residual_without_declared_absorber_is_rejected(monkeypatch):
    _use_rules(
        monkeypatch,
        [_rule(wallet_id=SELLER_WALLET, percentage="60")],
    )

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="saldo_residual_sem_absorvedor",
    ):
        service.build_asaas_split_for_sale(object(), **_kwargs())


def test_external_absorber_is_rejected_instead_of_redistributed(monkeypatch):
    _use_rules(
        monkeypatch,
        [
            _rule(wallet_id=SELLER_WALLET, percentage="60"),
            _rule(
                wallet_id=MANAGER_WALLET,
                cargo_id=4,
                user_id=11,
                absorber=True,
            ),
        ],
    )

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="absorvedor_externo_nao_suportado",
    ):
        service.build_asaas_split_for_sale(object(), **_kwargs())


def test_entry_consumes_only_finite_participant_without_transferring_value():
    rules = [
        _rule(wallet_id=SELLER_WALLET, percentage="20", cycles=1),
        _rule(
            wallet_id=MANAGER_WALLET,
            percentage="30",
            cargo_id=4,
            user_id=11,
            cycles=3,
        ),
        _rule(
            wallet_id=ROOT_WALLET,
            cargo_id=4,
            user_id=12,
            cycles=1,
            absorber=True,
        ),
    ]

    remaining = service.consume_entry_cycle(rules)

    assert len(remaining) == 2
    manager = next(rule for rule in remaining if rule.wallet_id == MANAGER_WALLET)
    absorber = next(rule for rule in remaining if rule.absorbs_balance)
    assert manager.percentual_value == Decimal("30")
    assert manager.cycles_to_participate == 2
    assert absorber.wallet_id == ROOT_WALLET
    assert absorber.cycles_to_participate == 1


def test_fixed_and_percentage_are_validated_together(monkeypatch):
    _use_rules(
        monkeypatch,
        [
            _rule(wallet_id=SELLER_WALLET, percentage="80"),
            _rule(
                wallet_id=MANAGER_WALLET,
                cargo_id=4,
                user_id=11,
                fixed="300",
            ),
            _rule(
                wallet_id=ROOT_WALLET,
                cargo_id=4,
                user_id=12,
                absorber=True,
            ),
        ],
    )

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="alocacao_excede_valor",
    ):
        service.build_asaas_split_for_sale(object(), **_kwargs())


@pytest.mark.parametrize("context", ["pix", "cartao"])
def test_recurring_context_rejects_fixed_or_finite_rules(monkeypatch, context):
    _use_rules(
        monkeypatch,
        [
            _rule(wallet_id=SELLER_WALLET, fixed="50", cycles=2),
            _rule(
                wallet_id=ROOT_WALLET,
                cargo_id=4,
                user_id=11,
                absorber=True,
            ),
        ],
    )

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="regra_nao_representavel_em_recorrencia",
    ):
        service.build_asaas_split_for_sale(
            object(),
            **_kwargs(contexto=context),
        )


def test_carne_aggregates_fixed_value_over_remaining_cycles(monkeypatch):
    _use_rules(
        monkeypatch,
        [
            _rule(wallet_id=SELLER_WALLET, fixed="50", cycles=2),
            _rule(
                wallet_id=ROOT_WALLET,
                cargo_id=4,
                user_id=11,
                absorber=True,
            ),
        ],
    )

    plan = service.build_asaas_split_for_sale(object(), **_kwargs())

    assert service.to_asaas_payload(plan) == [
        {"walletId": SELLER_WALLET, "totalFixedValue": 100.0}
    ]


def test_missing_domain_configuration_blocks_sale(monkeypatch):
    _use_rules(monkeypatch, [])

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="configuracao_split_asaas_ausente",
    ):
        service.build_asaas_split_for_sale(object(), **_kwargs())


@pytest.mark.parametrize(
    ("external_percentage", "error_code"),
    [
        ("99.999", "saldo_residual_sem_absorvedor"),
        ("100.001", "alocacao_excede_valor"),
    ],
)
def test_monetary_cent_is_not_silently_forgiven(
    monkeypatch,
    external_percentage,
    error_code,
):
    _use_rules(
        monkeypatch,
        [_rule(wallet_id=SELLER_WALLET, percentage=external_percentage)],
    )

    with pytest.raises(service.AsaasSplitValidationError, match=error_code):
        service.build_asaas_split_for_sale(object(), **_kwargs())


def test_company_wallet_mapping_rejects_unsupported_environment(monkeypatch):
    monkeypatch.setenv("ASAAS_SANDBOX_WALLET_ID_AKIMAIS", "wallet-company")

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="empresa_wallet_ambiente_nao_suportado",
    ):
        service._resolve_company_wallet(
            service.AKIMAIS_EMPRESA_ID,
            environment="production",
        )


class _DomainCursor:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.current = None
        self.queries = []

    def execute(self, query, params):
        self.queries.append(" ".join(query.split()))
        self.current = next(self._responses)

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current[0] if self.current else None
        return self.current

    def fetchall(self):
        if isinstance(self.current, list):
            return self.current
        return [] if self.current is None else [self.current]


def test_pf_selection_requires_integrated_approved_users_and_unique_manager():
    cursor = _DomainCursor(
        [
            (10, 3, SELLER_WALLET),
            (3, 0),
            (60, "percentual", None, None, False),
            (40, "percentual", None, None, False),
            [(11, MANAGER_WALLET), (12, "wallet-gerente-2")],
        ]
    )

    with pytest.raises(
        service.AsaasSplitValidationError,
        match="gerente_asaas_ambiguo",
    ):
        service._load_asaas_domain_rules(
            cursor,
            venda_id=42,
            unidade="Unidade A",
            environment="sandbox",
            tipo_odontograma_id=7,
            dentista_id=None,
            usuario_venda_id=10,
        )

    user_queries = [query for query in cursor.queries if "FROM users" in query]
    assert len(user_queries) == 2
    assert all(
        "asaas_integration_status = 'integrado'" not in query
        and "status_aprovacao = 'aprovado'" in query
        and "COALESCE(status_aprovacao" not in query
        and "unidade = %s" in query
        and "REGEXP_REPLACE" in query
        and "COALESCE(cpf, '')" in query
        and ") = 11" in query
        for query in user_queries
    )
