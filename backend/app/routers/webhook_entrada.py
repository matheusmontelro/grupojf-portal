# backend/app/routers/webhook_entrada.py

import logging
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Import database and models
from ..database.db import get_db
from ..models.pre_venda_entrada import PreVendaEntrada

logger = logging.getLogger(__name__)

# Configurar logger para arquivo
file_handler = logging.FileHandler(os.path.join(os.getenv("APP_LOG_DIR", "backend/arquivos/logs"), "entrada_webhook.log"))
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Schemas
class WebhookEntradaPayload(BaseModel):
    """Payload do webhook de confirmação de pagamento da entrada"""
    event_type: str
    transaction_id: str
    payment_status: str
    amount: Decimal = Field(..., decimal_places=2)
    metadata: Dict[str, Any]
    customer_info: Optional[Dict[str, Any]] = None
    payment_method: Optional[str] = None
    paid_at: Optional[datetime] = None

# Router
router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks - Entrada"]
)

def verificar_assinatura_webhook(
    payload: str,
    signature: str,
    secret: str = "SEU_WEBHOOK_SECRET"  # TODO: Mover para variável de ambiente
) -> bool:
    """
    Verifica a assinatura do webhook para garantir que veio da Delta.
    
    TODO: Implementar verificação real com HMAC-SHA256
    """
    # Por enquanto, retorna True. Em produção, implementar verificação real
    return True

@router.post("/entrada/delta")
async def webhook_entrada_delta(
    request: Request,
    pre_venda_id: Optional[str] = None,  # Query parameter
    orderStatus: Optional[str] = None,   # Query parameter
    lastChargeStatus: Optional[str] = None,  # Query parameter
    x_webhook_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Webhook chamado pela Delta quando um pagamento de entrada é confirmado.
    
    A Delta envia os dados como query parameters e/ou no body JSON.
    """
    # Log detalhado da requisição
    log_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pre_venda_id": pre_venda_id,
        "orderStatus": orderStatus,
        "lastChargeStatus": lastChargeStatus,
        "headers": dict(request.headers),
        "query_params": dict(request.query_params),
        "method": request.method,
        "url": str(request.url)
    }
    
    logger.info(f"=== WEBHOOK ENTRADA DELTA RECEBIDO ===")
    logger.info(f"Dados da requisição: {json.dumps(log_data, indent=2)}")
    logger.info(f"Webhook Delta recebido - pre_venda_id: {pre_venda_id}, orderStatus: {orderStatus}, lastChargeStatus: {lastChargeStatus}")
    
    try:
        # Validar que temos o pre_venda_id
        if not pre_venda_id:
            logger.error("pre_venda_id não fornecido")
            return {"status": "error", "reason": "pre_venda_id missing"}
            
        # Tentar ler o corpo da requisição se houver
        body_data = {}
        try:
            body = await request.body()
            if body:
                body_data = json.loads(body)
                logger.info(f"Body do webhook: {body_data}")
        except:
            logger.info("Nenhum body JSON encontrado, usando apenas query params")
        
        # Verificar status do pagamento
        charge_status = lastChargeStatus or body_data.get('lastChargeStatus', '')
        order_status = orderStatus or body_data.get('orderStatus', '')
        
        logger.info(f"Status recebido - charge: {charge_status}, order: {order_status}")
        
        failed_statuses = {'FAIL', 'FAILED', 'NOT_AUTHORIZED', 'NOT_APPROVED'}
        charge_status_normalizado = (charge_status or '').upper()
        order_status_normalizado = (order_status or '').upper()
        if charge_status_normalizado in failed_statuses or order_status_normalizado in failed_statuses:
            pre_venda = db.query(PreVendaEntrada).filter(
                PreVendaEntrada.pre_venda_id == pre_venda_id
            ).first()

            if not pre_venda:
                logger.error(f"Pré-venda {pre_venda_id} não encontrada")
                return {"status": "error", "reason": "pre_venda not found"}

            if pre_venda.status != 'pago':
                pre_venda.status = 'cancelado'
                pre_venda.updated_at = datetime.now(timezone.utc)
                metadata = dict(pre_venda.metadata_json or {})
                metadata.update({
                    'webhook_received_at': datetime.now(timezone.utc).isoformat(),
                    'order_status': order_status,
                    'charge_status': charge_status,
                    'motivo_cancelamento': 'Falha retornada pela Delta no pagamento da entrada',
                    'webhook_body': body_data
                })
                pre_venda.metadata_json = metadata
                db.commit()
                logger.info(
                    f"Pré-venda {pre_venda_id} marcada como CANCELADA por falha de pagamento. "
                    f"charge={charge_status}, order={order_status}"
                )

            return {
                "status": "failed",
                "message": "Payment failed; pre-sale canceled",
                "pre_venda_id": pre_venda_id
            }

        # A Delta envia PAY ou PAID quando o pagamento é confirmado
        valid_paid_statuses = ['PAID', 'PAY', 'COMPLETED', 'SUCCESS']
        if charge_status not in valid_paid_statuses and order_status not in valid_paid_statuses:
            logger.info(f"Pagamento ainda não confirmado: charge={charge_status}, order={order_status}")
            return {"status": "ignored", "reason": "not paid yet"}
        
        # Buscar pré-venda
        pre_venda = db.query(PreVendaEntrada).filter(
            PreVendaEntrada.pre_venda_id == pre_venda_id
        ).first()
        
        if not pre_venda:
            logger.error(f"Pré-venda {pre_venda_id} não encontrada")
            return {"status": "error", "reason": "pre_venda not found"}
        
        # Verificar se já foi processada
        if pre_venda.status == 'pago':
            logger.info(f"Pré-venda {pre_venda_id} já estava paga")
            return {"status": "success", "message": "already processed"}
        
        # Extrair informações do pagamento
        paid_amount = body_data.get('paidAmount')
        if paid_amount:
            # Converter de centavos para decimal
            valor_pago = Decimal(paid_amount) / 100
        else:
            # Se não veio o valor, usar o valor solicitado
            valor_pago = pre_venda.valor_solicitado
            
        charge_id = body_data.get('chargeId') or body_data.get('orderId')
        
        # Atualizar status da pré-venda
        pre_venda.status = 'pago'
        pre_venda.valor_pago = valor_pago
        if charge_id:
            pre_venda.checkout_id = str(charge_id)
        pre_venda.updated_at = datetime.now(timezone.utc)
        
        # Adicionar informações extras ao metadata
        pre_venda.metadata_json = pre_venda.metadata_json or {}
        pre_venda.metadata_json.update({
            'webhook_received_at': datetime.now(timezone.utc).isoformat(),
            'order_status': order_status,
            'charge_status': charge_status,
            'webhook_body': body_data
        })
        
        db.commit()
        
        # Log detalhado do sucesso
        success_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "PAGAMENTO_CONFIRMADO",
            "pre_venda_id": pre_venda_id,
            "valor_pago": str(valor_pago),
            "charge_id": charge_id,
            "order_status": order_status,
            "charge_status": charge_status,
            "metadata": pre_venda.metadata_json
        }
        
        logger.info(f"=== PAGAMENTO DE ENTRADA CONFIRMADO ===")
        logger.info(json.dumps(success_log, indent=2))
        logger.info(
            f"Pré-venda {pre_venda_id} atualizada para PAGO. "
            f"Valor: {valor_pago}, Charge ID: {charge_id}"
        )
        
        return {
            "status": "success",
            "message": "Payment confirmed",
            "pre_venda_id": pre_venda_id
        }
        
    except Exception as e:
        logger.error(f"Erro ao processar webhook Delta: {str(e)}", exc_info=True)
        db.rollback()
        
        # Retornar erro 500 para que a Delta tente novamente
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar webhook: {str(e)}"
        )

@router.post("/entrada/status-check")
async def webhook_status_check(
    db: Session = Depends(get_db)
):
    """
    Endpoint de verificação de saúde do webhook.
    
    Usado pela Delta para verificar se o endpoint está funcionando.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "webhook_entrada"
    }

