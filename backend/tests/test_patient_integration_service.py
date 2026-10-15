import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from app.services import patient_integration_service as service
from app.services.patient_integration_config import PatientIntegrationConfigError


PATIENT_NAME = "Maria Sigilosa"
PATIENT_DOCUMENT = "12345678901"
PATIENT_EMAIL = "maria.sigilosa@example.test"
UNIT = "São João de Meriti"


def make_patient(
    *,
    paciente_id=10,
    updated_at=None,
    is_minor=False,
    responsavel_id=None,
    unidade=UNIT,
):
    return service.PatientSnapshot(
        paciente_id=paciente_id,
        nome_paciente=PATIENT_NAME,
        cpf_cnpj=PATIENT_DOCUMENT,
        email=PATIENT_EMAIL,
        data_nascimento=date(1990, 1, 1),
        is_minor=is_minor,
        responsavel_id=responsavel_id,
        phone_country_code="55",
        phone_area_code="21",
        phone_number="999999999",
        street="Rua Privada",
        street_number="123",
        line_two=None,
        neighborhood="Centro",
        city="São João de Meriti",
        state="RJ",
        zip_code="25500000",
        unidade=unidade,
        updated_at=updated_at or datetime(2026, 7, 16, 12, 30),
    )


def make_job(
    *,
    provider="delta",
    target_key="delta:sandbox:sao_joao_de_meriti",
    environment="sandbox",
    patient_version=None,
    attempt_count=1,
):
    now = datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc)
    return service.jobs.PatientIntegrationJobRecord(
        id=41,
        paciente_id=10,
        provider=provider,
        target_key=target_key,
        environment=environment,
        patient_version=patient_version or now,
        status="processando",
        attempt_count=attempt_count,
        last_http_status=None,
        last_error_code=None,
        last_attempt_at=now,
        last_dispatched_at=now,
        next_retry_at=None,
        integrated_at=None,
        created_at=now,
        updated_at=now,
    )


def make_database_context():
    context = MagicMock(name="database_context")
    connection = context.__enter__.return_value
    cursor = connection.cursor.return_value
    return context, cursor


