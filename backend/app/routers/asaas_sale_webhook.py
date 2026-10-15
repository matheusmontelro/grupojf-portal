"""Recepcao autenticada e idempotente dos webhooks de vendas Asaas."""

from __future__ import annotations

import json
import logging
import secrets

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.asaas_sdk.environment import AsaasConfig
from app.asaas_sdk.exceptions import AsaasConfigurationError
from app.services import asaas_sale_job_service as jobs
from app.services import asaas_sale_webhook_service as webhooks
from app.services.asaas_sale_database import DatabaseConnection
from app.services.asaas_sales_config import (
    AsaasSalesConfigError,
    canonicalize_asaas_sales_unit,
    get_asaas_sales_account_id,
    get_asaas_sales_webhook_token,
    is_asaas_sales_enabled,
    validate_asaas_sales_account_configuration,
    validate_enabled_asaas_sales_account_isolation,
)


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/webhooks/asaas/sales",
    tags=["asaas-sales-webhooks"],
)


@router.post("/{unit_slug}")
async def receive_asaas_sale_webhook(
    unit_slug: str,
    request: Request,
    asaas_access_token: str | None = Header(
        default=None,
        alias="asaas-access-token",
    ),
) -> dict[str, bool]:
    unidade = canonicalize_asaas_sales_unit(unit_slug)
    if not unidade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint de webhook não encontrado.",
        )

    try:
        enabled = is_asaas_sales_enabled(unidade)
        if not enabled:
            raise AsaasSalesConfigError("Fluxo de vendas Asaas desabilitado.")
        validate_enabled_asaas_sales_account_isolation()
        expected_token = get_asaas_sales_webhook_token(unidade)
        config = AsaasConfig.from_env(unidade, strict=True)
        unidade, environment, account_wallet_id = (
            validate_asaas_sales_account_configuration(
                unidade=config.unidade or unidade,
                environment=config.environment.name.casefold(),
                account_wallet_id=config.account_wallet_id or "",
                api_key=config.api_key,
            )
        )
        expected_account_id = get_asaas_sales_account_id(
            unidade,
            environment,
        )
    except (AsaasConfigurationError, AsaasSalesConfigError):
        logger.error(
            "Configuracao do webhook de vendas Asaas indisponivel. unidade=%s",
            unidade,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook temporariamente indisponível.",
        ) from None
    received_token = str(asaas_access_token or "")
    if not received_token or not secrets.compare_digest(
        received_token.encode("utf-8"),
        expected_token.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook não autorizado.",
        )

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            parsed_content_length = int(content_length)
            if parsed_content_length < 0:
                raise ValueError
            if parsed_content_length > webhooks.MAX_WEBHOOK_BODY_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Evento de webhook excede o limite permitido.",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content-Length inválido.",
            ) from None

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > webhooks.MAX_WEBHOOK_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Evento de webhook excede o limite permitido.",
            )
        body.extend(chunk)
    try:
        raw_event = json.loads(bytes(body))
        technical_data = webhooks.sanitize_webhook_event(raw_event)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evento de webhook inválido.",
        ) from None

    received_account_id = webhooks.extract_account_id(technical_data)
    if not received_account_id or not secrets.compare_digest(
        received_account_id.encode("utf-8"),
        expected_account_id.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Origem do webhook não autorizada.",
        )

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            event, _created = webhooks.store_webhook_event(
                cursor,
                unidade=unidade,
                environment=environment,
                account_wallet_id=account_wallet_id,
                technical_data=technical_data,
            )
            jobs.enqueue_asaas_sale_job(
                cursor,
                webhook_event_id=event.id,
                operation="processar_webhook",
                deduplication_key=f"webhook:{event.id}",
            )
    except Exception as exc:
        logger.error(
            "Falha ao persistir webhook de vendas Asaas. unidade=%s "
            "error_type=%s",
            unidade,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook temporariamente indisponível.",
        ) from None

    return {"accepted": True}
