"""Testes da injecao de ``split`` nos managers de venda Asaas.

Cobre que cada manager (installment/entry/recurring) inclui ``split`` no
payload enviado ao HTTP quando ele e fornecido, omite o campo quando None,
e rejeita splits malformados antes de qualquer chamada remota.

O ``http_client`` e um MagicMock que captura o payload enviado via
``post.call_args.kwargs['json']``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.asaas_sdk.exceptions import AsaasValidationError
from app.asaas_sales_sdk import (
    AsaasSalesEntryManager,
    AsaasSalesInstallmentManager,
    AsaasSalesRecurringManager,
)


CUSTOMER_ID = "cus_000005219613"
REFERENCE = "grupojf:venda:42:r1"
PIX_ID = "pix_automatic_42"
CHECKOUT_ID = "checkout_42"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


# ===========================================================================
# AsaasSalesInstallmentManager
# ===========================================================================


def _remote_installment():
    return {
        "id": "ins_42",
        "installment": "ins_42",
        "customer": CUSTOMER_ID,
        "billingType": "BOLETO",
        "dueDate": "2030-08-10",
        "value": 100,
        "status": "PENDING",
        "externalReference": REFERENCE,
    }


def _installment_base():
    return {
        "customer": CUSTOMER_ID,
        "billingType": "BOLETO",
        "installmentCount": 2,
        "value": 100,
        "dueDate": "2030-08-10",
        "paymentExternalReference": REFERENCE,
    }


def test_installment_create_inclui_split_no_payload():
    client = MagicMock()
    client.post.return_value = FakeResponse(_remote_installment())
    manager = AsaasSalesInstallmentManager(client)

    manager.create_installment(
        {
            **_installment_base(),
            "split": [
                {"walletId": "wallet-com-3", "totalFixedValue": 40.0},
                {"walletId": "wallet-ger-4", "percentualValue": 10.0},
            ],
        }
    )

    posted = client.post.call_args.kwargs["json"]
    assert client.post.call_args.args[0] == "/installments"
    assert posted["split"] == [
        {"walletId": "wallet-com-3", "totalFixedValue": 40.0},
        {"walletId": "wallet-ger-4", "percentualValue": 10.0},
    ]


def test_installment_create_sem_split_omite_o_campo():
    client = MagicMock()
    client.post.return_value = FakeResponse(_remote_installment())
    manager = AsaasSalesInstallmentManager(client)

    manager.create_installment(_installment_base())

    posted = client.post.call_args.kwargs["json"]
    assert "split" not in posted


def test_installment_create_rejeita_split_malformado_antes_do_http():
    client = MagicMock()
    manager = AsaasSalesInstallmentManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_installment(
            {**_installment_base(), "split": "nao-e-uma-lista"}
        )

    assert raised.value.errors == ["installment_split_invalid"]
    client.post.assert_not_called()


# ===========================================================================
# AsaasSalesEntryManager
# ===========================================================================


def _remote_payment():
    return {
        "id": "pay_42",
        "customer": CUSTOMER_ID,
        "billingType": "PIX",
        "status": "PENDING",
        "externalReference": REFERENCE,
        "invoiceUrl": "https://sandbox.asaas.com/i/safe-token",
        "value": 100.0,
        "netValue": 100.0,
    }


def test_entry_create_inclui_split_no_payload():
    client = MagicMock()
    client.post.return_value = FakeResponse(_remote_payment())
    manager = AsaasSalesEntryManager(client)

    manager.create_payment(
        customer_id=CUSTOMER_ID,
        billing_type="PIX",
        amount="100.00",
        due_date="2030-08-10",
        external_reference=REFERENCE,
        split=[
            {"walletId": "wallet-com-3", "fixedValue": 30.0},
            {"walletId": "wallet-ger-4", "percentualValue": 20.0},
        ],
    )

    posted = client.post.call_args.kwargs["json"]
    assert client.post.call_args.args[0] == "/payments"
    assert posted["split"] == [
        {"walletId": "wallet-com-3", "fixedValue": 30.0},
        {"walletId": "wallet-ger-4", "percentualValue": 20.0},
    ]


# ===========================================================================
# AsaasSalesRecurringManager
# ===========================================================================


def _remote_pix():
    return {
        "id": PIX_ID,
        "status": "PENDING",
        "immediateQrCode": {"payload": "sandbox-pix"},
    }


def _remote_checkout():
    return {
        "id": CHECKOUT_ID,
        "status": "ACTIVE",
        "link": f"https://sandbox.asaas.com/checkoutSession/show/{CHECKOUT_ID}",
    }


def test_recurring_pix_authorization_inclui_split_no_payload():
    client = MagicMock()
    client.post.return_value = FakeResponse(_remote_pix())
    manager = AsaasSalesRecurringManager(client)

    manager.create_pix_authorization(
        customer_id=CUSTOMER_ID,
        contract_id=REFERENCE,
        start_date="2030-08-10",
        finish_date="2030-10-10",
        value="100.00",
        split=[{"walletId": "wallet-com-3", "percentualValue": 30.0}],
    )

    posted = client.post.call_args.kwargs["json"]
    assert client.post.call_args.args[0] == "/pix/automatic/authorizations"
    assert posted["split"] == [
        {"walletId": "wallet-com-3", "percentualValue": 30.0}
    ]


def test_recurring_card_checkout_inclui_split_no_payload():
    client = MagicMock()
    client.post.return_value = FakeResponse(_remote_checkout())
    manager = AsaasSalesRecurringManager(client)

    manager.create_recurring_card_checkout(
        customer_id=CUSTOMER_ID,
        external_reference=REFERENCE,
        item_name="Tratamento odontologico",
        quantity=1,
        value="100.00",
        next_due_date="2030-08-10",
        end_date="2030-10-10",
        callback_url="https://dev.grupojf.example/pagamento/retorno",
        split=[{"walletId": "wallet-com-3", "percentualValue": 25.0}],
    )

    posted = client.post.call_args.kwargs["json"]
    assert client.post.call_args.args[0] == "/checkouts"
    assert posted["split"] == [
        {"walletId": "wallet-com-3", "percentualValue": 25.0}
    ]


# ===========================================================================
# Validacao defensiva de split nos managers (dinheiro).
# ===========================================================================


def test_installment_split_item_sem_walletid_eh_rejeitado_antes_do_http():
    client = MagicMock()
    manager = AsaasSalesInstallmentManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_installment(
            {
                **_installment_base(),
                "split": [{"totalFixedValue": 40.0}],  # sem walletId
            }
        )

    assert raised.value.errors == ["installment_split_invalid"]
    client.post.assert_not_called()


def test_installment_split_total_fixed_negativo_eh_rejeitado():
    client = MagicMock()
    manager = AsaasSalesInstallmentManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_installment(
            {
                **_installment_base(),
                "split": [{"walletId": "wallet-1", "totalFixedValue": -40.0}],
            }
        )
    assert raised.value.errors == ["installment_split_invalid"]
    client.post.assert_not_called()


def test_installment_split_percentual_zero_eh_rejeitado():
    """Percentual 0 (sem repsaldo a conta-mae aqui) e invalido no payload
    direto do manager; o split explicito precisa de valor > 0.
    """
    client = MagicMock()
    manager = AsaasSalesInstallmentManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_installment(
            {
                **_installment_base(),
                "split": [{"walletId": "wallet-1", "percentualValue": 0.0}],
            }
        )
    assert raised.value.errors == ["installment_split_invalid"]


def test_entry_split_fixed_value_negativo_eh_rejeitado():
    client = MagicMock()
    manager = AsaasSalesEntryManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_payment(
            customer_id=CUSTOMER_ID,
            billing_type="PIX",
            amount="100.00",
            due_date="2030-08-10",
            external_reference=REFERENCE,
            split=[{"walletId": "wallet-1", "fixedValue": -30.0}],
        )
    assert raised.value.errors == ["entry_split_invalid"]
    client.post.assert_not_called()


def test_entry_split_item_sem_walletid_eh_rejeitado():
    client = MagicMock()
    manager = AsaasSalesEntryManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_payment(
            customer_id=CUSTOMER_ID,
            billing_type="PIX",
            amount="100.00",
            due_date="2030-08-10",
            external_reference=REFERENCE,
            split=[{"fixedValue": 30.0}],  # sem walletId
        )
    assert raised.value.errors == ["entry_split_invalid"]
    client.post.assert_not_called()


def test_entry_split_valor_nao_numerico_eh_rejeitado():
    client = MagicMock()
    manager = AsaasSalesEntryManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_payment(
            customer_id=CUSTOMER_ID,
            billing_type="PIX",
            amount="100.00",
            due_date="2030-08-10",
            external_reference=REFERENCE,
            split=[{"walletId": "wallet-1", "fixedValue": "nao-numero"}],
        )
    assert raised.value.errors == ["entry_split_invalid"]


def test_recurring_pix_split_percentual_maior_que_100_eh_rejeitado():
    client = MagicMock()
    manager = AsaasSalesRecurringManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_pix_authorization(
            customer_id=CUSTOMER_ID,
            contract_id=REFERENCE,
            start_date="2030-08-10",
            finish_date="2030-10-10",
            value="100.00",
            split=[{"walletId": "wallet-1", "percentualValue": 150.0}],
        )
    assert raised.value.errors == ["pix_split_invalid"]
    client.post.assert_not_called()


def test_recurring_pix_split_percentual_zero_ou_negativo_eh_rejeitado():
    client = MagicMock()
    manager = AsaasSalesRecurringManager(client)

    for bad in [0.0, -1.0]:
        with pytest.raises(AsaasValidationError) as raised:
            manager.create_pix_authorization(
                customer_id=CUSTOMER_ID,
                contract_id=REFERENCE,
                start_date="2030-08-10",
                finish_date="2030-10-10",
                value="100.00",
                split=[{"walletId": "wallet-1", "percentualValue": bad}],
            )
        assert raised.value.errors == ["pix_split_invalid"]
        client.post.reset_mock()


def test_recurring_pix_split_percentual_exatamente_100_passa():
    """Boundary: 100.0 e o maximo valido (mutante que troque > por >=)."""
    client = MagicMock()
    client.post.return_value = FakeResponse(_remote_pix())
    manager = AsaasSalesRecurringManager(client)

    manager.create_pix_authorization(
        customer_id=CUSTOMER_ID,
        contract_id=REFERENCE,
        start_date="2030-08-10",
        finish_date="2030-10-10",
        value="100.00",
        split=[{"walletId": "wallet-1", "percentualValue": 100.0}],
    )
    posted = client.post.call_args.kwargs["json"]
    assert posted["split"] == [
        {"walletId": "wallet-1", "percentualValue": 100.0}
    ]


def test_recurring_pix_split_item_sem_walletid_eh_rejeitado():
    client = MagicMock()
    manager = AsaasSalesRecurringManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_pix_authorization(
            customer_id=CUSTOMER_ID,
            contract_id=REFERENCE,
            start_date="2030-08-10",
            finish_date="2030-10-10",
            value="100.00",
            split=[{"percentualValue": 30.0}],
        )
    assert raised.value.errors == ["pix_split_invalid"]
    client.post.assert_not_called()


def test_recurring_checkout_split_percentual_maior_que_100_eh_rejeitado():
    client = MagicMock()
    manager = AsaasSalesRecurringManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_recurring_card_checkout(
            customer_id=CUSTOMER_ID,
            external_reference=REFERENCE,
            item_name="Tratamento odontologico",
            quantity=1,
            value="100.00",
            next_due_date="2030-08-10",
            end_date="2030-10-10",
            callback_url="https://dev.grupojf.example/pagamento/retorno",
            split=[{"walletId": "wallet-1", "percentualValue": 200.0}],
        )
    assert raised.value.errors == ["checkout_split_invalid"]
    client.post.assert_not_called()


# ---------------------------------------------------------------------------
# Comportamento documentado (RISCO): ambos campos de valor no mesmo item.
#
# O installment/entry manager NAO rejeita um item que traga duas chaves de
# valor (ex.: totalFixedValue E percentualValue): ele seleciona a primeira
# chave da tupla ``allowed_value_keys`` e descarta a outra silenciosamente.
# Isso e uma ambiguidade de contrato: o Asaas pode interpretar o item de
# forma diferente da esperada. Estes testes FIXAM o comportamento atual para
# detectar regressao e sinalizar a ambiguidade ao coordenador (ver entrega).
# ---------------------------------------------------------------------------


def test_installment_split_com_dois_campos_de_valor_eh_rejeitado():
    """Seguranca (fail-closed): item de split com duas chaves de valor
    (totalFixedValue E percentualValue) e ambiguo e DEVE ser rejeitado
    antes do HTTP — area de dinheiro nao admite selecao implicita.
    """
    import pytest as _pytest
    from app.asaas_sdk.exceptions import AsaasValidationError

    client = MagicMock()
    client.post.return_value = FakeResponse(_remote_installment())
    manager = AsaasSalesInstallmentManager(client)

    with _pytest.raises(AsaasValidationError):
        manager.create_installment(
            {
                **_installment_base(),
                "split": [
                    {
                        "walletId": "wallet-1",
                        "totalFixedValue": 40.0,
                        "percentualValue": 10.0,
                    }
                ],
            }
        )
    client.post.assert_not_called()


def test_entry_split_com_dois_campos_de_valor_eh_rejeitado():
    """Seguranca (fail-closed): item de split com duas chaves de valor
    (fixedValue E percentualValue) e ambiguo e DEVE ser rejeitado.
    """
    import pytest as _pytest
    from app.asaas_sdk.exceptions import AsaasValidationError

    client = MagicMock()
    client.post.return_value = FakeResponse(_remote_payment())
    manager = AsaasSalesEntryManager(client)

    with _pytest.raises(AsaasValidationError):
        manager.create_payment(
            customer_id=CUSTOMER_ID,
            billing_type="PIX",
            amount="100.00",
            due_date="2030-08-10",
            external_reference=REFERENCE,
            split=[
                {
                    "walletId": "wallet-1",
                    "fixedValue": 30.0,
                    "percentualValue": 20.0,
                }
            ],
        )
    client.post.assert_not_called()


def test_installment_split_lista_vazia_eh_rejeitada():
    client = MagicMock()
    manager = AsaasSalesInstallmentManager(client)

    with pytest.raises(AsaasValidationError) as raised:
        manager.create_installment({**_installment_base(), "split": []})
    assert raised.value.errors == ["installment_split_invalid"]
    client.post.assert_not_called()