class PatientIntegrationEnqueueTests(unittest.TestCase):
    def test_feature_flag_off_returns_before_database_or_provider_config(self):
        cursor = MagicMock(name="cursor")

        with (
            patch.object(service, "is_patient_integration_enabled", return_value=False),
            patch.object(service, "_load_patient") as load_patient,
            patch.object(service, "get_patient_integration_environment") as get_env,
            patch.object(service, "_validate_delta_configuration") as delta_config,
            patch.object(
                service.delta_links,
                "ensure_delta_customer_link",
                return_value=SimpleNamespace(id=81),
            ) as ensure_delta_link,
            patch.object(service, "_load_strict_asaas_config") as asaas_config,
            patch.object(service.jobs, "enqueue_patient_integration_job") as enqueue,
        ):
            result = service.enqueue_patient_jobs_for_patient(
                cursor,
                paciente_id=10,
                unidade=UNIT,
                patient_version=datetime(2026, 7, 16, 12, 30),
            )

        self.assertEqual(result, [])
        self.assertEqual(cursor.method_calls, [])
        load_patient.assert_not_called()
        get_env.assert_not_called()
        delta_config.assert_not_called()
        ensure_delta_link.assert_not_called()
        asaas_config.assert_not_called()
        enqueue.assert_not_called()

    def test_minor_enqueues_independent_delta_and_asaas_jobs_for_responsible(self):
        cursor = MagicMock(name="cursor")
        minor = make_patient(
            paciente_id=10,
            is_minor=True,
            responsavel_id=20,
            updated_at=datetime(2026, 7, 16, 12, 15),
        )
        responsible = make_patient(
            paciente_id=20,
            updated_at=datetime(2026, 7, 16, 12, 30),
        )
        link = SimpleNamespace(id=91)
        asaas_config = SimpleNamespace(account_wallet_id="wallet-sjm")

        def enqueue_job(_cursor, **kwargs):
            return SimpleNamespace(**kwargs)

        with (
            patch.object(service, "is_patient_integration_enabled", return_value=True),
            patch.object(
                service,
                "_load_patient",
                side_effect=lambda _cursor, patient_id: (
                    minor if patient_id == 10 else responsible
                ),
            ),
            patch.object(
                service,
                "get_patient_integration_environment",
                return_value="sandbox",
            ),
            patch.object(service, "_validate_delta_configuration") as delta_config,
            patch.object(
                service.delta_links,
                "ensure_delta_customer_link",
                return_value=SimpleNamespace(id=81),
            ) as ensure_delta_link,
            patch.object(
                service,
                "_load_strict_asaas_config",
                return_value=asaas_config,
            ),
            patch.object(
                service.asaas_links,
                "ensure_customer_link",
                return_value=link,
            ) as ensure_link,
            patch.object(service.asaas_links, "request_customer_sync") as request_sync,
            patch.object(
                service.jobs,
                "enqueue_patient_integration_job",
                side_effect=enqueue_job,
            ) as enqueue,
        ):
            result = service.enqueue_patient_jobs_for_patient(
                cursor,
                paciente_id=10,
                unidade=UNIT,
                patient_version=minor.updated_at,
                allow_delta_customer_creation=True,
                allow_asaas_customer_creation=True,
            )

        self.assertEqual([job.provider for job in result], ["delta", "asaas"])
        self.assertEqual(enqueue.call_count, 2)
        delta_call, asaas_call = enqueue.call_args_list
        expected_version = datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc)

        self.assertEqual(delta_call.kwargs["paciente_id"], 20)
        self.assertEqual(delta_call.kwargs["provider"], "delta")
        self.assertEqual(delta_call.kwargs["patient_version"], expected_version)
        self.assertEqual(delta_call.kwargs["patient_version"].tzinfo, timezone.utc)
        self.assertEqual(asaas_call.kwargs["paciente_id"], 20)
        self.assertEqual(asaas_call.kwargs["provider"], "asaas")
        self.assertEqual(asaas_call.kwargs["patient_version"], expected_version)
        self.assertNotEqual(delta_call.kwargs["target_key"], asaas_call.kwargs["target_key"])
        self.assertEqual(asaas_call.kwargs["target_key"], "asaas:sandbox:wallet-sjm")
        delta_config.assert_called_once_with(UNIT, "sandbox")
        ensure_delta_link.assert_called_once_with(
            cursor,
            paciente_id=20,
            environment="sandbox",
            target_key="delta:sandbox:sao_joao_de_meriti",
            allow_remote_create=False,
        )
        ensure_link.assert_called_once_with(
            cursor,
            paciente_id=20,
            unidade=UNIT,
            environment="sandbox",
            account_wallet_id="wallet-sjm",
            allow_remote_create=False,
        )
        request_sync.assert_called_once_with(
            cursor,
            link_id=91,
            patient_updated_at=expected_version,
        )

        persisted_metadata = " ".join(
            str(argument.kwargs) for argument in enqueue.call_args_list
        )
        self.assertNotIn(PATIENT_NAME, persisted_metadata)
        self.assertNotIn(PATIENT_DOCUMENT, persisted_metadata)
        self.assertNotIn(PATIENT_EMAIL, persisted_metadata)

    def test_update_can_authorize_asaas_creation_without_authorizing_delta(self):
        cursor = MagicMock(name="cursor")
        patient = make_patient()
        asaas_config = SimpleNamespace(account_wallet_id="wallet-sjm")

        with (
            patch.object(service, "is_patient_integration_enabled", return_value=True),
            patch.object(service, "_load_patient", return_value=patient),
            patch.object(
                service,
                "get_patient_integration_environment",
                return_value="sandbox",
            ),
            patch.object(service, "_validate_delta_configuration"),
            patch.object(
                service.delta_links,
                "ensure_delta_customer_link",
                return_value=SimpleNamespace(id=81),
            ) as ensure_delta_link,
            patch.object(
                service,
                "_load_strict_asaas_config",
                return_value=asaas_config,
            ),
            patch.object(
                service.asaas_links,
                "ensure_customer_link",
                return_value=SimpleNamespace(id=91),
            ) as ensure_asaas_link,
            patch.object(service.asaas_links, "request_customer_sync"),
            patch.object(
                service.jobs,
                "enqueue_patient_integration_job",
                side_effect=lambda _cursor, **kwargs: SimpleNamespace(**kwargs),
            ),
        ):
            result = service.enqueue_patient_jobs_for_patient(
                cursor,
                paciente_id=patient.paciente_id,
                unidade=UNIT,
                patient_version=patient.updated_at,
                allow_asaas_customer_creation=True,
            )

        self.assertEqual([job.provider for job in result], ["delta", "asaas"])
        ensure_delta_link.assert_called_once_with(
            cursor,
            paciente_id=patient.paciente_id,
            environment="sandbox",
            target_key="delta:sandbox:sao_joao_de_meriti",
            allow_remote_create=False,
        )
        ensure_asaas_link.assert_called_once_with(
            cursor,
            paciente_id=patient.paciente_id,
            unidade=UNIT,
            environment="sandbox",
            account_wallet_id="wallet-sjm",
            allow_remote_create=True,
        )

    def test_asaas_creation_from_edit_keeps_the_effective_unit_account(self):
        for unidade, wallet_id, expected_target in (
            (
                "São João de Meriti",
                "wallet-sjm",
                "asaas:sandbox:wallet-sjm",
            ),
            (
                "Vilar dos Teles",
                "wallet-vilar",
                "asaas:sandbox:wallet-vilar",
            ),
        ):
            with self.subTest(unidade=unidade):
                cursor = MagicMock(name="cursor")
                patient = make_patient(unidade=unidade)

                with (
                    patch.object(
                        service,
                        "is_patient_integration_enabled",
                        return_value=True,
                    ),
                    patch.object(service, "_load_patient", return_value=patient),
                    patch.object(
                        service,
                        "get_patient_integration_environment",
                        return_value="sandbox",
                    ),
                    patch.object(
                        service,
                        "_load_strict_asaas_config",
                        return_value=SimpleNamespace(account_wallet_id=wallet_id),
                    ) as load_config,
                    patch.object(
                        service.asaas_links,
                        "ensure_customer_link",
                        return_value=SimpleNamespace(id=91),
                    ) as ensure_link,
                    patch.object(service.asaas_links, "request_customer_sync"),
                    patch.object(
                        service.jobs,
                        "enqueue_patient_integration_job",
                        side_effect=lambda _cursor, **kwargs: SimpleNamespace(
                            **kwargs
                        ),
                    ) as enqueue_job,
                ):
                    result = service.enqueue_patient_jobs_for_patient(
                        cursor,
                        paciente_id=patient.paciente_id,
                        unidade=unidade,
                        patient_version=patient.updated_at,
                        providers=("asaas",),
                        allow_asaas_customer_creation=True,
                    )

                self.assertEqual(len(result), 1)
                self.assertEqual(result[0].target_key, expected_target)
                load_config.assert_called_once_with(unidade, "sandbox")
                ensure_link.assert_called_once_with(
                    cursor,
                    paciente_id=patient.paciente_id,
                    unidade=unidade,
                    environment="sandbox",
                    account_wallet_id=wallet_id,
                    allow_remote_create=True,
                )
                self.assertEqual(
                    enqueue_job.call_args.kwargs["target_key"],
                    expected_target,
                )

    def test_confirmed_delta_id_cannot_be_bound_through_a_minor(self):
        cursor = MagicMock(name="cursor")
        minor = make_patient(
            paciente_id=10,
            is_minor=True,
            responsavel_id=20,
            updated_at=datetime(2026, 7, 16, 12, 15),
        )
        responsible = make_patient(paciente_id=20)

        with (
            patch.object(service, "is_patient_integration_enabled", return_value=True),
            patch.object(
                service,
                "_load_patient",
                side_effect=lambda _cursor, patient_id: (
                    minor if patient_id == 10 else responsible
                ),
            ),
            patch.object(
                service.delta_links,
                "ensure_delta_customer_link",
            ) as ensure_delta_link,
        ):
            with self.assertRaisesRegex(
                service.PatientIntegrationDataError,
                "confirmed_delta_customer_requires_effective_patient",
            ):
                service.enqueue_patient_jobs_for_patient(
                    cursor,
                    paciente_id=10,
                    unidade=UNIT,
                    patient_version=minor.updated_at,
                    confirmed_delta_customer_id="delta-minor",
                )

        ensure_delta_link.assert_not_called()


