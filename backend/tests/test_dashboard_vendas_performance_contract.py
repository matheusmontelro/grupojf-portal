import inspect
from pathlib import Path
import unittest

from app.routers import dashboard_vendas


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROUTER_SOURCE = (BACKEND_ROOT / "app/routers/dashboard_vendas.py").read_text()
MIGRATION_SOURCE = (
    BACKEND_ROOT / "migrations/optimize_dashboard_vendas_indexes.sql"
).read_text()


class DashboardVendasPerformanceContractTests(unittest.TestCase):
    def test_endpoint_uses_threadpool_for_sync_database_work(self):
        self.assertFalse(inspect.iscoroutinefunction(dashboard_vendas.obter_dashboard_vendas))

    def test_date_filters_remain_indexable(self):
        self.assertNotIn("DATE(", ROUTER_SOURCE)
        self.assertIn("data_fim_exclusivo", ROUTER_SOURCE)
        self.assertIn("data_pagamento >= :data_inicio", ROUTER_SOURCE)
        self.assertIn("data_vencimento >= :data_inicio", ROUTER_SOURCE)

    def test_kpis_remain_consolidated(self):
        self.assertIn("vendas_kpis_query", ROUTER_SOURCE)
        self.assertEqual(ROUTER_SOURCE.count("db.execute("), 11)

    def test_migration_uses_concurrent_targeted_indexes(self):
        index_statements = [
            line
            for line in MIGRATION_SOURCE.splitlines()
            if line.startswith("CREATE INDEX CONCURRENTLY")
        ]
        self.assertEqual(len(index_statements), 8)
        for table in (
            "vendas",
            "venda_parcelas",
            "carne_parcelas",
            "pre_vendas_entradas",
        ):
            self.assertIn(f"ON {table}", MIGRATION_SOURCE)


if __name__ == "__main__":
    unittest.main()
