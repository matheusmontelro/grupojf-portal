# app/middleware/api_key_middleware.py

import os
import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

logger = logging.getLogger(__name__)

# Obter API Key do .env
API_KEY_PUBLIC = os.getenv("API_KEY_PUBLIC")

if not API_KEY_PUBLIC:
    logger.warning("⚠️ API_KEY_PUBLIC não configurada no .env!")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware para validar API Key em endpoints públicos.

    Endpoints que começam com /api/public/ requerem API Key no header:
    X-API-Key: sua-chave-aqui
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Lista de prefixos que requerem API Key
        protected_prefixes = [
            "/api/public/vendas",
        ]

        # Verificar se o endpoint requer API Key
        requires_api_key = any(path.startswith(prefix) for prefix in protected_prefixes)

        if requires_api_key:
            logger.info(f"🔐 API Key requerida para: {path}")

            # Obter API Key do header
            api_key = request.headers.get("X-API-Key")

            if not api_key:
                logger.warning(f"❌ API Key ausente: {path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "API Key obrigatória. Envie no header: X-API-Key"
                    }
                )

            # Validar API Key
            if api_key != API_KEY_PUBLIC:
                logger.warning(f"❌ API Key inválida: {path} - Key: {api_key[:10]}...")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "API Key inválida"
                    }
                )

            logger.info(f"✅ API Key válida: {path}")

        # API Key válida ou endpoint não protegido, continua
        response = await call_next(request)
        return response
