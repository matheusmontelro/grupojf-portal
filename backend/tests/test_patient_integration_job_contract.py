import inspect
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services import patient_integration_job_service as service


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "create_patient_integration_jobs.sql"
)


class FakeCursor:
    def __init__(self, rows=(), many_rows=()):
        self.rows = iter(rows)
        self.many_rows = list(many_rows)
        self.executions = []

    def execute(self, query, params):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return next(self.rows)

    def fetchall(self):
        return self.many_rows


def make_row(
    *,
    job_id=1,
    paciente_id=10,
    provider="delta",
    target_key="clinic_sjm",
    environment="production",
    patient_version=None,
    status="pendente",
    attempt_count=0,
    http_status=None,
    error_code=None,
    next_retry_at=None,
):
    now = datetime.now(timezone.utc)
    return (
        job_id,
        paciente_id,
        provider,
        target_key,
        environment,
        patient_version or now,
        status,
        attempt_count,
        http_status,
        error_code,
        now if attempt_count else None,
        None,
        next_retry_at,
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
            "create table if not exists patient_integration_jobs",
            self.normalized_sql,
        )
        self.assertGreaterEqual(self.normalized_sql.count("if not exists"), 5)
        self.assertNotIn("drop table", self.normalized_sql)
        self.assertNotIn("truncate", self.normalized_sql)
        self.assertNotIn("delete from", self.normalized_sql)
        self.assertIn(
            "alter table asaas_patient_customers drop constraint",
            self.normalized_sql,
        )
        self.assertIn(
            "alter table asaas_patient_customers add column if not exists "
            "requested_patient_updated_at timestamptz",
            self.normalized_sql,
        )
        self.assertGreaterEqual(self.normalized_sql.count("on delete restrict"), 3)

    def test_migration_does_not_backfill_existing_patients(self):
        self.assertNotRegex(
            self.normalized_sql,
            r"\bfrom\s+(public\.)?pacientes\b",
        )
        self.assertNotIn("insert into", self.normalized_sql)

    def test_table_contains_no_personal_or_secret_payload(self):
        for prohibited_column in (
            "cpf",
            "cnpj",
            "nome_paciente",
            "email",
            "telefone",
            "address",
            "endereco",
            "payload",
            "raw_response",
            "error_message",
            "api_key",
            "token",
        ):
            self.assertNotIn(prohibited_column, self.normalized_sql)

    def test_provider_environment_version_and_states_are_constrained(self):
        self.assertIn("provider in ('delta', 'asaas')", self.normalized_sql)
        self.assertIn("environment in ('sandbox', 'production')", self.normalized_sql)
        for status in (
            "pendente",
            "processando",
            "retry",
            "integrado",
            "conflito",
            "erro_terminal",
            "superseded",
        ):
            self.assertIn(f"'{status}'", self.normalized_sql)

    def test_version_is_idempotent_and_only_one_active_job_exists(self):
        self.assertIn(
            "paciente_id, provider, target_key, environment, patient_version",
            self.normalized_sql,
        )
        self.assertIn("uq_patient_integration_job_active", self.normalized_sql)
        self.assertIn(
            "where status = 'processando'",
            self.normalized_sql,
        )

    def test_dispatch_retry_stale_and_history_indexes_exist(self):
        self.assertIn("idx_patient_integration_dispatch", self.normalized_sql)
        self.assertIn("idx_patient_integration_stale_claim", self.normalized_sql)
        self.assertIn("idx_patient_integration_patient_history", self.normalized_sql)
        self.assertIn("last_dispatched_at", self.normalized_sql)

    def test_error_code_rejects_likely_personal_identifiers(self):
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
    def setUp(self):
        self.version = datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc)

    def test_enqueue_serializes_scope_and_supersedes_older_active_jobs(self):
        cursor = FakeCursor(
            rows=[make_row(patient_version=self.version)],
        )

        result = service.enqueue_patient_integration_job(
            cursor,
            paciente_id=10,
            provider=" DELTA ",
            target_key=" clinic_sjm ",
            environment=" PRODUCTION ",
            patient_version=self.version,
        )

        lock_query, lock_params = cursor.executions[0]
        upsert_query, upsert_params = cursor.executions[1]
        self.assertIn("pg_advisory_xact_lock", lock_query)
        self.assertNotIn("cpf", lock_params[0].lower())
        self.assertIn("patient_version < %s", upsert_query)
        self.assertIn(
            "status IN ('pendente', 'retry')",
            upsert_query,
        )
        self.assertIn("ON CONFLICT", upsert_query)
        self.assertIn("superseded", upsert_query)
        self.assertIn("delta", upsert_params)
        self.assertIn("clinic_sjm", upsert_params)
        self.assertEqual(result.status, "pendente")

    def test_enqueue_accepts_confirmed_import_as_integrated(self):
        cursor = FakeCursor(
            rows=[
                make_row(
                    provider="delta",
                    patient_version=self.version,
                    status="integrado",
                )
            ]
        )

        result = service.enqueue_patient_integration_job(
            cursor,
            paciente_id=10,
            provider="delta",
            target_key="clinic_sjm",
            environment="production",
            patient_version=self.version,
            initial_status="integrado",
        )

        query, params = cursor.executions[1]
        self.assertIn("WHEN %s = 'integrado' THEN NOW()", query)
        self.assertIn("integrado", params)
        self.assertEqual(result.status, "integrado")

    def test_confirmed_import_never_finishes_an_active_claim_without_fencing(self):
        cursor = FakeCursor(
            rows=[
                make_row(
                    provider="delta",
                    patient_version=self.version,
                    status="processando",
                    attempt_count=1,
                )
            ]
        )

        result = service.enqueue_patient_integration_job(
            cursor,
            paciente_id=10,
            provider="delta",
            target_key="clinic_sjm",
            environment="production",
            patient_version=self.version,
            initial_status="integrado",
        )

        query, _ = cursor.executions[1]
        self.assertIn(
            "patient_integration_jobs.status NOT IN ( 'superseded', 'processando' )",
            query,
        )
        self.assertEqual(result.status, "processando")

    def test_out_of_order_version_is_inserted_as_superseded(self):
        cursor = FakeCursor(
            rows=[
                make_row(
                    patient_version=self.version,
                    status="superseded",
                )
            ]
        )

        service.enqueue_patient_integration_job(
            cursor,
            paciente_id=10,
            provider="delta",
            target_key="clinic_sjm",
            environment="production",
            patient_version=self.version,
        )

        query, _ = cursor.executions[1]
        self.assertIn("latest_version.value > %s THEN 'superseded'", query)

    def test_list_dispatchable_jobs_includes_due_retry_and_stale_recovery(self):
        stale_before = self.version - timedelta(minutes=10)
        row = make_row(patient_version=self.version)
        cursor = FakeCursor(many_rows=[row])

        jobs = service.list_dispatchable_jobs(
            cursor,
            provider="delta",
            environment="production",
            stale_before=stale_before,
            dispatch_before=stale_before,
            limit=25,
        )

        query, params = cursor.executions[0]
        self.assertIn("job.status = 'pendente'", query)
        self.assertIn("job.status = 'retry'", query)
        self.assertIn("job.next_retry_at <= NOW()", query)
        self.assertIn("job.status = 'processando'", query)
        self.assertIn("job.last_attempt_at <= %s", query)
        self.assertIn("job.last_dispatched_at IS NULL", query)
        self.assertIn("job.last_dispatched_at <= %s", query)
        self.assertIn("active_job.status = 'processando'", query)
        self.assertIn("newer_job.patient_version > job.patient_version", query)
        self.assertLess(
            query.index("WHEN job.status = 'pendente'"),
            query.index("job.patient_version DESC"),
        )
        self.assertNotIn("FOR UPDATE", query)
        self.assertEqual(params[-1], 25)
        self.assertEqual(jobs[0].id, 1)

    def test_dispatcher_api_returns_only_safe_numeric_job_ids(self):
        stale_before = self.version - timedelta(minutes=5)
        cursor = FakeCursor(
            many_rows=[
                make_row(job_id=11, patient_version=self.version),
                make_row(job_id=12, patient_version=self.version),
            ]
        )

        job_ids = service.list_dispatchable_job_ids(
            cursor,
            provider="asaas",
            limit=50,
            stale_before=stale_before,
            dispatch_before=stale_before,
        )

        query, params = cursor.executions[0]
        self.assertIn("FROM patient_integration_jobs AS job", query)
        self.assertNotRegex(query, r"\bFROM\s+(public\.)?pacientes\b")
        self.assertEqual(job_ids, [11, 12])
        self.assertEqual(params[0], "asaas")
        self.assertEqual(params[-5:-1], (stale_before,) * 4)
        self.assertEqual(params[-1], 50)

    def test_successful_publish_records_dispatch_lease(self):
        cursor = FakeCursor(
            rows=[make_row(job_id=11, patient_version=self.version)]
        )

        result = service.mark_patient_integration_dispatched(
            cursor,
            job_id=11,
        )

        query, params = cursor.executions[0]
        self.assertIn("last_dispatched_at = NOW()", query)
        self.assertEqual(params, (11,))
        self.assertEqual(result.id, 11)

    def test_claim_is_atomic_due_aware_and_increments_fencing_token(self):
        cursor = FakeCursor(
            rows=[
                make_row(
                    patient_version=self.version,
                    status="processando",
                    attempt_count=2,
                )
            ]
        )

        result = service.claim_job(cursor, job_id=1)

        lock_query, lock_params = cursor.executions[0]
        query, params = cursor.executions[1]
        self.assertIn("pg_advisory_xact_lock", lock_query)
        self.assertEqual(lock_params, (1,))
        self.assertIn("UPDATE patient_integration_jobs", query)
        self.assertIn("attempt_count = job.attempt_count + 1", query)
        self.assertIn("status = 'retry'", query)
        self.assertIn("next_retry_at <= NOW()", query)
        self.assertIn("active_job.status = 'processando'", query)
        self.assertIn("active_job.id <> candidate.id", query)
        self.assertIn("newer_job.patient_version > candidate.patient_version", query)
        self.assertIn("older_job.status IN ('pendente', 'retry')", query)
        self.assertIn("RETURNING", query)
        self.assertEqual(params, (1, None, None))
        self.assertEqual(result.attempt_count, 2)

    def test_stale_processing_job_can_be_reclaimed(self):
        stale_before = self.version - timedelta(minutes=10)
        cursor = FakeCursor(rows=[None])

        result = service.claim_job(
            cursor,
            job_id=1,
            stale_before=stale_before,
        )

        query, params = cursor.executions[1]
        self.assertIn("last_attempt_at <= %s", query)
        self.assertEqual(params, (1, stale_before, stale_before))
        self.assertIsNone(result)

    def test_claim_next_prioritizes_oldest_eligible_then_uses_atomic_claim(self):
        candidate = make_row(patient_version=self.version)
        claimed = make_row(
            patient_version=self.version,
            status="processando",
            attempt_count=1,
        )
        cursor = FakeCursor(rows=[claimed], many_rows=[candidate])

        result = service.claim_next_job(cursor, provider="asaas")

        list_query, _ = cursor.executions[0]
        lock_query, _ = cursor.executions[1]
        claim_query, _ = cursor.executions[2]
        self.assertIn("patient_version DESC", list_query)
        self.assertIn("pg_advisory_xact_lock", lock_query)
        self.assertIn("attempt_count = job.attempt_count + 1", claim_query)
        self.assertEqual(result.status, "processando")

    def test_mark_integrated_is_fenced_by_status_and_attempt(self):
        cursor = FakeCursor(
            rows=[
                make_row(
                    patient_version=self.version,
                    status="integrado",
                    attempt_count=2,
                    http_status=200,
                )
            ]
        )

        service.mark_job_integrated(
            cursor,
            job_id=1,
            claim_attempt=2,
            http_status=200,
        )

        query, params = cursor.executions[0]
        self.assertIn("AND status = 'processando'", query)
        self.assertIn("AND attempt_count = %s", query)
        self.assertEqual(params, (200, 1, 2))

    def test_lost_fencing_token_cannot_finish_job(self):
        cursor = FakeCursor(rows=[None])

        with self.assertRaisesRegex(LookupError, "claim"):
            service.mark_job_integrated(
                cursor,
                job_id=1,
                claim_attempt=1,
            )

    def test_retry_requires_schedule_and_sanitizes_error_code(self):
        invalid_cursor = FakeCursor()
        with self.assertRaisesRegex(ValueError, "next_retry_at"):
            service.mark_job_failed(
                invalid_cursor,
                job_id=1,
                claim_attempt=1,
                error_code="timeout",
            )
        self.assertEqual(invalid_cursor.executions, [])

        retry_at = self.version + timedelta(minutes=5)
        cursor = FakeCursor(
            rows=[
                make_row(
                    patient_version=self.version,
                    status="retry",
                    attempt_count=1,
                    error_code="integration_error",
                    next_retry_at=retry_at,
                )
            ]
        )
        service.mark_job_failed(
            cursor,
            job_id=1,
            claim_attempt=1,
            error_code="cpf_123.456.789-01",
            http_status=503,
            next_retry_at=retry_at,
        )

        query, params = cursor.executions[0]
        self.assertEqual(params[2], "integration_error")
        self.assertEqual(params[3], retry_at)
        self.assertEqual(params[4], "retry")
        self.assertNotIn("error_message", query)
        self.assertNotIn(
            "error_message",
            inspect.signature(service.mark_job_failed).parameters,
        )

    def test_terminal_failure_never_keeps_retry_schedule(self):
        cursor = FakeCursor(
            rows=[
                make_row(
                    patient_version=self.version,
                    status="conflito",
                    attempt_count=1,
                    error_code="duplicate_customers",
                )
            ]
        )
        service.mark_job_failed(
            cursor,
            job_id=1,
            claim_attempt=1,
            error_code="duplicate_customers",
            status="conflito",
            next_retry_at=self.version + timedelta(minutes=5),
        )

        _, params = cursor.executions[0]
        self.assertIsNone(params[3])

    def test_superseded_transition_is_fenced(self):
        cursor = FakeCursor(
            rows=[
                make_row(
                    patient_version=self.version,
                    status="superseded",
                    attempt_count=1,
                )
            ]
        )

        service.mark_job_superseded(cursor, job_id=1, claim_attempt=1)

        query, params = cursor.executions[0]
        self.assertIn("AND status = 'processando'", query)
        self.assertIn("AND attempt_count = %s", query)
        self.assertEqual(params, (1, 1))

    def test_service_never_controls_transaction(self):
        source = inspect.getsource(service).lower()
        self.assertNotIn(".commit(", source)
        self.assertNotIn(".rollback(", source)

    def test_invalid_input_is_rejected_before_database_call(self):
        cursor = FakeCursor()

        with self.assertRaisesRegex(ValueError, "provider"):
            service.enqueue_patient_integration_job(
                cursor,
                paciente_id=10,
                provider="stripe",
                target_key="clinic_sjm",
                environment="production",
                patient_version=self.version,
            )
        with self.assertRaisesRegex(ValueError, "timezone"):
            service.enqueue_patient_integration_job(
                cursor,
                paciente_id=10,
                provider="delta",
                target_key="clinic_sjm",
                environment="production",
                patient_version=datetime(2026, 7, 16, 12, 30),
            )

        self.assertEqual(cursor.executions, [])


if __name__ == "__main__":
    unittest.main()
