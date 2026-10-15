from dataclasses import dataclass
from typing import Optional

from app.database.db import DatabaseConnection


AUTOMATIC_ORIGIN = "automatico"
MANUAL_ORIGIN = "manual"


@dataclass(frozen=True)
class DeliveryAuditAttempt:
    audit_id: int
    should_send: bool
    status: str
    error_message: Optional[str] = None


def mask_recipient(recipient: str) -> str:
    suffix = (recipient or "")[-4:]
    return f"••••••••{suffix}" if suffix else "não informado"


def begin_delivery_audit(
    *,
    document_type: str,
    document_id: int,
    paciente_id: int,
    dependente_id: Optional[int],
    template_name: str,
    sender_unit: str,
    recipient: str,
    origin: str,
    requested_by: Optional[int],
) -> DeliveryAuditAttempt:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        if origin == AUTOMATIC_ORIGIN:
            cursor.execute(
                """
                INSERT INTO whatsapp_document_deliveries (
                    document_type,
                    document_id,
                    paciente_id,
                    dependente_id,
                    template_name,
                    sender_unit,
                    recipient_masked,
                    origin,
                    status,
                    requested_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'processando', %s)
                ON CONFLICT (document_type, document_id)
                    WHERE origin = 'automatico'
                DO NOTHING
                RETURNING id
                """,
                (
                    document_type,
                    document_id,
                    paciente_id,
                    dependente_id,
                    template_name,
                    sender_unit,
                    mask_recipient(recipient),
                    origin,
                    requested_by,
                ),
            )
            inserted = cursor.fetchone()
            if inserted:
                conn.commit()
                return DeliveryAuditAttempt(
                    audit_id=inserted[0],
                    should_send=True,
                    status="processando",
                )

            cursor.execute(
                """
                SELECT id, status, error_message
                FROM whatsapp_document_deliveries
                WHERE document_type = %s
                  AND document_id = %s
                  AND origin = 'automatico'
                ORDER BY id DESC
                LIMIT 1
                """,
                (document_type, document_id),
            )
            existing = cursor.fetchone()
            if not existing:
                raise RuntimeError("Auditoria automática não encontrada após conflito")
            return DeliveryAuditAttempt(
                audit_id=existing[0],
                should_send=False,
                status=existing[1],
                error_message=existing[2],
            )

        cursor.execute(
            """
            INSERT INTO whatsapp_document_deliveries (
                document_type,
                document_id,
                paciente_id,
                dependente_id,
                template_name,
                sender_unit,
                recipient_masked,
                origin,
                status,
                requested_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'processando', %s)
            RETURNING id
            """,
            (
                document_type,
                document_id,
                paciente_id,
                dependente_id,
                template_name,
                sender_unit,
                mask_recipient(recipient),
                origin,
                requested_by,
            ),
        )
        audit_id = cursor.fetchone()[0]
        conn.commit()
        return DeliveryAuditAttempt(
            audit_id=audit_id,
            should_send=True,
            status="processando",
        )


def mark_delivery_sent(audit_id: int, meta_message_id: str) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE whatsapp_document_deliveries
            SET status = 'enviado',
                meta_message_id = %s,
                error_message = NULL,
                sent_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (meta_message_id, audit_id),
        )
        conn.commit()


def mark_delivery_failed(audit_id: int, error_message: str) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE whatsapp_document_deliveries
            SET status = 'erro',
                meta_message_id = NULL,
                error_message = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (error_message[:500], audit_id),
        )
        conn.commit()
