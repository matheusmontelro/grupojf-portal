"""Webhook para notificações de faturas avulsas Delta"""
from fastapi import APIRouter, Request, HTTPException, status
from sqlalchemy.orm import Session
from fastapi import Depends
from sqlalchemy import text
import logging
import json
from datetime import datetime, timezone
import os

from ..database.db import get_db
from ..models.fatura_avulsa import FaturaAvulsaWebhookPayload
from ..delta_avulsa_sdk import DeltaAvulsaSDK
from ..delta_avulsa_sdk.environment import DeltaConfig

# Configuração de logs (mesmo padrão do carnê)
log_dir = os.getenv("APP_LOG_DIR", "backend/arquivos/logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "fatura_avulsa_webhook.log")

# Configurar o logger
logger = logging.getLogger("fatura_avulsa_webhook")
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

PAID_INVOICE_STATUSES = {"PAID", "PAY"}
CANCELED_INVOICE_STATUSES = {"VOID", "DELETED", "CANCELED", "CANCELLED"}


def _parse_delta_timestamp(value):
    if value in (None, "", 0):
        return None

    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(tzinfo=None)

    if isinstance(value, str):
        try:
            numeric = float(value)
            return _parse_delta_timestamp(numeric)
        except ValueError:
            pass

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    return None


def _status_from_query_params(order_status, last_charge_status):
    order = (order_status or "").upper()
    charge = (last_charge_status or "").upper()

    if charge in PAID_INVOICE_STATUSES:
        return "PAID"
    if order in CANCELED_INVOICE_STATUSES or charge in CANCELED_INVOICE_STATUSES:
        return "VOID"
    if order == "EXPIRED":
        return "UNCOLLECTIBLE"
    if order in {"ACTIVE", "PENDING", "OVERDUE"}:
        return order

    return None


def _buscar_fatura_delta(unidade, invoice_id):
    config = DeltaConfig.from_env(unidade=unidade)
    with DeltaAvulsaSDK(config) as sdk:
        response = sdk.http_client.get(f"/api/v2/invoices/{invoice_id}")
        return response.json()


def _normalizar_status_fatura_delta(invoice_data, order_status, last_charge_status):
    if invoice_data:
        status = (invoice_data.get("status") or "").upper()
        if status:
            return status

    return _status_from_query_params(order_status, last_charge_status)


def _data_pagamento_fatura_delta(invoice_data):
    if not invoice_data:
        return None

    for key in ("paymentDate", "paidAt", "paid_at", "payment_date"):
        parsed = _parse_delta_timestamp(invoice_data.get(key))
        if parsed:
            return parsed

    return None

def save_webhook_payload(payload: dict, prefix: str = "fatura_avulsa_webhook"):
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

def get_delta_config():
    """Obtém configuração da API Delta"""
    api_key = os.getenv("DELTA_API_KEY")
    if not api_key:
        raise ValueError("API Delta não configurada")
    return DeltaConfig(api_key=api_key)

@router.post("/fatura-avulsa", status_code=status.HTTP_200_OK)
async def webhook_fatura_avulsa(request: Request):
    """
    Rota para receber o webhook de faturas avulsas da Bempaggo e:
    1. Salvar os dados do webhook no banco
    2. Atualizar o status da fatura correspondente
    3. Registrar logs detalhados para depuração
    """
    logger.info("=== Recebendo webhook de fatura avulsa da Bempaggo ===")
    
    try:
        # 1) Lê o corpo como string
        payload_bytes = await request.body()
        payload_str = payload_bytes.decode("utf-8", errors="ignore")
        logger.debug(f"Payload recebido: {payload_str}")

        # 2) Query params (token, status, etc.)
        query_params = dict(request.query_params)
        logger.info(f"Query params: {query_params}")

        # 3) Salvar dados em arquivo JSON para referência
        filename = f"fatura_avulsa_webhook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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

        # 4) Extrair token para identificar a fatura
        token = query_params.get("token")
        logger.info(f"Token extraído: {token}")
        
        # 5) Tentar processar o payload
        try:
            payload = json.loads(payload_str)
            logger.info(f"Payload JSON decodificado com sucesso")
            
            # Processar webhook estruturado
            event_type = payload.get('event_type')
            invoice_id = payload.get('invoice_id')
            
            logger.info(f"Evento: {event_type}, Invoice ID: {invoice_id}")
            
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
            from sqlalchemy import text
            db.execute(text("""
                INSERT INTO webhook_logs (tipo, token, payload, query_params, status_recebido)
                VALUES (:tipo, :token, :payload, :query_params, :status_recebido)
            """), {
                'tipo': 'fatura_avulsa',
                'token': token,
                'payload': json.dumps({"body": payload_str}),
                'query_params': json.dumps(query_params),
                'status_recebido': f"{order_status}_{last_charge_status}"
            })
            db.commit()
        except Exception as e:
            logger.error(f"Erro ao salvar log do webhook: {e}")
        
        # 8) Processar atualização de status se tiver token
        if token:
            try:
                # Buscar fatura pelo token
                result = db.execute(text("""
                    SELECT
                        fa.id,
                        fa.status,
                        fa.venda_id,
                        fa.invoice_id,
                        COALESCE(v.unidade, :default_unidade) AS unidade
                    FROM fatura_avulsa fa
                    LEFT JOIN vendas v ON v.id = fa.venda_id
                    WHERE fa.uuid = :uuid
                """), {
                    'uuid': token,
                    'default_unidade': os.getenv("DELTA_DEFAULT_UNIDADE", "Nova Iguaçu 1"),
                })
                fatura = result.fetchone()
                
                if fatura:
                    fatura_id, status_atual, venda_id, invoice_id, unidade = fatura
                    logger.info(
                        "Fatura encontrada: ID=%s, Invoice ID=%s, Unidade=%s, Status atual=%s",
                        fatura_id,
                        invoice_id,
                        unidade,
                        status_atual,
                    )

                    invoice_data = None
                    try:
                        invoice_data = _buscar_fatura_delta(unidade, invoice_id)
                        logger.info(
                            "Delta consultada para fatura avulsa %s: status=%s",
                            invoice_id,
                            invoice_data.get("status") if isinstance(invoice_data, dict) else None,
                        )
                    except Exception as consulta_error:
                        logger.error(
                            "Erro ao consultar fatura avulsa %s na Delta; usando query params como fallback: %s",
                            invoice_id,
                            consulta_error,
                        )

                    novo_status = _normalizar_status_fatura_delta(
                        invoice_data,
                        order_status,
                        last_charge_status,
                    )
                    data_pagamento_delta = _data_pagamento_fatura_delta(invoice_data)

                    if novo_status:
                        db.execute(text("""
                            UPDATE fatura_avulsa 
                            SET status = :status,
                                data_pagamento = CASE 
                                    WHEN :status = 'PAID' THEN COALESCE(:data_pagamento_delta, data_pagamento, CURRENT_TIMESTAMP)
                                    ELSE data_pagamento 
                                END,
                                atualizado_em = CURRENT_TIMESTAMP
                            WHERE id = :id
                        """), {
                            'status': novo_status,
                            'data_pagamento_delta': data_pagamento_delta,
                            'id': fatura_id,
                        })
                        
                        # Se a fatura avulsa foi paga, a venda pode ser marcada como paga.
                        # As parcelas locais não são baixadas aqui porque fatura avulsa não
                        # possui status individual por parcela na Delta.
                        if novo_status in PAID_INVOICE_STATUSES:
                            db.execute(text("""
                                UPDATE vendas 
                                SET status_pagamento = 'pago' 
                                WHERE id = :venda_id
                            """), {'venda_id': venda_id})
                            logger.info(f"Venda {venda_id} marcada como paga")
                        
                        db.commit()
                        logger.info(f"Status da fatura {fatura_id} atualizado de {status_atual} para {novo_status}")

                    # Marcar webhook como processado mesmo se o status não mudou.
                    db.execute(text("""
                        UPDATE webhook_logs
                        SET processado = true
                        WHERE id = (
                            SELECT id FROM webhook_logs
                            WHERE token = :token AND tipo = 'fatura_avulsa'
                            ORDER BY criado_em DESC
                            LIMIT 1
                        )
                    """), {'token': token})
                    db.commit()
                else:
                    logger.warning(f"Fatura não encontrada para token: {token}")
                    
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
                            WHERE token = :token AND tipo = 'fatura_avulsa'
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
