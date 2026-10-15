# app/patients_sdk/exceptions.py

import re


_SAFE_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
_SAFE_API_DETAILS = {
    "Erro remoto da API Delta",
    "Erro ao criar paciente",
    "Erro ao atualizar paciente",
    "Paciente nao encontrado",
    "Resposta invalida da API",
    "Erro ao consultar paciente",
}


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


class DeltaIntegrationError(Exception):
    """
    Exceção base para erros na integração com a API Delta.
    """
    pass


class DeltaAPIError(DeltaIntegrationError):
    """
    Exceção para erros retornados pela API Delta.
    """
    def __init__(self, status_code, response_body=None, detail=None):
        self.status_code = status_code
        # Mantido por compatibilidade com consumidores antigos, sem reter o
        # corpo remoto: ele pode conter documento e outros dados pessoais.
        self.response_body = None
        self.detail = (
            detail
            if isinstance(detail, str) and detail in _SAFE_API_DETAILS
            else "Erro remoto da API Delta"
        )

        message = f"Delta API error {status_code}: {self.detail}"
        super().__init__(message)


class DeltaConnectionError(DeltaIntegrationError):
    """
    Exceção para erros de conexão com a API Delta.
    """
    pass


class DeltaConfigurationError(DeltaIntegrationError):
    """
    Exceção para erros de configuração (token inválido, etc).
    """
    pass


class DeltaValidationError(DeltaIntegrationError):
    """
    Exceção para erros de validação de dados.
    """
    def __init__(self, errors):
        self.errors = _controlled_error_codes(errors)
        super().__init__("Delta request validation failed")
