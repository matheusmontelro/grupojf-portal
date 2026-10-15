import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


APP_DIR = Path(__file__).resolve().parents[1] / "app"
SENSITIVE_DICT_KEYS = {"password", "db_password", "database_password"}
SENSITIVE_VARIABLES = {"DB_PASSWORD", "DATABASE_PASSWORD"}


class DatabaseConfigSecurityTests(unittest.TestCase):
    def test_backend_app_has_no_nonempty_database_password_literals(self):
        findings = []

        for path in sorted(APP_DIR.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if (
                            isinstance(key, ast.Constant)
                            and isinstance(key.value, str)
                            and key.value.lower() in SENSITIVE_DICT_KEYS
                            and isinstance(value, ast.Constant)
                            and isinstance(value.value, str)
                            and value.value
                        ):
                            findings.append(f"{path.relative_to(APP_DIR)}:{value.lineno}")

                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    value = node.value
                    if (
                        any(
                            isinstance(target, ast.Name)
                            and target.id in SENSITIVE_VARIABLES
                            for target in targets
                        )
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                        and value.value
                    ):
                        findings.append(f"{path.relative_to(APP_DIR)}:{value.lineno}")

        self.assertEqual(
            findings,
            [],
            "Credenciais literais de banco encontradas em backend/app: "
            + ", ".join(findings),
        )

    def test_sheets_worker_reuses_central_database_config(self):
        from app.database import db as database_module
        from app.workers import sheets_tasks

        self.assertTrue(
            sheets_tasks.DB_CONFIG is database_module.DB_CONFIG,
            "O worker Sheets deve reutilizar a configuração central do banco.",
        )

    def test_sheets_connection_preserves_existing_return_contract(self):
        from app.workers import sheets_tasks

        connection = MagicMock()
        cursor = connection.cursor.return_value

        with patch.object(sheets_tasks.psycopg2, "connect", return_value=connection) as connect:
            result = sheets_tasks.connect_db()

        connect.assert_called_once_with(**sheets_tasks.DB_CONFIG)
        self.assertEqual(result, (connection, cursor))


if __name__ == "__main__":
    unittest.main()
