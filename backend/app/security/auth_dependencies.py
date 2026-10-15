"""Dependencias JWT que nao inicializam conexoes de banco globais."""

from __future__ import annotations

from typing import Dict

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security.tokens import decode_access_token


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict:
    """Decodifica o usuario; a invalidacao de sessao fica no middleware."""
    try:
        payload = decode_access_token(credentials.credentials)
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Token inválido")
        return {
            "email": email,
            "role": payload.get("role"),
            "nome": payload.get("nome"),
            "unidade": payload.get("unidade"),
            "user_id": payload.get("user_id"),
        }
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Token inválido") from exc
