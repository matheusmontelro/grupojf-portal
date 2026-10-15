import inspect
import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.routers import boletos, pacientes, pacientes_integrados


def make_request(unidade):
    return SimpleNamespace(state=SimpleNamespace(user={"unidade": unidade}))


class PatientRouteUnitScopeTests(unittest.TestCase):
    def test_unit_user_is_always_scoped_to_authenticated_unit(self):
        request = make_request("São João de Meriti")

        self.assertEqual(
            pacientes._resolve_read_unit_scope(request, "Vilar dos Teles"),
            "São João de Meriti",
        )
        self.assertEqual(
            pacientes_integrados._resolve_read_unit_scope(
                request,
                "Vilar dos Teles",
            ),
            "São João de Meriti",
        )

    def test_global_user_can_read_all_or_filter_one_known_unit(self):
        request = make_request("Todas Unidades")

        self.assertIsNone(pacientes._resolve_read_unit_scope(request))
        self.assertEqual(
            pacientes_integrados._resolve_read_unit_scope(request, "Vilar"),
            "Vilar dos Teles",
        )

    def test_unknown_user_unit_is_fail_closed(self):
        request = make_request("Unidade Desconhecida")

        for resolver in (
            pacientes._resolve_read_unit_scope,
            pacientes_integrados._resolve_read_unit_scope,
        ):
            with self.subTest(resolver=resolver.__module__):
                with self.assertRaises(HTTPException) as raised:
                    resolver(request)
                self.assertEqual(raised.exception.status_code, 403)

    def test_sensitive_id_and_delete_routes_receive_authenticated_request(self):
        for route in (
            pacientes.obter_paciente,
            pacientes.deletar_paciente,
            pacientes_integrados.obter_paciente_integrado,
            pacientes_integrados.criar_dependente_para_responsavel_existente,
        ):
            with self.subTest(route=route.__name__):
                self.assertIn("request", inspect.signature(route).parameters)

    def test_list_queries_no_longer_include_unassigned_patients_for_every_unit(self):
        source = inspect.getsource(pacientes_integrados.listar_pacientes_integrados)

        self.assertNotIn("unidade IS NULL", source)
        self.assertIn('where_conditions.append("unidade = ANY(%s)")', source)
        self.assertIn("patient_unit_storage_values(unit_scope)", source)

    def test_legacy_unit_values_are_included_without_exposing_null_unit(self):
        for route in (
            pacientes.listar_pacientes,
            pacientes.obter_paciente,
            pacientes_integrados.obter_paciente_integrado,
        ):
            with self.subTest(route=route.__name__):
                source = inspect.getsource(route)
                self.assertIn("unidade = ANY(%s)", source)
                self.assertNotIn("unidade IS NULL", source)

    def test_delta_import_authorizes_asaas_create_for_new_local_patient(self):
        source = inspect.getsource(pacientes_integrados.importar_paciente_delta)

        self.assertIn("confirmed_delta_customer_id=confirmed_delta_customer_id", source)
        self.assertIn("allow_asaas_customer_creation=True", source)

    def test_patient_creates_authorize_each_provider_explicitly(self):
        direct_source = inspect.getsource(pacientes.criar_paciente)
        integrated_source = inspect.getsource(
            pacientes_integrados._create_patient_with_async_integrations
        )

        self.assertIn("allow_delta_customer_creation=True", direct_source)
        self.assertIn("allow_asaas_customer_creation=True", direct_source)
        self.assertIn(
            "allow_delta_customer_creation=existing is None",
            integrated_source,
        )
        self.assertIn("allow_asaas_customer_creation=True", integrated_source)

    def test_patient_updates_may_create_only_in_asaas(self):
        direct_source = inspect.getsource(pacientes.atualizar_paciente)
        integrated_source = inspect.getsource(
            pacientes_integrados._update_patient_with_async_integrations
        )

        for source in (direct_source, integrated_source):
            self.assertIn("allow_asaas_customer_creation=True", source)
            self.assertNotIn("allow_delta_customer_creation=True", source)

    def test_boleto_issue_never_reassigns_patient_unit(self):
        source = inspect.getsource(boletos.criar_boletos)

        self.assertNotIn("UPDATE pacientes SET unidade", source)
        self.assertNotIn("data.dict()", source)

    def test_legacy_integrated_update_keeps_remote_identity_guard(self):
        source = inspect.getsource(pacientes_integrados.atualizar_paciente_integrado)

        self.assertIn("ensure_remote_identities_before_document_change", source)
        self.assertIn("except PatientIntegrationIdentityPendingError", source)


if __name__ == "__main__":
    unittest.main()
