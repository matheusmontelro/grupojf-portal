import logging

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.database.db import get_auth_version
from app.security.auth_dependencies import get_current_user
from app.security.tokens import decode_access_token


logger = logging.getLogger(__name__)

__all__ = ["AuthMiddleware", "get_current_user"]


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        public_paths = {
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/login",
            "/api/auth/login",
            "/api/auth/password-reset/request",
            "/api/auth/password-reset/verify",
            "/api/auth/password-reset/complete",
            "/",
            "/static",
        }
        public_prefixes = (
            "/webhook/",
            "/api/webhooks/",
            "/static/",
            "/public/",
            "/api/public/",
            "/api/contratos-digitais/view/",
            "/api/contratos-digitais/selfie/",
            "/api/contratos-digitais/sign/",
        )

        path = request.url.path
        if path in public_paths or any(path.startswith(prefix) for prefix in public_prefixes):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(status_code=401, content={"detail": "Token necessário"})

        try:
            scheme, token = auth_header.split(" ", 1)
            if scheme.casefold() != "bearer":
                raise ValueError
        except ValueError:
            return JSONResponse(status_code=401, content={"detail": "Token inválido"})

        try:
            payload = decode_access_token(token)
            email = payload.get("sub")
            if not email:
                raise jwt.InvalidTokenError("Token sem identificador")

            current_version = get_auth_version(email)
            token_version = int(payload.get("auth_version", 0))
            if current_version is None or token_version != int(current_version):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Sessão invalidada"},
                )

            request.state.user = payload
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "Token expirado"})
        except jwt.InvalidTokenError:
            return JSONResponse(status_code=401, content={"detail": "Token inválido"})
        except Exception as exc:
            logger.error("Falha ao validar sessão (%s)", type(exc).__name__)
            return JSONResponse(
                status_code=503,
                content={"detail": "Autenticação temporariamente indisponível"},
            )

        return await call_next(request)