# Schema para o formato real da Delta
class DeltaWebhookPayload(BaseModel):
    """Payload real enviado pela Delta"""
    orderId: Optional[int] = None
    orderStatus: Optional[str] = None
    lastChargeStatus: Optional[str] = None
    chargeId: Optional[int] = None
    paidAmount: Optional[int] = None  # Valor em centavos
    metadata: Optional[Dict[str, Any]] = None

@router.post("/entrada/delta-real")
async def webhook_entrada_delta_real(
    pre_venda_id: str,  # Vem como query parameter
    orderStatus: Optional[str] = None,
    lastChargeStatus: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Webhook real da Delta - recebe dados como query parameters e/ou JSON body.
    """
    logger.info(f"Webhook Delta real recebido - pre_venda_id: {pre_venda_id}, orderStatus: {orderStatus}, lastChargeStatus: {lastChargeStatus}")
    
    try:
        # Tentar ler o corpo da requisição se houver
        body_data = {}
        try:
            body = await request.body()
            if body:
                body_data = json.loads(body)
                logger.info(f"Body do webhook: {body_data}")
        except:
            logger.info("Nenhum body JSON encontrado, usando apenas query params")
        
        # Verificar status do pagamento
        charge_status = lastChargeStatus or body_data.get('lastChargeStatus', '')
        order_status = orderStatus or body_data.get('orderStatus', '')
        
        failed_statuses = {'FAIL', 'FAILED', 'NOT_AUTHORIZED', 'NOT_APPROVED'}
        charge_status_normalizado = (charge_status or '').upper()
        order_status_normalizado = (order_status or '').upper()
        if charge_status_normalizado in failed_statuses or order_status_normalizado in failed_statuses:
            pre_venda = db.query(PreVendaEntrada).filter(
                PreVendaEntrada.pre_venda_id == pre_venda_id
            ).first()

            if not pre_venda:
                logger.error(f"Pré-venda {pre_venda_id} não encontrada")
                return {"status": "error", "reason": "pre_venda not found"}

            if pre_venda.status != 'pago':
                pre_venda.status = 'cancelado'
                pre_venda.updated_at = datetime.now(timezone.utc)
                metadata = dict(pre_venda.metadata_json or {})
                metadata.update({
                    'webhook_received_at': datetime.now(timezone.utc).isoformat(),
                    'order_status': order_status,
                    'charge_status': charge_status,
                    'motivo_cancelamento': 'Falha retornada pela Delta no pagamento da entrada',
                    'webhook_body': body_data
                })
                pre_venda.metadata_json = metadata
                db.commit()
                logger.info(
                    f"Pré-venda {pre_venda_id} marcada como CANCELADA por falha de pagamento. "
                    f"charge={charge_status}, order={order_status}"
                )

            return {
                "status": "failed",
                "message": "Payment failed; pre-sale canceled",
                "pre_venda_id": pre_venda_id
            }

        # A Delta envia PAY ou PAID quando o pagamento é confirmado
        valid_paid_statuses = ['PAID', 'PAY', 'COMPLETED', 'SUCCESS']
        if charge_status not in valid_paid_statuses and order_status not in valid_paid_statuses:
            logger.info(f"Status ainda não é pago: charge={charge_status}, order={order_status}")
            return {"status": "ignored", "reason": "not paid yet"}
        
        # Buscar pré-venda
        pre_venda = db.query(PreVendaEntrada).filter(
            PreVendaEntrada.pre_venda_id == pre_venda_id
        ).first()
        
        if not pre_venda:
            logger.error(f"Pré-venda {pre_venda_id} não encontrada")
            return {"status": "error", "reason": "pre_venda not found"}
        
        # Verificar se já foi processada
        if pre_venda.status == 'pago':
            logger.info(f"Pré-venda {pre_venda_id} já estava paga")
            return {"status": "success", "message": "already processed"}
        
        # Extrair informações do pagamento
        paid_amount = body_data.get('paidAmount')
        if paid_amount:
            # Converter de centavos para decimal
            valor_pago = Decimal(paid_amount) / 100
        else:
            # Se não veio o valor, usar o valor solicitado
            valor_pago = pre_venda.valor_solicitado
            
        charge_id = body_data.get('chargeId') or body_data.get('orderId')
        
        # Atualizar status da pré-venda
        pre_venda.status = 'pago'
        pre_venda.valor_pago = valor_pago
        if charge_id:
            pre_venda.checkout_id = str(charge_id)
        pre_venda.updated_at = datetime.now(timezone.utc)
        
        # Adicionar informações extras ao metadata
        pre_venda.metadata_json = pre_venda.metadata_json or {}
        pre_venda.metadata_json.update({
            'webhook_received_at': datetime.now(timezone.utc).isoformat(),
            'order_status': order_status,
            'charge_status': charge_status,
            'webhook_body': body_data
        })
        
        db.commit()
        
        # Log detalhado do sucesso
        success_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "PAGAMENTO_CONFIRMADO",
            "pre_venda_id": pre_venda_id,
            "valor_pago": str(valor_pago),
            "charge_id": charge_id,
            "order_status": order_status,
            "charge_status": charge_status,
            "metadata": pre_venda.metadata_json
        }
        
        logger.info(f"=== PAGAMENTO DE ENTRADA CONFIRMADO ===")
        logger.info(json.dumps(success_log, indent=2))
        logger.info(
            f"Pré-venda {pre_venda_id} atualizada para PAGO. "
            f"Valor: {valor_pago}, Charge ID: {charge_id}"
        )
        
        return {
            "status": "success",
            "message": "Payment confirmed",
            "pre_venda_id": pre_venda_id
        }
        
    except Exception as e:
        logger.error(f"Erro ao processar webhook Delta: {str(e)}", exc_info=True)
        db.rollback()
        
        # Retornar erro 500 para que a Delta tente novamente
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar webhook: {str(e)}"
        )

# Função auxiliar para processar webhooks de outros gateways
@router.post("/entrada/{gateway}")
async def webhook_entrada_generico(
    gateway: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook genérico para outros gateways de pagamento.
    
    Cada gateway tem seu formato específico, então este endpoint
    serve como ponto de entrada para implementações futuras.
    """
    logger.info(f"Webhook genérico recebido para gateway: {gateway}")
    
    # Por enquanto, retornar não implementado
    raise HTTPException(
        status_code=501,
        detail=f"Gateway {gateway} não implementado"
    )
