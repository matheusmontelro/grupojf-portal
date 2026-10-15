# app/users_sdk/exceptions.py

class BempaggoIntegrationError(Exception):
    """
    Exceção base para erros na integração com a API da BemPaggo.
    """
    pass


class BempaggoAPIError(BempaggoIntegrationError):
    """
    Exceção para erros retornados pela API da BemPaggo.
    """
    def __init__(self, status_code, response_body, detail=None):
        self.status_code = status_code
        self.response_body = response_body
        self.detail = detail
        
        message = f"BemPaggo API error {status_code}: {detail or response_body}"
        super().__init__(message)


class BempaggoConnectionError(BempaggoIntegrationError):
    """
    Exceção para erros de conexão com a API da BemPaggo.
    """
    pass


class BempaggoConfigurationError(BempaggoIntegrationError):
    """
    Exceção para erros de configuração (token inválido, etc).
    """
    pass


class BempaggoValidationError(BempaggoIntegrationError):
    """
    Exceção para erros de validação de dados.
    """
    def __init__(self, errors):
        self.errors = errors
        message = f"Validation errors: {errors}"
        super().__init__(message)