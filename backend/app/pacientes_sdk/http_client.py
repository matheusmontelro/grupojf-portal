# app/patients_sdk/http_client.py

from __future__ import annotations

from typing import Tuple

import requests


DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 20.0


class TimeoutSession(requests.Session):
    """Session que aplica timeouts separados em todas as requisicoes."""

    def __init__(self, timeout: Tuple[float, float]):
        super().__init__()
        self._default_timeout = timeout

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self._default_timeout)
        return super().request(method, url, **kwargs)

class HttpClientFactory:
    """
    Fábrica para criar clientes HTTP com configuração padrão.
    """

    @staticmethod
    def create(
        api_token,
        *,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        read_timeout: float = DEFAULT_READ_TIMEOUT_SECONDS,
    ):
        """
        Cria e configura um cliente HTTP com o token de autenticação.
        
        Args:
            api_token (str): Token de API da Delta/BemPaggo.
            
        Returns:
            requests.Session: Sessão HTTP configurada com os headers necessários.
        """
        if connect_timeout <= 0 or read_timeout <= 0:
            raise ValueError("Os timeouts HTTP da Delta devem ser maiores que zero.")

        client = TimeoutSession((float(connect_timeout), float(read_timeout)))
        client.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        return client
