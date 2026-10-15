import unittest

from app.services.financeiro_pagamentos_service import (
    FinanceiroPagamentosService,
)


class FinanceiroPagamentosAsaasProjectionTests(unittest.TestCase):
    def test_query_projects_remote_resource_without_mutating_installment(self):
        query = " ".join(
            FinanceiroPagamentosService()._base_cte().split()
        )

        self.assertIn("LEFT JOIN asaas_sale_payment_links", query)
        self.assertIn("LEFT JOIN asaas_sale_resources", query)
        self.assertIn("pago_em_atraso", query)
        self.assertIn("Pix Recorrente", query)
        self.assertNotIn("UPDATE venda_parcelas", query)


if __name__ == "__main__":
    unittest.main()
