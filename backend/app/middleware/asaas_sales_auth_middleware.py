"""Autenticacao da API isolada usando somente o banco dedicado de vendas."""

from __future__ import annotations

import logging

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.security.tokens import TokenConfigurationError, decode_access_token
from app.services.asaas_sale_database import DatabaseConnection


logger = logging.getLogger(__name__)

_PUBLIC_PATHS = frozenset({"/internal/health"})
_PUBLIC_PREFIXES = ("/api/webhooks/asaas/sales/",)


class AsaasSalesAuthMiddleware(BaseHTTPMiddleware):
    """Preserva JWT e auth_version sem carregar ``app.database.db``."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            request.method == "OPTIONS"
            or path in _PUBLIC_PATHS
            or any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)
        ):
            return await call_next(request)

        authorization = request.headers.get("Authorization")
        if not authorization:
            return _authentication_response(401, "Token necessário")
        try:
            scheme, token = authorization.split(" ", 1)
            if scheme.casefold() != "bearer" or not token.strip():
                raise ValueError
        except ValueError:
            return _authentication_response(401, "Token inválido")

        try:
            payload = decode_access_token(token)
            email = str(payload.get("sub") or "").strip()
            if not email:
                raise jwt.InvalidTokenError("Token sem identificador")
            current_version = await run_in_threadpool(
                _load_auth_version,
                email,
            )
            token_version = int(payload.get("auth_version", 0))
            if current_version is None or token_version != int(current_version):
                return _authentication_response(401, "Sessão invalidada")
            request.state.user = payload
        except jwt.ExpiredSignatureError:
            return _authentication_response(401, "Token expirado")
        except jwt.InvalidTokenError:
            return _authentication_response(401, "Token inválido")
        except (TypeError, ValueError):
            return _authentication_response(401, "Token inválido")
        except TokenConfigurationError:
            logger.error("JWT da API isolada de vendas Asaas não configurado.")
            return _authentication_response(
                503,
                "Autenticação temporariamente indisponível",
            )
        except Exception as exc:
            logger.error(
                "Falha na autenticação isolada de vendas Asaas. error_type=%s",
                type(exc).__name__,
            )
            return _authentication_response(
                503,
                "Autenticação temporariamente indisponível",
            )

        return await call_next(request)


def _load_auth_version(email: str) -> int | None:
    with DatabaseConnection(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT auth_version
            FROM users
            WHERE LOWER(email) = %s
            LIMIT 1
            """,
            (email.casefold(),),
        )
        row = cursor.fetchone()
    return row[0] if row else None


def _authentication_response(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})
