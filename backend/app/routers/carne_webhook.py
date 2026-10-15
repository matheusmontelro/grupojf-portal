# app/routers/carne_webhook.py
import os
import json
import logging
import traceback
from datetime import datetime
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Request, status, HTTPException

from app.carne_sdk.sdk import CarneSDK
from app.carne_sdk.sdk_utils import get_token_and_seller_for_unidade
from app.database.db import DatabaseConnection, SessionLocal
from app.services.everest_subscription_service import (
    extract_subscription_id_from_payload,
    save_carne_everest_subscription_id,
)

# Configuração de logs
log_dir = os.getenv("APP_LOG_DIR", "backend/arquivos/logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "carne_webhook.log")

# Configurar o logger
logger = logging.getLogger("carne_webhook")
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

PAID_CHARGE_STATUSES = {"PAY", "PAID"}
TERMINAL_CHARGE_STATUSES = {"CANCELED", "CANCELLED", "EXPIRED", "VOID"}
MAX_CHARGES_TO_CHECK = 12
DEFAULT_UNIDADE = os.getenv("DELTA_DEFAULT_UNIDADE", "Nova Iguaçu 1")


def get_current_environment():
    """Retorna 'production' se ENVIRONMENT='production', senão 'sandbox'."""
    env = os.getenv("ENVIRONMENT", "sandbox").lower()
    return "production" if env == "production" else "sandbox"


def _normalizar_status(status_value):
    return str(status_value or "").strip().upper()


def _delta_datetime(value):
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


def _decimal_from_delta_amount(value, fallback=None):
    if value in (None, ""):
        return Decimal(str(fallback or "0"))

    try:
        amount = Decimal(str(value))
        if amount >= Decimal("1000"):
            return (amount / Decimal("100")).quantize(Decimal("0.01"))
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal(str(fallback or "0"))


def _charge_amount(charge_data, fallback):
    for key in ("paidAmount", "value", "amount", "totalAmount", "amountInCents"):
        if charge_data.get(key) not in (None, ""):
            return _decimal_from_delta_amount(charge_data.get(key), fallback)
    return _decimal_from_delta_amount(None, fallback)


def _charge_payment_datetime(charge_data):
    for key in ("paymentDate", "paidAt", "paymentAt"):
        parsed = _delta_datetime(charge_data.get(key))
        if parsed:
            return parsed

    transactions = charge_data.get("transactions") or []
    for transaction in transactions:
        parsed = _delta_datetime(
            transaction.get("paymentDate")
            or transaction.get("paidAt")
            or transaction.get("paymentAt")
        )
        if parsed:
            return parsed

    return None


def _consultar_charge_delta(unidade, charge_id):
    api_token, seller_id = get_token_and_seller_for_unidade(
        unidade or DEFAULT_UNIDADE,
        get_current_environment(),
    )
    sdk = CarneSDK(
        api_token=api_token,
        seller_id=seller_id,
        environment=get_current_environment(),
    )
    return sdk.get_charge(charge_id)


def _consultar_invoices_delta(unidade, recurring_invoice_id):
    api_token, seller_id = get_token_and_seller_for_unidade(
        unidade or DEFAULT_UNIDADE,
        get_current_environment(),
    )
    sdk = CarneSDK(
        api_token=api_token,
        seller_id=seller_id,
        environment=get_current_environment(),
    )
    return sdk.get_recurring_invoice_invoices(recurring_invoice_id)


def _reconciliar_parcelas_pagas_por_invoices(cursor, carne_id):
    resultado = {
        "invoices_consultadas": 0,
        "parcelas_pagas_delta": 0,
        "carne_parcelas_atualizadas": 0,
        "venda_parcelas_atualizadas": 0,
        "parcelas_pagas_sem_data": 0,
        "parcela_ids": [],
        "erro": None,
    }

    cursor.execute("""
        SELECT
            recurring_invoice_id,
            COALESCE(NULLIF(unidade, ''), %s) AS unidade
        FROM carne_pagamento
        WHERE id = %s
    """, (DEFAULT_UNIDADE, carne_id))
    carne_row = cursor.fetchone()

    if not carne_row:
        resultado["erro"] = "carnê não encontrado"
        return resultado

    recurring_invoice_id, unidade = carne_row
    if not recurring_invoice_id:
        resultado["erro"] = "carnê sem recurring_invoice_id"
        return resultado

    try:
        invoices = _consultar_invoices_delta(unidade, recurring_invoice_id)
    except Exception as exc:
        resultado["erro"] = str(exc)
        logger.warning(
            "Falha ao consultar invoices do carnê %s (recurring_invoice_id=%s) na Delta: %s",
            carne_id,
            recurring_invoice_id,
            exc,
        )
        return resultado

    resultado["invoices_consultadas"] = len(invoices)
    logger.info(
        "Delta retornou %s invoices para carnê %s (recurring_invoice_id=%s)",
        len(invoices),
        carne_id,
        recurring_invoice_id,
    )

    for invoice in invoices:
        status_invoice = _normalizar_status(invoice.get("status") or invoice.get("chargeStatus"))
        if status_invoice not in PAID_CHARGE_STATUSES:
            continue

        try:
            numero_parcela = int(invoice.get("invoiceSequence"))
        except (TypeError, ValueError):
            logger.warning("Invoice paga sem invoiceSequence ignorada no carnê %s: %s", carne_id, invoice)
            continue

        cursor.execute("""
            SELECT id, valor_parcela
            FROM carne_parcelas
            WHERE carne_id = %s
              AND numero_parcela = %s
        """, (carne_id, numero_parcela))
        parcela_row = cursor.fetchone()
        if not parcela_row:
            logger.warning(
                "Invoice paga sequence=%s não encontrou carne_parcela local no carnê %s",
                numero_parcela,
                carne_id,
            )
            continue

        parcela_id, valor_parcela = parcela_row
        resultado["parcelas_pagas_delta"] += 1

        data_pagamento = _charge_payment_datetime(invoice)
        if not data_pagamento:
            resultado["parcelas_pagas_sem_data"] += 1
            logger.warning(
                "Invoice paga sequence=%s do carnê %s ignorada: Delta não enviou paymentDate/paidAt/paymentAt",
                numero_parcela,
                carne_id,
            )
            continue

        valor_pago = _charge_amount(invoice, valor_parcela)
        charge_id = invoice.get("chargeId") or invoice.get("charge_id")

        cursor.execute("""
            UPDATE carne_parcelas
            SET status = 'PAID',
                data_pagamento = COALESCE(data_pagamento, %s),
                valor_pago = COALESCE(valor_pago, %s),
                charge_id = COALESCE(charge_id, %s)
            WHERE id = %s
              AND (
                    UPPER(COALESCE(status, '')) NOT IN ('PAID', 'PAGO')
                    OR data_pagamento IS NULL
                    OR valor_pago IS NULL
                    OR (charge_id IS NULL AND %s IS NOT NULL)
              )
            RETURNING id
        """, (data_pagamento, valor_pago, charge_id, parcela_id, charge_id))
        if cursor.fetchone():
            resultado["carne_parcelas_atualizadas"] += 1
            resultado["parcela_ids"].append(parcela_id)

        cursor.execute("""
            UPDATE venda_parcelas
            SET status_parcela = 'Pago',
                data_pagamento = COALESCE(data_pagamento, %s),
                valor_pago = COALESCE(valor_pago, %s),
                updated_at = CURRENT_TIMESTAMP
            WHERE venda_id IN (
                SELECT id
                FROM vendas
                WHERE carne_id = %s
                UNION
                SELECT venda_id
                FROM carne_pagamento
                WHERE id = %s
                  AND venda_id IS NOT NULL
            )
              AND numero_parcela = %s
              AND status_parcela <> 'Pago'
            RETURNING id
        """, (data_pagamento, valor_pago, carne_id, carne_id, numero_parcela))
        venda_rows = cursor.fetchall()
        if venda_rows:
            resultado["venda_parcelas_atualizadas"] += len(venda_rows)
            if parcela_id not in resultado["parcela_ids"]:
                resultado["parcela_ids"].append(parcela_id)

        if venda_rows:
            logger.info(
                "Parcela %s do carnê %s confirmada via invoices Delta e venda_parcelas baixada",
                numero_parcela,
                carne_id,
            )

    return resultado


def _reconciliar_primeira_parcela_paga_confirmada(cursor, carne_id):
    cursor.execute("""
        SELECT
            cp.id,
            cp.numero_parcela,
            cp.charge_id,
            cp.valor_parcela,
            COALESCE(NULLIF(c.unidade, ''), %s) AS unidade,
            venda_ref.venda_id,
            venda_ref.status_parcela
        FROM carne_parcelas cp
        JOIN carne_pagamento c ON c.id = cp.carne_id
        LEFT JOIN LATERAL (
            SELECT v.id AS venda_id, vp.status_parcela
            FROM vendas v
            LEFT JOIN venda_parcelas vp
              ON vp.venda_id = v.id
             AND vp.numero_parcela = cp.numero_parcela
            WHERE v.carne_id = cp.carne_id
               OR v.id = c.venda_id
            ORDER BY v.id
            LIMIT 1
        ) AS venda_ref ON TRUE
        WHERE cp.carne_id = %s
          AND cp.charge_id IS NOT NULL
          AND (
                UPPER(COALESCE(cp.status, '')) NOT IN ('PAID', 'PAGO')
                OR COALESCE(venda_ref.status_parcela, '') <> 'Pago'
          )
        ORDER BY cp.numero_parcela ASC
        LIMIT %s
    """, (DEFAULT_UNIDADE, carne_id, MAX_CHARGES_TO_CHECK))

    parcelas = cursor.fetchall()

    for parcela in parcelas:
        (
            parcela_id,
            numero_parcela,
            charge_id,
            valor_parcela,
            unidade,
            venda_id,
            status_parcela_venda,
        ) = parcela

        try:
            charge_data = _consultar_charge_delta(unidade, charge_id)
        except Exception as exc:
            logger.warning(
                "Falha ao consultar charge_id=%s do carnê %s na Delta: %s",
                charge_id,
                carne_id,
                exc,
            )
            continue

        charge_status = _normalizar_status(
            charge_data.get("status") or charge_data.get("chargeStatus")
        )
        logger.info(
            "Charge %s da parcela %s do carnê %s retornou status Delta=%s",
            charge_id,
            numero_parcela,
            carne_id,
            charge_status,
        )

        if charge_status not in PAID_CHARGE_STATUSES:
            continue

        data_pagamento = _charge_payment_datetime(charge_data)
        if not data_pagamento:
            logger.warning(
                "Charge %s paga da parcela %s do carnê %s ignorada: Delta não enviou paymentDate/paidAt/paymentAt",
                charge_id,
                numero_parcela,
                carne_id,
            )
            continue

        valor_pago = _charge_amount(charge_data, valor_parcela)

        cursor.execute("""
            UPDATE carne_parcelas
            SET status = 'PAID',
                data_pagamento = COALESCE(data_pagamento, %s),
                valor_pago = COALESCE(valor_pago, %s)
            WHERE id = %s
              AND (
                    UPPER(COALESCE(status, '')) NOT IN ('PAID', 'PAGO')
                    OR data_pagamento IS NULL
                    OR valor_pago IS NULL
              )
            RETURNING id
        """, (data_pagamento, valor_pago, parcela_id))

        carne_parcela_atualizada = cursor.fetchone() is not None
        venda_parcela_atualizada = False

        if venda_id:
            cursor.execute("""
                UPDATE venda_parcelas
                SET status_parcela = 'Pago',
                    data_pagamento = COALESCE(data_pagamento, %s),
                    valor_pago = COALESCE(valor_pago, %s),
                    updated_at = CURRENT_TIMESTAMP
                WHERE venda_id = %s
                  AND numero_parcela = %s
                  AND status_parcela <> 'Pago'
                RETURNING id
            """, (data_pagamento, valor_pago, venda_id, numero_parcela))
            venda_parcela_atualizada = cursor.fetchone() is not None

        if not carne_parcela_atualizada and not venda_parcela_atualizada:
            continue

        logger.info(
            "Parcela %s do carnê %s confirmada pela Delta e conciliada",
            numero_parcela,
            carne_id,
        )
        return True, parcela_id

    return False, None

@router.post("/carne", status_code=status.HTTP_200_OK)
async def carne_webhook(request: Request):
    """
    Rota para receber o webhook de carnês da Bempaggo e:
    1. Salvar os dados do webhook no banco
    2. Atualizar o status do carnê e suas parcelas correspondentes
    3. Registrar logs detalhados para depuração
    """
    logger.info("=== Recebendo webhook de carnê da Bempaggo ===")
    
    try:
        # 1) Lê o corpo como string
        payload_bytes = await request.body()
        payload_str = payload_bytes.decode("utf-8", errors="ignore")
        logger.debug(f"Payload recebido: {payload_str}")

        # 2) Query params (token, status, etc.)
        query_params = dict(request.query_params)
        logger.info(f"Query params: {query_params}")

        # 3) Salvar dados em arquivo JSON para referência
        output_dir = os.getenv("APP_PAYMENTS_DIR", "backend/arquivos/pagamentos")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"carne_webhook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(output_dir, filename)

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

        # 4) Extrair token para identificar o carnê
        token = query_params.get("token")
        logger.info(f"Token extraído: {token}")

        # 5) Processar dados do webhook (suporte a payload "Bempaggo" e JSON estruturado)
        recurring_invoice_id = None
        invoice_id = None
        subscription_id = None
        new_status = None
        data_webhook = datetime.now()
        
        # A Bempaggo envia apenas "Bempaggo" no payload, dados úteis vêm nos query_params
        if payload_str.strip() == "Bempaggo":
            logger.info("Payload Bempaggo padrão detectado - usando query_params como fonte de dados")
            
            # Extrair status dos query params
            order_status = query_params.get("orderStatus", "").upper()
            charge_status = query_params.get("lastChargeStatus", "").upper()
            
            logger.info(f"Status extraído dos query params - OrderStatus: {order_status}, ChargeStatus: {charge_status}")
            
            # Mapear status para status interno baseado nos query params
            if charge_status in PAID_CHARGE_STATUSES or order_status in PAID_CHARGE_STATUSES:
                new_status = 'PAID'
                logger.info("Status de charge pago detectado no webhook")
            elif order_status == "ACTIVE":
                new_status = 'ACTIVE'
            elif order_status in ["CANCELED", "CANCELLED"]:
                new_status = 'CANCELED'
            elif order_status == "OVERDUE":
                new_status = 'OVERDUE'
            elif order_status == "PENDING" and charge_status == "SCHEDULE":
                new_status = 'PENDING_SCHEDULED'
            elif order_status == "PENDING":
                new_status = 'PENDING'
            else:
                # Status não reconhecido
                new_status = f"{order_status}_{charge_status}"
                
            logger.info(f"Status mapeado para sistema interno: {new_status}")
            
        else:
            # Tentar processar como JSON estruturado (para casos futuros)
            try:
                payload_json = json.loads(payload_str)
                logger.info("Payload JSON estruturado detectado - processando dados")
                subscription_id = extract_subscription_id_from_payload(payload_json)
                
                # Extrair informações relevantes do JSON
                if 'data' in payload_json:
                    # Para eventos de carnê
                    if 'recurringInvoiceId' in payload_json['data']:
                        recurring_invoice_id = payload_json['data']['recurringInvoiceId']
                        logger.info(f"Recurring Invoice ID encontrado: {recurring_invoice_id}")
                    
                    # Para eventos de parcela específica
                    if 'invoiceId' in payload_json['data'] or 'id' in payload_json['data']:
                        invoice_id = payload_json['data'].get('invoiceId') or payload_json['data'].get('id')
                        logger.info(f"Invoice ID encontrado: {invoice_id}")
                    
                    # Extrair status do JSON
                    if 'status' in payload_json['data']:
                        webhook_status = payload_json['data']['status']
                        logger.info(f"Status do webhook (JSON): {webhook_status}")
                        
                        # Mapear status da Bempaggo para status interno
                        if webhook_status.upper() in ['PAY', 'PAID']:
                            new_status = 'PAID'
                        elif webhook_status.upper() in ['CANCELLED', 'CANCELED']:
                            new_status = 'CANCELED'
                        elif webhook_status.upper() == 'EXPIRED':
                            new_status = 'EXPIRED'
                        else:
                            new_status = webhook_status
                            
            except json.JSONDecodeError:
                logger.warning(f"Payload não é JSON válido e não é o padrão 'Bempaggo': {payload_str[:100]}...")
                # Usar query params como fallback
                order_status = query_params.get("orderStatus", "UNKNOWN")
                new_status = order_status
        
        # 6) Atualizar o carnê e/ou parcela no banco de dados
        carne_updated = False
        parcela_updated = False
        carne_id = None
        parcela_id = None
        
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Atualizar pelo token (uuid)
            if token:
                cursor.execute(
                    "SELECT id FROM carne_pagamento WHERE uuid = %s",
                    (token,)
                )
                carne_row = cursor.fetchone()
                
                if carne_row:
                    carne_id = carne_row[0]
                    logger.info(f"Carnê encontrado pelo token: ID={carne_id}")
            
            # Se não encontrou pelo token, tenta pelo recurring_invoice_id
            if not carne_id and recurring_invoice_id:
                cursor.execute(
                    "SELECT id FROM carne_pagamento WHERE recurring_invoice_id = %s",
                    (recurring_invoice_id,)
                )
                carne_row = cursor.fetchone()
                
                if carne_row:
                    carne_id = carne_row[0]
                    logger.info(f"Carnê encontrado pelo recurring_invoice_id: ID={carne_id}")

            if carne_id and subscription_id:
                session = SessionLocal()
                try:
                    if save_carne_everest_subscription_id(
                        db=session,
                        carne_id=carne_id,
                        everest_subscription_id=subscription_id,
                    ):
                        logger.info(
                            "everest_subscription_id=%s salvo para carnê %s via webhook",
                            subscription_id,
                            carne_id,
                        )
                except Exception as sync_error:
                    logger.warning(
                        "Erro ao salvar everest_subscription_id via webhook para carnê %s: %s",
                        carne_id,
                        sync_error,
                    )
                finally:
                    session.close()
            
            # Atualizar status agregado do carnê sem transformar ACTIVE em pagamento.
            if carne_id and new_status and new_status != 'PAID':
                cursor.execute(
                    "UPDATE carne_pagamento SET status = %s WHERE id = %s",
                    (new_status, carne_id)
                )
                conn.commit()
                carne_updated = True
                logger.info(f"Status do carnê ID={carne_id} atualizado para: {new_status}")

            # A Delta envia pouco detalhe no webhook; confirmar no provedor antes de pagar.
            # Primeiro consultamos o estado completo das invoices do carnê; se indisponível,
            # mantemos o fallback antigo por charge_id local.
            if carne_id:
                bulk_result = _reconciliar_parcelas_pagas_por_invoices(cursor, carne_id)
                parcela_updated = (
                    bulk_result["carne_parcelas_atualizadas"] > 0
                    or bulk_result["venda_parcelas_atualizadas"] > 0
                )
                parcela_id = bulk_result["parcela_ids"][0] if bulk_result["parcela_ids"] else None

                if bulk_result["invoices_consultadas"] > 0:
                    if parcela_updated:
                        conn.commit()
                    logger.info(
                        "Carnê ID=%s conciliado via invoices Delta: invoices=%s, pagas_delta=%s, carne_parcelas_atualizadas=%s, venda_parcelas_atualizadas=%s, pagas_sem_data=%s",
                        carne_id,
                        bulk_result["invoices_consultadas"],
                        bulk_result["parcelas_pagas_delta"],
                        bulk_result["carne_parcelas_atualizadas"],
                        bulk_result["venda_parcelas_atualizadas"],
                        bulk_result["parcelas_pagas_sem_data"],
                    )
                elif new_status not in TERMINAL_CHARGE_STATUSES:
                    parcela_updated, parcela_id = _reconciliar_primeira_parcela_paga_confirmada(cursor, carne_id)
                    if parcela_updated:
                        conn.commit()
                        logger.info(f"Carnê ID={carne_id}: parcela {parcela_id} conciliada como paga pela Delta")
                    else:
                        logger.info(
                            "Carnê ID=%s sem parcela paga confirmada pela Delta neste webhook",
                            carne_id,
                        )
                else:
                    logger.info(
                        "Carnê ID=%s não conciliado por invoices; fallback ignorado para status terminal %s. Erro bulk=%s",
                        carne_id,
                        new_status,
                        bulk_result["erro"],
                    )
            
            # Verificar se todas as parcelas foram pagas depois de qualquer conciliação.
            if carne_id and parcela_updated:
                cursor.execute(
                    "SELECT COUNT(*) FROM carne_parcelas WHERE carne_id = %s AND status != 'PAID'",
                    (carne_id,)
                )
                pendentes = cursor.fetchone()[0]
                
                if pendentes == 0:
                    cursor.execute(
                        "UPDATE carne_pagamento SET status = 'COMPLETED' WHERE id = %s",
                        (carne_id,)
                    )
                    conn.commit()
                    logger.info(f"Todas as parcelas do carnê ID={carne_id} foram pagas. Status atualizado para COMPLETED.")

        return {
            "detail": "OK", 
            "carne_updated": carne_updated if 'carne_updated' in locals() else False,
            "carne_id": carne_id if 'carne_id' in locals() else None,
            "parcela_updated": parcela_updated if 'parcela_updated' in locals() else False,
            "parcela_id": parcela_id if 'parcela_id' in locals() else None,
            "bulk_result": bulk_result if 'bulk_result' in locals() else None,
            "new_status": new_status if 'new_status' in locals() else None
        }
    
    except Exception as e:
        error_msg = f"Erro ao processar webhook de carnê: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Salvar o erro em um arquivo separado para facilitar a depuração
        error_file = os.path.join(log_dir, f"carne_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(f"Erro: {str(e)}\n\n")
            f.write(f"Traceback:\n{traceback.format_exc()}\n\n")
            
            # Tentar salvar também os dados da requisição
            try:
                f.write(f"Query params: {dict(request.query_params)}\n")
                f.write(f"Headers: {dict(request.headers)}\n")
                payload = await request.body()
                f.write(f"Payload: {payload.decode('utf-8', errors='ignore')}\n")
            except Exception as req_err:
                f.write(f"Erro ao capturar dados da requisição: {str(req_err)}\n")
        
        # Retornar erro 500 com mensagem
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar webhook de carnê: {str(e)}"
        )
