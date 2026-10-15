import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app import asaas_sales_app
from app.middleware import asaas_sales_auth_middleware as auth
from app.services.asaas_sales_preflight import AsaasSalesPreflightError


class _ConnectionContext:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class AsaasSalesAppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(asaas_sales_app.app)

    def test_import_does_not_initialize_legacy_database_module(self):
        backend_root = Path(__file__).resolve().parents[1]
        environment = {
            **os.environ,
            "PYTHONPATH": str(backend_root),
        }
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; import app.asaas_sales_app; "
                    "raise SystemExit("
                    "int('app.database.db' in sys.modules))"
                ),
            ],
            cwd=backend_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_main_entrypoint_imports_without_exposing_asaas_sales_routes(self):
        backend_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from sqlalchemy.orm import configure_mappers; "
                    "import app.main; configure_mappers(); "
                    "paths = set(app.main.app.openapi()['paths']); "
                    "forbidden = {"
                    "'/api/vendas-asaas/capabilities', "
                    "'/api/vendas-asaas/carnes', "
                    "'/api/webhooks/asaas/sales/{unit_slug}'"
                    "}; "
                    "raise SystemExit(int(bool(paths & forbidden)))"
                ),
            ],
            cwd=backend_root,
            env={**os.environ, "PYTHONPATH": str(backend_root)},
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_openapi_contains_only_sales_and_webhook_contracts(self):
        self.assertEqual(
            set(asaas_sales_app.app.openapi()["paths"]),
            {
                "/api/vendas-asaas/capabilities",
                "/api/vendas-asaas/carnes",
                "/api/vendas-asaas/cartao-recorrente",
                "/api/vendas-asaas/clientes/prontidao",
                "/api/vendas-asaas/entradas",
                "/api/vendas-asaas/entradas/{entry_id}",
                "/api/vendas-asaas/entradas/{entry_id}/checkout",
                "/api/vendas-asaas/integracoes/{integration_id}",
                "/api/vendas-asaas/integracoes/{integration_id}/checkout",
                "/api/vendas-asaas/integracoes/{integration_id}/payment-book",
                "/api/vendas-asaas/integracoes/{integration_id}/pix-qr",
                "/api/vendas-asaas/pix-automatico",
                "/api/vendas-asaas/subcontas",
                "/api/vendas-asaas/subcontas/{user_id}",
                "/api/webhooks/asaas/sales/{unit_slug}",
            },
        )
        self.assertIsNone(asaas_sales_app.app.openapi_url)
        self.assertIsNone(asaas_sales_app.app.docs_url)
        self.assertIsNone(asaas_sales_app.app.redoc_url)

    def test_internal_health_is_generic_for_success_and_failure(self):
        with patch.object(
            asaas_sales_app,
            "run_asaas_sales_preflight",
        ) as check:
            healthy = self.client.get("/internal/health")
        self.assertEqual(healthy.status_code, 200)
        self.assertEqual(healthy.json(), {"status": "ok"})
        check.assert_called_once_with(allow_no_units=True)

        with patch.object(
            asaas_sales_app,
            "run_asaas_sales_preflight",
            side_effect=AsaasSalesPreflightError(
                "database_configuration_missing"
            ),
        ):
            unavailable = self.client.get("/internal/health")
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.json(), {"status": "unavailable"})
        self.assertNotIn("database", unavailable.text.casefold())

    def test_missing_jwt_makes_health_unavailable_without_database_access(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "app.services.asaas_sales_preflight.DatabaseConnection"
            ) as database,
        ):
            response = self.client.get("/internal/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        database.assert_not_called()


class AsaasSalesAuthMiddlewareTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.add_middleware(auth.AsaasSalesAuthMiddleware)

        @app.get("/private")
        def private(request: Request):
            return {"email": request.state.user["sub"]}

        @app.post("/api/webhooks/asaas/sales/sjm")
        def webhook():
            return {"accepted": True}

        self.client = TestClient(app)

    def test_private_route_preserves_auth_version_validation(self):
        payload = {
            "sub": "User@Example.com",
            "auth_version": 7,
        }
        with (
            patch.object(auth, "decode_access_token", return_value=payload),
            patch.object(auth, "_load_auth_version", return_value=7) as version,
        ):
            response = self.client.get(
                "/private",
                headers={"Authorization": "Bearer signed-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"email": "User@Example.com"})
        version.assert_called_once_with("User@Example.com")

    def test_invalidated_session_fails_closed(self):
        with (
            patch.object(
                auth,
                "decode_access_token",
                return_value={"sub": "user@example.com", "auth_version": 6},
            ),
            patch.object(auth, "_load_auth_version", return_value=7),
        ):
            response = self.client.get(
                "/private",
                headers={"Authorization": "Bearer signed-token"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Sessão invalidada"})

    def test_webhook_bypasses_jwt_but_not_its_router_authentication(self):
        with patch.object(auth, "decode_access_token") as decode:
            response = self.client.post("/api/webhooks/asaas/sales/sjm")

        self.assertEqual(response.status_code, 200)
        decode.assert_not_called()

    def test_auth_version_uses_dedicated_read_only_connection(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (9,)
        connection = MagicMock()
        connection.cursor.return_value = cursor
        with patch.object(
            auth,
            "DatabaseConnection",
            return_value=_ConnectionContext(connection),
        ) as database:
            version = auth._load_auth_version("User@Example.com")

        self.assertEqual(version, 9)
        database.assert_called_once_with(read_only=True)
        cursor.execute.assert_called_once()
        self.assertEqual(
            cursor.execute.call_args.args[1],
            ("user@example.com",),
        )


if __name__ == "__main__":
    unittest.main()
