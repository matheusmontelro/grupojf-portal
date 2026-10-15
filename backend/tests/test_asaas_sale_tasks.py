import unittest
from unittest.mock import MagicMock, call, patch

from app.workers import asaas_sale_integration_tasks as tasks
from app.workers.asaas_sale_celery_app import (
    _asaas_sales_beat_schedule,
    celery_app,
)


class AsaasSaleTaskTests(unittest.TestCase):
    def test_processing_task_sends_only_numeric_job_id(self):
        with patch(
            "app.services.asaas_sale_integration_service."
            "process_asaas_sale_job"
        ) as process:
            result = tasks.process_asaas_sale_job_task.run(42)

        self.assertIsNone(result)
        process.assert_called_once_with(42)

    def test_invalid_job_id_never_reaches_service(self):
        with patch(
            "app.services.asaas_sale_integration_service."
            "process_asaas_sale_job"
        ) as process:
            for invalid in (None, True, 0, -1, "1"):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(ValueError):
                        tasks.process_asaas_sale_job_task.run(invalid)
        process.assert_not_called()

    def test_dispatcher_is_fail_closed_when_no_unit_is_enabled(self):
        with (
            patch.object(tasks, "_enabled_units", return_value=()),
            patch.object(tasks, "_load_dispatchable_job_ids") as load,
            patch.object(tasks.process_asaas_sale_job_task, "apply_async") as publish,
        ):
            tasks.dispatch_asaas_sale_jobs.run()

        load.assert_not_called()
        publish.assert_not_called()

    def test_dispatcher_deduplicates_ids_and_uses_its_own_queue(self):
        with (
            patch.object(
                tasks,
                "_enabled_units",
                return_value=("São João de Meriti",),
            ),
            patch.object(
                tasks,
                "_load_dispatchable_job_ids",
                return_value=[8, 8, "private", 9],
            ) as load,
            patch.object(tasks, "_mark_job_dispatched") as mark,
            patch.object(
                tasks.process_asaas_sale_job_task,
                "apply_async",
            ) as publish,
        ):
            tasks.dispatch_asaas_sale_jobs.run()

        self.assertEqual(
            publish.call_args_list,
            [
                call(
                    args=(8,),
                    queue="asaas_sale_integration",
                    expires=240,
                ),
                call(
                    args=(9,),
                    queue="asaas_sale_integration",
                    expires=240,
                ),
            ],
        )
        self.assertEqual(mark.call_args_list, [call(8), call(9)])
        load.assert_called_once_with(("São João de Meriti",))

    def test_loader_dispatches_carne_only_for_its_specific_allowlist(self):
        connection = MagicMock()
        context = MagicMock()
        context.__enter__.return_value = connection
        context.__exit__.return_value = None
        with (
            patch.object(tasks, "DatabaseConnection", return_value=context),
            patch(
                "app.services.asaas_sales_config."
                "get_enabled_asaas_sales_carne_units",
                return_value=frozenset({"São João de Meriti"}),
            ),
            patch(
                "app.services.asaas_sale_job_service."
                "list_dispatchable_job_ids",
                side_effect=[[1], [2]],
            ) as list_jobs,
        ):
            result = tasks._load_dispatchable_job_ids(
                ("São João de Meriti", "Vilar dos Teles")
            )

        self.assertEqual(result, [1, 2])
        self.assertEqual(
            list_jobs.call_args_list[0].kwargs["operations"],
            ("processar_webhook",),
        )
        self.assertEqual(
            list_jobs.call_args_list[0].kwargs["unidades"],
            ("São João de Meriti", "Vilar dos Teles"),
        )
        self.assertEqual(
            list_jobs.call_args_list[1].kwargs["operations"],
            ("provisionar_venda", "reconciliar_venda"),
        )
        self.assertEqual(
            list_jobs.call_args_list[1].kwargs["unidades"],
            ("São João de Meriti",),
        )

    def test_task_options_prevent_result_or_sensitive_error_storage(self):
        task = tasks.process_asaas_sale_job_task
        self.assertTrue(task.ignore_result)
        self.assertFalse(task.store_errors_even_if_ignored)
        self.assertTrue(task.acks_late)
        self.assertTrue(task.reject_on_worker_lost)
        self.assertEqual(task.soft_time_limit, 45)
        self.assertEqual(task.time_limit, 60)


class AsaasSaleCeleryConfigTests(unittest.TestCase):
    def test_beat_is_disabled_by_default_and_scoped_when_enabled(self):
        self.assertEqual(_asaas_sales_beat_schedule(""), {})
        schedule = _asaas_sales_beat_schedule("SJM,Vilar")
        entry = schedule["dispatch-asaas-sale-integrations"]
        self.assertEqual(
            entry["task"],
            "app.workers.asaas_sale_integration_tasks.dispatch_asaas_sale_jobs",
        )
        self.assertEqual(entry["schedule"], 15.0)
        self.assertEqual(
            entry["options"],
            {"queue": "asaas_sale_integration", "expires": 12.0},
        )
        self.assertEqual(
            schedule["dispatch-asaas-entry-integrations"]["task"],
            "app.workers.asaas_sale_integration_tasks.dispatch_asaas_entry_jobs",
        )
        self.assertEqual(
            schedule["dispatch-asaas-entry-integrations"]["schedule"],
            5.0,
        )

    def test_tasks_are_routed_to_the_dedicated_queue(self):
        for task in (
            tasks.process_asaas_sale_job_task,
            tasks.dispatch_asaas_sale_jobs,
            tasks.process_asaas_entry_job_task,
            tasks.dispatch_asaas_entry_jobs,
        ):
            route = celery_app.amqp.router.route(
                {},
                task.name,
                args=(),
                kwargs={},
            )
            self.assertEqual(route["queue"].name, "asaas_sale_integration")


if __name__ == "__main__":
    unittest.main()
