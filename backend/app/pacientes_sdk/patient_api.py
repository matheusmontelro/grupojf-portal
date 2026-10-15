"""Cliente de pacientes da Delta/BemPaggo."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from requests.exceptions import RequestException

from .environment import Environment
from .exceptions import DeltaAPIError, DeltaConnectionError, DeltaValidationError
from .http_client import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_READ_TIMEOUT_SECONDS,
    HttpClientFactory,
)

logger = logging.getLogger(__name__)

_REMOTE_CUSTOMER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def _only_digits(value: Any) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def normalize_delta_customer_id(value: Any) -> str:
    """Normaliza um ID tecnico sem permitir que ele altere o caminho HTTP."""
    if isinstance(value, bool):
        raise DeltaValidationError(["customer_id_invalid"])
    candidate = str(value or "").strip()
    if not _REMOTE_CUSTOMER_ID_PATTERN.fullmatch(candidate):
        raise DeltaValidationError(["customer_id_invalid"])
    return candidate


def _customer_mapping(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    for key in ("data", "customer"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
    return payload


def extract_delta_customer_id(payload: Any) -> Optional[str]:
    """Extrai somente formatos conhecidos e valida o identificador remoto."""
    customer = _customer_mapping(payload)
    if customer is None:
        return None
    for key in ("id", "customerId", "customer_id"):
        value = customer.get(key)
        if value is not None and str(value).strip():
            try:
                return normalize_delta_customer_id(value)
            except DeltaValidationError:
                raise DeltaAPIError(
                    502,
                    response_body=None,
                    detail="Resposta invalida da API",
                ) from None
    return None


class PatientAPI:
    """API client para gerenciar pacientes na Delta/BemPaggo."""

    def __init__(
        self,
        api_token,
        seller_id,
        environment="sandbox",
        *,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        read_timeout: float = DEFAULT_READ_TIMEOUT_SECONDS,
    ):
        self.api_token = api_token
        self.seller_id = seller_id
        self.base_url = Environment.get_base_url(environment)
        self.http_client = HttpClientFactory.create(
            api_token,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
        self.environment = environment
        logger.debug("PatientAPI inicializada. environment=%s", environment)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self) -> None:
        """Fecha sockets mantidos pela sessao HTTP."""
        self.http_client.close()

    @staticmethod
    def _success_payload(response) -> Dict[str, Any]:
        try:
            result = response.json()
        except ValueError:
            logger.warning("Delta retornou sucesso sem JSON valido.")
            result = {"success": True}

        if not isinstance(result, dict):
            result = {"success": True, "data": result}

        customer_id = extract_delta_customer_id(result)
        if customer_id is None:
            customer_id = PatientAPI._customer_id_from_headers(response)
        if customer_id is not None:
            result = dict(result)
            result["id"] = customer_id
        return result

    @staticmethod
    def _customer_id_from_headers(response) -> Optional[str]:
        headers = getattr(response, "headers", {}) or {}
        content_id = headers.get("content-id") or headers.get("Content-Id")
        if content_id is not None and str(content_id).strip():
            try:
                return normalize_delta_customer_id(content_id)
            except DeltaValidationError:
                raise DeltaAPIError(
                    502,
                    response_body=None,
                    detail="Resposta invalida da API",
                ) from None

        location = headers.get("location") or headers.get("Location")
        if location is None or not str(location).strip():
            return None
        location_path = urlsplit(str(location).strip()).path.rstrip("/")
        candidate = location_path.rsplit("/", 1)[-1] if location_path else ""
        try:
            return normalize_delta_customer_id(candidate)
        except DeltaValidationError:
            raise DeltaAPIError(
                502,
                response_body=None,
                detail="Resposta invalida da API",
            ) from None

    @staticmethod
    def extract_customer_id(payload: Any) -> Optional[str]:
        """API publica para extrair o ID tecnico de um resultado de sync."""
        return extract_delta_customer_id(payload)

    @staticmethod
    def _raise_for_write_error(response, operation: str) -> None:
        if response.status_code in {400, 422}:
            logger.warning(
                "Delta rejeitou dados de paciente. operation=%s status=%s",
                operation,
                response.status_code,
            )
            raise DeltaValidationError(["request_rejected"])

        logger.warning(
            "Delta retornou erro. operation=%s status=%s",
            operation,
            response.status_code,
        )
        raise DeltaAPIError(
            response.status_code,
            response_body=None,
            detail=f"Erro ao {operation} paciente",
        )

    @staticmethod
    def _connection_error(operation: str, exc: RequestException) -> DeltaConnectionError:
        logger.warning(
            "Falha de comunicacao com a Delta. operation=%s error_type=%s",
            operation,
            type(exc).__name__,
        )
        return DeltaConnectionError("Falha de comunicacao com a API Delta")

    def create_patient(self, patient_data):
        """Cria um paciente.

        Este metodo legado permanece disponivel. Fluxos idempotentes devem usar
        :meth:`upsert_patient`, que somente chama a criacao depois de uma
        ausencia confirmada pela Delta.
        """
        if not _only_digits(patient_data.get("document")):
            logger.warning("Documento obrigatorio ausente para criacao na Delta.")
            raise DeltaValidationError(["document_required"])

        endpoint = f"{self.base_url}/customers"
        logger.info("Criando paciente na Delta.")

        try:
            response = self.http_client.post(endpoint, json=patient_data)
        except RequestException as exc:
            raise self._connection_error("create", exc) from None

        logger.debug("Resposta da Delta. operation=create status=%s", response.status_code)
        if response.status_code in {200, 201}:
            logger.info("Paciente criado na Delta.")
            return self._success_payload(response)

        self._raise_for_write_error(response, "criar")

    def update_patient(self, document, patient_data):
        """Atualiza os dados de um paciente existente."""
        clean_document = _only_digits(document)
        if not clean_document:
            raise DeltaValidationError(["document_required"])

        endpoint = f"{self.base_url}/customers/document/{clean_document}"
        logger.info("Atualizando paciente na Delta.")

        try:
            response = self.http_client.put(endpoint, json=patient_data)
        except RequestException as exc:
            raise self._connection_error("update", exc) from None

        logger.debug("Resposta da Delta. operation=update status=%s", response.status_code)
        if response.status_code == 200:
            logger.info("Paciente atualizado na Delta.")
            return self._success_payload(response)

        if response.status_code == 404:
            logger.info("Paciente nao localizado na Delta durante atualizacao.")
            raise DeltaAPIError(
                response.status_code,
                response_body=None,
                detail="Paciente nao encontrado",
            )

        self._raise_for_write_error(response, "atualizar")

    @staticmethod
    def _lookup_payload(response) -> Dict[str, Any]:
        try:
            result = response.json()
        except ValueError:
            logger.warning("Delta retornou JSON invalido na consulta de paciente.")
            raise DeltaAPIError(
                502,
                response_body=None,
                detail="Resposta invalida da API",
            ) from None

        customer = _customer_mapping(result)
        recognized_fields = ("id", "customerId", "customer_id", "document", "name")
        if (
            not isinstance(result, dict)
            or not customer
            or not any(
                str(customer.get(field) or "").strip()
                for field in recognized_fields
            )
        ):
            raise DeltaAPIError(
                502,
                response_body=None,
                detail="Resposta invalida da API",
            )
        return result

    def get_patient_by_id(self, customer_id: Any) -> Optional[Dict[str, Any]]:
        """Busca um customer pelo ID tecnico; retorna ``None`` apenas no 404."""
        normalized_customer_id = normalize_delta_customer_id(customer_id)
        endpoint = f"{self.base_url}/customers/{normalized_customer_id}"
        logger.info("Consultando paciente na Delta por identificador tecnico.")

        try:
            response = self.http_client.get(endpoint)
        except RequestException as exc:
            raise self._connection_error("lookup_by_id", exc) from None

        logger.debug(
            "Resposta da Delta. operation=lookup_by_id status=%s",
            response.status_code,
        )
        if response.status_code == 200:
            result = self._lookup_payload(response)
            returned_id = extract_delta_customer_id(result)
            if returned_id is not None and returned_id != normalized_customer_id:
                raise DeltaAPIError(
                    502,
                    response_body=None,
                    detail="Resposta invalida da API",
                )
            logger.info("Paciente localizado na Delta por identificador tecnico.")
            return result

        if response.status_code == 404:
            logger.info("Paciente nao localizado na Delta por identificador tecnico.")
            return None

        logger.warning(
            "Delta retornou erro na consulta por identificador. status=%s",
            response.status_code,
        )
        raise DeltaAPIError(
            response.status_code,
            response_body=None,
            detail="Erro ao consultar paciente",
        )

    def get_patient_by_document(self, document):
        """Busca um paciente; retorna ``None`` somente apos ausencia confirmada."""
        clean_document = _only_digits(document)
        if not clean_document:
            raise DeltaValidationError(["document_required"])

        endpoint = f"{self.base_url}/customers/document/{clean_document}"
        logger.info("Consultando paciente na Delta.")

        try:
            response = self.http_client.get(endpoint)
        except RequestException as exc:
            raise self._connection_error("lookup", exc) from None

        logger.debug("Resposta da Delta. operation=lookup status=%s", response.status_code)
        if response.status_code == 200:
            result = self._lookup_payload(response)
            self._validate_lookup_document(result, clean_document)
            logger.info("Paciente localizado na Delta.")
            return result

        if response.status_code == 404:
            logger.info("Paciente nao localizado na Delta.")
            return None

        if response.status_code == 422:
            logger.info(
                "Consulta Delta inconclusiva; confirmando existencia do paciente."
            )
            if not self.check_patient_exists(clean_document):
                logger.info("Paciente nao localizado na Delta apos confirmacao.")
                return None

            logger.warning(
                "Delta confirmou paciente existente sem retornar dados na consulta."
            )
            raise DeltaAPIError(
                response.status_code,
                response_body=None,
                detail="Erro ao consultar paciente",
            )

        logger.warning("Delta retornou erro na consulta. status=%s", response.status_code)
        raise DeltaAPIError(
            response.status_code,
            response_body=None,
            detail="Erro ao consultar paciente",
        )

    def _recover_ambiguous_create(
        self,
        document: str,
        original_error: Exception,
    ) -> Dict[str, Any]:
        """Confirma se uma criacao ambigua chegou ao provedor remoto."""
        try:
            recovered = self.get_patient_by_document(document)
        except Exception:
            raise original_error from None

        if recovered is not None:
            self._validate_lookup_document(recovered, document)
            logger.info("Criacao Delta recuperada por consulta idempotente.")
            return recovered
        raise original_error from None

    @staticmethod
    def _result_with_customer_id(
        result: Dict[str, Any],
        expected_customer_id: str,
    ) -> Dict[str, Any]:
        returned_id = extract_delta_customer_id(result)
        if returned_id is not None and returned_id != expected_customer_id:
            raise DeltaAPIError(
                502,
                response_body=None,
                detail="Resposta invalida da API",
            )
        normalized_result = dict(result)
        normalized_result["id"] = expected_customer_id
        return normalized_result

    @staticmethod
    def _remote_document(customer: Dict[str, Any]) -> str:
        customer_data = _customer_mapping(customer)
        document = _only_digits(customer_data.get("document") if customer_data else None)
        if len(document) not in {11, 14}:
            raise DeltaAPIError(
                502,
                response_body=None,
                detail="Resposta invalida da API",
            )
        return document

    @staticmethod
    def _validate_lookup_document(
        customer: Dict[str, Any],
        requested_document: str,
    ) -> str:
        remote_document = PatientAPI._remote_document(customer)
        if remote_document != _only_digits(requested_document):
            raise DeltaAPIError(
                502,
                response_body=None,
                detail="Resposta invalida da API",
            )
        return remote_document

    def _finalize_created_patient(
        self,
        document: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        customer_id = extract_delta_customer_id(result)
        if customer_id is not None:
            return self._result_with_customer_id(result, customer_id)

        recovered = self.get_patient_by_document(document)
        if recovered is None:
            raise DeltaAPIError(
                502,
                response_body=None,
                detail="Resposta invalida da API",
            )
        self._validate_lookup_document(recovered, document)
        recovered_id = extract_delta_customer_id(recovered)
        if recovered_id is None:
            raise DeltaAPIError(
                502,
                response_body=None,
                detail="Resposta invalida da API",
            )
        return self._result_with_customer_id(recovered, recovered_id)

    def sync_patient(
        self,
        patient_data: Dict[str, Any],
        *,
        known_customer_id: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Sincroniza um paciente e sempre retorna seu ID tecnico remoto.

        A criacao ocorre apenas quando ``get_patient_by_document`` devolve
        ``None``, condicao reservada ao HTTP 404 ou a confirmacao HTTP 204 do
        endpoint ``/check``. Se a resposta da criacao for ambigua, uma nova
        consulta recupera uma criacao que tenha sido efetivada.

        Quando ``known_customer_id`` e informado, o customer e consultado pelo
        ID. O UPDATE usa o documento devolvido pela Delta, portanto continua
        funcionando quando o CPF/CNPJ do payload local foi alterado.
        """
        document = _only_digits(patient_data.get("document"))
        if not document:
            raise DeltaValidationError(["document_required"])

        if known_customer_id is not None:
            customer_id = normalize_delta_customer_id(known_customer_id)
            known_customer = self.get_patient_by_id(customer_id)
            if known_customer is None:
                # Um vinculo orfao nao autoriza criar outro customer.
                raise DeltaAPIError(
                    404,
                    response_body=None,
                    detail="Paciente nao encontrado",
                )
            previous_document = self._remote_document(known_customer)
            updated = self.update_patient(previous_document, patient_data)
            return self._result_with_customer_id(updated, customer_id)

        existing = self.get_patient_by_document(document)
        if existing is not None:
            self._validate_lookup_document(existing, document)
            customer_id = extract_delta_customer_id(existing)
            if customer_id is None:
                raise DeltaAPIError(
                    502,
                    response_body=None,
                    detail="Resposta invalida da API",
                )
            updated = self.update_patient(document, patient_data)
            return self._result_with_customer_id(updated, customer_id)

        try:
            created = self.create_patient(patient_data)
        except DeltaConnectionError as exc:
            created = self._recover_ambiguous_create(document, exc)
        except DeltaAPIError as exc:
            if exc.status_code in {408, 409, 429} or exc.status_code >= 500:
                created = self._recover_ambiguous_create(document, exc)
            else:
                raise
        return self._finalize_created_patient(document, created)

    def upsert_patient(
        self,
        patient_data: Dict[str, Any],
        known_customer_id: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Alias retrocompativel do fluxo idempotente de sincronizacao."""
        return self.sync_patient(
            patient_data,
            known_customer_id=known_customer_id,
        )

    def check_patient_exists(self, document):
        """Confirma existencia pelo endpoint sem corpo da Delta."""
        clean_document = _only_digits(document)
        if not clean_document:
            raise DeltaValidationError(["document_required"])

        endpoint = f"{self.base_url}/customers/document/{clean_document}/check"
        logger.info("Confirmando existencia de paciente na Delta.")

        try:
            response = self.http_client.get(endpoint)
        except RequestException as exc:
            raise self._connection_error("check", exc) from None

        logger.debug("Resposta da Delta. operation=check status=%s", response.status_code)
        if response.status_code == 200:
            logger.info("Existencia de paciente confirmada na Delta.")
            return True

        if response.status_code == 204:
            logger.info("Ausencia de paciente confirmada na Delta.")
            return False

        logger.warning(
            "Delta retornou erro na confirmacao de paciente. status=%s",
            response.status_code,
        )
        raise DeltaAPIError(
            response.status_code,
            response_body=None,
            detail="Erro ao consultar paciente",
        )
