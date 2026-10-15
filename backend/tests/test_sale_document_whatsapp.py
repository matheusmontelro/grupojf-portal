import os
import unittest
from unittest.mock import Mock, patch

from app.anamnese_digital.models import LinkEnvio, MeioEnvio
from app.anamnese_digital.notification_service import NotificationService
from app.digital_contracts import notification_service as contract_notifications
from app.services.meta_whatsapp_official_service import (
    WhatsAppDeliveryError,
    get_unit_display_name,
    normalize_recipient_phone,
    send_anamnesis_link,
    send_contract_link,
)
from app.services.whatsapp_document_audit_service import (
    AUTOMATIC_ORIGIN,
    DeliveryAuditAttempt,
    mask_recipient,
)


class OfficialDocumentTemplateTests(unittest.TestCase):
    @patch("app.services.meta_whatsapp_official_service.requests.post")
    def test_anamnesis_template_uses_unit_name_and_token_button(self, post):
        response = Mock(status_code=200)
        response.json.return_value = {"messages": [{"id": "wamid.anamnese"}]}
        post.return_value = response

        with patch.dict(
            os.environ,
            {
                "META_WHATSAPP_ACCESS_TOKEN": "test-token",
                "META_WHATSAPP_NI_PHONE_NUMBER_ID": "phone-ni",
            },
            clear=False,
        ):
            message_id = send_anamnesis_link(
                "5521999999999",
                "Responsável",
                "Beneficiário",
                "token-anamnese",
                "Nova Iguaçu 1",
            )

        payload = post.call_args.kwargs["json"]
        self.assertEqual(message_id, "wamid.anamnese")
        self.assertEqual(payload["template"]["name"], "link_anamnese_digital")
        self.assertEqual(
            [item["text"] for item in payload["template"]["components"][0]["parameters"]],
            [
                "Responsável",
                "Beneficiário",
                "Odontocompany Nova Iguaçu",
            ],
        )
        self.assertEqual(
            payload["template"]["components"][1]["parameters"][0]["text"],
            "token-anamnese",
        )

    @patch("app.services.meta_whatsapp_official_service.requests.post")
    def test_contract_template_uses_sjm_sender_and_approved_name(self, post):
        response = Mock(status_code=200)
        response.json.return_value = {"messages": [{"id": "wamid.contrato"}]}
        post.return_value = response

        with patch.dict(
            os.environ,
            {
                "META_WHATSAPP_ACCESS_TOKEN": "test-token",
                "META_WHATSAPP_SJM_PHONE_NUMBER_ID": "phone-sjm",
            },
            clear=False,
        ):
            send_contract_link(
                "5521999999999",
                "Responsável",
                "Beneficiário",
                "token-contrato",
                "São João de Meriti",
            )

        self.assertIn("/phone-sjm/messages", post.call_args.args[0])
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["template"]["name"], "link_contrato_digital")
        self.assertEqual(
            payload["template"]["components"][0]["parameters"][2]["text"],
            "Odontocompany São João de Meriti",
        )

    def test_phone_without_country_code_receives_brazil_prefix(self):
        self.assertEqual(
            normalize_recipient_phone("", "21", "998332217"),
            "5521998332217",
        )
        self.assertEqual(
            normalize_recipient_phone("", "55", "998332217"),
            "5555998332217",
        )

    def test_unit_display_names_match_approved_copy(self):
        self.assertEqual(
            get_unit_display_name("Nova Iguaçu 1"),
            "Odontocompany Nova Iguaçu",
        )
        self.assertEqual(
            get_unit_display_name("São João de Meriti"),
            "Odontocompany São João de Meriti",
        )
        self.assertEqual(
            get_unit_display_name("Vilar dos Teles"),
            "Odontocompany Vilar dos Teles",
        )


