import inspect
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.services import delta_patient_customer_service as service


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "create_patient_integration_jobs.sql"
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.executions = []

    def execute(self, query, params):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return next(self.rows)


def make_row(*, link_id=1, customer_id=None, remote_creation_allowed=False):
    now = datetime.now(timezone.utc)
    return (
        link_id,
        42,
        "production",
        "delta:production:sao_joao_de_meriti",
        customer_id,
        remote_creation_allowed,
        now,
        now,
    )


class DeltaLinkMigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION_PATH.read_text(encoding="utf-8")
        cls.normalized = " ".join(cls.sql.lower().split())

    def test_table_is_additive_and_idempotent(self):
        self.assertIn(
            "create table if not exists patient_delta_customers",
            self.normalized,
        )
        self.assertNotIn("drop table", self.normalized)
        self.assertNotIn("truncate", self.normalized)
        self.assertNotIn("delete from", self.normalized)

    def test_link_is_scoped_by_patient_environment_and_target(self):
        self.assertIn(
            "on patient_delta_customers (paciente_id, environment, target_key)",
            self.normalized,
        )
        self.assertIn(
            "on patient_delta_customers (environment, target_key, delta_customer_id)",
            self.normalized,
        )
        self.assertIn(
            "references pacientes(paciente_id) on delete restrict",
            self.normalized,
        )

    def test_table_does_not_duplicate_patient_personal_data(self):
        table_sql = self.normalized.split(
            "create table if not exists patient_delta_customers", 1
        )[1].split("create unique index", 1)[0]
        for prohibited_column in (
            "cpf_cnpj",
            "document",
            "nome_paciente",
            "email",
            "phone",
            "address",
            "raw_response",
            "last_error_message",
        ):
            self.assertNotIn(prohibited_column, table_sql)


class DeltaLinkPersistenceContractTests(unittest.TestCase):
    def test_ensure_is_idempotent_for_same_destination(self):
        cursor = FakeCursor([make_row()])

        record = service.ensure_delta_customer_link(
            cursor,
            paciente_id=42,
            environment="PRODUCTION",
            target_key=" delta:production:sao_joao_de_meriti ",
        )

        query, params = cursor.executions[0]
        self.assertIn(
            "ON CONFLICT (paciente_id, environment, target_key)",
            query,
        )
        self.assertEqual(
            params,
            (42, "production", "delta:production:sao_joao_de_meriti", False),
        )
        self.assertIsNone(record.delta_customer_id)
        self.assertFalse(record.remote_creation_allowed)

    def test_remote_creation_requires_explicit_authorization(self):
        cursor = FakeCursor([make_row(remote_creation_allowed=True)])

        record = service.ensure_delta_customer_link(
            cursor,
            paciente_id=42,
            environment="production",
            target_key="delta:production:sao_joao_de_meriti",
            allow_remote_create=True,
        )

        query, params = cursor.executions[0]
        self.assertIn("remote_creation_allowed", query)
        self.assertIn("OR EXCLUDED.remote_creation_allowed", query)
        self.assertEqual(params[-1], True)
        self.assertTrue(record.remote_creation_allowed)

    def test_confirmed_absence_can_authorize_creation_without_personal_data(self):
        cursor = FakeCursor([make_row(remote_creation_allowed=True)])

        record = service.allow_delta_customer_creation(cursor, link_id=1)

        query, params = cursor.executions[0]
        self.assertIn("delta_customer_id IS NULL", query)
        self.assertEqual(params, (1,))
        self.assertTrue(record.remote_creation_allowed)

    def test_get_returns_none_when_link_does_not_exist(self):
        cursor = FakeCursor([None])

        record = service.get_delta_customer_link(
            cursor,
            paciente_id=42,
            environment="production",
            target_key="delta:production:sao_joao_de_meriti",
        )

        self.assertIsNone(record)

    def test_set_remote_id_is_idempotent_but_never_remaps(self):
        cursor = FakeCursor([make_row(customer_id="customer_abc-123")])

        record = service.set_delta_customer_id(
            cursor,
            link_id=1,
            delta_customer_id=" customer_abc-123 ",
        )

        query, params = cursor.executions[0]
        self.assertIn("delta_customer_id IS NULL", query)
        self.assertIn("OR delta_customer_id = %s", query)
        self.assertEqual(params, ("customer_abc-123", 1, "customer_abc-123"))
        self.assertEqual(record.delta_customer_id, "customer_abc-123")

        conflict_cursor = FakeCursor([None])
        with self.assertRaisesRegex(ValueError, "associado a outro customer"):
            service.set_delta_customer_id(
                conflict_cursor,
                link_id=1,
                delta_customer_id="other-id",
            )

    def test_rejects_target_environment_mismatch_and_unsafe_remote_id(self):
        with self.assertRaisesRegex(ValueError, "environment"):
            service.ensure_delta_customer_link(
                FakeCursor([]),
                paciente_id=42,
                environment="production",
                target_key="delta:sandbox:sao_joao_de_meriti",
            )

        for unsafe_id in ("", "../customer", "customer/42", "customer?token=x"):
            with self.subTest(unsafe_id=unsafe_id):
                with self.assertRaisesRegex(ValueError, "delta_customer_id"):
                    service.normalize_delta_customer_id(unsafe_id)

    def test_service_does_not_control_transactions(self):
        source = inspect.getsource(service).lower()
        self.assertNotIn(".commit(", source)
        self.assertNotIn(".rollback(", source)


if __name__ == "__main__":
    unittest.main()
