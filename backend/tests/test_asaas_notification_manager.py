import unittest

from app.asaas_sdk.exceptions import (
    AsaasAPIError,
    AsaasConnectionError,
    AsaasValidationError,
)
from app.asaas_sdk.notification_manager import NotificationManager


CUSTOMER_ID = "cus_patient_10"
BOOLEAN_FIELDS = (
    "enabled",
    "emailEnabledForProvider",
    "smsEnabledForProvider",
    "emailEnabledForCustomer",
    "smsEnabledForCustomer",
    "phoneCallEnabledForCustomer",
    "whatsappEnabledForCustomer",
)
DEFAULT_RULES = (
    ("not_created", "PAYMENT_CREATED", 0),
    ("not_due_today", "PAYMENT_DUEDATE_WARNING", 0),
    ("not_received", "PAYMENT_RECEIVED", 0),
    ("not_digitable_line", "SEND_LINHA_DIGITAVEL", 0),
    ("not_overdue_now", "PAYMENT_OVERDUE", 0),
    ("not_overdue_repeat", "PAYMENT_OVERDUE", 7),
    ("not_due_before", "PAYMENT_DUEDATE_WARNING", 10),
    ("not_updated", "PAYMENT_UPDATED", 0),
)


class StubResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeHttpClient:
    def __init__(self, get_payloads, put_error=None):
        self.get_payloads = list(get_payloads)
        self.put_error = put_error
        self.get_calls = []
        self.put_calls = []

    def get(self, endpoint, params=None):
        self.get_calls.append((endpoint, params))
        payload = self.get_payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return StubResponse(payload)

    def put(self, endpoint, json=None):
        self.put_calls.append((endpoint, json))
        if self.put_error is not None:
            raise self.put_error
        return StubResponse({"notifications": []})


def make_notifications(*, configured=False, customer_id=CUSTOMER_ID):
    notifications = []
    for notification_id, event, schedule_offset in DEFAULT_RULES:
        if configured and notification_id == "not_overdue_repeat":
            schedule_offset = 1
        notification = {
            "object": "notification",
            "id": notification_id,
            "customer": customer_id,
            "event": event,
            "scheduleOffset": schedule_offset,
            "deleted": False,
        }
        notification.update(
            {field: configured for field in BOOLEAN_FIELDS}
        )
        if configured:
            provider_enabled = event == "PAYMENT_RECEIVED"
            notification["emailEnabledForProvider"] = provider_enabled
            notification["smsEnabledForProvider"] = provider_enabled
            notification["phoneCallEnabledForCustomer"] = (
                event == "PAYMENT_OVERDUE"
            )
            notification["whatsappEnabledForCustomer"] = (
                event != "SEND_LINHA_DIGITAVEL"
            )
        notifications.append(notification)
    return notifications


def make_page(notifications, *, total_count=None, has_more=False):
    return {
        "object": "list",
        "hasMore": has_more,
        "totalCount": (
            len(notifications) if total_count is None else total_count
        ),
        "limit": 10,
        "offset": 0,
        "data": notifications,
    }


