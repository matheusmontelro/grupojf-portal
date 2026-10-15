"""Serviços para sincronizar o ID da assinatura do endpoint Everest/BemPaggo."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..delta_recorrente_sdk.environment import DeltaConfig


def normalize_document(document: Optional[str]) -> str:
    """Mantém apenas dígitos do documento."""
    return "".join(ch for ch in str(document or "") if ch.isdigit())


def _get_everest_base_url(config: DeltaConfig) -> str:
    """Resolve a base URL do endpoint Everest a partir do ambiente ativo."""
    if "sandbox" in config.environment.value:
        return "https://apisandbox.bempaggo.io"
    return "https://api.bempaggo.io"


def _iter_subscriptions(payload: Any) -> Iterable[Dict[str, Any]]:
    """Normaliza formatos de resposta em uma lista de assinaturas."""
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("items", "content", "data", "subscriptions"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

    return []


def _candidate_score(
    candidate: Dict[str, Any],
    customer_document: str,
    amount_cents: int,
    total_cycles: int,
    created_reference_ms: int,
) -> tuple[int, int]:
    """
    Gera score para escolher a assinatura mais provável.

    Retorna `(score, distancia_ms)` para permitir desempate pela proximidade temporal.
    """
    customer = candidate.get("customer") or {}
    candidate_document = normalize_document(customer.get("document"))

    if candidate_document != customer_document:
        return (-1, 10**18)

    score = 100
    matched_specific_field = False

    candidate_amount = candidate.get("valueInCents")
    if candidate_amount == amount_cents:
        score += 50
        matched_specific_field = True

    candidate_cycles = candidate.get("maxCycle")
    if candidate_cycles == total_cycles:
        score += 30
        matched_specific_field = True

    order_date = candidate.get("orderDate")
    if isinstance(order_date, (int, float)):
        distance_ms = abs(int(order_date) - created_reference_ms)
        if distance_ms <= 5 * 60 * 1000:
            score += 25
            matched_specific_field = True
        elif distance_ms <= 60 * 60 * 1000:
            score += 15
            matched_specific_field = True
        elif distance_ms <= 24 * 60 * 60 * 1000:
            score += 5
            matched_specific_field = True
    else:
        distance_ms = 10**18

    if not matched_specific_field:
        return (-1, distance_ms)

    return (score, distance_ms)


def find_matching_everest_subscription(
    *,
    config: DeltaConfig,
    customer_document: str,
    amount_cents: int,
    total_cycles: int,
    created_reference_ms: Optional[int] = None,
    max_retries: int = 3,
    logger: Optional[logging.Logger] = None,
) -> Optional[Dict[str, Any]]:
    """
    Busca a assinatura correspondente no endpoint Everest.

    A busca é feita por CPF e o match final leva em conta valor, parcelas e proximidade
    temporal com a criação da fatura recorrente local.
    """
    log = logger or logging.getLogger(__name__)
    normalized_document = normalize_document(customer_document)
    if not normalized_document:
        log.warning("Documento vazio; lookup no Everest ignorado")
        return None

    created_reference_ms = created_reference_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    base_url = _get_everest_base_url(config)
    endpoint = f"{base_url}/everest/v1/subscriptions"
    params = {
        "offset": 0,
        "size": 10,
        "customerSearch": normalized_document,
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Accept": "application/json",
    }

    backoff_seconds = (0.0, 0.5, 1.0)

    for attempt in range(max_retries):
        if attempt < len(backoff_seconds) and backoff_seconds[attempt] > 0:
            time.sleep(backoff_seconds[attempt])

        try:
            with httpx.Client(timeout=httpx.Timeout(10.0), follow_redirects=True) as client:
                response = client.get(endpoint, headers=headers, params=params)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            log.warning(
                "Falha ao consultar Everest para CPF %s na tentativa %s/%s: %s",
                normalized_document,
                attempt + 1,
                max_retries,
                exc,
            )
            continue

        candidates = list(_iter_subscriptions(payload))
        if not candidates:
            log.info(
                "Everest não retornou assinaturas para CPF %s na tentativa %s/%s",
                normalized_document,
                attempt + 1,
                max_retries,
            )
            continue

        scored_candidates = []
        for candidate in candidates:
            score, distance_ms = _candidate_score(
                candidate=candidate,
                customer_document=normalized_document,
                amount_cents=amount_cents,
                total_cycles=total_cycles,
                created_reference_ms=created_reference_ms,
            )
            if score >= 0:
                scored_candidates.append((score, distance_ms, candidate))

        if not scored_candidates:
            log.info(
                "Everest retornou assinaturas para CPF %s, mas nenhuma casou com valor/ciclos",
                normalized_document,
            )
            continue

        scored_candidates.sort(key=lambda item: (-item[0], item[1]))
        best_score, _, best_candidate = scored_candidates[0]
        log.info(
            "Assinatura Everest conciliada para CPF %s com score %s: %s",
            normalized_document,
            best_score,
            best_candidate.get("id"),
        )
        return best_candidate

    return None


def fatura_recorrente_supports_everest_id(db: Session) -> bool:
    """Verifica se a coluna de assinatura do Everest já existe no banco."""
    query = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'fatura_recorrente'
          AND column_name = 'everest_subscription_id'
        """
    )
    return bool(db.execute(query).first())


