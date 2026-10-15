"""Entrypoint FastAPI mínimo e isolado do fluxo de vendas Asaas."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.middleware.asaas_sales_auth_middleware import (
    AsaasSalesAuthMiddleware,
)
from app.routers import asaas_sale_webhook, vendas_asaas
from app.services.asaas_sales_preflight import (
    AsaasSalesPreflightError,
    run_asaas_sales_preflight,
)


logger = logging.getLogger(__name__)

app = FastAPI(
    title="Grupo JF - Vendas Asaas",
    description="API isolada do fluxo de vendas Asaas.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(AsaasSalesAuthMiddleware)
app.include_router(vendas_asaas.router, prefix="/api")
app.include_router(asaas_sale_webhook.router, prefix="/api")


@app.get(
    "/internal/health",
    include_in_schema=False,
    response_model=None,
)
def health() -> dict[str, str] | JSONResponse:
    """Readiness sem detalhes de configuração, conta ou banco."""
    try:
        run_asaas_sales_preflight(allow_no_units=True)
    except AsaasSalesPreflightError as exc:
        logger.error(
            "Preflight da API isolada de vendas Asaas falhou. code=%s",
            exc.code,
        )
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable"},
        )
    except Exception as exc:
        logger.error(
            "Health da API isolada de vendas Asaas falhou. error_type=%s",
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable"},
        )
    return {"status": "ok"}
