"""Gerenciador de cobrancas do Asaas."""

from __future__ import annotations

from typing import Any, Dict, List

from .http_client import AsaasHttpClient


class PaymentManager:
    """Operacoes relacionadas a pagamentos/cobrancas."""

    def __init__(self, http_client: AsaasHttpClient):
        self.http_client = http_client

    def create_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.http_client.post("/payments", json=payment_data)
        return response.json()

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        response = self.http_client.get(f"/payments/{payment_id}")
        return response.json()

    def list_payments(self, **filters) -> List[Dict[str, Any]]:
        response = self.http_client.get("/payments", params={k: v for k, v in filters.items() if v is not None})
        return response.json().get("data", [])

    def delete_payment(self, payment_id: str) -> Dict[str, Any]:
        response = self.http_client.delete(f"/payments/{payment_id}")
        return response.json() if response.text else {"deleted": True}

    def restore_payment(self, payment_id: str) -> Dict[str, Any]:
        response = self.http_client.post(f"/payments/{payment_id}/restore")
        return response.json() if response.text else {"restored": True}

    def get_pix_qr_code(self, payment_id: str) -> Dict[str, Any]:
        response = self.http_client.get(f"/payments/{payment_id}/pixQrCode")
        return response.json()
