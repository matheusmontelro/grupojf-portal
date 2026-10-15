"""Gerenciamento seguro das notificacoes de clientes no Asaas."""

from __future__ import annotations

from collections import Counter
import logging
import re
from typing import Any, Dict, List, Optional, Sequence

from .exceptions import (
    AsaasAPIError,
    AsaasConnectionError,
    AsaasValidationError,
)
from .http_client import AsaasHttpClient

logger = logging.getLogger(__name__)

_REMOTE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
_BOOLEAN_FIELDS = (
    "enabled",
    "emailEnabledForProvider",
    "smsEnabledForProvider",
    "emailEnabledForCustomer",
    "smsEnabledForCustomer",
    "phoneCallEnabledForCustomer",
    "whatsappEnabledForCustomer",
)
_MUTABLE_FIELDS = frozenset(("id", "scheduleOffset", *_BOOLEAN_FIELDS))
_ALWAYS_ENABLED_POLICY = {
    "enabled": True,
    "emailEnabledForCustomer": True,
    "smsEnabledForCustomer": True,
}
_PROVIDER_ENABLED_EVENTS = frozenset({"PAYMENT_RECEIVED"})
_VOICE_ENABLED_EVENTS = frozenset({"PAYMENT_OVERDUE"})
_WHATSAPP_DISABLED_EVENTS = frozenset({"SEND_LINHA_DIGITAVEL"})
_EXPECTED_EVENT_COUNTS = Counter(
    {
        "PAYMENT_CREATED": 1,
        "PAYMENT_UPDATED": 1,
        "PAYMENT_RECEIVED": 1,
        "PAYMENT_OVERDUE": 2,
        "PAYMENT_DUEDATE_WARNING": 2,
        "SEND_LINHA_DIGITAVEL": 1,
    }
)
_LIST_ALLOWED_OFFSETS = {
    "PAYMENT_CREATED": {0},
    "PAYMENT_UPDATED": {0},
    "PAYMENT_RECEIVED": {0},
    # O Asaas lista a notificacao imediata com offset zero, embora o DTO de
    # atualizacao aceite somente os offsets positivos para PAYMENT_OVERDUE.
    "PAYMENT_OVERDUE": {0, 1, 7, 15, 30},
    "PAYMENT_DUEDATE_WARNING": {0, 5, 10, 15, 30},
    "SEND_LINHA_DIGITAVEL": {0},
}
_UPDATE_ALLOWED_OFFSETS = {
    "PAYMENT_OVERDUE": {1, 7, 15, 30},
    "PAYMENT_DUEDATE_WARNING": {0, 5, 10, 15, 30},
}