def carne_supports_everest_id(db: Session) -> bool:
    """Verifica se a coluna de assinatura do Everest já existe na tabela de carnês."""
    query = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'carne_pagamento'
          AND column_name = 'everest_subscription_id'
        """
    )
    return bool(db.execute(query).first())


def save_everest_subscription_id(
    *,
    db: Session,
    fatura_recorrente_id: int,
    everest_subscription_id: int,
) -> bool:
    """Persistir o ID da assinatura Everest sem quebrar ambientes sem migration aplicada."""
    if not everest_subscription_id:
        return False

    if not fatura_recorrente_supports_everest_id(db):
        return False

    db.execute(
        text(
            """
            UPDATE fatura_recorrente
            SET everest_subscription_id = :everest_subscription_id,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = :fatura_recorrente_id
            """
        ),
        {
            "everest_subscription_id": everest_subscription_id,
            "fatura_recorrente_id": fatura_recorrente_id,
        },
    )
    db.commit()
    return True


def save_carne_everest_subscription_id(
    *,
    db: Session,
    carne_id: int,
    everest_subscription_id: int,
) -> bool:
    """Persistir o ID da assinatura Everest no carnê sem quebrar ambientes sem migration aplicada."""
    if not everest_subscription_id:
        return False

    if not carne_supports_everest_id(db):
        return False

    db.execute(
        text(
            """
            UPDATE carne_pagamento
            SET everest_subscription_id = :everest_subscription_id
            WHERE id = :carne_id
            """
        ),
        {
            "everest_subscription_id": everest_subscription_id,
            "carne_id": carne_id,
        },
    )
    db.commit()
    return True


def get_local_everest_subscription_id(
    *,
    db: Session,
    recurring_invoice_id: int,
) -> Optional[int]:
    """Busca o ID Everest salvo localmente para uma recurring-invoice."""
    if not fatura_recorrente_supports_everest_id(db):
        return None

    result = db.execute(
        text(
            """
            SELECT everest_subscription_id
            FROM fatura_recorrente
            WHERE subscription_id = :recurring_invoice_id
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"recurring_invoice_id": recurring_invoice_id},
    ).first()

    if not result:
        return None

    return result[0]


def extract_subscription_id_from_payload(payload: Dict[str, Any]) -> Optional[int]:
    """Extrai subscription_id tanto do nível raiz quanto de payloads aninhados em `data`."""
    raw_value = payload.get("subscription_id")
    if raw_value is None and isinstance(payload.get("data"), dict):
        raw_value = payload["data"].get("subscription_id")

    if raw_value in (None, ""):
        return None

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None
