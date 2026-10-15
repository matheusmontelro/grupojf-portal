import hashlib
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import jwt

from app.security.passwords import (
    PasswordPolicyError,
    hash_password,
    validate_new_password,
    verify_password,
)
from app.security.tokens import decode_access_token
from app.services import account_recovery_service as recovery
from app.services.meta_whatsapp_official_service import (
    resolve_sender_unit,
    send_authentication_code,
)


class PasswordSecurityTests(unittest.TestCase):
    def test_argon2_round_trip(self):
        password = "frase senha longa e segura"
        stored = hash_password(password)

        valid, needs_rehash = verify_password(password, stored)

        self.assertTrue(valid)
        self.assertFalse(needs_rehash)
        self.assertTrue(stored.startswith("$argon2id$"))

    def test_legacy_sha256_is_accepted_and_marked_for_rehash(self):
        password = "senha-legada"
        stored = hashlib.sha256(password.encode("utf-8")).hexdigest()

        valid, needs_rehash = verify_password(password, stored)

        self.assertTrue(valid)
        self.assertTrue(needs_rehash)

    def test_new_password_requires_fifteen_characters(self):
        with self.assertRaises(PasswordPolicyError):
            validate_new_password("curta-demais")


class TokenCompatibilityTests(unittest.TestCase):
    def test_legacy_token_is_accepted_during_transition(self):
        legacy_secret = "legacy-secret-used-only-in-test"
        token = jwt.encode(
            {
                "sub": "user@example.com",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            legacy_secret,
            algorithm="HS256",
        )

        with patch.dict(
            os.environ,
            {
                "JWT_SECRET": "active-secret-used-only-in-test",
                "JWT_LEGACY_SECRET": legacy_secret,
            },
            clear=False,
        ):
            payload = decode_access_token(token)

        self.assertEqual(payload["sub"], "user@example.com")


class WhatsAppRoutingTests(unittest.TestCase):
    def test_master_and_admin_always_use_nova_iguacu(self):
        self.assertEqual(
            resolve_sender_unit("master", "Vilar dos Teles"),
            "Nova Iguaçu 1",
        )
        self.assertEqual(
            resolve_sender_unit("Administrador", "São João de Meriti"),
            "Nova Iguaçu 1",
        )

    def test_operational_user_uses_own_unit(self):
        self.assertEqual(
            resolve_sender_unit("Comercial", "Vilar dos Teles"),
            "Vilar dos Teles",
        )

    @patch("app.services.meta_whatsapp_official_service.requests.post")
    def test_authentication_code_is_sent_in_body_and_copy_button(self, post):
        response = Mock(status_code=200)
        response.json.return_value = {"messages": [{"id": "wamid.test"}]}
        post.return_value = response

        with patch.dict(
            os.environ,
            {
                "META_WHATSAPP_ACCESS_TOKEN": "test-token",
                "META_WHATSAPP_GRAPH_API_VERSION": "v23.0",
                "META_WHATSAPP_NI_PHONE_NUMBER_ID": "phone-id-test",
            },
            clear=False,
        ):
            message_id = send_authentication_code(
                "5521999999999",
                "123456",
                "Nova Iguaçu 1",
            )

        payload = post.call_args.kwargs["json"]
        self.assertEqual(message_id, "wamid.test")
        self.assertEqual(
            payload["template"]["components"][0]["parameters"][0]["text"],
            "123456",
        )
        self.assertEqual(
            payload["template"]["components"][1]["parameters"][0]["text"],
            "123456",
        )


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.executions = []

    def execute(self, query, params):
        self.executions.append((query, params))

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row):
        self.cursor_instance = FakeCursor(row)
        self.commit_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commit_count += 1


class SequenceCursor(FakeCursor):
    def __init__(self, rows):
        super().__init__(None)
        self.rows = iter(rows)

    def fetchone(self):
        return next(self.rows)


class SequenceConnection(FakeConnection):
    def __init__(self, rows):
        self.cursor_instance = SequenceCursor(rows)
        self.commit_count = 0


class RecoveryAttemptTests(unittest.TestCase):
    def test_registered_phone_receives_password_reset_code(self):
        pepper = "p" * 64
        connection = SequenceConnection(
            [
                (
                    10,
                    "master",
                    "Vilar dos Teles",
                    None,
                    "55",
                    "21",
                    "998332217",
                    "aprovado",
                ),
                (0, 0),
            ]
        )

        with patch.dict(os.environ, {"PASSWORD_RESET_PEPPER": pepper}, clear=False):
            with patch.object(recovery, "DatabaseConnection", return_value=connection):
                result = recovery.request_password_reset(
                    "matheus@example.com",
                    "requester-test",
                )

        self.assertIsNotNone(result.delivery)
        self.assertEqual(result.delivery.recipient, "5521998332217")
        self.assertEqual(result.delivery.sender_unit, "Nova Iguaçu 1")

    def test_registered_phone_code_authorizes_password_reset(self):
        request_id = str(uuid.uuid4())
        pepper = "p" * 64
        code = "654321"
        recipient = "5521999999999"

        with patch.dict(os.environ, {"PASSWORD_RESET_PEPPER": pepper}, clear=False):
            connection = SequenceConnection(
                [
                    (
                        10,
                        recovery._digest("code", f"{request_id}:{code}"),
                        recovery._digest("phone", recipient),
                        0,
                        datetime.now(timezone.utc) + timedelta(minutes=5),
                        None,
                        None,
                    ),
                    ("55", "21", "999999999"),
                ]
            )
            with patch.object(recovery, "DatabaseConnection", return_value=connection):
                reset_token = recovery.verify_password_reset_code(request_id, code)

        self.assertTrue(reset_token)

    def test_invalid_code_attempt_is_committed(self):
        request_id = str(uuid.uuid4())
        pepper = "p" * 64
        with patch.dict(os.environ, {"PASSWORD_RESET_PEPPER": pepper}, clear=False):
            stored_digest = recovery._digest("code", f"{request_id}:654321")
            connection = FakeConnection(
                (
                    10,
                    stored_digest,
                    None,
                    0,
                    datetime.now(timezone.utc) + timedelta(minutes=5),
                    None,
                    None,
                )
            )
            with patch.object(recovery, "DatabaseConnection", return_value=connection):
                with self.assertRaises(recovery.InvalidRecoveryCode):
                    recovery.verify_password_reset_code(request_id, "123456")

        self.assertEqual(connection.commit_count, 1)
        update_calls = [
            params
            for query, params in connection.cursor_instance.executions
            if "SET attempts" in query
        ]
        self.assertEqual(update_calls[0][0], 1)

    def test_password_reset_code_is_invalid_after_phone_change(self):
        request_id = str(uuid.uuid4())
        pepper = "p" * 64
        with patch.dict(os.environ, {"PASSWORD_RESET_PEPPER": pepper}, clear=False):
            code = "654321"
            connection = SequenceConnection(
                [
                    (
                        10,
                        recovery._digest("code", f"{request_id}:{code}"),
                        recovery._digest("phone", "5521999999999"),
                        0,
                        datetime.now(timezone.utc) + timedelta(minutes=5),
                        None,
                        None,
                    ),
                    ("55", "21", "988888888"),
                ]
            )
            with patch.object(recovery, "DatabaseConnection", return_value=connection):
                with self.assertRaises(recovery.InvalidRecoveryCode):
                    recovery.verify_password_reset_code(request_id, code)


if __name__ == "__main__":
    unittest.main()
