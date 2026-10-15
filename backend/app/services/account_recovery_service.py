import hashlib
import hmac
import logging
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database.db import DatabaseConnection
from app.security.passwords import hash_password, validate_new_password
from app.services.meta_whatsapp_official_service import (
    WhatsAppConfigurationError,
    WhatsAppDeliveryError,
    normalize_recipient_phone,
    resolve_sender_unit,
    send_authentication_code,
)


logger = logging.getLogger(__name__)

CODE_TTL_MINUTES = 10
RESET_TOKEN_TTL_MINUTES = 5
MAX_CODE_ATTEMPTS = 5
MAX_ACCOUNT_REQUESTS = 3
MAX_REQUESTER_REQUESTS = 10
RATE_WINDOW_MINUTES = 30


class InvalidRecoveryCode(ValueError):
    pass


class InvalidResetToken(ValueError):
    pass


class RecoveryUnavailable(ValueError):
    pass


class RecoveryConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PendingDelivery:
    request_id: str
    code: str
    recipient: str
    sender_unit: str


@dataclass(frozen=True)
class RecoveryRequestResult:
    request_id: str
    delivery: Optional[PendingDelivery]


@dataclass(frozen=True)
class AccountSecurityStatus:
    phone_masked: Optional[str]
    phone_verified: bool
    sender_unit: Optional[str]


def _pepper() -> bytes:
    value = os.getenv("PASSWORD_RESET_PEPPER", "").strip()
    if len(value) < 32:
        raise RecoveryConfigurationError("PASSWORD_RESET_PEPPER não configurado")
    return value.encode("utf-8")


def _digest(namespace: str, value: str) -> str:
    payload = f"{namespace}:{value}".encode("utf-8")
    return hmac.new(_pepper(), payload, hashlib.sha256).hexdigest()


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().casefold()


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _new_public_id() -> str:
    return str(uuid.uuid4())


def _new_reset_token() -> str:
    return secrets.token_urlsafe(32)


def _mask_phone(country_code: str, area_code: str, number: str) -> Optional[str]:
    try:
        digits = normalize_recipient_phone(country_code, area_code, number)
    except WhatsAppConfigurationError:
        return None
    return f"•••• •••• {digits[-4:]}"


def _is_approved(status_value: Optional[str]) -> bool:
    return not status_value or status_value.strip().casefold() == "aprovado"


def _within_rate_limit(cursor, account_digest: str, requester_digest: str) -> bool:
    since = datetime.now(timezone.utc) - timedelta(minutes=RATE_WINDOW_MINUTES)
    cursor.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE account_digest = %s),
            COUNT(*) FILTER (WHERE requester_digest = %s)
        FROM password_recovery_requests
        WHERE created_at >= %s
        """,
        (account_digest, requester_digest, since),
    )
    account_count, requester_count = cursor.fetchone()
    return (
        account_count < MAX_ACCOUNT_REQUESTS
        and requester_count < MAX_REQUESTER_REQUESTS
    )


def _insert_request(
    cursor,
    *,
    request_id: str,
    user_id: Optional[int],
    purpose: str,
    account_digest: str,
    requester_digest: str,
    code_digest: str,
    sender_unit: Optional[str],
    recipient_digest: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc)
    if user_id is not None:
        cursor.execute(
            """
            UPDATE password_recovery_requests
            SET consumed_at = %s, updated_at = %s
            WHERE user_id = %s
              AND purpose = %s
              AND consumed_at IS NULL
            """,
            (now, now, user_id, purpose),
        )

    cursor.execute(
        """
        INSERT INTO password_recovery_requests (
            id, user_id, purpose, account_digest, requester_digest,
            code_digest, recipient_digest, sender_unit, expires_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            request_id,
            user_id,
            purpose,
            account_digest,
            requester_digest,
            code_digest,
            recipient_digest,
            sender_unit,
            now + timedelta(minutes=CODE_TTL_MINUTES),
        ),
    )


def request_password_reset(email: str, requester_key: str) -> RecoveryRequestResult:
    public_id = _new_public_id()
    normalized_email = _normalize_email(email)

    try:
        account_digest = _digest("account", normalized_email)
        requester_digest = _digest("requester", requester_key)
        code = _new_code()
        code_digest = _digest("code", f"{public_id}:{code}")

        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    id, role, unidade, unidade_recuperacao,
                    phone_country_code, phone_area_code, phone_number,
                    status_aprovacao
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (normalized_email,),
            )
            row = cursor.fetchone()

            if not _within_rate_limit(cursor, account_digest, requester_digest):
                return RecoveryRequestResult(request_id=public_id, delivery=None)

            user_id: Optional[int] = None
            sender_unit: Optional[str] = None
            recipient: Optional[str] = None

            if row:
                (
                    candidate_user_id,
                    role,
                    unit,
                    recovery_unit,
                    country_code,
                    area_code,
                    phone_number,
                    approval_status,
                ) = row
                sender_unit = resolve_sender_unit(role, unit, recovery_unit)

                if (
                    _is_approved(approval_status)
                    and sender_unit
                    and country_code
                    and area_code
                    and phone_number
                ):
                    recipient = normalize_recipient_phone(
                        country_code, area_code, phone_number
                    )
                    user_id = candidate_user_id

            _insert_request(
                cursor,
                request_id=public_id,
                user_id=user_id,
                purpose="password_reset",
                account_digest=account_digest,
                requester_digest=requester_digest,
                code_digest=code_digest,
                sender_unit=sender_unit if user_id is not None else None,
                recipient_digest=(
                    _digest("phone", recipient)
                    if user_id is not None and recipient
                    else None
                ),
            )

        delivery = None
        if user_id is not None and recipient and sender_unit:
            delivery = PendingDelivery(
                request_id=public_id,
                code=code,
                recipient=recipient,
                sender_unit=sender_unit,
            )
        return RecoveryRequestResult(request_id=public_id, delivery=delivery)
    except Exception as exc:
        logger.error(
            "Falha ao preparar recuperação de senha (%s)",
            type(exc).__name__,
        )
        return RecoveryRequestResult(request_id=public_id, delivery=None)


