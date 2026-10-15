import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.routers import dentista, odontograma


class FakeQuery:
    def __init__(self, result):
        self.result = result
        self.filters = []

    def options(self, *args):
        return self

    def distinct(self):
        return self

    def join(self, *args):
        return self

    def filter(self, *conditions):
        self.filters.extend(conditions)
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return self.result

    def all(self):
        return self.result


class FakeDb:
    def __init__(self, queries):
        self.queries = list(queries)

    def query(self, _model):
        return self.queries.pop(0)


class FakeJoinedLoad:
    def joinedload(self, _relationship):
        return self


class OdontogramaDependenteRoutesTests(unittest.TestCase):
    def test_odontogramas_uses_explicit_responsible_and_dependent_ids(self):
        dependent_query = FakeQuery(SimpleNamespace())
        odontogramas = [SimpleNamespace(id=3824)]
        odontogram_query = FakeQuery(odontogramas)
        db = FakeDb([dependent_query, odontogram_query])

        with patch.object(
            odontograma, "_active_sale_ids_by_odontogram", return_value={}
        ) as active_sale_ids, patch.object(
            odontograma, "_with_sale_availability", side_effect=lambda rows, _sales: rows
        ) as with_sale_availability, patch.object(
            odontograma, "joinedload", return_value=FakeJoinedLoad()
        ):
            result = odontograma.get_odontogramas_por_paciente(
                paciente_id=2506,
                ativo=True,
                tipo="Particular",
                dependente_id=278,
                db=db,
            )

        self.assertEqual(result, odontogramas)
        self.assertIn("dependentes.dependente_id", str(dependent_query.filters[0]))
        self.assertIn("dependentes.responsavel_paciente_id", str(dependent_query.filters[1]))
        self.assertIn("odontogramas.paciente_id", str(odontogram_query.filters[0]))
        self.assertIn("odontogramas.dependente_id", str(odontogram_query.filters[1]))
        self.assertIn("odontogramas.ativo", str(odontogram_query.filters[2]))
        self.assertIn("odontogramas.tipo", str(odontogram_query.filters[3]))
        active_sale_ids.assert_called_once_with(db, odontogramas)
        with_sale_availability.assert_called_once_with(odontogramas, {})

    def test_odontogramas_returns_empty_when_dependent_is_not_linked(self):
        db = FakeDb([FakeQuery(None)])

        result = odontograma.get_odontogramas_por_paciente(
            paciente_id=2506,
            ativo=True,
            tipo=None,
            dependente_id=278,
            db=db,
        )

        self.assertEqual(result, [])

    def test_dentistas_uses_explicit_responsible_and_dependent_ids(self):
        dependent_query = FakeQuery(SimpleNamespace())
        dentistas = [SimpleNamespace(id=7)]
        dentist_query = FakeQuery(dentistas)
        db = FakeDb([dependent_query, dentist_query])

        result = dentista.get_dentistas_por_paciente_odontograma(
            paciente_id=2506,
            ativo=True,
            dependente_id=278,
            db=db,
        )

        self.assertEqual(result, dentistas)
        self.assertIn("dependentes.dependente_id", str(dependent_query.filters[0]))
        self.assertIn("dependentes.responsavel_paciente_id", str(dependent_query.filters[1]))
        self.assertIn("odontogramas.paciente_id", str(dentist_query.filters[0]))
        self.assertIn("odontogramas.dependente_id", str(dentist_query.filters[1]))
        self.assertIn("odontogramas.ativo", str(dentist_query.filters[2]))

    def test_dentistas_returns_empty_when_dependent_is_not_linked(self):
        db = FakeDb([FakeQuery(None)])

        result = dentista.get_dentistas_por_paciente_odontograma(
            paciente_id=2506,
            ativo=True,
            dependente_id=278,
            db=db,
        )

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
