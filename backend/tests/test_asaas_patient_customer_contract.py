import inspect
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.services import asaas_patient_customer_service as service


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "create_asaas_patient_customers.sql"
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.executions = []

    def execute(self, query, params):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return next(self.rows)


def make_row(
    *,
    link_id=1,
    paciente_id=10,
    unidade="São João de Meriti",
    environment="production",
    wallet_id="wallet_test_sjm",
    customer_id=None,
    remote_creation_allowed=False,
    status="pendente",
    attempt_count=0,
    error_code=None,
):
    now = datetime.now(timezone.utc)
    return (
        link_id,
        paciente_id,
        unidade,
        environment,
        wallet_id,
        customer_id,
        remote_creation_allowed,
        f"grupojf:paciente:{paciente_id}",
        status,
        attempt_count,
        None,
        error_code,
        None,
        None,
        now if status == "integrado" else None,
        now if status == "integrado" else None,
        now if status == "integrado" else None,
        now,
        now,
    )


class MigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION_PATH.read_text(encoding="utf-8")
        cls.normalized_sql = " ".join(cls.sql.lower().split())

    def test_migration_is_additive_and_idempotent(self):
        self.assertIn(
            "create table if not exists asaas_patient_customers",
            self.normalized_sql,
        )
        self.assertNotRegex(self.normalized_sql, r"\b(drop|truncate)\b")
        self.assertNotIn("delete from", self.normalized_sql)

    def test_migration_does_not_backfill_existing_patients(self):
        self.assertNotRegex(
            self.normalized_sql,
            r"\bfrom\s+(public\.)?pacientes\b",
        )
        self.assertNotIn("insert into", self.normalized_sql)

    def test_migration_preserves_patient_data_in_source_table(self):
        self.assertIn(
            "references pacientes(paciente_id) on delete cascade",
            self.normalized_sql,
        )
        for prohibited_column in (
            "api_key",
            "raw_response",
            "last_error_message",
            "cpf_cnpj",
            "nome_paciente",
            "email_paciente",
            "endereco_paciente",
        ):
            self.assertNotIn(prohibited_column, self.normalized_sql)

    def test_migration_scopes_customer_by_patient_environment_and_account(self):
        self.assertIn(
            "on asaas_patient_customers (paciente_id, environment, account_wallet_id)",
            self.normalized_sql,
        )
        self.assertIn(
            "on asaas_patient_customers (environment, account_wallet_id, asaas_customer_id)",
            self.normalized_sql,
        )
        self.assertIn(
            "on asaas_patient_customers (environment, account_wallet_id, external_reference)",
            self.normalized_sql,
        )

    def test_integrated_status_requires_remote_customer_id(self):
        self.assertIn(
            "check (status <> 'integrado' or asaas_customer_id is not null)",
            self.normalized_sql,
        )

    def test_remote_creation_is_fail_closed_for_existing_rows(self):
        self.assertIn(
            "add column if not exists remote_creation_allowed boolean not null default false",
            self.normalized_sql,
        )

    def test_error_code_is_constrained_to_non_pii_identifier(self):
        self.assertIn(
            "last_error_code ~ '^[a-za-z][a-za-z0-9_.:-]{0,99}$'",
            self.normalized_sql,
        )
        self.assertIn("last_error_code !~ '[0-9]{4,}'", self.normalized_sql)
        self.assertIn(
            "regexp_replace(last_error_code, '[^0-9]', '', 'g')",
            self.normalized_sql,
        )