def request_phone_verification(user_id: int, requester_key: str) -> RecoveryRequestResult:
    public_id = _new_public_id()
    try:
        requester_digest = _digest("requester", requester_key)
        account_digest = _digest("user", str(user_id))
        code = _new_code()
        code_digest = _digest("code", f"{public_id}:{code}")

        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    role, unidade, unidade_recuperacao,
                    phone_country_code, phone_area_code, phone_number,
                    status_aprovacao
                FROM users
                WHERE id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise RecoveryUnavailable("Usuário não encontrado")
            if not _within_rate_limit(cursor, account_digest, requester_digest):
                raise RecoveryUnavailable("Aguarde antes de solicitar outro código")

            (
                role,
                unit,
                recovery_unit,
                country_code,
                area_code,
                phone_number,
                approval_status,
            ) = row
            if not _is_approved(approval_status):
                raise RecoveryUnavailable("Conta ainda não está aprovada")

            sender_unit = resolve_sender_unit(role, unit, recovery_unit)
            if not sender_unit or not country_code or not area_code or not phone_number:
                raise RecoveryUnavailable("Telefone ou unidade de recuperação indisponível")

            recipient = normalize_recipient_phone(
                country_code, area_code, phone_number
            )
            _insert_request(
                cursor,
                request_id=public_id,
                user_id=user_id,
                purpose="phone_verification",
                account_digest=account_digest,
                requester_digest=requester_digest,
                code_digest=code_digest,
                sender_unit=sender_unit,
                recipient_digest=_digest("phone", recipient),
            )

        return RecoveryRequestResult(
            request_id=public_id,
            delivery=PendingDelivery(
                request_id=public_id,
                code=code,
                recipient=recipient,
                sender_unit=sender_unit,
            ),
        )
    except RecoveryUnavailable:
        raise
    except Exception as exc:
        logger.error(
            "Falha ao preparar verificação de telefone (%s)",
            type(exc).__name__,
        )
        raise RecoveryUnavailable("Verificação temporariamente indisponível") from exc


def deliver_pending_code(delivery: PendingDelivery) -> None:
    delivery_status = "failed"
    message_id: Optional[str] = None
    try:
        message_id = send_authentication_code(
            delivery.recipient,
            delivery.code,
            delivery.sender_unit,
        )
        delivery_status = "accepted"
    except (WhatsAppConfigurationError, WhatsAppDeliveryError) as exc:
        logger.warning(
            "Envio de código não aceito (unidade=%s, erro=%s)",
            delivery.sender_unit,
            type(exc).__name__,
        )
    finally:
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE password_recovery_requests
                    SET delivery_status = %s, meta_message_id = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (
                        delivery_status,
                        message_id,
                        datetime.now(timezone.utc),
                        delivery.request_id,
                    ),
                )
        except Exception as exc:
            logger.error(
                "Falha ao registrar entrega de código (%s)",
                type(exc).__name__,
            )