class PatientIntegrationIdentityGuardTests(unittest.TestCase):
    def test_unchanged_document_is_inert_even_before_migrations(self):
        cursor = MagicMock(name="cursor")

        service.ensure_remote_identities_before_document_change(
            cursor,
            paciente_id=10,
            unidade=UNIT,
            current_document="123.456.789-01",
            requested_document="12345678901",
        )

        self.assertEqual(cursor.method_calls, [])

    def test_enabled_unit_requires_delta_and_asaas_ids(self):
        cursor = MagicMock(name="cursor")
        config = SimpleNamespace(account_wallet_id="wallet-sjm")

        with (
            patch.object(service, "is_patient_integration_enabled", return_value=True),
            patch.object(
                service,
                "get_patient_integration_environment",
                return_value="sandbox",
            ),
            patch.object(
                service.delta_links,
                "get_delta_customer_link",
                return_value=SimpleNamespace(delta_customer_id="delta-10"),
            ),
            patch.object(
                service,
                "_load_strict_asaas_config",
                return_value=config,
            ),
            patch.object(
                service.asaas_links,
                "get_customer_link_for_update",
                return_value=SimpleNamespace(asaas_customer_id=None),
            ) as get_asaas_link,
        ):
            with self.assertRaisesRegex(
                service.PatientIntegrationIdentityPendingError,
                "asaas_identity_reconciliation_required",
            ):
                service.ensure_remote_identities_before_document_change(
                    cursor,
                    paciente_id=10,
                    unidade=UNIT,
                    current_document=PATIENT_DOCUMENT,
                    requested_document="99999999999",
                )

        get_asaas_link.assert_called_once_with(
            cursor,
            paciente_id=10,
            environment="sandbox",
            account_wallet_id="wallet-sjm",
        )

    def test_disabled_unit_keeps_guard_for_patient_already_in_new_flow(self):
        cursor = MagicMock(name="cursor")
        cursor.fetchone.return_value = (
            "patient_delta_customers",
            "asaas_patient_customers",
        )
        cursor.fetchall.side_effect = [
            [("delta-10",)],
            [(None,)],
        ]

        with patch.object(
            service,
            "is_patient_integration_enabled",
            return_value=False,
        ):
            with self.assertRaisesRegex(
                service.PatientIntegrationIdentityPendingError,
                "asaas_identity_reconciliation_required",
            ):
                service.ensure_remote_identities_before_document_change(
                    cursor,
                    paciente_id=10,
                    unidade=UNIT,
                    current_document=PATIENT_DOCUMENT,
                    requested_document="99999999999",
                )

    def test_disabled_unit_is_compatible_before_new_tables_exist(self):
        cursor = MagicMock(name="cursor")
        cursor.fetchone.return_value = (None, "asaas_patient_customers")

        with patch.object(
            service,
            "is_patient_integration_enabled",
            return_value=False,
        ):
            service.ensure_remote_identities_before_document_change(
                cursor,
                paciente_id=10,
                unidade=UNIT,
                current_document=PATIENT_DOCUMENT,
                requested_document="99999999999",
            )

        cursor.fetchall.assert_not_called()


