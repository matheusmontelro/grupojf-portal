import unittest

from app.anamnese_digital.pdf_generator import AnamnesePDFGenerator


class AnamnesePDFGeneratorTests(unittest.TestCase):
    def test_generate_returns_valid_pdf_for_synthetic_payload(self):
        payload = {
            "status": "assinado",
            "dados_anamnese": {
                "dados_identificacao": {
                    "nome": "Paciente <Teste>",
                    "cpf": "000.000.000-00",
                    "data_nascimento": "2000-01-01",
                    "telefone": "(00) 00000-0000",
                },
                "saude_geral": {
                    "q1": "nao",
                    "q2": "sim",
                    "q2_qual": "Resposta sintética & segura",
                    "doencas": ["nenhuma"],
                },
                "saude_bucal": {
                    "q12": "sim",
                    "q15": "frio",
                },
            },
            "observacoes": "Conteúdo exclusivamente sintético.",
        }

        pdf = AnamnesePDFGenerator().generate(payload)

        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", pdf[-1024:])
        self.assertGreater(len(pdf), 1000)

    def test_invalid_signature_image_is_ignored_safely(self):
        generator = AnamnesePDFGenerator()

        with self.assertLogs("app.anamnese_digital.pdf_generator", level="ERROR"):
            image = generator._process_base64_image("conteudo-base64-invalido")

        self.assertIsNone(image)


if __name__ == "__main__":
    unittest.main()