class AsaasNotificationPolicyTests(unittest.TestCase):
    def test_full_policy_enables_supported_channels_and_makes_overdue_daily(self):
        client = FakeHttpClient(
            [
                make_page(make_notifications()),
                make_page(make_notifications(configured=True)),
            ]
        )
        manager = NotificationManager(client)

        result = manager.apply_full_notification_policy(CUSTOMER_ID)

        self.assertEqual(
            client.get_calls,
            [
                (f"/customers/{CUSTOMER_ID}/notifications", None),
                (f"/customers/{CUSTOMER_ID}/notifications", None),
            ],
        )
        self.assertEqual(len(result), 8)
        self.assertEqual(len(client.put_calls), 1)
        endpoint, payload = client.put_calls[0]
        self.assertEqual(endpoint, "/notifications/batch")
        self.assertEqual(payload["customer"], CUSTOMER_ID)
        self.assertEqual(len(payload["notifications"]), 8)

        updates_by_id = {
            notification["id"]: notification
            for notification in payload["notifications"]
        }
        rules_by_id = {
            notification_id: event
            for notification_id, event, _offset in DEFAULT_RULES
        }
        always_enabled_fields = set(BOOLEAN_FIELDS) - {
            "emailEnabledForProvider",
            "smsEnabledForProvider",
            "phoneCallEnabledForCustomer",
            "whatsappEnabledForCustomer",
        }
        for notification_id, update in updates_by_id.items():
            for field in always_enabled_fields:
                self.assertIs(update[field], True)
            self.assertIs(
                update["phoneCallEnabledForCustomer"],
                rules_by_id[notification_id] == "PAYMENT_OVERDUE",
            )
            self.assertIs(
                update["whatsappEnabledForCustomer"],
                rules_by_id[notification_id] != "SEND_LINHA_DIGITAVEL",
            )
            provider_enabled = (
                rules_by_id[notification_id] == "PAYMENT_RECEIVED"
            )
            self.assertIs(
                update["emailEnabledForProvider"],
                provider_enabled,
            )
            self.assertIs(
                update["smsEnabledForProvider"],
                provider_enabled,
            )
        self.assertEqual(
            updates_by_id["not_overdue_repeat"]["scheduleOffset"],
            1,
        )
        self.assertNotIn(
            "scheduleOffset",
            updates_by_id["not_overdue_now"],
        )
        self.assertNotIn(
            "scheduleOffset",
            updates_by_id["not_due_before"],
        )

    def test_ambiguous_batch_is_accepted_only_after_remote_confirmation(self):
        original_error = AsaasConnectionError("connection_failed")
        client = FakeHttpClient(
            [
                make_page(make_notifications()),
                make_page(make_notifications(configured=True)),
            ],
            put_error=original_error,
        )
        manager = NotificationManager(client)

        result = manager.apply_full_notification_policy(CUSTOMER_ID)

        self.assertEqual(len(result), 8)
        self.assertEqual(len(client.put_calls), 1)

    def test_policy_already_applied_does_not_repeat_remote_write(self):
        client = FakeHttpClient(
            [make_page(make_notifications(configured=True))]
        )
        manager = NotificationManager(client)

        result = manager.apply_full_notification_policy(CUSTOMER_ID)

        self.assertEqual(len(result), 8)
        self.assertEqual(len(client.get_calls), 1)
        self.assertEqual(client.put_calls, [])

    def test_due_date_offsets_are_preserved_when_enabling_channels(self):
        initial = make_notifications()
        verified = make_notifications(configured=True)
        initial[1]["scheduleOffset"] = 5
        initial[6]["scheduleOffset"] = 15
        verified[1]["scheduleOffset"] = 5
        verified[6]["scheduleOffset"] = 15
        client = FakeHttpClient(
            [make_page(initial), make_page(verified)]
        )
        manager = NotificationManager(client)

        manager.apply_full_notification_policy(CUSTOMER_ID)

        updates = client.put_calls[0][1]["notifications"]
        due_date_updates = [
            update
            for update in updates
            if update["id"] in {"not_due_today", "not_due_before"}
        ]
        self.assertTrue(
            all("scheduleOffset" not in update for update in due_date_updates)
        )

    def test_ambiguous_batch_is_retried_when_policy_was_not_applied(self):
        original_error = AsaasConnectionError("connection_failed")
        client = FakeHttpClient(
            [
                make_page(make_notifications()),
                make_page(make_notifications()),
            ],
            put_error=original_error,
        )
        manager = NotificationManager(client)

        with self.assertRaises(AsaasConnectionError) as raised:
            manager.apply_full_notification_policy(CUSTOMER_ID)

        self.assertIs(raised.exception, original_error)

    def test_ambiguous_batch_does_not_mask_terminal_verification_error(self):
        original_error = AsaasConnectionError("connection_failed")
        verification_error = AsaasAPIError(401, detail="request_failed")
        client = FakeHttpClient(
            [
                make_page(make_notifications()),
                verification_error,
            ],
            put_error=original_error,
        )
        manager = NotificationManager(client)

        with self.assertRaises(AsaasAPIError) as raised:
            manager.apply_full_notification_policy(CUSTOMER_ID)

        self.assertIs(raised.exception, verification_error)

    def test_successful_batch_with_drift_is_not_considered_integrated(self):
        verification = make_notifications(configured=True)
        verification[0]["whatsappEnabledForCustomer"] = False
        client = FakeHttpClient(
            [
                make_page(make_notifications()),
                make_page(verification),
            ]
        )
        manager = NotificationManager(client)

        with self.assertRaises(AsaasAPIError) as raised:
            manager.apply_full_notification_policy(CUSTOMER_ID)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(
            raised.exception.detail,
            "notification_policy_not_applied",
        )

    def test_voice_drift_on_unsupported_event_is_not_considered_integrated(self):
        verification = make_notifications(configured=True)
        verification[0]["phoneCallEnabledForCustomer"] = True
        client = FakeHttpClient(
            [
                make_page(make_notifications()),
                make_page(verification),
            ]
        )
        manager = NotificationManager(client)

        with self.assertRaises(AsaasAPIError) as raised:
            manager.apply_full_notification_policy(CUSTOMER_ID)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(
            raised.exception.detail,
            "notification_policy_not_applied",
        )

    def test_provider_notification_drift_is_not_considered_integrated(self):
        verification = make_notifications(configured=True)
        verification[0]["emailEnabledForProvider"] = True
        client = FakeHttpClient(
            [
                make_page(make_notifications()),
                make_page(verification),
            ]
        )
        manager = NotificationManager(client)

        with self.assertRaises(AsaasAPIError) as raised:
            manager.apply_full_notification_policy(CUSTOMER_ID)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(
            raised.exception.detail,
            "notification_policy_not_applied",
        )

    def test_incomplete_or_inconsistent_listing_never_reaches_batch(self):
        duplicate = make_notifications()
        duplicate[-1]["id"] = duplicate[0]["id"]
        wrong_customer = make_notifications()
        wrong_customer[0]["customer"] = "cus_other"
        invalid_id_type = make_notifications()
        invalid_id_type[0]["id"] = 123
        invalid_event_type = make_notifications()
        invalid_event_type[0]["event"] = []
        missing_rule = make_notifications()[:-1]
        malformed_cases = (
            make_page(make_notifications(), total_count=9),
            make_page(make_notifications(), has_more=True),
            make_page(duplicate),
            make_page(wrong_customer),
            make_page(invalid_id_type),
            make_page(invalid_event_type),
            make_page(missing_rule),
            {"data": make_notifications()},
        )

        for payload in malformed_cases:
            with self.subTest(payload=payload):
                client = FakeHttpClient([payload])
                manager = NotificationManager(client)

                with self.assertRaises(AsaasAPIError) as raised:
                    manager.apply_full_notification_policy(CUSTOMER_ID)

                self.assertEqual(raised.exception.status_code, 502)
                self.assertEqual(client.put_calls, [])

    def test_generic_batch_rejects_unknown_or_invalid_updates_before_put(self):
        invalid_updates = (
            [],
            [{"id": "not_created"}],
            [{"id": "not_unknown", "enabled": True}],
            [{"id": "not_created", "enabled": "true"}],
            [
                {
                    "id": "not_overdue_now",
                    "scheduleOffset": 0,
                }
            ],
            [{"id": "not_created", "event": "PAYMENT_CREATED"}],
        )

        for updates in invalid_updates:
            with self.subTest(updates=updates):
                client = FakeHttpClient([make_page(make_notifications())])
                manager = NotificationManager(client)

                with self.assertRaises(AsaasValidationError):
                    manager.update_notifications_batch(CUSTOMER_ID, updates)

                self.assertEqual(client.put_calls, [])


if __name__ == "__main__":
    unittest.main()
