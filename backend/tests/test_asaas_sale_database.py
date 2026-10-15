import os
import unittest
from unittest.mock import MagicMock, patch

from app.services import asaas_sale_database as database


class AsaasSaleDatabaseTests(unittest.TestCase):
    def test_connection_uses_only_explicit_process_environment(self):
        connection = MagicMock()
        environment = {
            "ASAAS_SALES_DB_HOST": "postgres.internal",
            "ASAAS_SALES_DB_PORT": "5432",
            "ASAAS_SALES_DB_NAME": "grupojfdb",
            "ASAAS_SALES_DB_USER": "grupojf_asaas",
            "ASAAS_SALES_DB_PASSWORD": "not-logged-secret",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(
                database.psycopg2,
                "connect",
                return_value=connection,
            ) as connect,
        ):
            with database.DatabaseConnection() as opened:
                self.assertIs(opened, connection)

        connect.assert_called_once_with(
            host="postgres.internal",
            port=5432,
            dbname="grupojfdb",
            user="grupojf_asaas",
            password="not-logged-secret",
            connect_timeout=10,
            application_name="grupojf-asaas-sales",
        )
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        connection.close.assert_called_once_with()

    def test_incomplete_configuration_fails_before_connecting(self):
        with (
            patch.dict(
                os.environ,
                {
                    "ASAAS_SALES_DB_NAME": "grupojfdb",
                    "ASAAS_SALES_DB_USER": "grupojf_asaas",
                },
                clear=True,
            ),
            patch.object(database.psycopg2, "connect") as connect,
        ):
            with self.assertRaises(database.AsaasSaleDatabaseConfigError):
                with database.DatabaseConnection():
                    pass
        connect.assert_not_called()

    def test_global_database_variables_are_never_used_as_fallback(self):
        legacy_environment = {
            "DB_HOST": "legacy.internal",
            "DB_NAME": "legacy",
            "DB_USER": "legacy_user",
            "DB_PASSWORD": "legacy-password",
        }
        with (
            patch.dict(os.environ, legacy_environment, clear=True),
            patch.object(database.psycopg2, "connect") as connect,
        ):
            with self.assertRaises(database.AsaasSaleDatabaseConfigError):
                with database.DatabaseConnection():
                    pass
        connect.assert_not_called()

    def test_exception_rolls_back_and_always_closes(self):
        connection = MagicMock()
        environment = {
            "ASAAS_SALES_DB_NAME": "grupojfdb",
            "ASAAS_SALES_DB_USER": "grupojf_asaas",
            "ASAAS_SALES_DB_PASSWORD": "not-logged-secret",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(database.psycopg2, "connect", return_value=connection),
        ):
            with self.assertRaisesRegex(RuntimeError, "controlled"):
                with database.DatabaseConnection():
                    raise RuntimeError("controlled")

        connection.commit.assert_not_called()
        connection.rollback.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_read_only_connection_is_enforced_and_never_committed(self):
        connection = MagicMock()
        environment = {
            "ASAAS_SALES_DB_NAME": "grupojfdb",
            "ASAAS_SALES_DB_USER": "grupojf_asaas",
            "ASAAS_SALES_DB_PASSWORD": "not-logged-secret",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(database.psycopg2, "connect", return_value=connection),
        ):
            with database.DatabaseConnection(read_only=True) as opened:
                self.assertIs(opened, connection)

        connection.set_session.assert_called_once_with(readonly=True)
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        connection.close.assert_called_once_with()

    def test_read_only_setup_failure_closes_connection(self):
        connection = MagicMock()
        connection.set_session.side_effect = RuntimeError("controlled")
        environment = {
            "ASAAS_SALES_DB_NAME": "grupojfdb",
            "ASAAS_SALES_DB_USER": "grupojf_asaas",
            "ASAAS_SALES_DB_PASSWORD": "not-logged-secret",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(database.psycopg2, "connect", return_value=connection),
        ):
            with self.assertRaisesRegex(RuntimeError, "controlled"):
                with database.DatabaseConnection(read_only=True):
                    pass

        connection.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
