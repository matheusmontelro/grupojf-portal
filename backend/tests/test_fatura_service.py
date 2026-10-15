import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.fatura_service import (
    _normalizar_telefone_delta,
    criar_fatura_avulsa_service,
)


class NormalizarTelefoneDeltaTests(unittest.TestCase):
    def test_normaliza_celular_com_codigo_do_pais(self):
        self.assertEqual(
            _normalizar_telefone_delta("5521998765432"),
            {
                "countryCode": 55,
                "areaCode": 21,
                "number": 998765432,
            },
        )

    def test_normaliza_telefone_com_mascara_e_sem_codigo_do_pais(self):
        self.assertEqual(
            _normalizar_telefone_delta("(21) 3333-4444"),
            {
                "countryCode": 55,
                "areaCode": 21,
                "number": 33334444,
            },
        )

    def test_omite_telefone_incompleto(self):
        self.assertIsNone(_normalizar_telefone_delta("5521"))

    def test_omite_ddd_invalido(self):
        self.assertIsNone(_normalizar_telefone_delta("5509998765432"))

    def test_omite_telefone_ausente(self):
        self.assertIsNone(_normalizar_telefone_delta(None))

    def test_servico_envia_telefone_numerico_para_delta(self):
        request = SimpleNamespace(
            unidade="Nova Iguaçu 1",
            customer_name="Cliente Teste",
            customer_document="12345678901",
            customer_email="cliente@example.com",
            customer_phone="5521998765432",
            valor_total=60,
            payment_method="PIX AVULSO DELTA",
            metadata={
                "pre_venda_id": "PV-teste",
                "tipo_pagamento": "entrada_venda",
                "tipo_odontograma": "Particular",
            },
            criado_por=None,
        )

        with (
            patch(
                "app.delta_avulsa_sdk.environment.DeltaConfig.from_env",
                return_value=object(),
            ),
            patch("app.delta_avulsa_sdk.DeltaAvulsaSDK") as sdk_class,
        ):
            sdk = sdk_class.return_value.__enter__.return_value
            sdk.create_complete_invoice.return_value = {
                "id": 123,
                "checkoutUrl": "https://checkout.example.com/123",
            }

            asyncio.run(criar_fatura_avulsa_service(request))

        customer_data = sdk.create_complete_invoice.call_args.kwargs["customer_data"]
        self.assertEqual(
            customer_data["phone"],
            {
                "countryCode": 55,
                "areaCode": 21,
                "number": 998765432,
            },
        )
