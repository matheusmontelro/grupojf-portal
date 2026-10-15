import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable

import jwt


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12


class TokenConfigurationError(RuntimeError):
    """Configuração de assinatura JWT ausente."""


def _active_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        raise TokenConfigurationError("JWT_SECRET não configurado")
    return secret


def _decode_secrets() -> Iterable[str]:
    active = _active_secret()
    yield active

    legacy = os.getenv("JWT_LEGACY_SECRET", "").strip()
    if legacy and legacy != active:
        yield legacy


def create_access_token(payload: Dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    encoded_payload = {
        **payload,
        "iat": now,
        "exp": now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(encoded_payload, _active_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    last_error: Exception | None = None
    for secret in _decode_secrets():
        try:
            return jwt.decode(token, secret, algorithms=[ALGORITHM])
        except jwt.InvalidTokenError as exc:
            last_error = exc

    if last_error:
        raise last_error
    raise jwt.InvalidTokenError("Token inválido")
