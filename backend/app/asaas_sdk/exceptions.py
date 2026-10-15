"""Excecoes da integracao com Asaas."""

import re


_SAFE_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")


def _controlled_error_codes(errors):
    if isinstance(errors, str):
        errors = [errors]
    if not isinstance(errors, (list, tuple, set)):
        return ["validation_error"]

    controlled = []
    for error in errors:
        candidate = error.get("code") if isinstance(error, dict) else error
        candidate = str(candidate or "").strip().lower()
        if _SAFE_ERROR_CODE.fullmatch(candidate) and not re.search(r"\d{4,}", candidate):
            controlled.append(candidate)
    return list(dict.fromkeys(controlled)) or ["validation_error"]


class AsaasIntegrationError(Exception):
    """Excecao base da integracao com Asaas."""


class AsaasAPIError(AsaasIntegrationError):
    """Erro retornado pela API do Asaas."""

    def __init__(self, status_code, response_body=None, detail=None):
        self.status_code = status_code
        # O corpo remoto pode conter CPF, nome e endereco. O atributo continua
        # existindo para compatibilidade, mas nunca transporta esse conteudo.
        self.response_body = None
        candidate = str(detail or "").strip().lower()
        self.detail = (
            candidate
            if _SAFE_ERROR_CODE.fullmatch(candidate)
            and not re.search(r"\d{4,}", candidate)
            else "request_failed"
        )
        message = f"Asaas API error {status_code}: {self.detail}"
        super().__init__(message)


class AsaasConnectionError(AsaasIntegrationError):
    """Erro de comunicacao com o Asaas."""


class AsaasConfigurationError(AsaasIntegrationError):
    """Erro de configuracao da integracao."""


class AsaasCustomerConflictError(AsaasIntegrationError):
    """Mais de um customer, ou um customer incompativel, foi localizado."""

    _MESSAGES = {
        "multiple_matches": "Mais de um cliente Asaas corresponde ao identificador.",
        "document_mismatch": "O cliente Asaas localizado possui documento incompativel.",
        "external_reference_mismatch": (
            "O cliente Asaas localizado pertence a outra referencia externa."
        ),
        "known_customer_missing": (
            "O cliente Asaas vinculado nao existe mais e exige conciliacao manual."
        ),
    }

    def __init__(self, reason: str = "multiple_matches"):
        self.reason = reason if reason in self._MESSAGES else "multiple_matches"
        super().__init__(self._MESSAGES[self.reason])


class AsaasValidationError(AsaasIntegrationError):
    """Erro de validacao de dados enviados ao Asaas."""

    def __init__(self, errors):
        self.errors = _controlled_error_codes(errors)
        super().__init__("Asaas request validation failed")