class NotificationManager:
    """Consulta, atualiza e confere notificacoes de um customer."""

    def __init__(self, http_client: AsaasHttpClient):
        self.http_client = http_client

    @staticmethod
    def _invalid_response() -> AsaasAPIError:
        return AsaasAPIError(
            status_code=502,
            response_body=None,
            detail="invalid_notification_response",
        )

    @staticmethod
    def _normalize_remote_id(value: Any, error_code: str) -> str:
        if not isinstance(value, str):
            raise AsaasValidationError([error_code])
        normalized = value.strip()
        if not _REMOTE_ID_PATTERN.fullmatch(normalized):
            raise AsaasValidationError([error_code])
        return normalized

    @classmethod
    def _normalize_customer_id(cls, customer_id: Any) -> str:
        return cls._normalize_remote_id(customer_id, "customer_id_invalid")

    @classmethod
    def _normalize_notification_id(cls, notification_id: Any) -> str:
        return cls._normalize_remote_id(notification_id, "notification_id_invalid")

    @classmethod
    def _decode_notifications(
        cls,
        response: Any,
        customer_id: str,
    ) -> List[Dict[str, Any]]:
        try:
            page = response.json()
        except ValueError:
            raise cls._invalid_response() from None

        if not isinstance(page, dict) or not isinstance(page.get("data"), list):
            raise cls._invalid_response()

        total_count = page.get("totalCount")
        has_more = page.get("hasMore")
        data = page["data"]
        if (
            isinstance(total_count, bool)
            or not isinstance(total_count, int)
            or total_count < 0
            or not isinstance(has_more, bool)
            or has_more
            or total_count != len(data)
        ):
            # A referencia deste GET nao oferece parametros de paginacao. Uma
            # pagina incompleta nunca pode ser aplicada como politica total.
            raise cls._invalid_response()

        normalized: List[Dict[str, Any]] = []
        seen_ids = set()
        for raw_notification in data:
            if not isinstance(raw_notification, dict):
                raise cls._invalid_response()
            try:
                notification_id = cls._normalize_notification_id(
                    raw_notification.get("id")
                )
                returned_customer_id = cls._normalize_customer_id(
                    raw_notification.get("customer")
                )
            except AsaasValidationError:
                raise cls._invalid_response() from None

            event = raw_notification.get("event")
            schedule_offset = raw_notification.get("scheduleOffset")
            deleted = raw_notification.get("deleted")
            if (
                notification_id in seen_ids
                or returned_customer_id != customer_id
                or not isinstance(event, str)
                or event not in _LIST_ALLOWED_OFFSETS
                or isinstance(schedule_offset, bool)
                or not isinstance(schedule_offset, int)
                or schedule_offset not in _LIST_ALLOWED_OFFSETS[event]
                or not isinstance(deleted, bool)
                or any(
                    not isinstance(raw_notification.get(field), bool)
                    for field in _BOOLEAN_FIELDS
                )
            ):
                raise cls._invalid_response()

            seen_ids.add(notification_id)
            item = dict(raw_notification)
            item["id"] = notification_id
            item["customer"] = returned_customer_id
            normalized.append(item)

        return normalized

    def list_customer_notifications(
        self,
        customer_id: str,
    ) -> List[Dict[str, Any]]:
        normalized_customer_id = self._normalize_customer_id(customer_id)
        response = self.http_client.get(
            f"/customers/{normalized_customer_id}/notifications"
        )
        return self._decode_notifications(response, normalized_customer_id)

    @classmethod
    def _normalize_updates(
        cls,
        notifications: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if (
            isinstance(notifications, (str, bytes, dict))
            or not isinstance(notifications, Sequence)
            or not notifications
        ):
            raise AsaasValidationError(["notifications_invalid"])

        normalized: List[Dict[str, Any]] = []
        seen_ids = set()
        for raw_update in notifications:
            if (
                not isinstance(raw_update, dict)
                or set(raw_update) - _MUTABLE_FIELDS
                or set(raw_update) == {"id"}
            ):
                raise AsaasValidationError(["notifications_invalid"])
            notification_id = cls._normalize_notification_id(raw_update.get("id"))
            if notification_id in seen_ids:
                raise AsaasValidationError(["notifications_duplicated"])
            if any(
                field in raw_update and not isinstance(raw_update[field], bool)
                for field in _BOOLEAN_FIELDS
            ):
                raise AsaasValidationError(["notifications_invalid"])
            if "scheduleOffset" in raw_update and (
                isinstance(raw_update["scheduleOffset"], bool)
                or not isinstance(raw_update["scheduleOffset"], int)
            ):
                raise AsaasValidationError(["schedule_offset_invalid"])

            seen_ids.add(notification_id)
            item = dict(raw_update)
            item["id"] = notification_id
            normalized.append(item)
        return normalized

    @classmethod
    def _validate_update_targets(
        cls,
        current: Sequence[Dict[str, Any]],
        updates: Sequence[Dict[str, Any]],
    ) -> None:
        current_by_id = {
            notification["id"]: notification
            for notification in current
            if not notification["deleted"]
        }
        for update in updates:
            remote = current_by_id.get(update["id"])
            if remote is None:
                raise AsaasValidationError(["notification_id_unknown"])
            if "scheduleOffset" not in update:
                continue
            allowed = _UPDATE_ALLOWED_OFFSETS.get(remote["event"])
            if allowed is None or update["scheduleOffset"] not in allowed:
                raise AsaasValidationError(["schedule_offset_invalid"])

    @classmethod
    def _build_full_policy(
        cls,
        notifications: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        active = [
            notification
            for notification in notifications
            if not notification["deleted"]
        ]
        if Counter(notification["event"] for notification in active) != _EXPECTED_EVENT_COUNTS:
            raise cls._invalid_response()

        overdue_immediate = [
            notification
            for notification in active
            if notification["event"] == "PAYMENT_OVERDUE"
            and notification["scheduleOffset"] == 0
        ]
        overdue_recurring = [
            notification
            for notification in active
            if notification["event"] == "PAYMENT_OVERDUE"
            and notification["scheduleOffset"] > 0
        ]
        if (
            len(overdue_immediate) != 1
            or len(overdue_recurring) != 1
        ):
            raise cls._invalid_response()

        recurring_id = overdue_recurring[0]["id"]
        updates: List[Dict[str, Any]] = []
        for notification in active:
            event = notification["event"]
            update = {
                "id": notification["id"],
                **_ALWAYS_ENABLED_POLICY,
                # A unidade recebe aviso somente quando o pagamento entra.
                "emailEnabledForProvider": event in _PROVIDER_ENABLED_EVENTS,
                "smsEnabledForProvider": event in _PROVIDER_ENABLED_EVENTS,
                # A API responde invalid_action quando voz e enviada para
                # eventos que nao sejam de cobranca vencida.
                "phoneCallEnabledForCustomer": event in _VOICE_ENABLED_EVENTS,
                # O envio isolado da linha digitavel nao aceita WhatsApp. Nos
                # demais eventos o canal foi confirmado pela API.
                "whatsappEnabledForCustomer": (
                    event not in _WHATSAPP_DISABLED_EVENTS
                ),
            }
            if notification["id"] == recurring_id:
                # O segundo PAYMENT_OVERDUE e a regua recorrente. Offset 1
                # aplica a menor frequencia aceita pela API (um dia).
                update["scheduleOffset"] = 1
            updates.append(update)
        return updates

    @staticmethod
    def _matches_updates(
        notifications: Sequence[Dict[str, Any]],
        updates: Sequence[Dict[str, Any]],
    ) -> bool:
        current_by_id = {
            notification["id"]: notification
            for notification in notifications
            if not notification["deleted"]
        }
        for update in updates:
            current = current_by_id.get(update["id"])
            if current is None:
                return False
            if any(
                current.get(field) != expected
                for field, expected in update.items()
                if field != "id"
            ):
                return False
        return True

    @staticmethod
    def _is_ambiguous_write_error(exc: Exception) -> bool:
        if isinstance(exc, AsaasConnectionError):
            return True
        if isinstance(exc, AsaasAPIError):
            return exc.status_code in {408, 409, 425, 429} or exc.status_code >= 500
        return False

    def _put_and_verify(
        self,
        customer_id: str,
        updates: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        original_error: Optional[Exception] = None
        try:
            self.http_client.put(
                "/notifications/batch",
                json={
                    "customer": customer_id,
                    "notifications": list(updates),
                },
            )
        except Exception as exc:
            if not self._is_ambiguous_write_error(exc):
                raise
            original_error = exc

        try:
            verified = self.list_customer_notifications(customer_id)
        except Exception as verification_error:
            if (
                original_error is not None
                and self._is_ambiguous_write_error(verification_error)
            ):
                raise original_error from None
            raise

        if not self._matches_updates(verified, updates):
            if original_error is not None:
                raise original_error from None
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="notification_policy_not_applied",
            )

        if original_error is not None:
            logger.info("Atualizacao ambigua de notificacoes confirmada por consulta.")
        else:
            logger.info("Politica de notificacoes confirmada no Asaas.")
        return verified

    def update_notifications_batch(
        self,
        customer_id: str,
        notifications: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        normalized_customer_id = self._normalize_customer_id(customer_id)
        updates = self._normalize_updates(notifications)
        current = self.list_customer_notifications(normalized_customer_id)
        self._validate_update_targets(current, updates)
        if self._matches_updates(current, updates):
            return current
        return self._put_and_verify(normalized_customer_id, updates)

    def apply_full_notification_policy(
        self,
        customer_id: str,
    ) -> List[Dict[str, Any]]:
        """Aplica todos os canais aceitos e torna o atraso recorrente diario."""
        normalized_customer_id = self._normalize_customer_id(customer_id)
        current = self.list_customer_notifications(normalized_customer_id)
        updates = self._build_full_policy(current)
        self._validate_update_targets(current, updates)
        if self._matches_updates(current, updates):
            logger.info("Politica de notificacoes ja estava aplicada no Asaas.")
            return current
        return self._put_and_verify(normalized_customer_id, updates)
