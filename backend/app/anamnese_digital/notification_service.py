import asyncio
import logging
from typing import Any, Dict, Optional

from app.database.db import DatabaseConnection
from app.services.meta_whatsapp_official_service import (
    ANAMNESIS_TEMPLATE_NAME,
    WhatsAppConfigurationError,
    WhatsAppDeliveryError,
    normalize_recipient_phone,
    normalize_recipient_value,
    send_anamnesis_link,
)
from app.services.whatsapp_document_audit_service import (
    AUTOMATIC_ORIGIN,
    MANUAL_ORIGIN,
    begin_delivery_audit,
    mark_delivery_failed,
    mark_delivery_sent,
)

from .models import LinkEnvio, MeioEnvio
from .token_service import TokenService


logger = logging.getLogger(__name__)


class NotificationService:
    """Envia links de anamnese e registra cada tentativa para auditoria."""

    async def enviar_link(
        self,
        data: LinkEnvio,
        *,
        origin: str = MANUAL_ORIGIN,
        requested_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        context = self._load_context(data.token)
        if not context:
            return {
                "success": False,
                "delivery_status": "error",
                "error": "Token não encontrado",
            }

        (
            token_id,
            paciente_id,
            dependente_id,
            nome_paciente,
            phone_country_code,
            phone_area_code,
            phone_number,
            nome_dependente,
        ) = context
        link = TokenService.generate_link(data.token)

        if data.meio_envio != MeioEnvio.WHATSAPP:
            return {
                "success": False,
                "delivery_status": "error",
                "error": "Apenas envio por WhatsApp é suportado",
            }

        sender_unit = data.unidade or "não identificada"
        recipient_input = data.destinatario or (
            f"{phone_country_code or ''}{phone_area_code or ''}{phone_number or ''}"
        )

        try:
            if data.destinatario:
                recipient = normalize_recipient_value(data.destinatario)
            else:
                recipient = normalize_recipient_phone(
                    phone_country_code or "",
                    phone_area_code or "",
                    phone_number or "",
                )
        except WhatsAppConfigurationError as exc:
            audit = begin_delivery_audit(
                document_type="anamnese",
                document_id=token_id,
                paciente_id=paciente_id,
                dependente_id=dependente_id,
                template_name=ANAMNESIS_TEMPLATE_NAME,
                sender_unit=sender_unit,
                recipient=recipient_input,
                origin=origin,
                requested_by=requested_by,
            )
            if audit.should_send:
                mark_delivery_failed(audit.audit_id, str(exc))
                self._record_operational_delivery(
                    token_id,
                    data.meio_envio,
                    recipient_input,
                    "erro",
                    str(exc),
                )
            return self._existing_or_failed_result(audit, str(exc), link)

        audit = begin_delivery_audit(
            document_type="anamnese",
            document_id=token_id,
            paciente_id=paciente_id,
            dependente_id=dependente_id,
            template_name=ANAMNESIS_TEMPLATE_NAME,
            sender_unit=sender_unit,
            recipient=recipient,
            origin=origin,
            requested_by=requested_by,
        )
        if not audit.should_send:
            return self._existing_or_failed_result(audit, audit.error_message, link)

        success, error_message, message_id = await self._enviar_whatsapp(
            numero=recipient,
            nome_responsavel=nome_paciente,
            nome_beneficiario=nome_dependente or nome_paciente,
            token=data.token,
            unidade=data.unidade,
        )

        if success and message_id:
            mark_delivery_sent(audit.audit_id, message_id)
        else:
            mark_delivery_failed(
                audit.audit_id,
                error_message or "Não foi possível enviar o link pelo WhatsApp",
            )

        self._record_operational_delivery(
            token_id,
            data.meio_envio,
            recipient,
            "enviado" if success else "erro",
            error_message,
        )
        return {
            "success": success,
            "delivery_status": "sent" if success else "error",
            "error": error_message,
            "link": link,
        }

    @staticmethod
    def _load_context(token: str) -> Optional[tuple]:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    t.id,
                    t.paciente_id,
                    t.dependente_id,
                    p.nome_paciente,
                    p.phone_country_code,
                    p.phone_area_code,
                    p.phone_number,
                    d.nome_dependente
                FROM anamnese_tokens t
                JOIN pacientes p ON p.paciente_id = t.paciente_id
                LEFT JOIN dependentes d ON d.dependente_id = t.dependente_id
                WHERE t.token = %s
                """,
                (token,),
            )
            return cursor.fetchone()

    @staticmethod
    def _record_operational_delivery(
        token_id: int,
        meio_envio: MeioEnvio,
        recipient: str,
        status: str,
        error_message: Optional[str],
    ) -> None:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO anamnese_envios (
                    token_id, meio_envio, destinatario, status, mensagem_erro
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (token_id, meio_envio, recipient, status, error_message),
            )
            conn.commit()

    @staticmethod
    def _existing_or_failed_result(
        audit,
        error_message: Optional[str],
        link: str,
    ) -> Dict[str, Any]:
        if not audit.should_send and audit.status in {"processando", "enviado"}:
            return {
                "success": True,
                "delivery_status": "already_sent",
                "error": None,
                "link": link,
            }
        return {
            "success": False,
            "delivery_status": "error",
            "error": error_message or "O envio automático anterior falhou",
            "link": link,
        }

    async def _enviar_whatsapp(
        self,
        numero: str,
        nome_responsavel: str,
        nome_beneficiario: str,
        token: str,
        unidade: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        try:
            if not unidade:
                raise WhatsAppConfigurationError("Unidade de envio não identificada")

            message_id = await asyncio.to_thread(
                send_anamnesis_link,
                numero,
                nome_responsavel,
                nome_beneficiario,
                token,
                unidade,
            )
            logger.info("Link de anamnese enviado pela Meta (unidade=%s)", unidade)
            return True, None, message_id
        except (WhatsAppConfigurationError, WhatsAppDeliveryError) as exc:
            logger.warning(
                "Falha no envio oficial da anamnese (unidade=%s, tipo=%s)",
                unidade,
                type(exc).__name__,
            )
            return False, str(exc), None
        except Exception as exc:
            logger.error(
                "Erro inesperado no envio da anamnese (%s)",
                type(exc).__name__,
            )
            return False, "Não foi possível enviar o link pelo WhatsApp", None

    async def reenviar_link(
        self,
        token: str,
        unidade: Optional[str] = None,
        requested_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e.meio_envio, e.destinatario
                FROM anamnese_envios e
                JOIN anamnese_tokens t ON t.id = e.token_id
                WHERE t.token = %s
                ORDER BY e.id DESC
                LIMIT 1
                """,
                (token,),
            )
            result = cursor.fetchone()

        if not result:
            return {
                "success": False,
                "delivery_status": "error",
                "error": "Nenhum envio anterior encontrado",
            }

        meio_envio, destinatario = result
        return await self.enviar_link(
            LinkEnvio(
                token=token,
                meio_envio=meio_envio,
                destinatario=destinatario,
                unidade=unidade,
            ),
            origin=MANUAL_ORIGIN,
            requested_by=requested_by,
        )