class ContractNotificationTests(unittest.TestCase):
    context = (
        77,
        "contract-token",
        "draft",
        11,
        None,
        "Responsável",
        "Beneficiário",
        "55",
        "21",
        "998332217",
    )

    def test_draft_contract_is_audited_and_sent_once(self):
        attempt = DeliveryAuditAttempt(91, True, "processando")
        with (
            patch.object(contract_notifications, "_load_delivery_context", return_value=self.context),
            patch.object(contract_notifications, "begin_delivery_audit", return_value=attempt) as begin,
            patch.object(contract_notifications, "send_contract_link", return_value="wamid.contract") as send,
            patch.object(contract_notifications, "mark_delivery_sent") as mark_sent,
            patch.object(contract_notifications, "_mark_contract_sent") as mark_contract,
        ):
            result = contract_notifications.send_contract_whatsapp(
                123,
                {
                    "role": "Comercial",
                    "unidade": "Vilar dos Teles",
                    "user_id": 8,
                },
            )

        self.assertTrue(result.sent)
        self.assertEqual(result.status, "sent")
        begin.assert_called_once_with(
            document_type="contrato",
            document_id=77,
            paciente_id=11,
            dependente_id=None,
            template_name="link_contrato_digital",
            sender_unit="Vilar dos Teles",
            recipient="5521998332217",
            origin=AUTOMATIC_ORIGIN,
            requested_by=8,
        )
        send.assert_called_once_with(
            "5521998332217",
            "Responsável",
            "Beneficiário",
            "contract-token",
            "Vilar dos Teles",
        )
        mark_sent.assert_called_once_with(91, "wamid.contract")
        mark_contract.assert_called_once_with(77)

    def test_automatic_audit_conflict_does_not_duplicate_contract(self):
        existing = DeliveryAuditAttempt(91, False, "enviado")
        with (
            patch.object(contract_notifications, "_load_delivery_context", return_value=self.context),
            patch.object(contract_notifications, "begin_delivery_audit", return_value=existing),
            patch.object(contract_notifications, "send_contract_link") as send,
        ):
            result = contract_notifications.send_contract_whatsapp(
                123,
                {"role": "Comercial", "unidade": "Vilar dos Teles"},
            )

        self.assertEqual(result.status, "already_sent")
        send.assert_not_called()

    def test_meta_acceptance_remains_success_when_audit_update_fails(self):
        attempt = DeliveryAuditAttempt(91, True, "processando")
        with (
            patch.object(contract_notifications, "_load_delivery_context", return_value=self.context),
            patch.object(contract_notifications, "begin_delivery_audit", return_value=attempt),
            patch.object(contract_notifications, "send_contract_link", return_value="wamid.contract"),
            patch.object(
                contract_notifications,
                "mark_delivery_sent",
                side_effect=RuntimeError("falha na auditoria"),
            ),
            patch.object(contract_notifications, "_mark_contract_sent") as mark_contract,
        ):
            result = contract_notifications.send_contract_whatsapp(
                123,
                {"role": "Comercial", "unidade": "Vilar dos Teles"},
            )

        self.assertTrue(result.sent)
        self.assertEqual(result.status, "sent")
        mark_contract.assert_called_once_with(77)

    def test_meta_acceptance_remains_success_when_contract_update_fails(self):
        attempt = DeliveryAuditAttempt(91, True, "processando")
        with (
            patch.object(contract_notifications, "_load_delivery_context", return_value=self.context),
            patch.object(contract_notifications, "begin_delivery_audit", return_value=attempt),
            patch.object(contract_notifications, "send_contract_link", return_value="wamid.contract"),
            patch.object(contract_notifications, "mark_delivery_sent") as mark_sent,
            patch.object(
                contract_notifications,
                "_mark_contract_sent",
                side_effect=RuntimeError("falha no contrato"),
            ),
        ):
            result = contract_notifications.send_contract_whatsapp(
                123,
                {"role": "Comercial", "unidade": "Vilar dos Teles"},
            )

        self.assertTrue(result.sent)
        self.assertEqual(result.status, "sent")
        mark_sent.assert_called_once_with(91, "wamid.contract")

    def test_failed_contract_delivery_is_recorded_for_manual_retry(self):
        attempt = DeliveryAuditAttempt(91, True, "processando")
        with (
            patch.object(contract_notifications, "_load_delivery_context", return_value=self.context),
            patch.object(contract_notifications, "begin_delivery_audit", return_value=attempt),
            patch.object(
                contract_notifications,
                "send_contract_link",
                side_effect=WhatsAppDeliveryError("Meta recusou a mensagem"),
            ),
            patch.object(contract_notifications, "mark_delivery_failed") as mark_failed,
            patch.object(contract_notifications, "_mark_contract_sent") as mark_contract,
        ):
            with self.assertRaises(WhatsAppDeliveryError):
                contract_notifications.send_contract_whatsapp(
                    123,
                    {"role": "Comercial", "unidade": "Vilar dos Teles"},
                )

        mark_failed.assert_called_once_with(91, "Meta recusou a mensagem")
        mark_contract.assert_not_called()


class AnamnesisNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_anamnesis_uses_official_template_and_records_meta_id(self):
        service = NotificationService()
        attempt = DeliveryAuditAttempt(92, True, "processando")
        with (
            patch.object(
                service,
                "_load_context",
                return_value=(
                    5,
                    11,
                    9,
                    "Responsável",
                    "55",
                    "21",
                    "998332217",
                    "Dependente",
                ),
            ),
            patch("app.anamnese_digital.notification_service.begin_delivery_audit", return_value=attempt) as begin,
            patch("app.anamnese_digital.notification_service.send_anamnesis_link", return_value="wamid.anamnese") as send,
            patch("app.anamnese_digital.notification_service.mark_delivery_sent") as mark_sent,
            patch.object(service, "_record_operational_delivery") as record_operational,
        ):
            result = await service.enviar_link(
                LinkEnvio(
                    token="token-anamnese",
                    meio_envio=MeioEnvio.WHATSAPP,
                    destinatario="(21) 99833-2217",
                    unidade="Nova Iguaçu 1",
                ),
                origin=AUTOMATIC_ORIGIN,
                requested_by=8,
            )

        self.assertTrue(result["success"])
        begin.assert_called_once_with(
            document_type="anamnese",
            document_id=5,
            paciente_id=11,
            dependente_id=9,
            template_name="link_anamnese_digital",
            sender_unit="Nova Iguaçu 1",
            recipient="5521998332217",
            origin=AUTOMATIC_ORIGIN,
            requested_by=8,
        )
        send.assert_called_once_with(
            "5521998332217",
            "Responsável",
            "Dependente",
            "token-anamnese",
            "Nova Iguaçu 1",
        )
        mark_sent.assert_called_once_with(92, "wamid.anamnese")
        record_operational.assert_called_once()

    async def test_existing_automatic_anamnesis_delivery_is_not_repeated(self):
        service = NotificationService()
        existing = DeliveryAuditAttempt(92, False, "enviado")
        with (
            patch.object(
                service,
                "_load_context",
                return_value=(5, 11, None, "Paciente", "55", "21", "998332217", None),
            ),
            patch("app.anamnese_digital.notification_service.begin_delivery_audit", return_value=existing),
            patch("app.anamnese_digital.notification_service.send_anamnesis_link") as send,
        ):
            result = await service.enviar_link(
                LinkEnvio(
                    token="token-anamnese",
                    meio_envio=MeioEnvio.WHATSAPP,
                    destinatario="",
                    unidade="Nova Iguaçu 1",
                ),
                origin=AUTOMATIC_ORIGIN,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["delivery_status"], "already_sent")
        send.assert_not_called()


class AuditSanitizationTests(unittest.TestCase):
    def test_audit_masks_recipient_and_keeps_only_last_four_digits(self):
        masked = mask_recipient("5521998332217")

        self.assertEqual(masked, "••••••••2217")
        self.assertNotIn("998332217", masked)


if __name__ == "__main__":
    unittest.main()
