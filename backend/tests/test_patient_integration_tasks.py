import sys
import unittest
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import MagicMock, call, patch

from app.workers import patient_integration_tasks as tasks
from app.workers.celery_app import (
    _patient_integration_beat_schedule,
    celery_app,
)


class PatientIntegrationProcessingTaskTests(unittest.TestCase):
    def test_provider_task_sends_only_job_id_to_service(self):
        with patch.object(tasks, "_run_integration_service") as process:
            result = tasks.delta_process_job.run(42)

        self.assertIsNone(result)
        process.assert_called_once_with(42, provider="delta")

    def test_unexpected_exception_is_sanitized(self):
        with (
            patch.object(
                tasks,
                "_run_integration_service",
                side_effect=RuntimeError("cpf=12345678901"),
            ),
            self.assertLogs(tasks.logger, level="ERROR") as captured,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "patient_integration_unexpected_failure",
            ) as raised:
                tasks.asaas_process_job.run(7)

        combined_logs = " ".join(captured.output)
        self.assertNotIn("12345678901", combined_logs)
        self.assertNotIn("12345678901", str(raised.exception))
        self.assertIn("error_type=RuntimeError", combined_logs)

    def test_invalid_job_id_never_reaches_integration_service(self):
        with patch.object(tasks, "_run_integration_service") as process:
            for invalid_job_id in (None, True, 0, -1, "1"):
                with self.subTest(job_id=invalid_job_id):
                    with self.assertRaises(ValueError):
                        tasks.delta_process_job.run(invalid_job_id)

        process.assert_not_called()

    def test_processing_tasks_do_not_store_results_and_use_safe_delivery(self):
        for task in (tasks.delta_process_job, tasks.asaas_process_job):
            with self.subTest(task=task.name):
                self.assertTrue(task.ignore_result)
                self.assertFalse(task.store_errors_even_if_ignored)
                self.assertTrue(task.acks_late)
                self.assertTrue(task.reject_on_worker_lost)
                self.assertEqual(task.soft_time_limit, 90)
                self.assertEqual(task.time_limit, 120)


