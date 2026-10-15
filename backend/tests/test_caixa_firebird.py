from datetime import date
from decimal import Decimal
import sys
import types
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import caixa_firebird
from app.routers.caixa_firebird import _resposta
from app.services import caixa_firebird_service as service_module
from app.security.auth_dependencies import get_current_user
from app.services.caixa_firebird_service import CaixaFirebirdService, CaixaFonteResultado, _categoria


def _app_for(user):
    app = FastAPI()
    app.include_router(caixa_firebird.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _source(unit="Nova Iguaçu 1", total="20.00"):
    return CaixaFonteResultado(
        unidade=unit,
        alias=f"{unit}-clinico",
        dias=[{
            "data": date(2026, 10, 1), "total_centavos": int(Decimal(total) * 100),
            "categorias": {"manutencao": 0, "adesao": 0, "raio_panoramico": 0, "odc": 0, "rec_cred": 0, "vendas": int(Decimal(total) * 100), "nao_classificado": 0},
            "formas_pagamento": {"PIX": int(Decimal(total) * 100)},
            "status_fechamento": "aberto", "manutencoes_recebidas": 1,
        }],
    )


def test_acceptance_rejects_unapproved_role_before_source_access():
    client = _app_for({"role": "Comercial", "unidade": "Nova Iguaçu 1"})
    with patch.object(caixa_firebird, "CaixaFirebirdService") as service:
        response = client.get("/api/caixa-firebird?mes=2026-10")

    assert response.status_code == 403
    service.assert_not_called()


def test_acceptance_rejects_forged_unit_for_financeiro_before_source_access():
    client = _app_for({"role": "Financeiro", "unidade": "Nova Iguaçu 1"})
    with patch.object(caixa_firebird, "CaixaFirebirdService") as service:
        response = client.get("/api/caixa-firebird?mes=2026-10&unidade=Vilar")

    assert response.status_code == 403
    service.assert_not_called()


def test_acceptance_rejects_all_for_restricted_roles_before_source_access():
    for role in ("Financeiro", "Gerente"):
        client = _app_for({"role": role, "unidade": "Nova Iguaçu 1"})
        with patch.object(caixa_firebird, "CaixaFirebirdService") as service:
            response = client.get("/api/caixa-firebird?mes=2026-10&unidade=all")

        assert response.status_code == 403
        service.assert_not_called()


def test_acceptance_limits_financeiro_to_authenticated_unit_and_preserves_partial_data():
    client = _app_for({"role": "Financeiro", "unidade": "Nova Iguaçu 1"})
    with patch.object(caixa_firebird, "CaixaFirebirdService") as service:
        service.return_value.consultar_mes.return_value = {
            "fontes": [_source()],
            "falhas": [{"unidade": "Nova Iguaçu 1", "codigo": "fonte_indisponivel"}, {"unidade": "São João de Meriti", "codigo": "fonte_indisponivel"}],
            "atualizado_em": "2026-10-01T12:00:00+00:00",
        }
        response = client.get("/api/caixa-firebird?mes=2026-10")

    assert response.status_code == 200
    body = response.json()
    assert body["unidades_consultadas"] == ["Nova Iguaçu 1"]
    assert body["status"] == "parcial"
    assert body["resumo"]["total_centavos"] == 2000
    assert body["falhas"] == [{"unidade": "Nova Iguaçu 1", "codigo": "fonte_indisponivel"}]
    service.return_value.consultar_mes.assert_called_once_with(
        mes=date(2026, 10, 1), unidades=("Nova Iguaçu 1",)
    )


def test_money_is_rounded_per_transaction_before_sum_and_unknown_types_remain_visible():
    service = CaixaFirebirdService()
    result = service.agrupar_lancamentos("Nova Iguaçu 1", "ni1_clinico", [
        (date(2026, 10, 1), "10", "+", Decimal("10.005"), "PIX"),
        (date(2026, 10, 1), "999", "+", Decimal("10.005"), "Outro"),
        (date(2026, 10, 1), "36", "-", Decimal("5.00"), "Dinheiro"),
    ], [])

    assert result.dias[0]["total_centavos"] == 2002
    assert result.dias[0]["categorias"]["vendas"] == 1001
    assert result.dias[0]["categorias"]["nao_classificado"] == 1001
    assert result.dias[0]["codigos_nao_classificados"] == ["999"]


def test_source_failure_never_becomes_zero_and_config_is_fail_closed(monkeypatch):
    monkeypatch.delenv("CAIXA_FIREBIRD_CONFIG_PATH", raising=False)
    service = CaixaFirebirdService()

    result = service.consultar_mes(date(2026, 10, 1), ("Nova Iguaçu 1",))

    assert result["fontes"] == []
    assert result["falhas"] == [{"codigo": "configuracao_indisponivel"}]


def test_golden_ni1_four_days_preserves_homologated_aggregate():
    valores = {
        date(2026, 10, 1): (210436, 0, 110744, 65223, 1670000, 2056403, 24),
        date(2026, 10, 2): (257160, 0, 122185, 90000, 295000, 764345, 31),
        date(2026, 10, 3): (207831, 0, 79995, 808927, 398000, 1494753, 26),
        date(2026, 10, 5): (318335, 3000, 121847, 1533364, 1643000, 3619546, 39),
    }
    service = CaixaFirebirdService()
    clinico = []
    contratos = []
    for dia, (manut, adesao, odc, rec_cred, vendas, total, qtd_manut) in valores.items():
        # O valor principal e os centavos restantes mantêm a contagem de
        # manutencoes homologada sem introduzir qualquer identificador real.
        clinico.append((dia, "50", "+", Decimal(manut - qtd_manut + 1) / 100, "PIX"))
        clinico.extend((dia, "50", "+", Decimal("0.01"), "PIX") for _ in range(qtd_manut - 1))
        if adesao:
            clinico.append((dia, "554", "+", Decimal(adesao) / 100, "PIX"))
        clinico.append((dia, "84", "+", Decimal(rec_cred) / 100, "PIX"))
        clinico.append((dia, "10", "+", Decimal(vendas) / 100, "PIX"))
        contratos.append((dia, "18", "+", Decimal(odc) / 100, "PIX"))

    clinico_resultado = service.agrupar_lancamentos("Nova Iguaçu 1", "ni1_clinico", clinico, [])
    contratos_resultado = service.agrupar_lancamentos("Nova Iguaçu 1", "ni1_contratos", contratos, [])

    body = _resposta(date(2026, 10, 1), {
        "fontes": [clinico_resultado, contratos_resultado],
        "falhas": [], "atualizado_em": "2026-10-14T00:00:00Z",
    })

    assert body["status"] == "completo"
    assert body["resumo"]["total_centavos"] == sum(item[5] for item in valores.values())
    assert body["resumo"]["categorias"] == {
        "manutencao": 993762, "adesao": 3000, "raio_panoramico": 0,
        "odc": 434771, "rec_cred": 2497514, "vendas": 4006000,
        "nao_classificado": 0,
    }
    assert body["resumo"]["manutencoes_recebidas"] == 120


def test_source_exception_is_sanitized_as_partial_failure(monkeypatch):
    service = CaixaFirebirdService()
    monkeypatch.setattr(service, "_configuracao", lambda: {"sources": {"ni1_clinico": {}, "ni1_contratos": {}}})

    def source(unidade, alias, config, inicio, fim):
        if alias == "ni1_clinico":
            raise RuntimeError("erro interno que nao deve vazar")
        return "fonte_indisponivel"

    monkeypatch.setattr(service, "_consultar_fonte", source)
    resultado = service.consultar_mes(date(2026, 10, 1), ("Nova Iguaçu 1",))

    assert resultado["fontes"] == []
    assert sorted(resultado["falhas"], key=lambda item: item["alias"]) == [
        {"unidade": "Nova Iguaçu 1", "alias": "ni1_clinico", "codigo": "fonte_indisponivel"},
        {"unidade": "Nova Iguaçu 1", "alias": "ni1_contratos", "codigo": "fonte_indisponivel"},
    ]


def test_source_capacity_is_reported_without_starting_process(monkeypatch):
    monkeypatch.setattr(service_module._REQUESTS, "acquire", lambda blocking=False: False)
    service = CaixaFirebirdService()

    resultado = service._consultar_fonte(
        "Nova Iguaçu 1", "ni1_clinico",
        {"dsn": "placeholder", "user": "placeholder", "password": "placeholder"},
        date(2026, 10, 1), date(2026, 11, 1),
    )

    assert resultado == "capacidade_indisponivel"


def test_source_process_start_failure_is_sanitized(monkeypatch):
    class FakePipe:
        def close(self):
            pass

    class FakeProcess:
        def start(self):
            raise OSError("processo indisponivel")

    class FakeContext:
        def Pipe(self, duplex=False):
            return FakePipe(), FakePipe()

        def Process(self, target, args):
            return FakeProcess()

    monkeypatch.setattr(service_module.multiprocessing, "get_context", lambda name: FakeContext())
    service = CaixaFirebirdService()

    resultado = service._consultar_fonte(
        "Nova Iguaçu 1", "ni1_clinico",
        {"dsn": "placeholder", "user": "placeholder", "password": "placeholder"},
        date(2026, 10, 1), date(2026, 11, 1),
    )

    assert resultado == "fonte_indisponivel"


def test_admin_can_request_all_units_but_unknown_unit_is_rejected():
    client = _app_for({"role": "Administrador", "unidade": "Nova Iguaçu 1"})
    with patch.object(caixa_firebird, "CaixaFirebirdService") as service:
        service.return_value.consultar_mes.return_value = {"fontes": [], "falhas": []}
        response = client.get("/api/caixa-firebird?mes=2026-10&unidade=all")

    assert response.status_code == 200
    service.return_value.consultar_mes.assert_called_once_with(
        mes=date(2026, 10, 1), unidades=tuple(caixa_firebird.UNIDADES)
    )

    with patch.object(caixa_firebird, "CaixaFirebirdService") as service:
        invalid = client.get("/api/caixa-firebird?mes=2026-10&unidade=desconhecida")
    assert invalid.status_code == 422
    service.assert_not_called()


def test_no_sources_is_unavailable_and_pending_metrics_stay_null():
    client = _app_for({"role": "Financeiro", "unidade": "Nova Iguaçu 1"})
    with patch.object(caixa_firebird, "CaixaFirebirdService") as service:
        service.return_value.consultar_mes.return_value = {
            "fontes": [],
            "falhas": [{"unidade": "Nova Iguaçu 1", "codigo": "fonte_indisponivel"}],
        }
        response = client.get("/api/caixa-firebird?mes=2026-10")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "indisponivel"
    assert body["resumo"]["total_centavos"] is None
    assert body["resumo"]["contratos_vendidos"] is None
    assert body["resumo"]["vidas_vendidas"] is None
    assert body["resumo"]["ortos_vendidos"] is None
    assert body["resumo"]["media_diaria"] is None
    assert body["resumo"]["projecao"] is None


def _fake_fdb(monkeypatch, readonly):
    class FakeTPB:
        def __init__(self):
            self.rendered = "tpb-rendered"

        def render(self):
            return self.rendered

    class FakeCursor:
        def execute(self, query, params):
            pass

        def fetchmany(self, limit):
            return []

        def fetchone(self):
            return None

    class FakeTransaction:
        def __init__(self):
            self.default_action = None
            self.begun = False
            self.rollbacks = 0

        def begin(self):
            self.begun = True

        def trans_info(self, info):
            return readonly

        def cursor(self):
            return FakeCursor()

        def rollback(self):
            self.rollbacks += 1

    class FakeConnection:
        def __init__(self, transaction):
            self.main_transaction = transaction
            self.closed = False

        def rollback(self):
            self.main_transaction.rollbacks += 1

        def close(self):
            self.closed = True

    transaction = FakeTransaction()
    connection = FakeConnection(transaction)
    calls = {}

    def connect(**kwargs):
        calls.update(kwargs)
        return connection

    fake = types.SimpleNamespace(
        TPB=FakeTPB,
        isc_tpb_read="read",
        isc_tpb_read_committed="read-committed",
        isc_tpb_rec_version="rec-version",
        isc_tpb_nowait="nowait",
        isc_info_tra_access="access",
        isc_info_tra_readonly="readonly",
        connect=connect,
    )
    monkeypatch.setitem(sys.modules, "fdb", fake)
    return calls, transaction, connection


def test_firebird_worker_requires_readonly_and_rolls_back_and_closes(monkeypatch):
    calls, transaction, connection = _fake_fdb(monkeypatch, "readonly")
    sent = []
    channel = types.SimpleNamespace(send=sent.append, close=lambda: None)

    service_module._consulta_fonte_processo(
        {"dsn": "dsn", "user": "user", "password": "password"},
        date(2026, 10, 1), date(2026, 11, 1), channel,
    )

    assert sent == [("ok", [], [])]
    assert calls["no_db_triggers"] is True
    assert calls["no_gc"] is True
    assert calls["isolation_level"] == "tpb-rendered"
    assert transaction.default_action == "rollback"
    assert transaction.begun is True
    assert transaction.rollbacks >= 1
    assert connection.closed is True


def test_firebird_worker_rejects_non_readonly_transaction(monkeypatch):
    calls, transaction, connection = _fake_fdb(monkeypatch, "read-write")
    sent = []
    channel = types.SimpleNamespace(send=sent.append, close=lambda: None)

    service_module._consulta_fonte_processo(
        {"dsn": "dsn", "user": "user", "password": "password"},
        date(2026, 10, 1), date(2026, 11, 1), channel,
    )

    assert sent == [("erro",)]
    assert transaction.rollbacks >= 1
    assert connection.closed is True


def test_source_timeout_is_bounded_and_returns_sanitized_failure(monkeypatch):
    class FakePipe:
        def poll(self, timeout):
            assert timeout == 3
            return False

        def close(self):
            pass

    class FakeProcess:
        def start(self):
            pass

        def join(self, timeout=None):
            pass

        def terminate(self):
            pass

        def is_alive(self):
            return False

    class FakeContext:
        def Pipe(self, duplex=False):
            return FakePipe(), FakePipe()

        def Process(self, target, args):
            return FakeProcess()

    monkeypatch.setattr(service_module.multiprocessing, "get_context", lambda name: FakeContext())
    service = CaixaFirebirdService()
    service.timeout = 3

    result = service._consultar_fonte(
        "Nova Iguaçu 1", "ni1_clinico",
        {"dsn": "placeholder", "user": "placeholder", "password": "placeholder"},
        date(2026, 10, 1), date(2026, 11, 1),
    )

    assert result == "prazo_excedido"


def test_static_maps_cover_the_six_aliases_and_keep_unknown_visible():
    casos = {
        "ni1_clinico": ("194", "vendas"), "ni1_contratos": ("18", "odc"),
        "sjm_clinico": ("561", "adesao"), "sjm_contratos": ("38", "adesao"),
        "vilar_clinico": ("191", "vendas"), "vilar_contratos": ("81", "odc"),
    }
    for alias, (codigo, esperado) in casos.items():
        assert _categoria(alias, codigo) == esperado
    assert _categoria("ni1_clinico", "TIPO-NAO-HOMOLOGADO") == "nao_classificado"
