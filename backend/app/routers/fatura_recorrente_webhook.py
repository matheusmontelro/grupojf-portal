"""Webhook para notificações de faturas recorrentes Delta"""
from fastapi import APIRouter, Request, status
from sqlalchemy import text
import logging
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..database.db import get_db
from ..delta_recorrente_sdk import DeltaRecorrenteSDK
from ..delta_recorrente_sdk.environment import DeltaConfig
from ..services.everest_subscription_service import (
    extract_subscription_id_from_payload,
    save_everest_subscription_id,
)

# Configuração de logs (mesmo padrão do carnê)
log_dir = os.getenv("APP_LOG_DIR", "backend/arquivos/logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "fatura_recorrente_webhook.log")

# Configurar o logger
logger = logging.getLogger("fatura_recorrente_webhook")
logger.setLevel(logging.DEBUG)

# Handler para arquivo
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)

# Handler para console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formato dos logs
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Adicionar handlers ao logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

router = APIRouter(prefix="/webhook", tags=["webhooks"])

# Diretório para salvar logs de webhook
WEBHOOK_LOG_DIR = os.getenv("APP_PAYMENTS_DIR", "backend/arquivos/pagamentos")
os.makedirs(WEBHOOK_LOG_DIR, exist_ok=True)

def save_webhook_payload(payload: dict, prefix: str = "fatura_recorrente_webhook"):
    """Salva payload do webhook em arquivo para auditoria"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.json"
    filepath = os.path.join(WEBHOOK_LOG_DIR, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Payload salvo em: {filepath}")
    except Exception as e:
        logger.error(f"Erro ao salvar payload: {e}")

PAID_INVOICE_STATUSES = {"PAID", "PAY"}
CANCELED_STATUSES = {"CANCELED", "CANCELLED"}
DEFAULT_UNIDADE = os.getenv("DELTA_DEFAULT_UNIDADE", "Nova Iguaçu 1")


def get_delta_config(unidade: Optional[str] = None):
    """Obtém configuração da API Delta respeitando o token da unidade."""
    return DeltaConfig.from_env(unidade=unidade or DEFAULT_UNIDADE)


def _normalizar_status(status_value: Optional[Any]) -> str:
    return str(status_value or "").strip().upper()


def _delta_datetime(value: Optional[Any]) -> Optional[datetime]:
    if value in (None, ""):
        return None

    try:
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp)

        value_str = str(value).strip()
        if not value_str:
            return None
        if value_str.isdigit():
            return _delta_datetime(int(value_str))

        parsed = datetime.fromisoformat(value_str.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _delta_date(value: Optional[Any]):
    parsed = _delta_datetime(value)
    return parsed.date() if parsed else None


def _decimal_from_delta_amount(value: Optional[Any], fallback: Optional[Any] = None) -> Decimal:
    if value in (None, ""):
        return Decimal(str(fallback or "0"))

    try:
        amount = Decimal(str(value))
        if amount >= Decimal("1000"):
            return (amount / Decimal("100")).quantize(Decimal("0.01"))
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal(str(fallback or "0"))


def _invoice_amount(invoice: Dict[str, Any], fallback: Optional[Any]) -> Decimal:
    for key in ("paidAmount", "amount", "value", "totalAmount", "amountInCents"):
        if invoice.get(key) not in (None, ""):
            return _decimal_from_delta_amount(invoice.get(key), fallback)
    return _decimal_from_delta_amount(None, fallback)


def _invoice_payment_datetime(invoice: Dict[str, Any]) -> Optional[datetime]:
    for key in ("paymentDate", "paidAt", "paymentAt"):
        parsed = _delta_datetime(invoice.get(key))
        if parsed:
            return parsed

    transactions = invoice.get("transactions") or []
    for transaction in transactions:
        parsed = _delta_datetime(
            transaction.get("paymentDate")
            or transaction.get("paidAt")
            or transaction.get("paymentAt")
        )
        if parsed:
            return parsed

    return None


def _next_due_date_from_invoices(invoices: Iterable[Dict[str, Any]]):
    candidate_dates = []
    for invoice in invoices:
        status_invoice = _normalizar_status(invoice.get("status"))
        if status_invoice in PAID_INVOICE_STATUSES or status_invoice in CANCELED_STATUSES:
            continue

        for key in ("dueDate", "billingDate", "scheduledDate", "createdAt"):
            due_date = _delta_date(invoice.get(key))
            if due_date:
                candidate_dates.append(due_date)
                break

    return min(candidate_dates) if candidate_dates else None


def _status_recorrente_from_delta(
    order_status: Optional[str],
    last_charge_status: Optional[str],
    paid_count: int,
    total_parcelas: Optional[int],
    status_atual: Optional[str],
) -> str:
    order = _normalizar_status(order_status)
    charge = _normalizar_status(last_charge_status)

    if total_parcelas and paid_count >= total_parcelas:
        return "COMPLETED"
    if order in CANCELED_STATUSES:
        return "CANCELED"
    if order in {"ACTIVE", "PENDING", "PAUSED", "OVERDUE", "COMPLETED"}:
        return order
    if charge in PAID_INVOICE_STATUSES and paid_count > 0:
        return "ACTIVE"
    return status_atual or "PENDING"


def _candidate_recurring_ids(*values: Optional[Any]) -> List[int]:
    candidates: List[int] = []
    for value in values:
        if value in (None, ""):
            continue
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _buscar_invoices_delta(
    recurring_ids: Iterable[int],
    unidade: Optional[str],
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    last_error: Optional[Exception] = None

    for recurring_id in recurring_ids:
        try:
            config = get_delta_config(unidade=unidade)
            with DeltaRecorrenteSDK(config) as sdk:
                invoices = sdk.get_recurring_invoice_invoices(recurring_id)
            return invoices, recurring_id
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Falha ao consultar invoices da fatura recorrente %s na Delta: %s",
                recurring_id,
                exc,
            )

    if last_error:
        raise last_error

    return [], None

@router.post("/fatura-recorrente", status_code=status.HTTP_200_OK)
async def webhook_fatura_recorrente(request: Request):
    """
    Rota para receber o webhook de faturas recorrentes da Bempaggo e:
    1. Salvar os dados do webhook no banco
    2. Atualizar o status da assinatura correspondente
    3. Registrar logs detalhados para depuração
    """
    logger.info("=== Recebendo webhook de fatura recorrente da Bempaggo ===")
    
    try:
        # 1) Lê o corpo como string
        payload_bytes = await request.body()
        payload_str = payload_bytes.decode("utf-8", errors="ignore")
        logger.debug(f"Payload recebido: {payload_str}")

        # 2) Query params (token, status, etc.)
        query_params = dict(request.query_params)
        logger.info(f"Query params: {query_params}")

        # 3) Salvar dados em arquivo JSON para referência
        filename = f"fatura_recorrente_webhook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(WEBHOOK_LOG_DIR, filename)

        logger.info(f"Salvando JSON em: {filepath}")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "query_params": query_params,
                    "body": payload_str
                },
                f,
                indent=2,
                ensure_ascii=False
            )
        logger.info(f"JSON salvo com sucesso em: {filepath}")

        # 4) Extrair token para identificar a assinatura
        token = query_params.get("token")
        logger.info(f"Token extraído: {token}")
        subscription_id = None
        
        # 5) Tentar processar o payload
        try:
            payload = json.loads(payload_str)
            logger.info(f"Payload JSON decodificado com sucesso")
            
            # Processar webhook estruturado
            event_type = payload.get('event_type')
            subscription_id = extract_subscription_id_from_payload(payload)
            
            logger.info(f"Evento: {event_type}, Subscription ID: {subscription_id}")
            
        except json.JSONDecodeError:
            logger.warning("Não foi possível decodificar o payload como JSON")
            # Se não for JSON, continuar com processamento básico baseado em query params
            
        # 6) Processar com base nos query params (padrão Bempaggo)
        order_status = query_params.get("orderStatus")
        last_charge_status = query_params.get("lastChargeStatus")
        
        logger.info(f"Order Status: {order_status}, Last Charge Status: {last_charge_status}")
        
        # 7) Salvar log do webhook
        db = next(get_db())
        try:
            db.execute(text("""
                INSERT INTO webhook_logs (tipo, token, payload, query_params, status_recebido)
                VALUES (:tipo, :token, :payload, :query_params, :status_recebido)
            """), {
                'tipo': 'fatura_recorrente',
                'token': token,
                'payload': json.dumps({"body": payload_str}),
                'query_params': json.dumps(query_params),
                'status_recebido': f"{order_status}_{last_charge_status}"
            })
            db.commit()
        except Exception as e:
            logger.error(f"Erro ao salvar log do webhook: {e}")
            db.rollback()
        
        # 8) Processar atualização de status se tiver token
        if token:
            try:
                # Buscar fatura recorrente pelo token
                result = db.execute(text("""
                    SELECT
                        fr.id,
                        fr.status,
                        fr.venda_id,
                        COALESCE(fr.parcelas_pagas, 0) AS parcelas_pagas,
                        fr.total_parcelas,
                        fr.subscription_id,
                        fr.valor_mensal,
                        fr.everest_subscription_id,
                        COALESCE(NULLIF(v.unidade, ''), :default_unidade) AS unidade
                    FROM fatura_recorrente fr
                    LEFT JOIN vendas v ON v.id = fr.venda_id
                    WHERE fr.uuid = :uuid
                """), {'uuid': token, 'default_unidade': DEFAULT_UNIDADE})
                fatura_row = result.fetchone()
                
                if fatura_row:
                    fatura = fatura_row._mapping
                    fatura_id = fatura["id"]
                    status_atual = fatura["status"]
                    venda_id = fatura["venda_id"]
                    parcelas_pagas = fatura["parcelas_pagas"] or 0
                    total_parcelas = fatura["total_parcelas"] or 0
                    valor_mensal = fatura["valor_mensal"]
                    unidade = fatura["unidade"] or DEFAULT_UNIDADE
                    logger.info(f"Fatura recorrente encontrada: ID={fatura_id}, Status atual={status_atual}")

                    if subscription_id:
                        try:
                            if save_everest_subscription_id(
                                db=db,
                                fatura_recorrente_id=fatura_id,
                                everest_subscription_id=subscription_id,
                            ):
                                logger.info(
                                    "everest_subscription_id=%s salvo para fatura recorrente %s via webhook",
                                    subscription_id,
                                    fatura_id,
                                )
                        except Exception as sync_error:
                            logger.warning(
                                "Erro ao salvar everest_subscription_id via webhook para fatura %s: %s",
                                fatura_id,
                                sync_error,
                            )

                    recurring_ids = _candidate_recurring_ids(
                        fatura["subscription_id"],
                        fatura["everest_subscription_id"],
                        subscription_id,
                    )
                    invoices, recurring_id_usado = _buscar_invoices_delta(recurring_ids, unidade)
                    paid_sequences = set()
                    parcelas_atualizadas = 0
                    pagas_sem_data_pagamento = 0

                    logger.info(
                        "Delta retornou %s invoices para fatura recorrente %s (id consultado=%s)",
                        len(invoices),
                        fatura_id,
                        recurring_id_usado,
                    )

                    for invoice in invoices:
                        status_invoice = _normalizar_status(invoice.get("status"))
                        if status_invoice not in PAID_INVOICE_STATUSES:
                            continue

                        try:
                            numero_parcela = int(invoice.get("invoiceSequence"))
                        except (TypeError, ValueError):
                            logger.warning("Invoice paga sem invoiceSequence ignorada: %s", invoice)
                            continue

                        paid_sequences.add(numero_parcela)
                        data_pagamento = _invoice_payment_datetime(invoice)
                        if not data_pagamento:
                            pagas_sem_data_pagamento += 1
                            logger.warning(
                                "Invoice paga sequence=%s da fatura recorrente %s ignorada: Delta não enviou paymentDate/paidAt/paymentAt",
                                numero_parcela,
                                fatura_id,
                            )
                            continue

                        valor_pago = _invoice_amount(invoice, valor_mensal)

                        parcela_result = db.execute(text("""
                            UPDATE venda_parcelas
                            SET status_parcela = 'Pago',
                                data_pagamento = COALESCE(data_pagamento, :data_pagamento),
                                valor_pago = COALESCE(valor_pago, :valor_pago),
                                updated_at = CURRENT_TIMESTAMP
                            WHERE venda_id = :venda_id
                              AND numero_parcela = :numero_parcela
                              AND status_parcela <> 'Pago'
                            RETURNING id
                        """), {
                            'venda_id': venda_id,
                            'numero_parcela': numero_parcela,
                            'data_pagamento': data_pagamento,
                            'valor_pago': valor_pago,
                        })

                        if parcela_result.fetchone():
                            parcelas_atualizadas += 1

                    parcelas_pagas_delta = len(paid_sequences) if invoices else parcelas_pagas
                    if total_parcelas:
                        parcelas_pagas_delta = min(parcelas_pagas_delta, total_parcelas)

                    proxima_cobranca = _next_due_date_from_invoices(invoices)
                    novo_status = _status_recorrente_from_delta(
                        order_status,
                        last_charge_status,
                        parcelas_pagas_delta,
                        total_parcelas,
                        status_atual,
                    )

                    db.execute(text("""
                        UPDATE fatura_recorrente
                        SET status = :status,
                            parcelas_pagas = :parcelas_pagas,
                            proxima_cobranca = COALESCE(:proxima_cobranca, proxima_cobranca),
                            atualizado_em = CURRENT_TIMESTAMP
                        WHERE id = :id
                    """), {
                        'status': novo_status,
                        'parcelas_pagas': parcelas_pagas_delta,
                        'proxima_cobranca': proxima_cobranca,
                        'id': fatura_id,
                    })

                    if total_parcelas and parcelas_pagas_delta >= total_parcelas:
                        db.execute(text("""
                            UPDATE vendas
                            SET status_pagamento = 'pago',
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = :venda_id
                        """), {'venda_id': venda_id})
                        logger.info(f"Todas as parcelas pagas! Venda {venda_id} marcada como paga")

                    db.execute(text("""
                        UPDATE webhook_logs
                        SET processado = true
                        WHERE id = (
                            SELECT id FROM webhook_logs
                            WHERE token = :token AND tipo = 'fatura_recorrente'
                            ORDER BY criado_em DESC
                            LIMIT 1
                        )
                    """), {'token': token})

                    db.commit()
                    logger.info(
                        "Fatura recorrente %s conciliada: status %s -> %s, parcelas %s -> %s, venda_parcelas atualizadas=%s, pagas_sem_data=%s",
                        fatura_id,
                        status_atual,
                        novo_status,
                        parcelas_pagas,
                        parcelas_pagas_delta,
                        parcelas_atualizadas,
                        pagas_sem_data_pagamento,
                    )
                else:
                    logger.warning(f"Fatura recorrente não encontrada para token: {token}")
                    
            except Exception as e:
                logger.error(f"Erro ao processar webhook: {e}")
                logger.exception(e)
                db.rollback()
                # Registrar erro no log
                try:
                    db.execute(text("""
                        UPDATE webhook_logs 
                        SET erro = :erro 
                        WHERE id = (
                            SELECT id FROM webhook_logs 
                            WHERE token = :token AND tipo = 'fatura_recorrente'
                            ORDER BY criado_em DESC 
                            LIMIT 1
                        )
                    """), {'erro': str(e), 'token': token})
                    db.commit()
                except:
                    pass
        
        return {"status": "success", "message": "Webhook recebido e processado"}
        
    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}")
        logger.exception(e)
        # Retorna sucesso para evitar retry desnecessário
        return {"status": "error", "message": str(e)}
