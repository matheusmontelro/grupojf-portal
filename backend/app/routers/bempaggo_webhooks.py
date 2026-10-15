import os
import json
import logging
import traceback
from datetime import datetime
from fastapi import APIRouter, Request, status, HTTPException

# Classe Pydantic para validar/organizar os dados do webhook
from app.models.bempaggo_webhooks import BempaggoCreate
# Pool de conexões psycopg2 + context manager
from app.database.db import DatabaseConnection

# Configuração de logs
log_dir = os.getenv("APP_LOG_DIR", "backend/arquivos/logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "bempaggo_webhook.log")

# Configurar o logger
logger = logging.getLogger("bempaggo_webhook")
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


@router.post("/bempaggo", status_code=status.HTTP_200_OK)
async def bempaggo_webhook(request: Request):
    """
    Rota para receber o webhook da Bempaggo e:
    1. Salvar os dados do webhook no banco
    2. Atualizar o status do boleto correspondente
    3. Registrar logs detalhados para depuração
    """
    logger.info("=== Recebendo webhook da Bempaggo ===")
    
    try:
        # 1) Lê o corpo como string
        payload_bytes = await request.body()
        payload_str = payload_bytes.decode("utf-8", errors="ignore")
        logger.debug(f"Payload recebido: {payload_str}")

        # 2) Query params (token, orderStatus, etc.)
        query_params = dict(request.query_params)
        logger.info(f"Query params: {query_params}")

        # 3) Monta o dicionário com dados
        data_to_save = {
            "request_timestamp": datetime.now(),
            "token": query_params.get("token"),
            "order_status": query_params.get("orderStatus"),
            "last_charge_status": query_params.get("lastChargeStatus"),
            "body": payload_str
        }
        logger.debug(f"Dados preparados para salvar: {data_to_save}")

        # Salvar em arquivo local JSON
        output_dir = os.getenv("APP_PAYMENTS_DIR", "backend/arquivos/pagamentos")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"webhook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(output_dir, filename)

        logger.info(f"Salvando JSON em: {filepath}")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": data_to_save["request_timestamp"].isoformat(),
                    "query_params": query_params,
                    "body": payload_str
                },
                f,
                indent=2,
                ensure_ascii=False
            )
        logger.info(f"JSON salvo com sucesso em: {filepath}")

        # 4) Validar/transformar usando Pydantic
        logger.debug("Validando dados com Pydantic")
        bempaggo_obj = BempaggoCreate(**data_to_save)

        # 5) Inserir no banco usando psycopg2 (DatabaseConnection)
        logger.info("Inserindo no banco de dados (tabela bempaggo_webhooks)")
        webhook_id = None
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO bempaggo_webhooks (request_timestamp, token, order_status, last_charge_status, body)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    datetime.now(),  # Adicionar este valor explicitamente
                    bempaggo_obj.token,
                    bempaggo_obj.order_status,
                    bempaggo_obj.last_charge_status,
                    bempaggo_obj.body
                    # Não precisamos fornecer created_at, pois tem CURRENT_TIMESTAMP como padrão
                )
            )
            webhook_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Webhook salvo no banco com ID: {webhook_id}")

        # 6) NOVO: Atualizar o status do boleto usando o token do webhook
        boleto_updated = False
        boleto_id = None
        
        if bempaggo_obj.token:
            logger.info(f"Tentando atualizar boleto com token: {bempaggo_obj.token}")
            
            # Determinar o novo status com base no last_charge_status
            # Mapeie os status da Bempaggo para os status do seu banco
            new_status = None
            if bempaggo_obj.last_charge_status:
                if bempaggo_obj.last_charge_status.upper() in ['PAY', 'PAID']:
                    new_status = 'PAY'  # Status para boleto pago
                elif bempaggo_obj.last_charge_status.upper() in ['CANCELLED', 'CANCELED']:
                    new_status = 'CANCELED'  # Status para boleto cancelado
                elif bempaggo_obj.last_charge_status.upper() == 'EXPIRED':
                    new_status = 'EXPIRED'  # Status para boleto expirado
                else:
                    # Para outros status, use o próprio lastChargeStatus
                    new_status = bempaggo_obj.last_charge_status
            
            if new_status:
                try:
                    with DatabaseConnection() as conn:
                        cursor = conn.cursor()
                        
                        # Primeiro busca o boleto pelo token para verificar
                        cursor.execute(
                            "SELECT id, status FROM boletos WHERE uuid = %s",
                            (bempaggo_obj.token,)
                        )
                        boleto = cursor.fetchone()
                        
                        if boleto:
                            boleto_id = boleto[0]
                            current_status = boleto[1]
                            
                            logger.info(f"Boleto encontrado: ID={boleto_id}, Status Atual={current_status}")
                            
                            # Só atualiza se o status for diferente
                            if current_status != new_status:
                                cursor.execute(
                                    "UPDATE boletos SET status = %s WHERE id = %s",
                                    (new_status, boleto_id)
                                )
                                conn.commit()
                                boleto_updated = True
                                logger.info(f"Status do boleto ID={boleto_id} atualizado: {current_status} -> {new_status}")
                            else:
                                logger.info(f"Boleto ID={boleto_id} já está com status '{current_status}'. Nenhuma atualização necessária.")
                        else:
                            logger.warning(f"Nenhum boleto encontrado com token={bempaggo_obj.token}")
                
                except Exception as db_err:
                    logger.error(f"Erro ao atualizar boleto: {str(db_err)}")
                    logger.error(traceback.format_exc())
        else:
            logger.warning("Token não recebido no webhook. Não é possível atualizar boleto.")

        # 7) Verificar se há referência ao pedido no payload JSON para atualização adicional
        try:
            # Tenta analisar o body como JSON
            payload_json = json.loads(payload_str)
            
            # Verifica se há order.reference no payload para encontrar boletos por order_reference
            order_reference = None
            if 'data' in payload_json and 'order' in payload_json['data'] and 'reference' in payload_json['data']['order']:
                order_reference = payload_json['data']['order']['reference']
                charge_id = payload_json['data'].get('id')
                
                logger.info(f"Encontrada referência de pedido no payload: {order_reference}, ChargeID: {charge_id}")
                
                if order_reference and new_status:
                    try:
                        with DatabaseConnection() as conn:
                            cursor = conn.cursor()
                            
                            # Atualizar boleto pelo order_reference se ainda não atualizamos pelo token
                            if not boleto_updated:
                                cursor.execute(
                                    "UPDATE boletos SET status = %s WHERE order_reference = %s RETURNING id",
                                    (new_status, order_reference)
                                )
                                updated = cursor.fetchone()
                                
                                if updated:
                                    boleto_id = updated[0]
                                    conn.commit()
                                    boleto_updated = True
                                    logger.info(f"Status do boleto ID={boleto_id} atualizado via order_reference={order_reference}: -> {new_status}")
                            
                            # Se temos o charge_id, atualizamos este campo também para referência futura
                            if charge_id:
                                cursor.execute(
                                    "UPDATE boletos SET charge_id = %s WHERE order_reference = %s",
                                    (charge_id, order_reference)
                                )
                                conn.commit()
                                logger.info(f"ChargeID atualizado para boleto com order_reference={order_reference}")
                    
                    except Exception as db_err:
                        logger.error(f"Erro ao atualizar boleto por order_reference: {str(db_err)}")
                        logger.error(traceback.format_exc())
        
        except json.JSONDecodeError:
            logger.warning("Não foi possível decodificar o payload como JSON para análise adicional")
        except Exception as e:
            logger.error(f"Erro ao processar payload JSON: {str(e)}")
            logger.error(traceback.format_exc())

        return {
            "detail": "OK", 
            "webhook_id": webhook_id,
            "boleto_updated": boleto_updated,
            "boleto_id": boleto_id,
            "new_status": new_status if 'new_status' in locals() else None
        }
    
    except Exception as e:
        error_msg = f"Erro ao processar webhook: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Salvar o erro em um arquivo separado para facilitar a depuração
        error_file = os.path.join(log_dir, f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
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
            detail=f"Erro interno ao processar webhook: {str(e)}"
        )
