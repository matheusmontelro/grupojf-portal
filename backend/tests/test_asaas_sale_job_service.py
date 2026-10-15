import unittest
from datetime import datetime, timedelta, timezone

from app.services import asaas_sale_job_service as service


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


def make_job_row(
    *,
    job_id=1,
    integration_id=None,
    webhook_event_id=20,
    operation="processar_webhook",
    deduplication_key="webhook:20",
    status="pendente",
    attempt_count=0,
    error_code=None,
    next_retry_at=None,
):
    now = datetime.now(timezone.utc)
    return (
        job_id,
        integration_id,
        webhook_event_id,
        operation,
        deduplication_key,
        status,
        attempt_count,
        error_code,
        now if attempt_count else None,
        None,
        next_retry_at,
        now if status in {"integrado", "conflito", "erro_terminal"} else None,
        now,
        now,
    )


class AsaasSaleJobServiceTests(unittest.TestCase):
    def test_enqueue_is_idempotent_and_has_exactly_one_technical_subject(self):
        cursor = FakeCursor(rows=[make_job_row()])

        result = service.enqueue_asaas_sale_job(
            cursor,
            webhook_event_id=20,
            operation="processar_webhook",
            deduplication_key="webhook:20",
        )

        query, params = cursor.executions[0]
        self.assertIn("ON CONFLICT (operation, deduplication_key)", query)
        self.assertEqual(params, (None, 20, "processar_webhook", "webhook:20"))
        self.assertEqual(result.webhook_event_id, 20)

        invalid_subjects = (
            {},
            {"integration_id": 1, "webhook_event_id": 2},
        )
        for subject in invalid_subjects:
            with self.subTest(subject=subject):
                with self.assertRaises(ValueError):
                    service.enqueue_asaas_sale_job(
                        cursor,
                        operation="processar_webhook",
                        deduplication_key="webhook:21",
                        **subject,
                    )

    def test_enqueue_rejects_deduplication_collision_between_subjects(self):
        cursor = FakeCursor(rows=[make_job_row(webhook_event_id=20)])

        with self.assertRaisesRegex(RuntimeError, "identidade idempotente"):
            service.enqueue_asaas_sale_job(
                cursor,
                webhook_event_id=21,
                operation="processar_webhook",
                deduplication_key="webhook:20",
            )

    def test_reconciliation_enqueue_coalesces_active_job(self):
        retry_at = datetime.now(timezone.utc) + timedelta(minutes=1)
        cursor = FakeCursor(
            rows=[
                make_job_row(
                    integration_id=7,
                    webhook_event_id=None,
                    operation="reconciliar_venda",
                    deduplication_key="reconcile:7",
                    status="retry",
                    attempt_count=2,
                    error_code="resource_not_ready",
                    next_retry_at=retry_at,
                )
            ]
        )

        result = service.enqueue_asaas_sale_reconciliation_job(
            cursor,
            integration_id=7,
        )

        query, params = cursor.executions[0]
        self.assertIn("ON CONFLICT (operation, deduplication_key)", query)
        self.assertIn("ELSE asaas_sale_integration_jobs.status", query)
        self.assertEqual(params, (7, "reconcile:7"))
        self.assertEqual(result.status, "retry")
        self.assertEqual(result.next_retry_at, retry_at)

    def test_reconciliation_enqueue_reopens_terminal_job(self):
        cursor = FakeCursor(
            rows=[
                make_job_row(
                    integration_id=7,
                    webhook_event_id=None,
                    operation="reconciliar_venda",
                    deduplication_key="reconcile:7",
                    status="pendente",
                    attempt_count=3,
                )
            ]
        )

        result = service.enqueue_asaas_sale_reconciliation_job(
            cursor,
            integration_id=7,
        )

        query, _params = cursor.executions[0]
        self.assertIn("'integrado'", query)
        self.assertIn("'conflito'", query)
        self.assertIn("'erro_terminal'", query)
        self.assertIn("'superseded'", query)
        self.assertIn("THEN 'pendente'", query)
        self.assertIn("last_error_code = CASE", query)
        self.assertIn("last_dispatched_at = CASE", query)
        self.assertIn("next_retry_at = CASE", query)
        self.assertIn("completed_at = CASE", query)
        self.assertEqual(result.status, "pendente")
        self.assertIsNone(result.last_error_code)
        self.assertIsNone(result.next_retry_at)
        self.assertIsNone(result.completed_at)

    def test_reconciliation_enqueue_rejects_subject_collision(self):
        cursor = FakeCursor(rows=[None])

        with self.assertRaisesRegex(RuntimeError, "identidade idempotente"):
            service.enqueue_asaas_sale_reconciliation_job(
                cursor,
                integration_id=7,
            )

        query, _params = cursor.executions[0]
        self.assertIn(
            "asaas_sale_integration_jobs.integration_id = EXCLUDED.integration_id",
            query,
        )
        self.assertIn(
            "asaas_sale_integration_jobs.webhook_event_id IS NULL",
            query,
        )

    def test_dispatcher_scopes_phase_one_to_webhook_operations(self):
        stale = datetime.now(timezone.utc) - timedelta(minutes=5)
        cursor = FakeCursor(many_rows=[(11,), (11,), (12,), (False,)])

        result = service.list_dispatchable_job_ids(
            cursor,
            limit=50,
            stale_before=stale,
            dispatch_before=stale,
            operations=("processar_webhook",),
            unidades=("São João de Meriti",),
        )

        query, params = cursor.executions[0]
        self.assertIn("COALESCE(integration.unidade, event.unidade) = ANY(%s)", query)
        self.assertIn("job.operation = ANY(%s)", query)
        self.assertIn("job.status = 'retry'", query)
        self.assertIn("job.last_attempt_at <= %s", query)
        self.assertIn("active_job.status = 'processando'", query)
        self.assertEqual(params[0], ["São João de Meriti"])
        self.assertEqual(params[1], ["processar_webhook"])
        self.assertEqual(result, [11, 11, 12])

    def test_claim_is_atomic_and_attempt_count_is_the_fencing_token(self):
        stale = datetime.now(timezone.utc) - timedelta(minutes=5)
        cursor = FakeCursor(
            rows=[
                make_job_row(
                    status="processando",
                    attempt_count=2,
                )
            ]
        )

        result = service.claim_job(cursor, job_id=1, stale_before=stale)

        lock_query, lock_params = cursor.executions[0]
        claim_query, claim_params = cursor.executions[1]
        self.assertIn("pg_advisory_xact_lock", lock_query)
        self.assertEqual(lock_params, (1,))
        self.assertIn("attempt_count = job.attempt_count + 1", claim_query)
        self.assertEqual(claim_params, (1, stale, stale))
        self.assertEqual(result.attempt_count, 2)

    def test_completion_requires_matching_claim_attempt(self):
        cursor = FakeCursor(
            rows=[make_job_row(status="integrado", attempt_count=3)]
        )

        result = service.mark_job_integrated(
            cursor,
            job_id=1,
            claim_attempt=3,
        )

        query, params = cursor.executions[0]
        self.assertIn("status = 'processando'", query)
        self.assertIn("attempt_count = %s", query)
        self.assertEqual(params[-2:], (1, 3))
        self.assertEqual(result.status, "integrado")

    def test_failure_code_cannot_persist_personal_identifier(self):
        retry_at = datetime.now(timezone.utc) + timedelta(minutes=1)
        cursor = FakeCursor(
            rows=[
                make_job_row(
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
            status="retry",
            error_code="cpf_12345678901",
            next_retry_at=retry_at,
        )

        _query, params = cursor.executions[0]
        self.assertIn("integration_error", params)
        self.assertNotIn("cpf_12345678901", params)


if __name__ == "__main__":
    unittest.main()
