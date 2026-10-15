import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request

from app.digital_contracts import router as contract_router


SENTINELS = {
    "authorization": "Bearer secret-authorization-value",
    "token": "secret-contract-token-value",
    "cpf": "12345678901",
    "name": "Paciente Sentinela Confidencial",
    "html": "<html>CONTRATO-SENTINELA-CONFIDENCIAL</html>",
    "exception": "EXCECAO-SENTINELA-CONFIDENCIAL",
}


def make_request() -> Request:
    path = f"/api/contratos-digitais/view/{SENTINELS['token']}"
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": f"cpf={SENTINELS['cpf']}".encode(),
            "headers": [
                (b"authorization", SENTINELS["authorization"].encode()),
                (b"user-agent", b"sentinel-user-agent"),
            ],
            "client": ("203.0.113.10", 12345),
            "server": ("portal.example", 443),
        }
    )


class DigitalContractLoggingTests(unittest.TestCase):
    def assert_no_sentinels(self, output: str) -> None:
        for label, value in SENTINELS.items():
            with self.subTest(label=label):
                self.assertNotIn(value, output)

    def test_request_logging_omits_headers_url_and_extra_payload(self):
        request = make_request()

        with self.assertLogs("digital_contracts", level=logging.INFO) as captured:
            contract_router.log_request_details(
                request,
                "SECURITY_REGRESSION",
                {
                    "token": SENTINELS["token"],
                    "cpf": SENTINELS["cpf"],
                    "nome": SENTINELS["name"],
                    "contract_html": SENTINELS["html"],
                },
            )

        output = "\n".join(captured.output)
        self.assertIn("SECURITY_REGRESSION", output)
        self.assertIn("GET", output)
        self.assert_no_sentinels(output)
        self.assertNotIn("sentinel-user-agent", output)
        self.assertNotIn("203.0.113.10", output)

    def test_contract_response_is_preserved_but_not_logged(self):
        contract = {
            "contract_id": 99,
            "paciente_nome": SENTINELS["name"],
            "paciente_cpf": SENTINELS["cpf"],
            "contract_html": SENTINELS["html"],
        }

        with patch.object(
            contract_router.service,
            "get_contract_for_client",
            return_value=contract,
        ), self.assertLogs("digital_contracts", level=logging.INFO) as captured:
            result = contract_router.view_contract(SENTINELS["token"], make_request())

        self.assertEqual(result, contract)
        output = "\n".join(captured.output)
        self.assertIn("Contrato recuperado", output)
        self.assert_no_sentinels(output)

    def test_exception_message_is_not_copied_to_logs(self):
        with patch.object(
            contract_router.service,
            "get_contract_for_client",
            side_effect=ValueError(SENTINELS["exception"]),
        ), self.assertLogs("digital_contracts", level=logging.INFO) as captured:
            with self.assertRaises(Exception):
                contract_router.view_contract(SENTINELS["token"], make_request())

        output = "\n".join(captured.output)
        self.assertIn("ValueError", output)
        self.assert_no_sentinels(output)

    def test_runtime_sources_do_not_contain_known_sensitive_log_sinks(self):
        backend_root = Path(__file__).resolve().parents[1]
        sources = {
            "router": backend_root / "app/digital_contracts/router.py",
            "service": backend_root / "app/digital_contracts/service.py",
            "public_router": backend_root / "app/digital_contracts/public_router.py",
            "pdf_generator": backend_root / "app/services/html_contract_pdf_generator.py",
        }
        forbidden = (
            "dict(request.headers)",
            "str(request.url)",
            "token[:",
            "access_token[:",
            "Contrato recuperado: {contract}",
            "Query: {base_query}",
            "Params: {params}",
            "Contract data completo para salvar: {contract_data}",
            "{existing_contract_data}",
            "Dados encontrados: {result['paciente_nome']}",
            "dados.get('paciente_nome'",
            "{paciente_nome} - R$",
            "logging.basicConfig(",
            "FileHandler('digital_contracts.log')",
        )

        for source_name, path in sources.items():
            content = path.read_text(encoding="utf-8")
            for pattern in forbidden:
                with self.subTest(source=source_name, pattern=pattern):
                    self.assertNotIn(pattern, content)


if __name__ == "__main__":
    unittest.main()