class PatientIntegrationDispatchTaskTests(unittest.TestCase):
    def test_dispatcher_is_fail_closed_when_no_unit_is_enabled(self):
        with (
            patch.object(tasks, "_has_enabled_units", return_value=False),
            patch.object(tasks, "_load_dispatchable_job_ids") as load_jobs,
            patch.object(tasks.delta_process_job, "apply_async") as publish,
        ):
            tasks.dispatch_delta_jobs.run()

        load_jobs.assert_not_called()
        publish.assert_not_called()

    def test_dispatcher_publishes_only_unique_numeric_job_ids(self):
        with (
            patch.object(tasks, "_has_enabled_units", return_value=True),
            patch.object(
                tasks,
                "_load_dispatchable_job_ids",
                return_value=[8, 8, "cpf=12345678901", 9],
            ),
            patch.object(tasks, "_mark_job_dispatched") as mark_dispatched,
            patch.object(tasks.delta_process_job, "apply_async") as publish,
            self.assertLogs(tasks.logger, level="ERROR") as captured,
        ):
            result = tasks.dispatch_delta_jobs.run()

        self.assertIsNone(result)
        self.assertEqual(
            publish.call_args_list,
            [
                call(
                    args=(8,),
                    queue=tasks.DELTA_QUEUE,
                ),
                call(
                    args=(9,),
                    queue=tasks.DELTA_QUEUE,
                ),
            ],
        )
        self.assertEqual(
            mark_dispatched.call_args_list,
            [call(8), call(9)],
        )
        self.assertNotIn("12345678901", " ".join(captured.output))

    def test_database_connection_is_closed_before_broker_publish(self):
        connection_context = MagicMock()
        connection = connection_context.__enter__.return_value
        cursor = connection.cursor.return_value

        def assert_connection_closed_before_publish(*args, **kwargs):
            connection_context.__exit__.assert_called_once()

        fake_job_service = ModuleType(
            "app.services.patient_integration_job_service"
        )
        list_jobs = MagicMock(return_value=[11])
        fake_job_service.list_dispatchable_job_ids = list_jobs

        with (
            patch.object(tasks, "DatabaseConnection", return_value=connection_context),
            patch.dict(
                sys.modules,
                {
                    "app.services.patient_integration_job_service": (
                        fake_job_service
                    )
                },
            ),
            patch.object(tasks, "_has_enabled_units", return_value=True),
            patch.object(tasks, "_mark_job_dispatched") as mark_dispatched,
            patch.object(
                tasks.delta_process_job,
                "apply_async",
                side_effect=assert_connection_closed_before_publish,
            ) as publish,
        ):
            tasks.dispatch_delta_jobs.run()

        list_jobs.assert_called_once_with(
            cursor,
            provider="delta",
            limit=tasks.DISPATCH_BATCH_SIZE,
            stale_before=list_jobs.call_args.kwargs["stale_before"],
            dispatch_before=list_jobs.call_args.kwargs["dispatch_before"],
        )
        stale_before = list_jobs.call_args.kwargs["stale_before"]
        self.assertIsInstance(stale_before, datetime)
        self.assertIsNotNone(stale_before.tzinfo)
        age = datetime.now(timezone.utc) - stale_before
        self.assertGreaterEqual(age, tasks.PROCESSING_STALE_AFTER)
        self.assertLess(age, tasks.PROCESSING_STALE_AFTER * 2)
        dispatch_before = list_jobs.call_args.kwargs["dispatch_before"]
        dispatch_age = datetime.now(timezone.utc) - dispatch_before
        self.assertGreaterEqual(dispatch_age, tasks.DISPATCH_STALE_AFTER)
        self.assertLess(dispatch_age, tasks.DISPATCH_STALE_AFTER * 2)
        publish.assert_called_once_with(args=(11,), queue=tasks.DELTA_QUEUE)
        mark_dispatched.assert_called_once_with(11)

    def test_broker_failure_is_sanitized_and_job_remains_reconcilable(self):
        with (
            patch.object(tasks, "_has_enabled_units", return_value=True),
            patch.object(
                tasks,
                "_load_dispatchable_job_ids",
                return_value=[15],
            ),
            patch.object(
                tasks.delta_process_job,
                "apply_async",
                side_effect=RuntimeError(
                    "redis://usuario:segredo@broker/paciente=12345678901"
                ),
            ),
            patch.object(tasks, "_mark_job_dispatched") as mark_dispatched,
            self.assertLogs(tasks.logger, level="ERROR") as captured,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "patient_integration_dispatch_failed",
            ) as raised:
                tasks.dispatch_delta_jobs.run()

        combined_logs = " ".join(captured.output)
        self.assertNotIn("segredo", combined_logs)
        self.assertNotIn("12345678901", combined_logs)
        self.assertNotIn("segredo", str(raised.exception))
        mark_dispatched.assert_not_called()

    def test_database_failure_is_sanitized(self):
        with (
            patch.object(tasks, "_has_enabled_units", return_value=True),
            patch.object(
                tasks,
                "_load_dispatchable_job_ids",
                side_effect=RuntimeError(
                    "postgres://usuario:segredo@db/paciente=12345678901"
                ),
            ),
            self.assertLogs(tasks.logger, level="ERROR") as captured,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "patient_integration_reconcile_failed",
            ) as raised:
                tasks.dispatch_asaas_jobs.run()

        combined_logs = " ".join(captured.output)
        self.assertNotIn("segredo", combined_logs)
        self.assertNotIn("12345678901", combined_logs)
        self.assertNotIn("segredo", str(raised.exception))

    def test_successful_publish_is_marked_before_next_job(self):
        events = []

        with (
            patch.object(tasks, "_has_enabled_units", return_value=True),
            patch.object(
                tasks,
                "_load_dispatchable_job_ids",
                return_value=[21, 22],
            ),
            patch.object(
                tasks.delta_process_job,
                "apply_async",
                side_effect=lambda *, args, queue: events.append(
                    ("publish", args[0], queue)
                ),
            ),
            patch.object(
                tasks,
                "_mark_job_dispatched",
                side_effect=lambda job_id: events.append(("mark", job_id)),
            ),
        ):
            tasks.dispatch_delta_jobs.run()

        self.assertEqual(
            events,
            [
                ("publish", 21, tasks.DELTA_QUEUE),
                ("mark", 21),
                ("publish", 22, tasks.DELTA_QUEUE),
                ("mark", 22),
            ],
        )

    def test_mark_failure_is_sanitized_without_blocking_other_jobs(self):
        with (
            patch.object(tasks, "_has_enabled_units", return_value=True),
            patch.object(
                tasks,
                "_load_dispatchable_job_ids",
                return_value=[31, 32],
            ),
            patch.object(tasks.delta_process_job, "apply_async") as publish,
            patch.object(
                tasks,
                "_mark_job_dispatched",
                side_effect=[
                    RuntimeError("cpf=12345678901 senha=segredo"),
                    None,
                ],
            ) as mark_dispatched,
            self.assertLogs(tasks.logger, level="ERROR") as captured,
        ):
            tasks.dispatch_delta_jobs.run()

        self.assertEqual(publish.call_count, 2)
        self.assertEqual(
            mark_dispatched.call_args_list,
            [call(31), call(32)],
        )
        combined_logs = " ".join(captured.output)
        self.assertNotIn("12345678901", combined_logs)
        self.assertNotIn("segredo", combined_logs)


class PatientIntegrationCeleryConfigurationTests(unittest.TestCase):
    def test_provider_tasks_are_routed_to_dedicated_queues(self):
        expected_routes = {
            tasks.delta_process_job.name: tasks.DELTA_QUEUE,
            tasks.dispatch_delta_jobs.name: tasks.DELTA_QUEUE,
            tasks.asaas_process_job.name: tasks.ASAAS_QUEUE,
            tasks.dispatch_asaas_jobs.name: tasks.ASAAS_QUEUE,
        }

        for task_name, expected_queue in expected_routes.items():
            with self.subTest(task=task_name):
                route = celery_app.amqp.router.route(
                    {},
                    task_name,
                    args=(),
                    kwargs={},
                )
                self.assertEqual(route["queue"].name, expected_queue)

    def test_beat_reconciles_both_providers_every_thirty_seconds(self):
        schedule = _patient_integration_beat_schedule("São João de Meriti")
        expected_entries = {
            "dispatch-delta-patient-integrations": (
                tasks.dispatch_delta_jobs.name,
                tasks.DELTA_QUEUE,
            ),
            "dispatch-asaas-patient-integrations": (
                tasks.dispatch_asaas_jobs.name,
                tasks.ASAAS_QUEUE,
            ),
        }

        for schedule_name, (task_name, queue) in expected_entries.items():
            with self.subTest(schedule=schedule_name):
                entry = schedule[schedule_name]
                self.assertEqual(entry["task"], task_name)
                self.assertEqual(entry["schedule"], 30.0)
                self.assertEqual(
                    entry["options"],
                    {"queue": queue, "expires": 25.0},
                )

    def test_beat_does_not_publish_patient_tasks_with_empty_allowlist(self):
        self.assertEqual(_patient_integration_beat_schedule(""), {})


if __name__ == "__main__":
    unittest.main()
