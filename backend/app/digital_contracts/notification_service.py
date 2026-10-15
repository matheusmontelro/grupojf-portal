import logging
from dataclasses import dataclass
from typing import Any, Mapping

from app.database.db import DatabaseConnection
from app.services.meta_whatsapp_official_service import (
    CONTRACT_TEMPLATE_NAME,
    WhatsAppConfigurationError,
    WhatsAppDeliveryError,
    normalize_recipient_phone,
    resolve_sender_unit,
    send_contract_link,
)
from app.services.whatsapp_document_audit_service import (
    AUTOMATIC_ORIGIN,
    begin_delivery_audit,
    mark_delivery_failed,
    mark_delivery_sent,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContractDeliveryResult:
    sent: bool
    status: str
    message: str


def _load_delivery_context(odontograma_id: int) -> tuple:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                c.id,
                c.access_token,
                c.status,
                c.paciente_id,
                c.dependente_id,
                p.nome_paciente,
                COALESCE(d.nome_dependente, p.nome_paciente) AS beneficiario_nome,
                p.phone_country_code,
                p.phone_area_code,
                p.phone_number
            FROM digital_contracts c
            JOIN pacientes p ON p.paciente_id = c.paciente_id
            LEFT JOIN dependentes d ON d.dependente_id = c.dependente_id
            WHERE c.odontograma_id = %s
              AND c.expires_at > NOW()
              AND c.status NOT IN ('expired', 'cancelled')
            ORDER BY c.created_at DESC
            LIMIT 1
            """,
            (odontograma_id,),
        )
        row = cursor.fetchone()

    if not row:
        raise WhatsAppConfigurationError("Contrato válido não encontrado")
    return row


def _mark_contract_sent(contract_id: int) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE digital_contracts
            SET status = 'sent',
                sent_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
              AND status = 'draft'
            """,
            (contract_id,),
        )
        conn.commit()


def send_contract_whatsapp(
    odontograma_id: int,
    user_context: Mapping[str, Any],
    origin: str = AUTOMATIC_ORIGIN,
) -> ContractDeliveryResult:
    sender_unit = resolve_sender_unit(
        user_context.get("role"),
        user_context.get("unidade"),
    )
    if not sender_unit:
        raise WhatsAppConfigurationError(
            "Não foi possível identificar o WhatsApp da unidade"
        )

    (
        contract_id,
        access_token,
        status,
        paciente_id,
        dependente_id,
        recipient_name,
        beneficiary_name,
        country_code,
        area_code,
        phone_number,
    ) = _load_delivery_context(odontograma_id)

    if status in {"sent", "opened", "selfie_taken", "signed", "completed"}:
        return ContractDeliveryResult(
            sent=True,
            status="already_sent",
            message="Link já enviado pelo WhatsApp da unidade",
        )

    recipient = normalize_recipient_phone(
        country_code or "",
        area_code or "",
        phone_number or "",
    )

    audit = begin_delivery_audit(
        document_type="contrato",
        document_id=contract_id,
        paciente_id=paciente_id,
        dependente_id=dependente_id,
        template_name=CONTRACT_TEMPLATE_NAME,
        sender_unit=sender_unit,
        recipient=recipient,
        origin=origin,
        requested_by=user_context.get("user_id"),
    )
    if not audit.should_send:
        if audit.status == "erro":
            return ContractDeliveryResult(
                sent=False,
                status="error",
                message=audit.error_message or "O envio automático anterior falhou",
            )
        return ContractDeliveryResult(
            sent=True,
            status="already_sent",
            message="Link já enviado ou em processamento pelo WhatsApp da unidade",
        )

    try:
        message_id = send_contract_link(
            recipient,
            recipient_name,
            beneficiary_name,
            access_token,
            sender_unit,
        )
    except (WhatsAppConfigurationError, WhatsAppDeliveryError) as exc:
        mark_delivery_failed(audit.audit_id, str(exc))
        logger.warning(
            "Falha no envio oficial do contrato (contrato_id=%s, unidade=%s)",
            contract_id,
            sender_unit,
        )
        raise
    except Exception as exc:
        mark_delivery_failed(
            audit.audit_id,
            "Não foi possível enviar o contrato pelo WhatsApp",
        )
        logger.error(
            "Falha inesperada no envio oficial do contrato "
            "(contrato_id=%s, tipo=%s)",
            contract_id,
            type(exc).__name__,
        )
        raise

    try:
        mark_delivery_sent(audit.audit_id, message_id)
    except Exception as exc:
        logger.error(
            "Mensagem do contrato aceita pela Meta, mas a auditoria não foi "
            "atualizada (contrato_id=%s, auditoria_id=%s, tipo=%s)",
            contract_id,
            audit.audit_id,
            type(exc).__name__,
        )

    try:
        _mark_contract_sent(contract_id)
    except Exception as exc:
        logger.error(
            "Mensagem do contrato aceita pela Meta, mas o status do contrato "
            "não foi atualizado (contrato_id=%s, tipo=%s)",
            contract_id,
            type(exc).__name__,
        )

    logger.info(
        "Link de contrato enviado pela Meta (contrato_id=%s, unidade=%s)",
        contract_id,
        sender_unit,
    )
    return ContractDeliveryResult(
        sent=True,
        status="sent",
        message="Link enviado pelo WhatsApp da unidade",
    )