def _verify_code(
    request_id: str,
    code: str,
    *,
    purpose: str,
    expected_user_id: Optional[int] = None,
) -> Optional[str]:
    try:
        parsed_id = str(uuid.UUID(request_id))
    except (ValueError, TypeError) as exc:
        raise InvalidRecoveryCode("Código inválido ou expirado") from exc

    now = datetime.now(timezone.utc)
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                user_id, code_digest, recipient_digest,
                attempts, expires_at, verified_at, consumed_at
            FROM password_recovery_requests
            WHERE id = %s AND purpose = %s
            FOR UPDATE
            """,
            (parsed_id, purpose),
        )
        row = cursor.fetchone()
        if not row:
            raise InvalidRecoveryCode("Código inválido ou expirado")

        (
            user_id,
            stored_digest,
            recipient_digest,
            attempts,
            expires_at,
            verified_at,
            consumed_at,
        ) = row
        if (
            user_id is None
            or consumed_at is not None
            or verified_at is not None
            or attempts >= MAX_CODE_ATTEMPTS
            or expires_at <= now
            or (expected_user_id is not None and user_id != expected_user_id)
        ):
            raise InvalidRecoveryCode("Código inválido ou expirado")

        candidate_digest = _digest("code", f"{parsed_id}:{code}")
        next_attempt = min(attempts + 1, MAX_CODE_ATTEMPTS)
        if not hmac.compare_digest(candidate_digest, stored_digest):
            cursor.execute(
                """
                UPDATE password_recovery_requests
                SET attempts = %s, updated_at = %s
                WHERE id = %s
                """,
                (next_attempt, now, parsed_id),
            )
            # Persiste a tentativa mesmo que a validação termine em erro.
            conn.commit()
            raise InvalidRecoveryCode("Código inválido ou expirado")

        if purpose == "phone_verification":
            cursor.execute(
                """
                SELECT phone_country_code, phone_area_code, phone_number
                FROM users
                WHERE id = %s
                FOR UPDATE
                """,
                (user_id,),
            )
            phone_row = cursor.fetchone()
            if not phone_row or not all(phone_row):
                raise InvalidRecoveryCode("Código inválido ou expirado")
            current_recipient = normalize_recipient_phone(*phone_row)
            if not recipient_digest or not hmac.compare_digest(
                recipient_digest,
                _digest("phone", current_recipient),
            ):
                raise InvalidRecoveryCode("Código inválido ou expirado")

            cursor.execute(
                """
                UPDATE users
                SET phone_verified_at = %s
                WHERE id = %s
                """,
                (now, user_id),
            )
            cursor.execute(
                """
                UPDATE password_recovery_requests
                SET attempts = %s, verified_at = %s, consumed_at = %s, updated_at = %s
                WHERE id = %s
                """,
                (next_attempt, now, now, now, parsed_id),
            )
            return None

        cursor.execute(
            """
            SELECT phone_country_code, phone_area_code, phone_number
            FROM users
            WHERE id = %s
            FOR UPDATE
            """,
            (user_id,),
        )
        phone_row = cursor.fetchone()
        if not phone_row or not all(phone_row):
            raise InvalidRecoveryCode("Código inválido ou expirado")

        current_recipient = normalize_recipient_phone(*phone_row)
        if not recipient_digest or not hmac.compare_digest(
            recipient_digest,
            _digest("phone", current_recipient),
        ):
            raise InvalidRecoveryCode("Código inválido ou expirado")

        reset_token = _new_reset_token()
        cursor.execute(
            """
            UPDATE password_recovery_requests
            SET attempts = %s,
                verified_at = %s,
                reset_token_digest = %s,
                reset_token_expires_at = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (
                next_attempt,
                now,
                _token_digest(reset_token),
                now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
                now,
                parsed_id,
            ),
        )
        return reset_token


def verify_password_reset_code(request_id: str, code: str) -> str:
    token = _verify_code(request_id, code, purpose="password_reset")
    if token is None:
        raise InvalidRecoveryCode("Código inválido ou expirado")
    return token


def confirm_phone_verification(user_id: int, request_id: str, code: str) -> None:
    _verify_code(
        request_id,
        code,
        purpose="phone_verification",
        expected_user_id=user_id,
    )


def complete_password_reset(reset_token: str, new_password: str) -> None:
    validate_new_password(new_password)
    now = datetime.now(timezone.utc)
    digest = _token_digest(reset_token)

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, reset_token_expires_at, consumed_at
            FROM password_recovery_requests
            WHERE reset_token_digest = %s
              AND purpose = 'password_reset'
              AND verified_at IS NOT NULL
            FOR UPDATE
            """,
            (digest,),
        )
        row = cursor.fetchone()
        if not row:
            raise InvalidResetToken("Autorização inválida ou expirada")

        request_id, user_id, expires_at, consumed_at = row
        if user_id is None or consumed_at is not None or expires_at <= now:
            raise InvalidResetToken("Autorização inválida ou expirada")

        cursor.execute(
            """
            UPDATE users
            SET senha = %s, auth_version = auth_version + 1
            WHERE id = %s
            """,
            (hash_password(new_password), user_id),
        )
        cursor.execute(
            """
            UPDATE password_recovery_requests
            SET consumed_at = %s, updated_at = %s
            WHERE id = %s
            """,
            (now, now, request_id),
        )


def get_account_security_status(user_id: int) -> AccountSecurityStatus:
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    role, unidade, unidade_recuperacao,
                    phone_country_code, phone_area_code, phone_number,
                    phone_verified_at
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise RecoveryUnavailable("Usuário não encontrado")

        (
            role,
            unit,
            recovery_unit,
            country_code,
            area_code,
            phone_number,
            verified_at,
        ) = row
        phone_masked = None
        if country_code and area_code and phone_number:
            phone_masked = _mask_phone(country_code, area_code, phone_number)
        return AccountSecurityStatus(
            phone_masked=phone_masked,
            phone_verified=verified_at is not None,
            sender_unit=resolve_sender_unit(role, unit, recovery_unit),
        )
    except RecoveryUnavailable:
        raise
    except Exception as exc:
        logger.error(
            "Falha ao consultar segurança da conta (%s)",
            type(exc).__name__,
        )
        raise RecoveryUnavailable("Segurança da conta temporariamente indisponível") from exc