class PersistenceContractTests(unittest.TestCase):
    def test_external_reference_contains_only_local_patient_id(self):
        self.assertEqual(
            service.build_external_reference(42),
            "grupojf:paciente:42",
        )

    def test_ensure_customer_link_is_idempotent_per_account(self):
        cursor = FakeCursor([make_row()])

        result = service.ensure_customer_link(
            cursor,
            paciente_id=10,
            unidade="  São João de Meriti  ",
            environment="PRODUCTION",
            account_wallet_id="  wallet_test_sjm  ",
        )

        query, params = cursor.executions[0]
        self.assertIn(
            "ON CONFLICT (paciente_id, environment, account_wallet_id)",
            query,
        )
        self.assertEqual(
            params,
            (
                10,
                "São João de Meriti",
                "production",
                "wallet_test_sjm",
                "grupojf:paciente:10",
                False,
            ),
        )
        self.assertEqual(result.status, "pendente")
        self.assertFalse(result.remote_creation_allowed)

    def test_new_local_patient_can_authorize_remote_creation(self):
        cursor = FakeCursor([make_row(remote_creation_allowed=True)])

        result = service.ensure_customer_link(
            cursor,
            paciente_id=10,
            unidade="São João de Meriti",
            environment="production",
            account_wallet_id="wallet_test_sjm",
            allow_remote_create=True,
        )

        query, params = cursor.executions[0]
        self.assertIn("remote_creation_allowed", query)
        self.assertIn("OR EXCLUDED.remote_creation_allowed", query)
        self.assertTrue(params[-1])
        self.assertTrue(result.remote_creation_allowed)

    def test_customer_link_can_be_locked_before_document_change(self):
        cursor = FakeCursor([make_row(customer_id="cus_known")])

        result = service.get_customer_link_for_update(
            cursor,
            paciente_id=10,
            environment="production",
            account_wallet_id="wallet_test_sjm",
        )

        query, _ = cursor.executions[0]
        self.assertIn("FOR UPDATE", query)
        self.assertEqual(result.asaas_customer_id, "cus_known")

    def test_same_patient_can_be_linked_to_distinct_accounts(self):
        sjm_cursor = FakeCursor([make_row(wallet_id="wallet_test_sjm")])
        vilar_cursor = FakeCursor(
            [
                make_row(
                    link_id=2,
                    unidade="Vilar dos Teles",
                    wallet_id="wallet_test_vilar",
                )
            ]
        )

        sjm = service.ensure_customer_link(
            sjm_cursor,
            paciente_id=10,
            unidade="São João de Meriti",
            environment="production",
            account_wallet_id="wallet_test_sjm",
        )
        vilar = service.ensure_customer_link(
            vilar_cursor,
            paciente_id=10,
            unidade="Vilar dos Teles",
            environment="production",
            account_wallet_id="wallet_test_vilar",
        )

        self.assertNotEqual(sjm.account_wallet_id, vilar.account_wallet_id)
        self.assertEqual(sjm.paciente_id, vilar.paciente_id)

    def test_claim_is_atomic_and_only_accepts_eligible_states(self):
        cursor = FakeCursor(
            [make_row(status="processando", attempt_count=1)]
        )

        result = service.claim_customer_sync(cursor, link_id=1)

        query, params = cursor.executions[0]
        self.assertIn("status IN ('pendente', 'erro')", query)
        self.assertIn("SET status = 'processando'", query)
        self.assertEqual(params, (1, None, None))
        self.assertEqual(result.status, "processando")

    def test_claim_returns_none_when_another_worker_owns_the_row(self):
        cursor = FakeCursor([None])

        result = service.claim_customer_sync(cursor, link_id=1)

        self.assertIsNone(result)

    def test_remote_customer_is_reserved_with_link_fencing(self):
        cursor = FakeCursor(
            [make_row(customer_id="cus_reserved", status="processando", attempt_count=3)]
        )

        result = service.reserve_customer_id(
            cursor,
            link_id=1,
            claim_attempt=3,
            asaas_customer_id="cus_reserved",
        )

        query, params = cursor.executions[0]
        self.assertIn("status = 'processando'", query)
        self.assertIn("attempt_count = %s", query)
        self.assertIn("asaas_customer_id IS NULL", query)
        self.assertEqual(params, ("cus_reserved", 1, 3, "cus_reserved"))
        self.assertEqual(result.asaas_customer_id, "cus_reserved")
        self.assertFalse(result.remote_creation_allowed)

    def test_reconciliation_can_authorize_create_after_confirmed_absence(self):
        cursor = FakeCursor([make_row(remote_creation_allowed=True)])

        result = service.allow_customer_creation(cursor, link_id=1)

        query, params = cursor.executions[0]
        self.assertIn("remote_creation_allowed = TRUE", query)
        self.assertEqual(params, (1,))
        self.assertTrue(result.remote_creation_allowed)

    def test_newer_patient_version_requests_resync_without_resetting_active_claim(self):
        requested = datetime(2026, 7, 16, tzinfo=timezone.utc)
        cursor = FakeCursor(
            [make_row(status="processando", attempt_count=1)]
        )

        result = service.request_customer_sync(
            cursor,
            link_id=1,
            patient_updated_at=requested,
        )

        query, params = cursor.executions[0]
        self.assertIn("status <> 'processando'", query)
        self.assertIn("requested_patient_updated_at", query)
        self.assertEqual(params[-1], 1)
        self.assertEqual(result.status, "processando")

    def test_integrated_link_is_claimable_when_requested_version_is_newer(self):
        cursor = FakeCursor(
            [make_row(status="processando", attempt_count=2)]
        )

        service.claim_customer_sync(cursor, link_id=1)

        query, _ = cursor.executions[0]
        self.assertIn("requested_patient_updated_at > last_synced_patient_updated_at", query)

    def test_mark_integrated_clears_failure_and_tracks_patient_version(self):
        patient_updated_at = datetime(2026, 7, 15, tzinfo=timezone.utc)
        cursor = FakeCursor(
            [
                make_row(
                    customer_id="cus_test_123",
                    status="integrado",
                    attempt_count=1,
                )
            ]
        )

        result = service.mark_customer_integrated(
            cursor,
            link_id=1,
            claim_attempt=1,
            asaas_customer_id="cus_test_123",
            http_status=200,
            patient_updated_at=patient_updated_at,
        )

        query, params = cursor.executions[0]
        self.assertIn("last_error_code = NULL", query)
        self.assertIn("AND status = 'processando'", query)
        self.assertIn("AND attempt_count = %s", query)
        self.assertEqual(
            params,
            (
                "cus_test_123",
                200,
                patient_updated_at,
                1,
                1,
                "cus_test_123",
            ),
        )
        self.assertEqual(result.asaas_customer_id, "cus_test_123")

    def test_failure_persists_only_controlled_error_code(self):
        cursor = FakeCursor(
            [
                make_row(
                    status="erro",
                    attempt_count=1,
                    error_code="integration_error",
                )
            ]
        )

        service.mark_customer_failed(
            cursor,
            link_id=1,
            claim_attempt=1,
            error_code="cpf_123.456.789-01",
            http_status=400,
        )

        query, params = cursor.executions[0]
        stored_error_code = params[2]
        self.assertEqual(stored_error_code, "integration_error")
        self.assertNotIn("last_error_message", query)
        self.assertNotIn(
            "error_message",
            inspect.signature(service.mark_customer_failed).parameters,
        )

    def test_conflict_is_terminal_and_does_not_schedule_retry(self):
        cursor = FakeCursor([make_row(status="conflito", attempt_count=1)])
        requested_retry = datetime(2026, 7, 16, tzinfo=timezone.utc)

        service.mark_customer_failed(
            cursor,
            link_id=1,
            claim_attempt=1,
            error_code="duplicate_customers",
            next_retry_at=requested_retry,
            status="conflito",
        )

        _, params = cursor.executions[0]
        self.assertIsNone(params[3])

    def test_newer_requested_version_reopens_link_after_older_failure(self):
        older_version = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
        cursor = FakeCursor([make_row(status="pendente", attempt_count=1)])

        service.mark_customer_failed(
            cursor,
            link_id=1,
            claim_attempt=1,
            error_code="duplicate_customers",
            status="conflito",
            patient_updated_at=older_version,
        )

        query, params = cursor.executions[0]
        self.assertIn(
            "requested_patient_updated_at > input.patient_version",
            query,
        )
        self.assertEqual(params[4], older_version)

    def test_dict_cursor_rows_are_mapped_by_column_name(self):
        row = make_row(customer_id="cus_test_123", status="integrado")
        row_dict = dict(
            zip(service.AsaasPatientCustomerRecord.__dataclass_fields__, row)
        )
        cursor = FakeCursor([row_dict])

        result = service.get_customer_link(
            cursor,
            paciente_id=10,
            environment="production",
            account_wallet_id="wallet_test_sjm",
        )

        self.assertEqual(result.id, 1)
        self.assertEqual(result.asaas_customer_id, "cus_test_123")

    def test_http_status_must_match_transition(self):
        success_cursor = FakeCursor([])
        failure_cursor = FakeCursor([])

        with self.assertRaisesRegex(ValueError, "integracao"):
            service.mark_customer_integrated(
                success_cursor,
                link_id=1,
                claim_attempt=1,
                asaas_customer_id="cus_test_123",
                http_status=400,
            )
        with self.assertRaisesRegex(ValueError, "falha"):
            service.mark_customer_failed(
                failure_cursor,
                link_id=1,
                claim_attempt=1,
                error_code="invalid_object",
                http_status=200,
            )

        self.assertEqual(success_cursor.executions, [])
        self.assertEqual(failure_cursor.executions, [])

    def test_invalid_environment_is_rejected_before_database_call(self):
        cursor = FakeCursor([])

        with self.assertRaisesRegex(ValueError, "environment"):
            service.ensure_customer_link(
                cursor,
                paciente_id=10,
                unidade="São João de Meriti",
                environment="development",
                account_wallet_id="wallet_test_sjm",
            )

        self.assertEqual(cursor.executions, [])


if __name__ == "__main__":
    unittest.main()
