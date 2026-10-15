import unittest
from datetime import date, datetime
from pathlib import Path

from pydantic import ValidationError

from app.models.pacientes import DadosDependenteModel, DependenteUpdate, PacienteCreate
from app.pacientes_sdk.sdk_utils import transform_from_delta_format, transform_to_delta_format
from app.routers.pacientes import _map_row_to_paciente_read as map_patient_row
from app.routers.pacientes_integrados import _map_row_to_paciente_read as map_integrated_patient_row


class PacientesAddressContractTests(unittest.TestCase):
    def test_line_two_is_optional_and_preserved_by_model(self):
        without_complement = PacienteCreate(nome_paciente="Paciente", cpf_cnpj="12345678901")
        with_complement = PacienteCreate(
            nome_paciente="Paciente",
            cpf_cnpj="12345678901",
            line_two="Apto 202",
        )

        self.assertIsNone(without_complement.line_two)
        self.assertEqual(with_complement.line_two, "Apto 202")

    def test_delta_round_trip_preserves_line_two(self):
        payload = transform_to_delta_format({
            "nome_paciente": "Paciente",
            "cpf_cnpj": "12345678901",
            "street": "Rua A",
            "street_number": "10",
            "line_two": "Fundos",
            "neighborhood": "Centro",
            "city": "Rio de Janeiro",
            "state": "RJ",
            "zip_code": "20000-000",
        })

        self.assertEqual(payload["address"]["lineTwo"], "Fundos")
        restored = transform_from_delta_format({"address": payload["address"]})
        self.assertEqual(restored["line_two"], "Fundos")

    def test_dependent_requires_complete_data(self):
        with self.assertRaises(ValidationError):
            DadosDependenteModel(nome_dependente="Ana")

        dependent = DadosDependenteModel(
            nome_dependente="Ana",
            data_nascimento_dependente=date(2020, 1, 2),
            genero_dependente="Feminino",
            parentesco="Filha",
        )
        self.assertEqual(dependent.parentesco, "Filha")

    def test_status_only_update_remains_compatible(self):
        self.assertFalse(DependenteUpdate(ativo=False).ativo)
        with self.assertRaises(ValidationError):
            DependenteUpdate(nome_dependente="Ana")

    def test_database_row_mappers_keep_line_two_position(self):
        common = [
            1, "Paciente", "12345678901", "p@example.invalid", date(1990, 1, 1),
            False, None, "55", "21", "999999999", "Rua A", "10", "Apto 202",
            "Centro", "Rio de Janeiro", "RJ", "20000000", datetime(2026, 1, 1), datetime(2026, 1, 1), "Unidade",
            None, None, None, None,
        ]
        mapped = map_patient_row(common)
        integrated = map_integrated_patient_row([*common, None])

        self.assertEqual(mapped.line_two, "Apto 202")
        self.assertEqual(integrated.line_two, "Apto 202")

    def test_migration_is_additive_and_idempotent(self):
        migration = Path(__file__).parents[1] / "migrations" / "add_line_two_to_pacientes.sql"
        source = migration.read_text(encoding="utf-8").upper()

        self.assertIn("ADD COLUMN IF NOT EXISTS LINE_TWO TEXT", source)
        self.assertNotIn("DROP COLUMN", source)
        self.assertNotIn("DELETE ", source)


if __name__ == "__main__":
    unittest.main()
