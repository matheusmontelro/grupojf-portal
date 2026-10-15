"""Cliente HTTP do Asaas."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from .exceptions import AsaasAPIError, AsaasConnectionError, AsaasValidationError

logger = logging.getLogger(__name__)

DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 20.0
_HTTPX_REQUEST_LOG_TEMPLATE = 'HTTP Request: %s %s "%s %d %s"'
_HTTPX_REDACTED_URL = "<redacted>"
_REMOTE_VALIDATION_CODE_ALLOWLIST = frozenset({"invalid_action"})


class _HttpxRequestUrlRedactionFilter(logging.Filter):
    """Remove a URL completa dos logs internos do HTTPX."""

    def filter(self, record: logging.LogRecord) -> bool:
        if (
            record.name == "httpx"
            and record.msg == _HTTPX_REQUEST_LOG_TEMPLATE
            and isinstance(record.args, tuple)
            and len(record.args) == 5
        ):
            method, _url, protocol, status_code, reason = record.args
            record.args = (
                method,
                _HTTPX_REDACTED_URL,
                protocol,
                status_code,
                reason,
            )
        return True


_HTTPX_REQUEST_URL_REDACTION_FILTER = _HttpxRequestUrlRedactionFilter()


def _install_httpx_request_url_redaction_filter() -> None:
    # O HTTPX registra a URL completa em INFO, inclusive query params. Usar a
    # mesma instancia torna a instalacao idempotente via logging.addFilter().
    logging.getLogger("httpx").addFilter(_HTTPX_REQUEST_URL_REDACTION_FILTER)


def _validation_error_from_response(response: httpx.Response) -> AsaasValidationError:
    """Extrai somente codigos controlados, sem reter o corpo remoto."""

    codes = []
    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = None

    if isinstance(payload, dict):
        raw_errors = payload.get("errors")
        if isinstance(raw_errors, list):
            for raw_error in raw_errors:
                if not isinstance(raw_error, dict):
                    continue
                code = raw_error.get("code")
                if not isinstance(code, str):
                    continue
                normalized_code = code.strip().lower()
                if normalized_code in _REMOTE_VALIDATION_CODE_ALLOWLIST:
                    codes.append(normalized_code)

    error = AsaasValidationError(codes or ["request_rejected"])
    error.status_code = response.status_code
    return error


class AsaasHttpClient:
    """Cliente HTTP com tratamento padrao para a API do Asaas."""

    def __init__(
        self,
        base_url: str,
        headers: Dict[str, str],
        timeout: Optional[float] = None,
        *,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        read_timeout: float = DEFAULT_READ_TIMEOUT_SECONDS,
    ):
        if timeout is not None:
            # Compatibilidade com o argumento unico usado antes do hardening.
            connect_timeout = float(timeout)
            read_timeout = float(timeout)
        if connect_timeout <= 0 or read_timeout <= 0:
            raise ValueError("Os timeouts HTTP do Asaas devem ser maiores que zero.")

        self.base_url = base_url
        self.headers = headers
        self.connect_timeout = float(connect_timeout)
        self.read_timeout = float(read_timeout)
        self.timeout = httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=self.read_timeout,
            pool=self.connect_timeout,
        )
        _install_httpx_request_url_redaction_filter()
        self.client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=self.timeout,
            follow_redirects=False,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _log_request(self, method: str, endpoint: str, **kwargs):
        # Endpoint, query params e payload podem carregar documento/PII.
        logger.debug("Asaas request. method=%s", method)

    def _log_response(self, response: httpx.Response):
        # Nunca registrar o corpo: respostas de customer contem dados pessoais.
        logger.debug("Asaas response. status=%s", response.status_code)

    def close(self) -> None:
        """Fecha o pool HTTP e seus sockets."""
        self.client.close()

    def request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        self._log_request(method, endpoint, **kwargs)
        try:
            response = self.client.request(method, endpoint, **kwargs)
        except httpx.RequestError as exc:
            logger.warning(
                "Falha de comunicacao com o Asaas. error_type=%s",
                type(exc).__name__,
            )
            raise AsaasConnectionError("Falha de comunicacao com a API do Asaas") from None

        self._log_response(response)

        if response.is_error:
            if response.status_code in {400, 422}:
                raise _validation_error_from_response(response)

            raise AsaasAPIError(
                status_code=response.status_code,
                response_body=None,
                detail="request_failed",
            )

        return response

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return self.request("GET", endpoint, params=params)

    def post(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return self.request("POST", endpoint, json=json)

    def put(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return self.request("PUT", endpoint, json=json)

    def delete(self, endpoint: str) -> httpx.Response:
        return self.request("DELETE", endpoint)
