"""SDK principal do Asaas."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Iterable, Optional

from .customer_manager import CustomerManager
from .environment import AsaasConfig
from .http_client import AsaasHttpClient
from .notification_manager import NotificationManager
from .payment_manager import PaymentManager
from .sdk_utils import (
    build_callback,
    cents_to_decimal,
    format_due_date,
    normalize_billing_type,
    normalize_money,
    transform_splits_to_asaas,
)

logger = logging.getLogger(__name__)


class AsaasSDK:
    """SDK para cobrancas avulsas e checkout no Asaas."""

    def __init__(self, config: AsaasConfig):
        self.config = config
        self.http_client = AsaasHttpClient(
            base_url=config.base_url,
            headers=config.headers,
        )
        self.customer_manager = CustomerManager(self.http_client)
        self.notification_manager = NotificationManager(self.http_client)
        self.payment_manager = PaymentManager(self.http_client)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self) -> None:
        """Fecha os recursos HTTP usados pelo SDK."""
        self.http_client.close()

    def create_complete_payment(
        self,
        customer_data: Dict[str, Any],
        amount_cents: Optional[int] = None,
        value: Optional[Any] = None,
        billing_type: str = "PIX",
        due_date: Optional[Any] = None,
        description: Optional[str] = None,
        external_reference: Optional[str] = None,
        splits: Optional[Iterable[Dict[str, Any]]] = None,
        success_url: Optional[str] = None,
        auto_redirect: bool = False,
        installments: int = 1,
        total_value: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        customer = self.customer_manager.create_or_get_customer(customer_data)
        customer_id = customer.get("id")
        if not customer_id:
            raise ValueError("Nao foi possivel obter customer id do Asaas")

        billing_type = normalize_billing_type(billing_type)
        total_amount = normalize_money(value) if value is not None else cents_to_decimal(amount_cents or 0)

        payload: Dict[str, Any] = {
            "customer": customer_id,
            "billingType": billing_type,
            "dueDate": format_due_date(due_date),
        }

        if installments and installments > 1:
            payload["installmentCount"] = installments
            payload["installmentValue"] = float(
                (normalize_money(total_value) if total_value is not None else total_amount / installments).quantize(Decimal("0.01"))
            )
            payload["totalValue"] = float(normalize_money(total_value) if total_value is not None else total_amount)
        else:
            payload["value"] = float(total_amount)

        if description:
            payload["description"] = description
        if external_reference:
            payload["externalReference"] = external_reference
        if metadata:
            payload["externalReference"] = payload.get("externalReference") or str(metadata)

        callback = build_callback(success_url=success_url, auto_redirect=auto_redirect)
        if callback:
            payload["callback"] = callback

        transformed_splits = transform_splits_to_asaas(splits)
        if transformed_splits:
            payload["split"] = transformed_splits

        logger.info(
            "Criando cobranca no Asaas. customer=%s billingType=%s installments=%s",
            customer_id,
            billing_type,
            installments,
        )
        result = self.payment_manager.create_payment(payload)
        logger.info("Cobranca criada no Asaas. id=%s", result.get("id"))
        return result

    def get_checkout_url(self, payment_id: str) -> Optional[str]:
        payment = self.payment_manager.get_payment(payment_id)
        return payment.get("invoiceUrl")

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        return self.payment_manager.get_payment(payment_id)

    def delete_payment(self, payment_id: str) -> Dict[str, Any]:
        return self.payment_manager.delete_payment(payment_id)

    def restore_payment(self, payment_id: str) -> Dict[str, Any]:
        return self.payment_manager.restore_payment(payment_id)

    def get_pix_qr_code(self, payment_id: str) -> Dict[str, Any]:
        return self.payment_manager.get_pix_qr_code(payment_id)
