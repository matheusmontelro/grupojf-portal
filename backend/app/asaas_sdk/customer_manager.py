"""Gerenciador de clientes no Asaas."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .exceptions import (
    AsaasAPIError,
    AsaasConnectionError,
    AsaasCustomerConflictError,
    AsaasValidationError,
)
from .http_client import AsaasHttpClient
from .sdk_utils import build_customer_payload

logger = logging.getLogger(__name__)

_CUSTOMER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def _only_digits(value: Any) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


class CustomerManager:
    """Operacoes relacionadas a clientes no Asaas."""

    def __init__(self, http_client: AsaasHttpClient):
        self.http_client = http_client

    @staticmethod
    def _decode_page(response) -> Dict[str, Any]:
        try:
            page = response.json()
        except ValueError:
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_response",
            ) from None
        if (
            not isinstance(page, dict)
            or "data" not in page
            or not isinstance(page["data"], list)
            or "totalCount" not in page
        ):
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_response",
            )
        total_count = page["totalCount"]
        if isinstance(total_count, bool) or not isinstance(total_count, int):
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_response",
            )
        if total_count < 0 or total_count < len(page["data"]):
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_response",
            )
        return page

    def create_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = build_customer_payload(customer_data)
        response = self.http_client.post("/customers", json=payload)
        try:
            customer = response.json()
        except ValueError:
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_response",
            ) from None
        normalized_customer = self._normalize_remote_customer(customer)
        logger.info("Cliente criado no Asaas.")
        return normalized_customer

    def update_customer(
        self,
        customer_id: str,
        customer_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Atualiza um customer conhecido sem expor o ID em endpoint/log invalido."""
        normalized_id = self._normalize_customer_id(customer_id)
        payload = build_customer_payload(customer_data)
        response = self.http_client.put(f"/customers/{normalized_id}", json=payload)
        try:
            customer = response.json()
        except ValueError:
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_response",
            ) from None
        normalized_customer = self._normalize_remote_customer(customer)
        returned_id = normalized_customer["id"]
        if returned_id != normalized_id:
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_customer_response",
            )
        logger.info("Cliente atualizado no Asaas.")
        return normalized_customer

    def list_customers(self, **filters) -> List[Dict[str, Any]]:
        response = self.http_client.get(
            "/customers",
            params={key: value for key, value in filters.items() if value is not None},
        )
        return self._decode_page(response).get("data", [])

    def _find_single_customer(self, **filters) -> Optional[Dict[str, Any]]:
        response = self.http_client.get(
            "/customers",
            params={key: value for key, value in filters.items() if value is not None},
        )
        page = self._decode_page(response)
        customers = page["data"]
        total_count = page["totalCount"]
        if total_count != len(customers):
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_response",
            )
        if total_count > 1:
            raise AsaasCustomerConflictError("multiple_matches")
        if total_count == 0:
            return None
        return self._normalize_remote_customer(customers[0])

    def find_customer_by_external_reference(
        self,
        external_reference: str,
    ) -> Optional[Dict[str, Any]]:
        normalized = str(external_reference or "").strip()
        if not normalized:
            return None
        customer = self._find_single_customer(externalReference=normalized)
        if customer is not None:
            self._validate_remote_external_reference(customer, normalized)
        return customer

    def find_customer_by_document(self, document: str) -> Optional[Dict[str, Any]]:
        clean_document = _only_digits(document)
        if not clean_document:
            return None
        customer = self._find_single_customer(cpfCnpj=clean_document)
        if customer is not None:
            self._validate_remote_document(customer, clean_document)
        return customer

    @staticmethod
    def _validate_remote_document(
        customer: Dict[str, Any],
        requested_document: str,
    ) -> None:
        requested_document = _only_digits(requested_document)
        remote_document = _only_digits(customer.get("cpfCnpj"))
        if len(remote_document) not in {11, 14}:
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_customer_response",
            )
        if remote_document != requested_document:
            raise AsaasCustomerConflictError("document_mismatch")

    @staticmethod
    def _validate_remote_external_reference(
        customer: Dict[str, Any],
        requested_external_reference: str,
    ) -> None:
        raw_reference = customer.get("externalReference")
        if not isinstance(raw_reference, str) or not raw_reference.strip():
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_customer_response",
            )
        remote_reference = raw_reference.strip()
        if remote_reference != requested_external_reference:
            raise AsaasCustomerConflictError("external_reference_mismatch")

    @staticmethod
    def _validate_assignable_external_reference(
        customer: Dict[str, Any],
        requested_external_reference: str,
    ) -> None:
        """Aceita referencia ausente em customer legado, mas nunca divergente."""
        raw_reference = customer.get("externalReference")
        if raw_reference is None:
            return
        if not isinstance(raw_reference, str):
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_customer_response",
            )
        remote_reference = raw_reference.strip()
        if not remote_reference:
            return
        if remote_reference != requested_external_reference:
            raise AsaasCustomerConflictError("external_reference_mismatch")

    @staticmethod
    def _validate_match(
        customer: Dict[str, Any],
        *,
        requested_document: str,
        requested_external_reference: str,
    ) -> None:
        CustomerManager._validate_remote_document(customer, requested_document)
        if requested_external_reference:
            CustomerManager._validate_assignable_external_reference(
                customer,
                requested_external_reference,
            )

    def _find_existing_customer(
        self,
        customer_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        return self.find_existing_customer(customer_data)

    def find_existing_customer(
        self,
        customer_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Localiza uma identidade remota sem criar ou atualizar customer."""
        document = customer_data.get("document") or customer_data.get("cpfCnpj")
        external_reference = str(
            customer_data.get("externalReference")
            or customer_data.get("external_reference")
            or ""
        ).strip()

        if external_reference:
            existing = self.find_customer_by_external_reference(external_reference)
            if existing:
                # A referencia deterministica e a identidade primaria do
                # Grupo JF no Asaas. O documento pode ter mudado localmente
                # depois de um POST cuja resposta se perdeu; o worker reserva
                # este ID e faz PUT no mesmo customer.
                return existing

        existing = self.find_customer_by_document(document)
        if existing:
            self._validate_match(
                existing,
                requested_document=document,
                requested_external_reference=external_reference,
            )
        return existing

    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        normalized_id = self._normalize_customer_id(customer_id)
        response = self.http_client.get(f"/customers/{normalized_id}")
        try:
            customer = response.json()
        except ValueError:
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_response",
            ) from None
        normalized_customer = self._normalize_remote_customer(customer)
        returned_id = normalized_customer["id"]
        if returned_id != normalized_id:
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_customer_response",
            )
        return normalized_customer

    @staticmethod
    def _normalize_customer_id(customer_id: str) -> str:
        if isinstance(customer_id, bool):
            raise AsaasValidationError(["customer_id_invalid"])
        normalized = str(customer_id or "").strip()
        if not _CUSTOMER_ID_PATTERN.fullmatch(normalized):
            raise AsaasValidationError(["customer_id_invalid"])
        return normalized

    @staticmethod
    def _normalize_remote_customer(customer: Any) -> Dict[str, Any]:
        if (
            not isinstance(customer, dict)
            or not isinstance(customer.get("id"), str)
            or not customer["id"].strip()
        ):
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_customer_response",
            )
        try:
            normalized_id = CustomerManager._normalize_customer_id(customer["id"])
        except AsaasValidationError:
            raise AsaasAPIError(
                status_code=502,
                response_body=None,
                detail="invalid_customer_response",
            ) from None
        normalized_customer = dict(customer)
        normalized_customer["id"] = normalized_id
        return normalized_customer

    @staticmethod
    def _validate_known_reference(
        customer: Dict[str, Any],
        requested_external_reference: str,
    ) -> None:
        if requested_external_reference:
            CustomerManager._validate_assignable_external_reference(
                customer,
                requested_external_reference,
            )

    def sync_customer(
        self,
        customer_data: Dict[str, Any],
        *,
        known_customer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cria ou atualiza o customer preservando a identidade remota.

        O ID persistido tem precedencia e permite alterar CPF/CNPJ sem criar um
        segundo customer. Sem ID, a referencia externa estavel precede a busca
        por documento.
        """
        document = customer_data.get("document") or customer_data.get("cpfCnpj")
        external_reference = str(
            customer_data.get("externalReference")
            or customer_data.get("external_reference")
            or ""
        ).strip()

        if known_customer_id:
            try:
                known_customer = self.get_customer(known_customer_id)
            except AsaasAPIError as exc:
                if exc.status_code == 404:
                    raise AsaasCustomerConflictError("known_customer_missing") from None
                raise
            else:
                self._validate_known_reference(known_customer, external_reference)
                return self.update_customer(known_customer_id, customer_data)

        if external_reference:
            existing = self.find_customer_by_external_reference(external_reference)
            if existing:
                self._validate_known_reference(existing, external_reference)
                return self.update_customer(existing.get("id"), customer_data)

        existing = self.find_customer_by_document(document)
        if existing:
            self._validate_match(
                existing,
                requested_document=document,
                requested_external_reference=external_reference,
            )
            return self.update_customer(existing.get("id"), customer_data)

        return self.create_customer(customer_data)

    def _recover_customer_after_create(
        self,
        customer_data: Dict[str, Any],
        original_error: Exception,
    ) -> Dict[str, Any]:
        try:
            recovered = self._find_existing_customer(customer_data)
        except AsaasCustomerConflictError:
            raise
        except Exception:
            raise original_error from None
        if recovered:
            logger.info("Criacao Asaas recuperada por consulta idempotente.")
            return recovered
        raise original_error from None

    def create_or_get_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Busca por externalReference, depois CPF, antes de criar.

        A segunda busca depois de uma falha ambigua recupera o caso em que o
        Asaas persistiu o customer, mas a resposta se perdeu por timeout/crash.
        """
        existing = self._find_existing_customer(customer_data)
        if existing:
            logger.info("Cliente localizado no Asaas.")
            return existing

        try:
            return self.create_customer(customer_data)
        except AsaasConnectionError as exc:
            return self._recover_customer_after_create(customer_data, exc)
        except AsaasAPIError as exc:
            if exc.status_code in {408, 409, 429} or exc.status_code >= 500:
                return self._recover_customer_after_create(customer_data, exc)
            raise
