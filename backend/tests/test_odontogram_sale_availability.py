import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.routers.odontograma import (
    _active_sale_ids_by_odontogram,
    _with_sale_availability,
)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.executions = []

    def execute(self, query, params):
        self.executions.append((str(query), params))
        return FakeResult(self.rows)


class OdontogramSaleAvailabilityTests(unittest.TestCase):
    @staticmethod
    def make_odontogram():
        now = datetime.now(timezone.utc)
        return SimpleNamespace(
            id=10,
            paciente_id=1,
            dentista_orcamentista_id=2,
            unidade="SJM",
            Tipo="Particular",
            dependente_id=None,
            ativo=True,
            data_criacao=now,
            usuario_criacao_id=3,
            created_at=now,
            updated_at=now,
            itens=[],
            dentista_orcamentista=None,
        )

    def test_non_cancelled_sale_blocks_odontogram(self):
        odontogram = self.make_odontogram()
        db = FakeDb([(10, 18)])

        active_sale_ids = _active_sale_ids_by_odontogram(db, [odontogram])
        self.assertEqual(active_sale_ids, {10: 18})
        self.assertIn("status_venda <> 'Cancelada'", db.executions[0][0])
        self.assertEqual(db.executions[0][1], {"odontogram_ids": [10]})

        response = _with_sale_availability([odontogram], active_sale_ids)[0]
        self.assertFalse(response.disponivel_para_venda)
        self.assertEqual(response.venda_ativa_id, 18)

    def test_cancelled_sale_releases_odontogram(self):
        odontogram = self.make_odontogram()
        db = FakeDb([])

        active_sale_ids = _active_sale_ids_by_odontogram(db, [odontogram])
        self.assertEqual(active_sale_ids, {})
        response = _with_sale_availability([odontogram], active_sale_ids)[0]
        self.assertTrue(response.disponivel_para_venda)
        self.assertIsNone(response.venda_ativa_id)


if __name__ == "__main__":
    unittest.main()