class PatientIntegrationProcessingTests(unittest.TestCase):
    def test_disabled_unit_does_not_claim_or_call_provider(self):
        job = make_job()
        patient = make_patient(updated_at=job.patient_version)

        with (
            patch.object(service, "_get_job", return_value=job),
            patch.object(
                service,
                "_load_effective_patient_by_id",
                return_value=patient,
            ),
            patch.object(service, "is_patient_integration_enabled", return_value=False),
            patch.object(service, "_claim_job") as claim_job,
            patch.object(service, "_process_delta") as process_delta,
            patch.object(service, "_process_asaas") as process_asaas,
            patch.object(service, "PatientAPI") as delta_api,
            patch.object(service, "AsaasSDK") as asaas_sdk,
            self.assertLogs(service.logger, level="INFO") as captured,
        ):
            service.process_patient_integration_job(41, expected_provider="delta")

        claim_job.assert_not_called()
        process_delta.assert_not_called()
        process_asaas.assert_not_called()
        delta_api.assert_not_called()
        asaas_sdk.assert_not_called()
        self._assert_no_pii(captured.output)

    def test_invalid_environment_does_not_consume_a_claim_attempt(self):
        job = make_job()
        patient = make_patient(updated_at=job.patient_version)

        with (
            patch.object(service, "_get_job", return_value=job),
            patch.object(
                service,
                "_load_effective_patient_by_id",
                return_value=patient,
            ),
            patch.object(service, "is_patient_integration_enabled", return_value=True),
            patch.object(
                service,
                "get_patient_integration_environment",
                side_effect=PatientIntegrationConfigError("invalid"),
            ),
            patch.object(service, "_claim_job") as claim_job,
            patch.object(service, "_process_delta") as process_delta,
            self.assertLogs(service.logger, level="ERROR") as captured,
        ):
            service.process_patient_integration_job(41, expected_provider="delta")

        claim_job.assert_not_called()
        process_delta.assert_not_called()
        self._assert_no_pii(captured.output)

    def test_invalid_responsible_chain_is_terminal_without_provider_http(self):
        job = make_job()

        with (
            patch.object(service, "_get_job", return_value=job),
            patch.object(
                service,
                "_load_effective_patient_by_id",
                side_effect=service.PatientIntegrationDataError(
                    "responsible_cycle"
                ),
            ),
            patch.object(service, "_claim_and_finish_without_http") as finish,
            patch.object(service, "PatientAPI") as delta_api,
        ):
            service.process_patient_integration_job(41, expected_provider="delta")

        finish.assert_called_once_with(41, "delta", "patient_invalid")
        delta_api.assert_not_called()

    def test_delta_success_upserts_and_marks_job_integrated(self):
        version = datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc)
        job = make_job(patient_version=version)
        patient = make_patient(updated_at=version)
        database_context, cursor = make_database_context()
        patient_api_context = MagicMock(name="patient_api_context")
        patient_api = patient_api_context.__enter__.return_value
        patient_api.sync_patient.return_value = {"id": "delta-remote-10"}
        patient_api.extract_customer_id.return_value = "delta-remote-10"
        delta_payload = {"name": PATIENT_NAME, "document": PATIENT_DOCUMENT}

        with (
            patch.object(service, "_get_job", return_value=job),
            patch.object(
                service,
                "_load_effective_patient_by_id",
                side_effect=[patient, patient],
            ),
            patch.object(service, "is_patient_integration_enabled", return_value=True),
            patch.object(
                service,
                "get_patient_integration_environment",
                return_value="sandbox",
            ),
            patch.object(service, "_claim_job", return_value=job),
            patch.object(
                service,
                "get_token_and_seller_for_unidade",
                return_value=("token-test", "seller-test"),
            ),
            patch.object(
                service,
                "transform_to_delta_format",
                return_value=delta_payload,
            ),
            patch.object(service, "validate_patient_data", return_value=(True, [])),
            patch.object(service, "PatientAPI", return_value=patient_api_context) as api_cls,
            patch.object(service, "_reserve_delta_customer_id") as reserve_delta_id,
            patch.object(service, "DatabaseConnection", return_value=database_context),
            patch.object(
                service.delta_links,
                "get_delta_customer_link",
                return_value=SimpleNamespace(
                    id=81,
                    delta_customer_id="delta-remote-10",
                    remote_creation_allowed=False,
                ),
            ),
            patch.object(service.delta_links, "set_delta_customer_id") as set_delta_id,
            patch.object(service.jobs, "mark_job_integrated") as mark_integrated,
            self.assertLogs(service.logger, level="INFO") as captured,
        ):
            service.process_patient_integration_job(41, expected_provider="delta")

        api_cls.assert_called_once_with("token-test", "seller-test", "sandbox")
        patient_api.sync_patient.assert_called_once_with(
            delta_payload,
            known_customer_id="delta-remote-10",
        )
        patient_api.extract_customer_id.assert_called_once_with(
            {"id": "delta-remote-10"}
        )
        patient_api_context.__exit__.assert_called_once()
        reserve_delta_id.assert_called_once_with(
            job,
            link_id=81,
            customer_id="delta-remote-10",
        )
        set_delta_id.assert_called_once_with(
            cursor,
            link_id=81,
            delta_customer_id="delta-remote-10",
        )
        mark_integrated.assert_called_once_with(
            cursor,
            job_id=41,
            claim_attempt=1,
        )
        self.assertTrue(
            any(
                "delta_integration_status = 'integrado'" in call_args.args[0]
                for call_args in cursor.execute.call_args_list
            )
        )
        self._assert_no_pii(captured.output)

    def test_delta_connection_failure_is_retried_with_sanitized_log(self):
        version = datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc)
        job = make_job(patient_version=version)
        patient = make_patient(updated_at=version)
        database_context, cursor = make_database_context()
        patient_api_context = MagicMock(name="patient_api_context")
        patient_api_context.__enter__.return_value.sync_patient.side_effect = (
            service.DeltaConnectionError(
                f"falha para {PATIENT_NAME} cpf={PATIENT_DOCUMENT} email={PATIENT_EMAIL}"
            )
        )

        with (
            patch.object(service, "_get_job", return_value=job),
            patch.object(
                service,
                "_load_effective_patient_by_id",
                side_effect=[patient, patient],
            ),
            patch.object(service, "is_patient_integration_enabled", return_value=True),
            patch.object(
                service,
                "get_patient_integration_environment",
                return_value="sandbox",
            ),
            patch.object(service, "_claim_job", return_value=job),
            patch.object(
                service,
                "get_token_and_seller_for_unidade",
                return_value=("token-test", "seller-test"),
            ),
            patch.object(
                service,
                "transform_to_delta_format",
                return_value={"document": PATIENT_DOCUMENT},
            ),
            patch.object(service, "validate_patient_data", return_value=(True, [])),
            patch.object(service, "PatientAPI", return_value=patient_api_context),
            patch.object(service, "DatabaseConnection", return_value=database_context),
            patch.object(
                service.delta_links,
                "get_delta_customer_link",
                return_value=SimpleNamespace(
                    id=81,
                    delta_customer_id="delta-remote-10",
                    remote_creation_allowed=False,
                ),
            ),
            patch.object(service.jobs, "mark_job_failed") as mark_failed,
            patch.object(service.jobs, "mark_job_integrated") as mark_integrated,
            self.assertLogs(service.logger, level="WARNING") as captured,
        ):
            service.process_patient_integration_job(41, expected_provider="delta")

        mark_integrated.assert_not_called()
        mark_failed.assert_called_once()
        failure_call = mark_failed.call_args
        self.assertIs(failure_call.args[0], cursor)
        self.assertEqual(failure_call.kwargs["job_id"], 41)
        self.assertEqual(failure_call.kwargs["claim_attempt"], 1)
        self.assertEqual(failure_call.kwargs["error_code"], "delta_connection")
        self.assertEqual(failure_call.kwargs["status"], "retry")
        self.assertIsNone(failure_call.kwargs["http_status"])
        self.assertEqual(failure_call.kwargs["next_retry_at"].tzinfo, timezone.utc)
        self._assert_no_pii(captured.output)

    def test_asaas_reserves_customer_then_configures_notifications_before_success(self):
        job = make_job(
            provider="asaas",
            target_key="asaas:production:wallet-sjm",
            environment="production",
        )
        patient = make_patient(updated_at=job.patient_version)
        config = SimpleNamespace(account_wallet_id="wallet-sjm")
        initial_claim = service._AsaasClaim(
            link_id=91,
            claim_attempt=3,
            customer_id=None,
            remote_creation_allowed=True,
        )
        sdk_context = MagicMock(name="asaas_sdk_context")
        sdk = sdk_context.__enter__.return_value
        sdk.customer_manager.find_existing_customer.return_value = None
        sdk.customer_manager.create_customer.return_value = {
            "id": "cus_patient_10",
            "notificationDisabled": False,
        }

        with (
            patch.object(service, "_load_strict_asaas_config", return_value=config),
            patch.object(
                service,
                "_claim_asaas_link",
                return_value=(initial_claim, False),
            ),
            patch.object(
                service,
                "transform_to_delta_format",
                return_value={
                    "name": PATIENT_NAME,
                    "cpfCnpj": PATIENT_DOCUMENT,
                },
            ),
            patch.object(service, "AsaasSDK", return_value=sdk_context),
            patch.object(service, "_reserve_asaas_customer_id") as reserve,
            patch.object(service, "_mark_asaas_and_job_integrated") as mark_integrated,
        ):
            ordered = MagicMock()
            ordered.attach_mock(reserve, "reserve")
            ordered.attach_mock(
                sdk.notification_manager.apply_full_notification_policy,
                "configure",
            )
            ordered.attach_mock(mark_integrated, "mark_integrated")

            service._process_asaas(job, patient, UNIT)

        create_payload = sdk.customer_manager.create_customer.call_args.args[0]
        self.assertIs(create_payload["notificationDisabled"], False)
        expected_claim = service._AsaasClaim(
            link_id=91,
            claim_attempt=3,
            customer_id="cus_patient_10",
            remote_creation_allowed=False,
        )
        self.assertEqual(
            ordered.mock_calls,
            [
                call.reserve(
                    initial_claim,
                    customer_id="cus_patient_10",
                ),
                call.configure("cus_patient_10"),
                call.mark_integrated(
                    job,
                    link_claim=expected_claim,
                    customer_id="cus_patient_10",
                ),
            ],
        )

    def test_asaas_sandbox_disables_notifications_without_full_policy(self):
        job = make_job(
            provider="asaas",
            target_key="asaas:sandbox:wallet-sjm",
            environment="sandbox",
        )
        patient = make_patient(updated_at=job.patient_version)
        config = SimpleNamespace(account_wallet_id="wallet-sjm")
        initial_claim = service._AsaasClaim(
            link_id=91,
            claim_attempt=3,
            customer_id="cus_patient_10",
            remote_creation_allowed=False,
        )
        sdk_context = MagicMock(name="asaas_sdk_context")
        sdk = sdk_context.__enter__.return_value
        sdk.customer_manager.sync_customer.return_value = {
            "id": "cus_patient_10",
            "notificationDisabled": True,
        }

        with (
            patch.object(service, "_load_strict_asaas_config", return_value=config),
            patch.object(
                service,
                "_claim_asaas_link",
                return_value=(initial_claim, False),
            ),
            patch.object(
                service,
                "transform_to_delta_format",
                return_value={
                    "name": PATIENT_NAME,
                    "cpfCnpj": PATIENT_DOCUMENT,
                },
            ),
            patch.object(service, "AsaasSDK", return_value=sdk_context),
            patch.object(service, "_reserve_asaas_customer_id") as reserve,
            patch.object(service, "_mark_asaas_and_job_integrated") as integrated,
        ):
            service._process_asaas(job, patient, UNIT)

        payload = sdk.customer_manager.sync_customer.call_args.args[0]
        self.assertIs(payload["notificationDisabled"], True)
        sdk.customer_manager.sync_customer.assert_called_once_with(
            payload,
            known_customer_id="cus_patient_10",
        )
        reserve.assert_called_once_with(
            initial_claim,
            customer_id="cus_patient_10",
        )
        sdk.notification_manager.apply_full_notification_policy.assert_not_called()
        integrated.assert_called_once()

    def test_asaas_notification_failure_keeps_reserved_id_for_retry(self):
        job = make_job(
            provider="asaas",
            target_key="asaas:production:wallet-sjm",
            environment="production",
        )
        patient = make_patient(updated_at=job.patient_version)
        config = SimpleNamespace(account_wallet_id="wallet-sjm")
        initial_claim = service._AsaasClaim(
            link_id=91,
            claim_attempt=3,
            customer_id=None,
            remote_creation_allowed=True,
        )
        sdk_context = MagicMock(name="asaas_sdk_context")
        sdk = sdk_context.__enter__.return_value
        sdk.customer_manager.find_existing_customer.return_value = None
        sdk.customer_manager.create_customer.return_value = {
            "id": "cus_patient_10",
            "notificationDisabled": False,
        }
        notification_error = service.AsaasConnectionError("connection_failed")
        sdk.notification_manager.apply_full_notification_policy.side_effect = (
            notification_error
        )

        with (
            patch.object(service, "_load_strict_asaas_config", return_value=config),
            patch.object(
                service,
                "_claim_asaas_link",
                return_value=(initial_claim, False),
            ),
            patch.object(
                service,
                "transform_to_delta_format",
                return_value={
                    "name": PATIENT_NAME,
                    "cpfCnpj": PATIENT_DOCUMENT,
                },
            ),
            patch.object(service, "AsaasSDK", return_value=sdk_context),
            patch.object(service, "_reserve_asaas_customer_id") as reserve,
            patch.object(service, "_record_provider_failure") as record_failure,
            patch.object(service, "_mark_asaas_and_job_integrated") as mark_integrated,
        ):
            service._process_asaas(job, patient, UNIT)

        reserve.assert_called_once_with(
            initial_claim,
            customer_id="cus_patient_10",
        )
        record_failure.assert_called_once_with(
            job,
            "asaas",
            notification_error,
            link_claim=service._AsaasClaim(
                link_id=91,
                claim_attempt=3,
                customer_id="cus_patient_10",
                remote_creation_allowed=False,
            ),
        )
        mark_integrated.assert_not_called()

    def test_asaas_global_notification_flag_must_be_confirmed_before_policy(self):
        job = make_job(
            provider="asaas",
            target_key="asaas:production:wallet-sjm",
            environment="production",
        )
        patient = make_patient(updated_at=job.patient_version)
        config = SimpleNamespace(account_wallet_id="wallet-sjm")
        initial_claim = service._AsaasClaim(
            link_id=91,
            claim_attempt=3,
            customer_id=None,
            remote_creation_allowed=True,
        )
        sdk_context = MagicMock(name="asaas_sdk_context")
        sdk = sdk_context.__enter__.return_value
        sdk.customer_manager.find_existing_customer.return_value = None
        sdk.customer_manager.create_customer.return_value = {
            "id": "cus_patient_10",
            "notificationDisabled": True,
        }

        with (
            patch.object(service, "_load_strict_asaas_config", return_value=config),
            patch.object(
                service,
                "_claim_asaas_link",
                return_value=(initial_claim, False),
            ),
            patch.object(
                service,
                "transform_to_delta_format",
                return_value={
                    "name": PATIENT_NAME,
                    "cpfCnpj": PATIENT_DOCUMENT,
                },
            ),
            patch.object(service, "AsaasSDK", return_value=sdk_context),
            patch.object(service, "_reserve_asaas_customer_id") as reserve,
            patch.object(service, "_record_provider_failure") as record_failure,
            patch.object(service, "_mark_asaas_and_job_integrated") as mark_integrated,
        ):
            service._process_asaas(job, patient, UNIT)

        reserve.assert_called_once_with(
            initial_claim,
            customer_id="cus_patient_10",
        )
        sdk.notification_manager.apply_full_notification_policy.assert_not_called()
        failure = record_failure.call_args.args[2]
        self.assertIsInstance(failure, service.AsaasAPIError)
        self.assertEqual(failure.status_code, 502)
        self.assertEqual(failure.detail, "notification_policy_not_applied")
        self.assertEqual(
            record_failure.call_args.kwargs["link_claim"].customer_id,
            "cus_patient_10",
        )
        mark_integrated.assert_not_called()

    def test_asaas_conflict_marks_link_and_job_without_logging_patient_data(self):
        job = make_job(
            provider="asaas",
            target_key="asaas:sandbox:wallet-sjm",
        )
        patient = make_patient(updated_at=job.patient_version)
        config = SimpleNamespace(account_wallet_id="wallet-sjm")
        database_context, cursor = make_database_context()
        sdk_context = MagicMock(name="asaas_sdk_context")
        sdk_context.__enter__.return_value.customer_manager.find_existing_customer.side_effect = (
            service.AsaasCustomerConflictError("multiple_matches")
        )

        with (
            patch.object(service, "_load_strict_asaas_config", return_value=config),
            patch.object(
                service,
                "_claim_asaas_link",
                return_value=(
                    service._AsaasClaim(
                        link_id=91,
                        claim_attempt=3,
                        customer_id=None,
                        remote_creation_allowed=False,
                    ),
                    False,
                ),
            ),
            patch.object(
                service,
                "transform_to_delta_format",
                return_value={"name": PATIENT_NAME, "cpfCnpj": PATIENT_DOCUMENT},
            ),
            patch.object(service, "AsaasSDK", return_value=sdk_context),
            patch.object(service, "DatabaseConnection", return_value=database_context),
            patch.object(service.asaas_links, "mark_customer_failed") as mark_link_failed,
            patch.object(service.jobs, "mark_job_failed") as mark_job_failed,
            self.assertLogs(service.logger, level="WARNING") as captured,
        ):
            service._process_asaas(job, patient, UNIT)

        mark_link_failed.assert_called_once_with(
            cursor,
            link_id=91,
            claim_attempt=3,
            error_code="asaas_conflict",
            http_status=None,
            next_retry_at=None,
            status="conflito",
            patient_updated_at=job.patient_version,
        )
        mark_job_failed.assert_called_once_with(
            cursor,
            job_id=41,
            claim_attempt=1,
            error_code="asaas_conflict",
            status="conflito",
            http_status=None,
            next_retry_at=None,
        )
        self._assert_no_pii(captured.output)

    def test_asaas_invalid_action_is_persisted_without_remote_content(self):
        job = make_job(
            provider="asaas",
            target_key="asaas:sandbox:wallet-sjm",
        )
        database_context, cursor = make_database_context()
        error = service.AsaasValidationError(["invalid_action"])
        error.status_code = 400
        link_claim = service._AsaasClaim(
            link_id=91,
            claim_attempt=3,
            customer_id="cus_patient_10",
            remote_creation_allowed=False,
        )

        with (
            patch.object(service, "DatabaseConnection", return_value=database_context),
            patch.object(
                service.asaas_links,
                "mark_customer_failed",
            ) as mark_link_failed,
            patch.object(service.jobs, "mark_job_failed") as mark_job_failed,
            self.assertLogs(service.logger, level="WARNING") as captured,
        ):
            service._record_provider_failure(
                job,
                "asaas",
                error,
                link_claim=link_claim,
            )

        self.assertEqual(
            mark_link_failed.call_args.kwargs["error_code"],
            "asaas_invalid_action",
        )
        self.assertEqual(mark_link_failed.call_args.kwargs["http_status"], 400)
        self.assertEqual(
            mark_job_failed.call_args.kwargs["error_code"],
            "asaas_invalid_action",
        )
        self.assertEqual(
            mark_job_failed.call_args.kwargs["status"],
            "erro_terminal",
        )
        self.assertEqual(mark_job_failed.call_args.kwargs["http_status"], 400)
        self._assert_no_pii(captured.output)

    def test_untrusted_asaas_validation_code_remains_generic(self):
        error = service.AsaasValidationError(["cpf_111.222.333-44"])
        error.status_code = 400

        decision = service._classify_failure(
            "asaas",
            error,
            attempt_count=1,
            job_id=41,
        )

        self.assertEqual(decision.error_code, "asaas_validation")
        self.assertEqual(decision.http_status, 400)
        self.assertNotIn("111", decision.error_code)

    def test_asaas_malformed_success_is_retried_as_gateway_failure(self):
        job = make_job(
            provider="asaas",
            target_key="asaas:sandbox:wallet-sjm",
        )
        patient = make_patient(updated_at=job.patient_version)
        config = SimpleNamespace(account_wallet_id="wallet-sjm")
        database_context, cursor = make_database_context()
        sdk_context = MagicMock(name="asaas_sdk_context")
        sdk_context.__enter__.return_value.customer_manager.find_existing_customer.side_effect = (
            service.AsaasAPIError(200, detail="invalid_response")
        )

        with (
            patch.object(service, "_load_strict_asaas_config", return_value=config),
            patch.object(
                service,
                "_claim_asaas_link",
                return_value=(
                    service._AsaasClaim(
                        link_id=91,
                        claim_attempt=3,
                        customer_id=None,
                        remote_creation_allowed=False,
                    ),
                    False,
                ),
            ),
            patch.object(
                service,
                "transform_to_delta_format",
                return_value={"name": PATIENT_NAME, "cpfCnpj": PATIENT_DOCUMENT},
            ),
            patch.object(service, "AsaasSDK", return_value=sdk_context),
            patch.object(service, "DatabaseConnection", return_value=database_context),
            patch.object(service.asaas_links, "mark_customer_failed") as mark_link_failed,
            patch.object(service.jobs, "mark_job_failed") as mark_job_failed,
        ):
            service._process_asaas(job, patient, UNIT)

        self.assertEqual(mark_link_failed.call_args.kwargs["http_status"], 502)
        self.assertEqual(mark_link_failed.call_args.kwargs["status"], "erro")
        self.assertEqual(mark_job_failed.call_args.kwargs["http_status"], 502)
        self.assertEqual(mark_job_failed.call_args.kwargs["status"], "retry")
        self.assertIsNotNone(mark_job_failed.call_args.kwargs["next_retry_at"])

    def _assert_no_pii(self, output):
        combined = " ".join(output)
        self.assertNotIn(PATIENT_NAME, combined)
        self.assertNotIn(PATIENT_DOCUMENT, combined)
        self.assertNotIn(PATIENT_EMAIL, combined)
        self.assertNotIn("Rua Privada", combined)


if __name__ == "__main__":
    unittest.main()
