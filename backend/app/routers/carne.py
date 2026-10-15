# app/routers/carne.py
import re
import uuid
import logging
import traceback
import os
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
import requests
from fastapi.responses import HTMLResponse
from ..services.split_service import SplitService

from fastapi import APIRouter, HTTPException, status, Query
from ..carne_sdk.customer_manager import CustomerManager
from ..carne_sdk.environment import Environment
from ..carne_sdk.sdk import CarneSDK
from ..carne_sdk.split_manager import SplitManager
from ..carne_sdk.sdk_utils import get_token_and_seller_for_unidade
from ..database.db import DatabaseConnection, SessionLocal
from ..delta_recorrente_sdk.environment import DeltaConfig
from ..services.everest_subscription_service import (
    find_matching_everest_subscription,
    save_carne_everest_subscription_id,
)
from ..services.venda_akimais_service import sync_venda_akimais_flags_conn

from ..models.carne import (
    CarneCreateRequest,
    CarneResponseItem,
    CarneDetalhado,
    CarneParcela,
    CarneSplit,
    CarneUpdateStatus
)

logger = logging.getLogger(__name__)

# Determinar o ambiente baseado na variável ENVIRONMENT
def get_current_environment():
    """Retorna 'production' se ENVIRONMENT='production', senão 'sandbox'"""
    env = os.getenv("ENVIRONMENT", "sandbox").lower()
    return "production" if env == "production" else "sandbox"
router = APIRouter(prefix="/carne", tags=["carne"])

def _metadata_to_dict(metadata_json):
    if isinstance(metadata_json, dict):
        return metadata_json
    if isinstance(metadata_json, str):
        try:
            return json.loads(metadata_json)
        except json.JSONDecodeError:
            return {}
    return {}

def _pre_venda_exige_odontograma(tipo_odontograma: Optional[str]) -> bool:
    return tipo_odontograma not in {"Taxa de Adesão"}

def criar_venda_automatica_pos_carne(
    carne_id: int,
    pre_venda,
    tipo_odontograma_id: int,
    paciente_id: int,
    dependente_id: Optional[int],
    dentista_id: int,
    odontograma_id: Optional[int],
    unidade: str,
    valor_total: Decimal,
    valor_parcela: Decimal,
    qtd_parcelas: int,
    usuario_id: int,
    carne_uuid: str,
    conn
) -> Optional[int]:
    """
    Cria uma venda automaticamente após a emissão bem-sucedida do carnê.
    Usada quando há uma pré-venda com entrada paga.
    """
    try:
        cursor = conn.cursor()
        metadata = _metadata_to_dict(getattr(pre_venda, "metadata_json", None))
        if not odontograma_id and metadata.get("odontograma_id"):
            odontograma_id = int(metadata["odontograma_id"])
        
        # Determinar o tipo de venda baseado no tipo_odontograma_id
        if not tipo_odontograma_id:
            raise ValueError(
                f"Pré-venda {pre_venda.pre_venda_id} sem tipo_odontograma_id; venda automática não será criada como genérica."
            )

        cursor.execute("""
            SELECT nome FROM tipos_odontograma WHERE id = %s
        """, (tipo_odontograma_id,))
        tipo_result = cursor.fetchone()
        if not tipo_result:
            raise ValueError(
                f"tipo_odontograma_id {tipo_odontograma_id} inválido para a pré-venda {pre_venda.pre_venda_id}."
            )

        tipo_venda = tipo_result[0]
        if _pre_venda_exige_odontograma(tipo_venda) and not odontograma_id:
            raise ValueError(
                f"Pré-venda {pre_venda.pre_venda_id} do tipo '{tipo_venda}' sem odontograma_id; venda automática bloqueada."
            )
        
        # Gerar documento da venda
        documento_venda = f"VND-{carne_uuid}"
        
        # Criar a venda
        cursor.execute("""
            INSERT INTO vendas (
                documento_venda, paciente_id, dentista_orcamentista_id, 
                odontograma_id, unidade, data_venda, valor_bruto_total, 
                valor_desconto_regra, valor_desconto_solicitado, 
                valor_desconto_aprovado, valor_liquido_total, qtd_parcelas, 
                usuario_venda_id, status_venda, tipo_venda, dependente_id,
                valor_entrada, tipo_cobranca_inicial, pre_venda_id
            ) VALUES (
                %s, %s, %s, %s, %s, NOW(), %s, 0, 0, 0, %s, %s, %s, 
                'Efetuada', %s, %s, %s, 'entrada', %s
            ) RETURNING id
        """, (
            documento_venda,
            paciente_id,
            dentista_id,
            odontograma_id,
            unidade,
            valor_total,
            valor_total,
            qtd_parcelas,
            usuario_id,
            tipo_venda,
            dependente_id,
            pre_venda.valor_pago,
            pre_venda.pre_venda_id
        ))
        
        venda_id = cursor.fetchone()[0]
        logger.info(f"Venda criada automaticamente com ID: {venda_id} vinculada à pré-venda: {pre_venda.pre_venda_id}")
        
        # Fazer linkagem bidirecional entre venda e carnê
        cursor.execute("""
            UPDATE carne_pagamento SET venda_id = %s WHERE id = %s
        """, (venda_id, carne_id))

        cursor.execute("""
            UPDATE vendas SET carne_id = %s WHERE id = %s  
        """, (carne_id, venda_id))

        logger.info(f"Linkagem estabelecida: Venda {venda_id} ↔ Carnê {carne_id}")

        sync_venda_akimais_flags_conn(
            conn=conn,
            venda_id=venda_id,
            pre_venda_id=pre_venda.pre_venda_id,
            carne_id=carne_id,
        )
        
        # Criar parcela 0 (entrada)
        # Para boleto pendente, usar valor_solicitado e marcar como Pendente
        if pre_venda.status == 'pendente' and pre_venda.valor_pago is None:
            # Buscar o valor solicitado da pré-venda
            cursor.execute("""
                SELECT valor_solicitado FROM pre_vendas_entradas WHERE pre_venda_id = %s
            """, (pre_venda.pre_venda_id,))
            valor_solicitado_result = cursor.fetchone()
            valor_entrada = valor_solicitado_result[0] if valor_solicitado_result else 0
            
            cursor.execute("""
                INSERT INTO venda_parcelas (
                    venda_id, numero_parcela, valor_parcela, data_vencimento,
                    status_parcela, documento_referencia, forma_pagamento_id
                ) VALUES (
                    %s, 0, %s, CURRENT_DATE, 'Pendente', %s, %s
                )
            """, (
                venda_id,
                valor_entrada,
                f"{documento_venda}/00",
                pre_venda.forma_pagamento_id
            ))
            logger.info(f"Parcela de entrada criada como PENDENTE para boleto não compensado. Valor: {valor_entrada}")
        else:
            # Caso normal - entrada já paga
            cursor.execute("""
                INSERT INTO venda_parcelas (
                    venda_id, numero_parcela, valor_parcela, data_vencimento,
                    status_parcela, documento_referencia, forma_pagamento_id,
                    data_pagamento, valor_pago
                ) VALUES (
                    %s, 0, %s, CURRENT_DATE, 'Pago', %s, %s, NOW(), %s
                )
            """, (
                venda_id,
                pre_venda.valor_pago,
                f"{documento_venda}/00",
                pre_venda.forma_pagamento_id,
                pre_venda.valor_pago
            ))
        
        # Criar as parcelas do carnê (1 até N)
        for i in range(qtd_parcelas):
            # Calcular data de vencimento baseado no carnê já criado
            cursor.execute("""
                SELECT data_vencimento FROM carne_parcelas 
                WHERE carne_id = %s AND numero_parcela = %s
            """, (carne_id, i + 1))
            
            data_venc_result = cursor.fetchone()
            data_vencimento = data_venc_result[0] if data_venc_result else None
            
            if not data_vencimento:
                # Fallback: calcular data com base no mês
                from datetime import date
                from dateutil.relativedelta import relativedelta
                data_vencimento = date.today() + relativedelta(months=i+1)
            
            cursor.execute("""
                INSERT INTO venda_parcelas (
                    venda_id, numero_parcela, valor_parcela, data_vencimento,
                    status_parcela, documento_referencia
                ) VALUES (
                    %s, %s, %s, %s, 'Pendente', %s
                )
            """, (
                venda_id,
                i + 1,
                valor_parcela,
                data_vencimento,
                f"{documento_venda}/{i+1:02}"
            ))
        
        # Commit da transação
        conn.commit()
        logger.info(f"Venda {venda_id} criada automaticamente após emissão do carnê {carne_id}")
        
        return venda_id
        
    except Exception as e:
        logger.error(f"Erro ao criar venda automaticamente: {e}")
        if conn and not conn.autocommit:
            conn.rollback()
        return None

def _verificar_se_contrato_existe(contrato_id: int) -> bool:
    """
    Retorna True se o contrato existir, False caso contrário.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT contrato_id FROM contratos WHERE contrato_id = %s", (contrato_id,))
        row = cursor.fetchone()
    return bool(row)

def _hidratar_dados_pre_venda_no_carne(data: CarneCreateRequest) -> None:
    """
    Quando o carnê vem de uma pré-venda, o frontend pode enviar tipo/odontograma
    vazios. Preencher esses campos aqui evita cair no split padrão do payload.
    """
    pre_venda_id = getattr(data, "pre_venda_id", None)
    if not pre_venda_id:
        return

    precisa_tipo = not getattr(data, "tipo_odontograma_id", None)
    precisa_odontograma = not getattr(data, "odontograma_id", None)
    if not precisa_tipo and not precisa_odontograma:
        return

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pve.tipo_odontograma, pve.metadata_json, t.id
                FROM pre_vendas_entradas pve
                LEFT JOIN tipos_odontograma t ON t.nome = pve.tipo_odontograma
                WHERE pve.pre_venda_id = %s
            """, (pre_venda_id,))
            row = cursor.fetchone()

        if not row:
            logger.warning("Pré-venda %s não encontrada para hidratar dados do carnê", pre_venda_id)
            raise HTTPException(
                status_code=400,
                detail=f"Pré-venda {pre_venda_id} não encontrada. Carnê bloqueado para evitar venda genérica."
            )

        tipo_nome, metadata_json, tipo_odontograma_id = row

        if precisa_tipo and tipo_odontograma_id:
            data.tipo_odontograma_id = int(tipo_odontograma_id)
            logger.info(
                "Tipo de odontograma hidratado pela pré-venda %s: %s (%s)",
                pre_venda_id,
                data.tipo_odontograma_id,
                tipo_nome,
            )

        metadata = _metadata_to_dict(metadata_json)

        odontograma_id = metadata.get("odontograma_id") if isinstance(metadata, dict) else None
        if precisa_odontograma and odontograma_id:
            data.odontograma_id = int(odontograma_id)
            logger.info(
                "Odontograma hidratado pela pré-venda %s: %s",
                pre_venda_id,
                data.odontograma_id,
            )

        if precisa_tipo and not getattr(data, "tipo_odontograma_id", None):
            logger.warning("Pré-venda %s não permitiu resolver tipo_odontograma_id", pre_venda_id)
            raise HTTPException(
                status_code=400,
                detail=f"Pré-venda {pre_venda_id} sem tipo de odontograma. Carnê bloqueado para evitar venda genérica."
            )

        if (
            precisa_odontograma
            and _pre_venda_exige_odontograma(tipo_nome)
            and not getattr(data, "odontograma_id", None)
        ):
            logger.warning("Pré-venda %s não permitiu resolver odontograma_id", pre_venda_id)
            raise HTTPException(
                status_code=400,
                detail=f"Pré-venda {pre_venda_id} sem odontograma. Carnê bloqueado para evitar venda genérica."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Erro ao hidratar dados da pré-venda %s no carnê: %s", pre_venda_id, e)
        raise HTTPException(
            status_code=400,
            detail=f"Não foi possível validar a pré-venda {pre_venda_id}. Carnê bloqueado para evitar venda genérica."
        )

@router.post("", response_model=CarneResponseItem, status_code=status.HTTP_201_CREATED)
def criar_carne(data: CarneCreateRequest):
    """
    Cria um carnê de pagamento na Bempaggo e salva no banco de dados.
    """
    logger.info("==== [CRIA CARNÊ] Recebendo requisição de criar carnê ====")
    logger.info(f"==== [CRIA CARNÊ] Payload recebido (completo): {data.dict()}")
    _hidratar_dados_pre_venda_no_carne(data)

    # VERIFICAÇÃO: Se há pré-venda associada, verificar se a entrada foi paga
    if hasattr(data, 'pre_venda_id') and data.pre_venda_id:
        logger.info(f"==== [CRIA CARNÊ] Verificando status da pré-venda {data.pre_venda_id} ====")
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status, valor_solicitado, valor_pago, forma_pagamento_id
                    FROM pre_vendas_entradas
                    WHERE pre_venda_id = %s
                """, (data.pre_venda_id,))
                result = cursor.fetchone()

                if result:
                    status_pv, valor_solicitado, valor_pago, forma_pagamento_id = result

                    # Se há valor de entrada solicitado (entrada obrigatória)
                    if valor_solicitado and valor_solicitado > 0:
                        logger.info(f"==== [CRIA CARNÊ] Pré-venda tem entrada obrigatória: R$ {valor_solicitado} (Status: {status_pv}) ====")
                        status_pv_normalizado = (status_pv or '').lower()

                        # Buscar forma de pagamento para verificar se é boleto
                        cursor.execute("""
                            SELECT nome FROM formas_pagamento WHERE id = %s
                        """, (forma_pagamento_id,))
                        fp_result = cursor.fetchone()
                        forma_pagamento_nome = fp_result[0] if fp_result else "não identificada"

                        # REGRA DE NEGÓCIO: Boleto pode prosseguir mesmo pendente (será pago depois)
                        # Apenas bloquear se for pagamento instantâneo (PIX, cartão) e não estiver pago
                        is_boleto = 'BOLETO' in forma_pagamento_nome.upper()

                        if status_pv_normalizado in {'cancelado', 'expirado', 'falhou', 'falha', 'fail', 'failed'}:
                            logger.error(f"==== [CRIA CARNÊ] BLOQUEADO: Entrada com status inválido para emissão do carnê (Status: {status_pv}, Forma: {forma_pagamento_nome}) ====")
                            raise HTTPException(
                                status_code=400,
                                detail={
                                    "message": "Entrada não pode ser usada para emitir carnê",
                                    "pre_venda_id": data.pre_venda_id,
                                    "valor_entrada": float(valor_solicitado),
                                    "status": status_pv,
                                    "forma_pagamento": forma_pagamento_nome,
                                    "instrucao": "Gere uma nova entrada válida antes de emitir o carnê das parcelas."
                                }
                            )

                        if status_pv_normalizado != 'pago' and not is_boleto:
                            logger.error(f"==== [CRIA CARNÊ] BLOQUEADO: Entrada obrigatória não foi paga (Status: {status_pv}, Forma: {forma_pagamento_nome}) ====")
                            raise HTTPException(
                                status_code=400,
                                detail={
                                    "message": "Entrada obrigatória não foi paga",
                                    "pre_venda_id": data.pre_venda_id,
                                    "valor_entrada": float(valor_solicitado),
                                    "status": status_pv,
                                    "forma_pagamento": forma_pagamento_nome,
                                    "instrucao": "É necessário que a entrada seja paga antes de emitir o carnê das parcelas."
                                }
                            )

                        if is_boleto and status_pv_normalizado != 'pago':
                            logger.info(f"==== [CRIA CARNÊ] Entrada via BOLETO pendente - permitindo prosseguir (será pago depois) ====")
                        else:
                            logger.info(f"==== [CRIA CARNÊ] Entrada obrigatória confirmada como paga (R$ {valor_pago}) ====")
                    else:
                        logger.info(f"==== [CRIA CARNÊ] Pré-venda sem entrada obrigatória (valor_solicitado=0 ou NULL) ====")
                else:
                    logger.warning(f"==== [CRIA CARNÊ] Pré-venda {data.pre_venda_id} não encontrada na tabela ====")
        except HTTPException:
            raise  # Re-raise HTTPException para não ser capturada pelo except genérico
        except Exception as e:
            logger.error(f"==== [CRIA CARNÊ] Erro ao verificar pré-venda: {e} ====")
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao verificar pré-venda: {str(e)}"
            )

    days_until_due_original = data.days_until_due
    days_until_due_for_bempaggo = data.days_until_due

    if data.dia_vencimento_escolhido is not None:
        logger.info(f"==== [CRIA CARNÊ] Recalculando days_until_due com base no dia_vencimento_escolhido: {data.dia_vencimento_escolhido}.")
        try:
            import calendar
            from datetime import datetime, timedelta
            
            # Usar timezone America/Sao_Paulo para consistência
            from zoneinfo import ZoneInfo
            tz_brasil = ZoneInfo('America/Sao_Paulo')
            agora = datetime.now(tz_brasil)
            ano_atual = agora.year
            mes_atual = agora.month
            dia_atual = agora.day
            
            # NOVA LÓGICA UNIFICADA: Todos os contratos vencerão no dia escolhido do MÊS SEGUINTE
            # Isso garante que sempre teremos days_until_due >= 1 para a BemPaggo
            logger.info(f"==== [CRIA CARNÊ] Primeira parcela será no dia {data.dia_vencimento_escolhido} do próximo mês (lógica unificada para todos os tipos).")
            
            # Calcular o próximo mês
            mes_vencimento = mes_atual + 1
            ano_vencimento = ano_atual
            
            # Ajustar ano se necessário
            if mes_vencimento > 12:
                mes_vencimento = 1
                ano_vencimento += 1
            
            # Verificar se o dia existe no próximo mês
            ultimo_dia_proximo_mes = calendar.monthrange(ano_vencimento, mes_vencimento)[1]
            dia_vencimento_ajustado = min(data.dia_vencimento_escolhido, ultimo_dia_proximo_mes)
            
            if dia_vencimento_ajustado != data.dia_vencimento_escolhido:
                logger.warning(f"==== [CRIA CARNÊ] Dia {data.dia_vencimento_escolhido} não existe em {mes_vencimento}/{ano_vencimento}. Ajustado para dia {dia_vencimento_ajustado}.")
            
            # Calcular data de vencimento no próximo mês
            data_vencimento = datetime(ano_vencimento, mes_vencimento, dia_vencimento_ajustado, tzinfo=tz_brasil)
            
            # Normalizar para início do dia para cálculo correto
            agora_normalizado = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            data_vencimento_normalizada = data_vencimento.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Calcular diferença em dias
            delta = data_vencimento_normalizada - agora_normalizado
            days_until_due_for_bempaggo = delta.days
            
            # CORREÇÃO: Removido ajuste -1 que causava boletos com 1 dia a menos
            # A Bempaggo usa exatamente o valor de days_until_due enviado
            logger.info(f"==== [CRIA CARNÊ] days_until_due calculado para Bempaggo: {days_until_due_for_bempaggo} dias")
            
            logger.info(f"==== [CRIA CARNÊ] Data vencimento (próximo mês): {data_vencimento.date()}, dias até vencimento (sem ajuste): {days_until_due_for_bempaggo}")
            
            # Garantir que não seja negativo
            days_until_due_for_bempaggo = max(0, days_until_due_for_bempaggo)
            
            logger.info(f"==== [CRIA CARNÊ] days_until_due_for_bempaggo final: {days_until_due_for_bempaggo}")
        
        except ValueError as ve:
            logger.error(f"==== [CRIA CARNÊ] Erro de ValueError ao calcular data de vencimento UTC: {ve}. Usando days_until_due original: {days_until_due_original}")
            days_until_due_for_bempaggo = days_until_due_original
        except Exception as e:
            logger.error(f"==== [CRIA CARNÊ] Erro inesperado ao calcular data de vencimento UTC: {e}. Usando days_until_due original: {days_until_due_original}")
            days_until_due_for_bempaggo = days_until_due_original
    else:
        logger.info(f"==== [CRIA CARNÊ] dia_vencimento_escolhido não fornecido. Usando days_until_due do payload: {days_until_due_original}")

    # Log específico para days_until_due que será enviado para a Bempaggo
    logger.info(f"==== [CRIA CARNÊ] days_until_due a ser enviado para Bempaggo: {days_until_due_for_bempaggo}")
    # Log para o valor que será usado para salvar no banco local
    logger.info(f"==== [CRIA CARNÊ] days_until_due original (para banco de dados local): {days_until_due_original}")

    # Se o campo contrato_id estiver preenchido, verifica se existe no banco.
    if data.contrato_id is not None:
        existe = _verificar_se_contrato_existe(data.contrato_id)
        if not existe:
            raise HTTPException(
                status_code=400,
                detail=f"Contrato {data.contrato_id} não encontrado no banco."
            )

    # 1) Obter token e seller_id a partir da unidade
    try:
        logger.debug("Buscando token e seller_id para a unidade '%s'", data.unidade)
        api_token, seller_id = get_token_and_seller_for_unidade(data.unidade, get_current_environment())
        logger.debug("Obtido: api_token=[REDACTED], seller_id=%s", seller_id)
    except ValueError as e:
        logger.error("Unidade inválida ou sem token configurado: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    if not api_token:
        logger.error("Token não configurado para a unidade '%s'", data.unidade)
        raise HTTPException(status_code=400, detail=f"Token não configurado para unidade {data.unidade}.")

    # 2) Inicializar o ambiente e o gerenciador de clientes
    base_url = Environment.get_base_url(get_current_environment())
    customer_manager = CustomerManager(base_url, api_token)
    
    # 3) Verificar se o cliente existe na Bempaggo ou criá-lo
    try:
        # Preparar dados do cliente para criação, se necessário
        customer_data = {
            "name": data.nome_cliente,
            "document": data.cpf_cnpj.replace(".", "").replace("-", "").replace("/", ""),
            "email": data.email if hasattr(data, 'email') and data.email else None
        }
        
        # Adicionar telefone se disponível
        if (hasattr(data, 'phone_country_code') and data.phone_country_code and 
            hasattr(data, 'phone_area_code') and data.phone_area_code and
            hasattr(data, 'phone_number') and data.phone_number):
            customer_data["phone"] = {
                "countryCode": int(data.phone_country_code),
                "areaCode": int(data.phone_area_code),
                "number": int(data.phone_number)
            }
        
        # Adicionar endereço se disponível
        if (hasattr(data, 'street') and data.street and
            hasattr(data, 'street_number') and data.street_number and
            hasattr(data, 'neighborhood') and data.neighborhood and
            hasattr(data, 'city') and data.city and
            hasattr(data, 'state') and data.state and
            hasattr(data, 'zip_code') and data.zip_code):
            customer_data["address"] = {
                "street": data.street,
                "streetNumber": data.street_number,
                "neighborhood": data.neighborhood,
                "city": data.city,
                "state": data.state,
                "zipCode": data.zip_code.replace("-", "")
            }
            # Adicionar complemento se disponível
            if hasattr(data, 'complement') and data.complement:
                customer_data["address"]["lineTwo"] = data.complement
        
        # Verificar se o cliente existe e criá-lo se necessário
        logger.info(f"Verificando/criando cliente com documento: {data.cpf_cnpj}")
        customer_id = customer_manager.get_or_create_customer(
            document=customer_data["document"],
            customer_data=customer_data
        )
        
        # Atualizar o customer_id com o ID obtido da Bempaggo
        data.customer_id = customer_id
        logger.info(f"Cliente configurado com ID: {customer_id}")
        
    except Exception as e:
        logger.error("Erro ao verificar/criar cliente: %s", traceback.format_exc())
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao verificar/criar cliente: {str(e)}"
        )

    # 4) Instanciar a SDK para carnês
    carne_sdk = CarneSDK(
        api_token=api_token,
        seller_id=seller_id,
        environment=get_current_environment()
    )
    logger.debug(f"Instanciada CarneSDK com environment={get_current_environment()}")

    # 3) Configurar SplitManager se tiver splits
    splits = None
    configuracao_splits = None  # Inicializar para evitar UnboundLocalError
    
    # NOVA REGRA: Verificar se deve aplicar split no carnê
    # Se a venda tem entrada/taxa separada, aplicar split considerando ciclos restantes.
    aplicar_split_no_carne = True
    aplicar_split_pos_entrada = False
    
    # Verificar se há pré-venda com entrada
    if hasattr(data, 'pre_venda_id') and data.pre_venda_id:
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status, valor_solicitado, valor_pago
                    FROM pre_vendas_entradas
                    WHERE pre_venda_id = %s
                """, (data.pre_venda_id,))
                result = cursor.fetchone()
                
                if result:
                    status, valor_solicitado, valor_pago = result
                    # Se existe entrada (independente do status), aplicar split pós-entrada.
                    if valor_solicitado and valor_solicitado > 0:
                        aplicar_split_pos_entrada = True
                        valor_display = valor_pago if valor_pago else valor_solicitado
                        logger.info(f"Pré-venda {data.pre_venda_id} tem entrada de R$ {valor_display} com status '{status}'. Split no carnê será aplicado com ciclos restantes.")
        except Exception as e:
            logger.warning(f"Erro ao verificar pré-venda: {e}")
    
    # Verificação original para vendas com entrada/taxa
    if aplicar_split_no_carne and hasattr(data, 'venda_id') and data.venda_id:
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT tipo_cobranca_inicial, valor_entrada, valor_taxa_adesao
                    FROM vendas 
                    WHERE id = %s
                """, (data.venda_id,))
                venda_info = cursor.fetchone()
                
                if venda_info:
                    tipo_cobranca, valor_entrada, valor_taxa = venda_info
                    if tipo_cobranca in ['entrada', 'taxa_adesao'] and (valor_entrada or valor_taxa):
                        aplicar_split_pos_entrada = True
                        logger.info(f"Venda {data.venda_id} tem {tipo_cobranca} separada. Split no carnê será aplicado com ciclos restantes.")
        except Exception as e:
            logger.warning(f"Erro ao verificar entrada/taxa da venda: {e}")
    
    # Se a requisição inclui tipo_odontograma_id, buscar splits configurados no banco
    if aplicar_split_no_carne and hasattr(data, 'tipo_odontograma_id') and data.tipo_odontograma_id:
        logger.info("Buscando configuração de split para tipo_odontograma_id=%s", data.tipo_odontograma_id)
        
        # Se temos odontograma_id mas não temos dentista_id, obtê-lo do odontograma
        dentista_id = None
        if hasattr(data, 'odontograma_id') and data.odontograma_id:
            dentista_id = SplitService.obter_dentista_por_odontograma(data.odontograma_id)
            logger.info(f"Dentista ID={dentista_id} obtido do odontograma ID={data.odontograma_id}")
        
        # Usar o dentista_id explícito do payload se fornecido
        if hasattr(data, 'dentista_id') and data.dentista_id:
            dentista_id = data.dentista_id
        
        # Usar o usuário que está criando o carnê
        usuario_id = data.criado_por
        
        # Calcular valor base para split
        # REGRA: Para pagamentos parcelados/recorrentes, split é sobre o valor da PARCELA
        # Para pagamentos à vista, split é sobre o valor TOTAL
        valor_base_split = None
        if hasattr(data.recurring_item, 'unit_price_in_cents'):
            valor_parcela = Decimal(str(data.recurring_item.unit_price_in_cents)) / 100
            
            # Para carnê (pagamento parcelado), usar valor da parcela como base
            valor_base_split = valor_parcela
            logger.info(f"[SPLIT] Carnê detectado - Base de cálculo: valor da parcela = R$ {valor_parcela}")
            
            if hasattr(data, 'charges_by_booklet'):
                valor_total_contrato = valor_parcela * data.charges_by_booklet
                logger.info(f"[SPLIT] Valor total do contrato: R$ {valor_total_contrato} ({data.charges_by_booklet} parcelas de R$ {valor_parcela})")
        
        # NOVA LÓGICA: Verificar se deve buscar splits pós-entrada
        # usando a nova função verificar_venda_tem_entrada
        tem_entrada_na_venda = False
        if hasattr(data, 'venda_id') and data.venda_id:
            tem_entrada_na_venda = SplitService.verificar_venda_tem_entrada(data.venda_id)
        usar_split_pos_entrada = aplicar_split_pos_entrada or tem_entrada_na_venda
        
        # Se tem entrada, a entrada já consumiu o primeiro ciclo. Nas parcelas,
        # manter participantes com ciclos restantes (ex.: gerente 5 -> 4).
        if usar_split_pos_entrada:
            logger.info("Buscando splits pós-entrada (entrada detectada)")
            configuracao_splits = SplitService.obter_splits_para_parcelas_pos_entrada(
                tipo_odontograma_id=data.tipo_odontograma_id,
                dentista_id=dentista_id,
                usuario_id=usuario_id,
                valor_total_venda=valor_base_split,  # Passar valor da parcela para conversão de valores fixos
                unidade=data.unidade,
                incluir_metadata=True
            )
        else:
            logger.info("Buscando splits completos (sem entrada)")
            # Usar o método dinâmico que considera dentista, usuário, valor da venda e unidade
            configuracao_splits = SplitService.obter_splits_para_venda(
                data.tipo_odontograma_id,
                dentista_id,
                usuario_id,
                valor_base_split,  # Usar valor da parcela para carnês
                data.unidade,
                incluir_metadata=True
            )
        
        if configuracao_splits:
            if usar_split_pos_entrada:
                logger.info("Usando configuração de split pós-entrada")
            else:
                logger.info("Usando configuração de split dinâmica baseada em hierarquia")
            splits = SplitService.sanitizar_splits_para_api(configuracao_splits)
        else:
            logger.warning("Nenhuma configuração de split dinâmica encontrada. Verificando payload.")
    
    # Se não temos splits da configuração do banco, verificar se vieram no payload
    if splits is None and data.splits:
        logger.info("Usando configuração de split fornecida no payload")
        split_manager = SplitManager()
        for split in data.splits:
            split_manager.add_split(
                seller_id=split.seller_id,
                percentage=float(split.percentage),
                cycles_to_participate=split.cycles_to_participate,
                absorb_balance=split.absorb_balance
            )
        
        # Valida se os percentuais somam 100%
        if not split_manager.validate_total_percentage():
            logger.error("Os percentuais dos splits não somam 100%")
            raise HTTPException(status_code=400, detail="Os percentuais dos splits devem somar 100%")
        
        splits = split_manager.get_splits()

    # 4) Preparar dados para a API
    recurring_item = {
        "quantity": data.recurring_item.quantity,
        "productId": data.recurring_item.product_id,
        "maxBillingCycles": data.recurring_item.max_billing_cycles,
        "unitPriceInCents": data.recurring_item.unit_price_in_cents
    }

    accepted_payment_methods = []
    for method in data.accepted_payment_methods:
        payment_method = {
            "method": method.method
        }
        if method.amount_off:
            payment_method["amountOff"] = method.amount_off
        accepted_payment_methods.append(payment_method)

    # 5) Gerar UUID único para referência e rastreabilidade
    my_unique_id = str(uuid.uuid4())

    # Gerar um notification URL padronizado
    notification_url = f"{os.getenv('PUBLIC_BASE_URL', 'https://api.exemplo.com')}/webhook/carne?token={my_unique_id}"

    # 6) Chamar a API da Bempaggo para criar o carnê
    try:
        # Gerar referência única para o pedido usando UUID
        order_reference = my_unique_id

        # LOG 2: Parâmetros para a chamada create_booklet
        booklet_params = {
            "customer_id": data.customer_id,
            "days_until_due": days_until_due_for_bempaggo,
            "billing_frequency": data.billing_frequency,
            "collection_method": data.collection_method,
            "charges_by_booklet": data.charges_by_booklet,
            "recurring_item": recurring_item,
            "accepted_payment_methods": accepted_payment_methods,
            "order_reference": order_reference,
            "notification_url": notification_url,
            "splits": SplitService.sanitizar_splits_para_api(splits)
        }
        logger.info(f"==== [CRIA CARNÊ] Parâmetros para carne_sdk.create_booklet: {booklet_params}")
        
        response = carne_sdk.create_booklet(
            customer_id=data.customer_id,
            days_until_due=days_until_due_for_bempaggo,
            billing_frequency=data.billing_frequency,
            collection_method=data.collection_method,
            charges_by_booklet=data.charges_by_booklet,
            recurring_item=recurring_item,
            accepted_payment_methods=accepted_payment_methods,
            order_reference=order_reference,
            notification_url=notification_url,
            splits=SplitService.sanitizar_splits_para_api(splits)
        )
        logger.debug("Resposta Bempaggo: %s", response)
    except requests.exceptions.HTTPError as http_err:
        logger.error("Erro HTTP ao criar carnê: %s", traceback.format_exc())
        if http_err.response is not None:
            logger.error("Corpo da resposta Bempaggo (HTTP %s): %s",
                        http_err.response.status_code, http_err.response.text)
            try:
                bempaggo_data = http_err.response.json()
                bempaggo_msg = bempaggo_data.get("message", http_err.response.text)
            except:
                bempaggo_msg = http_err.response.text
        else:
            bempaggo_msg = str(http_err)

        raise HTTPException(
            status_code=400,
            detail=f"Erro ao criar carnê: {bempaggo_msg}"
        )
    except Exception as e:
        logger.error("Erro inesperado ao chamar SDK Bempaggo: %s", traceback.format_exc())
        raise HTTPException(
            status_code=400,
            detail=f"Erro inesperado: {str(e)}"
        )

    # Extrair valor total do item recorrente
    valor_total = data.recurring_item.unit_price_in_cents * data.recurring_item.quantity * data.charges_by_booklet / 100
    valor_parcela = data.recurring_item.unit_price_in_cents * data.recurring_item.quantity / 100
    
    # Se tiver desconto para boleto, aplicar
    desconto_boleto = None
    for method in data.accepted_payment_methods:
        if method.method == "BANK_SLIP" and method.amount_off:
            desconto_boleto = method.amount_off / 100

    # Extrair o recurring_invoice_id e a location_url da resposta
    recurring_invoice_id = response.get("id", "")
    location_url = response.get("location", "")

    everest_subscription_id = None

    # 7) Salvar o carnê no banco de dados
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO carne_pagamento (
                    customer_id, recurring_invoice_id, documento_cliente, nome_cliente,
                    valor_total, valor_parcela, total_parcelas, frequencia,
                    metodo_cobranca, dias_vencimento, status, unidade,
                    produto_id, criado_por, uuid, desconto_boleto, location_url,
                    tipo_odontograma_id 
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s  
                )
                RETURNING id
            """, (
                data.customer_id,
                recurring_invoice_id,
                data.cpf_cnpj,
                data.nome_cliente,
                valor_total,
                valor_parcela,
                data.charges_by_booklet,
                data.billing_frequency,
                data.collection_method,
                days_until_due_original,
                "CREATED",
                data.unidade,
                data.recurring_item.product_id,
                data.criado_por,
                my_unique_id,
                desconto_boleto,
                location_url,
                data.tipo_odontograma_id  
            ))
            carne_id = cursor.fetchone()[0]

            # Se há venda_id associada, fazer linkagem bidirecional
            if hasattr(data, 'venda_id') and data.venda_id:
                # Atualizar venda com carne_id
                cursor.execute("""
                    UPDATE vendas SET carne_id = %s WHERE id = %s
                """, (carne_id, data.venda_id))
                
                # Atualizar carne com venda_id  
                cursor.execute("""
                    UPDATE carne_pagamento SET venda_id = %s WHERE id = %s
                """, (data.venda_id, carne_id))
                
                logger.info(f"Linkagem estabelecida: Venda {data.venda_id} ↔ Carnê {carne_id}")

            if configuracao_splits:
                logger.info("Usando configuração de split dinâmica baseada em hierarquia")
                splits = configuracao_splits
                
                # Criar split_manager com base nos splits configurados
                split_manager = SplitManager()
                for split in configuracao_splits:
                    # Extrair metadados (campos que não fazem parte da estrutura padrão de split)
                    metadata = {k: v for k, v in split.items() 
                            if k not in ['sellerId', 'percentage', 'cyclesToParticipate', 'absorbBalance', 'absorbFee']}
                    
                    split_manager.add_split(
                        seller_id=split['sellerId'],
                        percentage=float(split['percentage']),
                        cycles_to_participate=split['cyclesToParticipate'],
                        absorb_balance=split['absorbBalance'],
                        **metadata  # Adiciona os campos adicionais como metadados
                    )
                    
                # Salvar os splits com metadados na tabela
                splits_com_metadata = split_manager.get_splits_with_metadata()
                for split in splits_com_metadata:
                    cursor.execute("""
                        INSERT INTO carne_splits (
                            carne_id, seller_id, cargo_id, user_id, empresa_id,
                            percentage, cycles_to_participate, absorb_balance
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        carne_id,
                        split['sellerId'],
                        split.get('cargo_id'),
                        split.get('user_id'),
                        split.get('empresa_id'),
                        split['percentage'],
                        split['cyclesToParticipate'],
                        split['absorbBalance']
                    ))
                    
            elif data.splits:
                logger.info("Usando configuração de split fornecida no payload")
                # Código para processar data.splits
                for split in data.splits:
                    cursor.execute("""
                        INSERT INTO carne_splits (
                            carne_id, seller_id, percentage, 
                            cycles_to_participate, absorb_balance
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (
                        carne_id,
                        split.seller_id,
                        split.percentage,
                        split.cycles_to_participate,
                        split.absorb_balance
                    ))
            else:
                logger.warning("Nenhuma configuração de split encontrada para este carnê")

            if hasattr(data, 'venda_id') and data.venda_id:
                sync_venda_akimais_flags_conn(
                    conn=conn,
                    venda_id=data.venda_id,
                    pre_venda_id=getattr(data, 'pre_venda_id', None),
                    carne_id=carne_id,
                )
            
            # Criar as parcelas previstas (informação local, não contém dados do boleto ainda)
            data_base_hoje_local = datetime.now()
            
            # O dia que queremos para o vencimento
            dia_vencimento_desejado = data.dia_vencimento_escolhido if data.dia_vencimento_escolhido is not None else (data_base_hoje_local + timedelta(days=days_until_due_original)).day
            
            logger.info(f"==== [CRIA PARCELAS DB] Data base HOJE local: {data_base_hoje_local}, dia_vencimento_desejado: {dia_vencimento_desejado}")

            import calendar
            
            # LÓGICA UNIFICADA: Todos os contratos sempre próximo mês (igual Bempaggo)
            # Entrada obrigatória é tratada separadamente, carnê sempre consistente
            logger.info(f"==== [CRIA PARCELAS DB] Aplicando lógica unificada - próximo mês para todos os tipos")
            
            # Calcular próximo mês
            mes_vencimento = data_base_hoje_local.month + 1
            ano_vencimento = data_base_hoje_local.year
            
            # Ajustar ano se necessário
            if mes_vencimento > 12:
                mes_vencimento = 1
                ano_vencimento += 1
            
            # Verificar se o dia existe no próximo mês
            ultimo_dia_proximo_mes = calendar.monthrange(ano_vencimento, mes_vencimento)[1]
            dia_ajustado = min(dia_vencimento_desejado, ultimo_dia_proximo_mes)
            
            # Primeira parcela sempre no próximo mês
            primeira_parcela_data_final_db = datetime(ano_vencimento, mes_vencimento, dia_ajustado)
            
            logger.info(f"==== [CRIA PARCELAS DB] Primeira parcela unificada: {primeira_parcela_data_final_db.date()}")

            for i in range(data.charges_by_booklet):
                parcela_idx = i + 1
                data_vencimento_parcela_atual_db = None

                if data.billing_frequency == "MONTHLY":
                    if i == 0:
                        # Primeira parcela já calculada
                        data_vencimento_parcela_atual_db = primeira_parcela_data_final_db
                    else:
                        # LÓGICA UNIFICADA: Adicionar meses sequencialmente a partir da primeira parcela
                        mes_alvo = primeira_parcela_data_final_db.month + i
                        ano_alvo = primeira_parcela_data_final_db.year
                        
                        # Ajustar ano se necessário
                        ano_alvo += (mes_alvo - 1) // 12
                        mes_alvo_corrigido = (mes_alvo - 1) % 12 + 1
                        
                        # Usar sempre o dia_vencimento_desejado, ajustando para o último dia do mês se necessário
                        ultimo_dia_mes_alvo = calendar.monthrange(ano_alvo, mes_alvo_corrigido)[1]
                        dia_alvo_final = min(dia_vencimento_desejado, ultimo_dia_mes_alvo)
                        
                        data_vencimento_parcela_atual_db = datetime(ano_alvo, mes_alvo_corrigido, dia_alvo_final)
                
                elif data.billing_frequency == "WEEKLY":
                    data_vencimento_parcela_atual_db = primeira_parcela_data_final_db + timedelta(weeks=i)
                
                # Adicione mais casos para outras frequências aqui...
                
                if data_vencimento_parcela_atual_db is None:
                    logger.error(f"Frequência de cobrança {data.billing_frequency} não suportada no cálculo de parcelas locais para DB.")
                    data_vencimento_para_insercao_db = None 
                else:
                    data_vencimento_para_insercao_db = data_vencimento_parcela_atual_db.date()

                # Log detalhado ANTES de inserir
                logger.info(f"==== [CRIA PARCELAS DB PRE-INSERT] Parcela {parcela_idx}: Enviando para DB: {repr(data_vencimento_para_insercao_db)} (Tipo: {type(data_vencimento_para_insercao_db)})")
                
                cursor.execute("""
                    INSERT INTO carne_parcelas (
                        carne_id, numero_parcela, valor_parcela, 
                        data_vencimento, status
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    carne_id,
                    parcela_idx,
                    valor_parcela,
                    data_vencimento_para_insercao_db,
                    "PENDENTE"
                ))
            
            conn.commit()
            
            # Recuperar o carnê completo para retornar
            cursor.execute("""
                SELECT 
                    id, recurring_invoice_id, customer_id, nome_cliente, 
                    documento_cliente AS cpf_cnpj, valor_total, valor_parcela, 
                    total_parcelas, frequencia, metodo_cobranca, 
                    dias_vencimento, data_criacao, status, unidade, 
                    criado_por, uuid, location_url
                FROM carne_pagamento 
                WHERE id = %s
            """, (carne_id,))
            carne_data = cursor.fetchone()
            
    except Exception as e:
        logger.error("Erro ao salvar carnê no banco: %s", traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao salvar carnê no banco: {str(e)}"
        )

    if recurring_invoice_id and carne_id:
        session = SessionLocal()
        try:
            created_reference_ms = int(carne_data[11].replace(tzinfo=timezone.utc).timestamp() * 1000)
            config = DeltaConfig.from_env(unidade=data.unidade)
            matched_subscription = find_matching_everest_subscription(
                config=config,
                customer_document=data.cpf_cnpj,
                amount_cents=int(data.recurring_item.unit_price_in_cents * data.recurring_item.quantity),
                total_cycles=data.charges_by_booklet,
                created_reference_ms=created_reference_ms,
                logger=logger,
            )

            if matched_subscription and matched_subscription.get("id"):
                everest_subscription_id = int(matched_subscription["id"])
                if save_carne_everest_subscription_id(
                    db=session,
                    carne_id=carne_id,
                    everest_subscription_id=everest_subscription_id,
                ):
                    logger.info(
                        "ID da assinatura Everest %s salvo para carnê local %s",
                        everest_subscription_id,
                        carne_id,
                    )
                else:
                    logger.info(
                        "ID da assinatura Everest %s conciliado, mas coluna ainda não existe no banco para carnê",
                        everest_subscription_id,
                    )
            else:
                logger.info(
                    "Assinatura Everest ainda não encontrada automaticamente para o carnê %s",
                    recurring_invoice_id,
                )
        except Exception as e:
            logger.warning(
                "Erro ao sincronizar assinatura Everest para carnê %s: %s",
                recurring_invoice_id,
                e,
            )
        finally:
            session.close()

    logger.info("==== [CRIA CARNÊ] Finalizado com sucesso. Carnê ID: %s ====", carne_id)
    
    # Verificar se há pré-venda associada para criar venda automaticamente
    if hasattr(data, 'pre_venda_id') and data.pre_venda_id:
        logger.info(f"==== [CRIA CARNÊ] Verificando pré-venda {data.pre_venda_id} para criação automática de venda ====")
        
        try:
            # Criar nova conexão para verificação da pré-venda
            with DatabaseConnection() as conn_pre_venda:
                cursor_pre_venda = conn_pre_venda.cursor()
                
                # Buscar pré-venda usando psycopg2 diretamente
                cursor_pre_venda.execute("""
                    SELECT pre_venda_id, paciente_id, dependente_id, dentista_id, 
                           unidade, valor_pago, status, metadata_json, forma_pagamento_id
                    FROM pre_vendas_entradas
                    WHERE pre_venda_id = %s AND status IN ('pago', 'pendente')
                """, (data.pre_venda_id,))
                
                pre_venda_row = cursor_pre_venda.fetchone()
            
            if pre_venda_row:
                logger.info(f"Pré-venda {data.pre_venda_id} encontrada com status '{pre_venda_row[6]}'. Criando venda automaticamente...")
                
                # Criar objeto simples com os dados da pré-venda
                class PreVenda:
                    def __init__(self, row):
                        self.pre_venda_id = row[0]
                        self.paciente_id = row[1]
                        self.dependente_id = row[2]
                        self.dentista_id = row[3]
                        self.unidade = row[4]
                        self.valor_pago = row[5]
                        self.status = row[6]
                        self.metadata_json = row[7]
                        self.forma_pagamento_id = row[8]
                
                pre_venda = PreVenda(pre_venda_row)
                
                # Criar venda automaticamente usando nova conexão
                with DatabaseConnection() as conn_venda:
                    venda_id = criar_venda_automatica_pos_carne(
                        carne_id=carne_id,
                        pre_venda=pre_venda,
                        tipo_odontograma_id=data.tipo_odontograma_id,
                        paciente_id=pre_venda.paciente_id,
                        dependente_id=pre_venda.dependente_id,
                        dentista_id=pre_venda.dentista_id,
                        odontograma_id=data.odontograma_id if hasattr(data, 'odontograma_id') else None,
                        unidade=pre_venda.unidade,
                        valor_total=valor_total,
                        valor_parcela=valor_parcela,
                        qtd_parcelas=data.charges_by_booklet,
                        usuario_id=int(data.criado_por),
                        carne_uuid=my_unique_id,
                        conn=conn_venda
                    )
                    
                    if venda_id:
                        logger.info(f"Venda {venda_id} criada automaticamente com sucesso!")
                    else:
                        logger.warning("Falha ao criar venda automaticamente")
            else:
                logger.warning(f"Pré-venda {data.pre_venda_id} não encontrada ou não paga")
                
        except Exception as e:
            logger.error(f"Erro ao verificar pré-venda para criação automática de venda: {e}")
            logger.error(traceback.format_exc())
            # Não falhar a criação do carnê por causa disso
    
    # Criar objeto de resposta
    return CarneResponseItem(
        id=carne_data[0],
        recurring_invoice_id=carne_data[1],
        everest_subscription_id=everest_subscription_id,
        customer_id=carne_data[2],
        nome_cliente=carne_data[3],
        cpf_cnpj=carne_data[4],
        valor_total=carne_data[5],
        valor_parcela=carne_data[6],
        total_parcelas=carne_data[7],
        frequencia=carne_data[8],
        metodo_cobranca=carne_data[9],
        dias_vencimento=carne_data[10],
        data_criacao=carne_data[11],
        status=carne_data[12],
        unidade=carne_data[13],
        criado_por=carne_data[14],
        uuid=carne_data[15],
        location_url=carne_data[16]
    )

@router.get("/{carne_id}", response_model=CarneDetalhado)
def get_carne(carne_id: int):
    """
    Recupera um carnê pelo ID, incluindo suas parcelas e splits.
    """
    logger.info("Buscando carnê ID=%s", carne_id)
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Buscar dados do carnê
        cursor.execute("""
            SELECT 
                id, recurring_invoice_id, customer_id, nome_cliente, 
                documento_cliente AS cpf_cnpj, valor_total, valor_parcela, 
                total_parcelas, frequencia, metodo_cobranca, 
                dias_vencimento, data_criacao, status, unidade, 
                criado_por, uuid, location_url, everest_subscription_id
            FROM carne_pagamento 
            WHERE id = %s
        """, (carne_id,))
        carne_data = cursor.fetchone()
        
        if not carne_data:
            logger.warning("Carnê ID=%s não encontrado", carne_id)
            raise HTTPException(status_code=404, detail="Carnê não encontrado")
        
        # Buscar parcelas do carnê
        cursor.execute("""
            SELECT 
                id, carne_id, numero_parcela, valor_parcela, 
                data_vencimento, status, data_pagamento, valor_pago, 
                codigo_barras, linha_digitavel, boleto_url, 
                charge_id, created_at
            FROM carne_parcelas
            WHERE carne_id = %s
            ORDER BY numero_parcela
        """, (carne_id,))
        parcelas_data = cursor.fetchall()
        
        # Buscar splits do carnê
        cursor.execute("""
            SELECT 
                id, carne_id, seller_id, cargo_id, 
                percentage, cycles_to_participate, absorb_balance, 
                created_at
            FROM carne_splits
            WHERE carne_id = %s
        """, (carne_id,))
        splits_data = cursor.fetchall()
    
    # Construir objetos de parcelas
    parcelas = []
    for p in parcelas_data:
        parcelas.append(CarneParcela(
            id=p[0],
            carne_id=p[1],
            numero_parcela=p[2],
            valor_parcela=p[3],
            data_vencimento=p[4],
            status=p[5],
            data_pagamento=p[6],
            valor_pago=p[7],
            codigo_barras=p[8],
            linha_digitavel=p[9],
            boleto_url=p[10],
            charge_id=p[11],
            created_at=p[12]
        ))
    
    # Construir objetos de splits
    splits = []
    for s in splits_data:
        splits.append(CarneSplit(
            id=s[0],
            carne_id=s[1],
            seller_id=s[2],
            cargo_id=s[3],
            percentage=s[4],
            cycles_to_participate=s[5],
            absorb_balance=s[6],
            created_at=s[7]
        ))
    
    # Montar objeto completo
    return CarneDetalhado(
        id=carne_data[0],
        recurring_invoice_id=carne_data[1],
        everest_subscription_id=carne_data[17],
        customer_id=carne_data[2],
        nome_cliente=carne_data[3],
        cpf_cnpj=carne_data[4],
        valor_total=carne_data[5],
        valor_parcela=carne_data[6],
        total_parcelas=carne_data[7],
        frequencia=carne_data[8],
        metodo_cobranca=carne_data[9],
        dias_vencimento=carne_data[10],
        data_criacao=carne_data[11],
        status=carne_data[12],
        unidade=carne_data[13],
        criado_por=carne_data[14],
        uuid=carne_data[15],
        location_url=carne_data[16],
        parcelas=parcelas,
        splits=splits
    )

@router.get("", response_model=List[CarneResponseItem])
def list_carnes(
    status: Optional[str] = Query(None),
    unidade: Optional[str] = Query(None),
    cpf_cnpj: Optional[str] = Query(None),
    contrato_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),  # ID do paciente
    odontograma_id: Optional[int] = Query(None),  # ID específico do odontograma
    tipo_odontograma: Optional[str] = Query(None)  # Tipo de odontograma
):
    """
    Lista carnês com filtros opcionais.
    """
    logger.info(
        "Listando carnês com filtros: status=%s, unidade=%s, cpf_cnpj=%s, contrato_id=%s, "
        "customer_id=%s, odontograma_id=%s, tipo_odontograma=%s", 
        status, unidade, cpf_cnpj, contrato_id, customer_id, odontograma_id, tipo_odontograma
    )
    
    query = """
        SELECT 
            cp.id, cp.recurring_invoice_id, cp.customer_id, cp.nome_cliente, 
            cp.documento_cliente AS cpf_cnpj, cp.valor_total, cp.valor_parcela, 
            cp.total_parcelas, cp.frequencia, cp.metodo_cobranca, 
            cp.dias_vencimento, cp.data_criacao, cp.status, cp.unidade, 
            cp.criado_por, cp.uuid, cp.location_url, cp.everest_subscription_id,
            tipo.nome AS tipo_odontograma, -- Corrigido: usando tipo.nome
            cp.tipo_odontograma_id -- Usando o id do tipo de odontograma
        FROM carne_pagamento cp
        LEFT JOIN tipos_odontograma tipo ON cp.tipo_odontograma_id = tipo.id
        WHERE 1=1
    """
    params = []
    
    if status:
        query += " AND cp.status = %s"
        params.append(status)
    
    if unidade:
        query += " AND cp.unidade = %s"
        params.append(unidade)
    
    if cpf_cnpj:
        query += " AND cp.documento_cliente = %s"
        params.append(cpf_cnpj)
    
    if contrato_id:
        query += " AND cp.contrato_id = %s"
        params.append(contrato_id)
    
    if customer_id:
        query += " AND cp.customer_id = %s"
        params.append(customer_id)
    
    if odontograma_id:
        query += " AND cp.odontograma_id = %s"
        params.append(odontograma_id)
    
    if tipo_odontograma:
        query += " AND tipo.nome = %s"
        params.append(tipo_odontograma)
    
    query += " ORDER BY cp.data_criacao DESC"
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
    
    carnes = []
    for row in rows:
        # Atualizar a criação do CarneResponseItem para incluir os campos adicionais
        carne_item = {
            "id": row[0],
            "recurring_invoice_id": row[1],
            "everest_subscription_id": row[17],
            "customer_id": row[2],
            "nome_cliente": row[3],
            "cpf_cnpj": row[4],
            "valor_total": row[5],
            "valor_parcela": row[6],
            "total_parcelas": row[7],
            "frequencia": row[8],
            "metodo_cobranca": row[9],
            "dias_vencimento": row[10],
            "data_criacao": row[11],
            "status": row[12],
            "unidade": row[13],
            "criado_por": row[14],
            "uuid": row[15],
            "location_url": row[16],
            "tipo_odontograma": row[18],  # Novo campo
            "odontograma_id": row[19]  # Novo campo
        }
        carnes.append(CarneResponseItem(**carne_item))
    
    return carnes

@router.put("/{carne_id}/status", response_model=CarneResponseItem)
def update_carne_status(carne_id: int, data: CarneUpdateStatus):
    """
    Atualiza o status de um carnê.
    """
    logger.info("Atualizando status do carnê ID=%s para %s", carne_id, data.status)
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se o carnê existe
        cursor.execute("SELECT id FROM carne_pagamento WHERE id = %s", (carne_id,))
        if not cursor.fetchone():
            logger.warning("Carnê ID=%s não encontrado", carne_id)
            raise HTTPException(status_code=404, detail="Carnê não encontrado")
        
        # Atualizar status
        cursor.execute("""
            UPDATE carne_pagamento
            SET status = %s
            WHERE id = %s
            RETURNING 
                id, recurring_invoice_id, customer_id, nome_cliente, 
                documento_cliente AS cpf_cnpj, valor_total, valor_parcela, 
                total_parcelas, frequencia, metodo_cobranca, 
                dias_vencimento, data_criacao, status, unidade, 
                criado_por, uuid, location_url, everest_subscription_id
        """, (data.status, carne_id))
        updated_row = cursor.fetchone()
        conn.commit()
    
    return CarneResponseItem(
        id=updated_row[0],
        recurring_invoice_id=updated_row[1],
        everest_subscription_id=updated_row[17],
        customer_id=updated_row[2],
        nome_cliente=updated_row[3],
        cpf_cnpj=updated_row[4],
        valor_total=updated_row[5],
        valor_parcela=updated_row[6],
        total_parcelas=updated_row[7],
        frequencia=updated_row[8],
        metodo_cobranca=updated_row[9],
        dias_vencimento=updated_row[10],
        data_criacao=updated_row[11],
        status=updated_row[12],
        unidade=updated_row[13],
        criado_por=updated_row[14],
        uuid=updated_row[15],
        location_url=updated_row[16]
    )

@router.post("/webhooks")
def process_carne_webhook(request_body: dict):
    """
    Processa webhooks da Bempaggo para atualizar status dos carnês e parcelas.
    """
    logger.info("Recebido webhook para carnê: %s", request_body)
    
    try:
        # Extrair informações do webhook
        recurring_invoice_id = request_body.get("recurringInvoiceId")
        invoice_id = request_body.get("invoiceId")
        status = request_body.get("status")
        
        if not recurring_invoice_id:
            logger.error("Webhook sem recurring_invoice_id")
            return {"message": "Webhook sem recurring_invoice_id"}
        
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Buscar o carnê pelo recurring_invoice_id
            cursor.execute(
                "SELECT id FROM carne_pagamento WHERE recurring_invoice_id = %s",
                (recurring_invoice_id,)
            )
            carne_row = cursor.fetchone()
            
            if not carne_row:
                logger.warning("Carnê com recurring_invoice_id=%s não encontrado", recurring_invoice_id)
                return {"message": f"Carnê com recurring_invoice_id {recurring_invoice_id} não encontrado"}
            
            carne_id = carne_row[0]
            
            # Atualizar a parcela específica se tiver invoice_id
            if invoice_id:
                cursor.execute(
                    "SELECT id FROM carne_parcelas WHERE carne_id = %s AND charge_id = %s",
                    (carne_id, invoice_id)
                )
                parcela_row = cursor.fetchone()
                
                if parcela_row:
                    parcela_id = parcela_row[0]
                    cursor.execute(
                        "UPDATE carne_parcelas SET status = %s WHERE id = %s",
                        (status, parcela_id)
                    )
            
            # Verificar se todas as parcelas foram pagas
            if status == "PAID":
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
        
        return {"message": "Webhook processado com sucesso"}
    except Exception as e:
        logger.error("Erro ao processar webhook: %s", traceback.format_exc())
        return {"message": f"Erro ao processar webhook: {str(e)}"}
    
# app/routers/carne.py (Atualizado - parte relevante)

@router.post("/{carne_id}/boletos", status_code=status.HTTP_200_OK)
def gerar_boletos(carne_id: int):
    """
    Gera os boletos para um carnê específico.
    """
    logger.info("==== [GERA BOLETOS] Gerando boletos para carnê ID: %s ====", carne_id)
    
    # Buscar informações do carnê
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT recurring_invoice_id, unidade
            FROM carne_pagamento
            WHERE id = %s
        """, (carne_id,))
        result = cursor.fetchone()
        
        if not result:
            logger.error("Carnê ID=%s não encontrado", carne_id)
            raise HTTPException(status_code=404, detail="Carnê não encontrado")
        
        recurring_invoice_id, unidade = result
    
    try:
        # Obter token e seller_id para a unidade
        api_token, seller_id = get_token_and_seller_for_unidade(unidade, get_current_environment())
        logger.info("Token e seller_id obtidos para unidade %s", unidade)
        
        # Instanciar SDK
        environment = get_current_environment()
        logger.info("Ambiente detectado: %s", environment)
        
        carne_sdk = CarneSDK(
            api_token=api_token,
            seller_id=seller_id,
            environment=environment
        )
        
        logger.info("Chamando API Bempaggo para gerar boletos do recurring_invoice_id: %s", recurring_invoice_id)
        
        # Chamar API para gerar boletos
        boletos = carne_sdk.generate_booklet_boletos(recurring_invoice_id)
        logger.info("Boletos gerados com sucesso: %d boletos", len(boletos) if isinstance(boletos, list) else 0)
        logger.debug("Boletos gerados: %s", boletos)
        
        # Atualizar parcelas no banco de dados
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            for boleto in boletos:
                invoice_sequence = boleto.get("invoiceSequence")
                status_boleto = boleto.get("status")
                charge_id = boleto.get("chargeId")
                boleto_data = boleto.get("boleto", {})
                
                codigo_barras = boleto_data.get("barCode")
                linha_digitavel = boleto_data.get("digitableLine")
                boleto_url = boleto_data.get("boletoUrl")
                data_vencimento_bempaggo_str = boleto_data.get("dueDate") # String: "2025-06-16T02:59:59.999+00:00"
                
                # Mantemos o log para observação, mas não faremos parse ou uso direto para sobrescrever nossa data
                logger.info(f"==== [GERA BOLETOS] Parcela {invoice_sequence} - dueDate Bempaggo (original): {data_vencimento_bempaggo_str}")

                # Atualiza a parcela correspondente (SEM ATUALIZAR data_vencimento daqui)
                cursor.execute("""
                    UPDATE carne_parcelas
                    SET status = %s,
                        charge_id = %s,
                        codigo_barras = %s,
                        linha_digitavel = %s,
                        boleto_url = %s
                    WHERE carne_id = %s AND numero_parcela = %s
                """, (
                    status_boleto,
                    charge_id,
                    codigo_barras,
                    linha_digitavel,
                    boleto_url,
                    carne_id,
                    invoice_sequence
                ))
            
            # Atualiza status do carnê
            cursor.execute("""
                UPDATE carne_pagamento
                SET status = 'BOLETOS_GERADOS'
                WHERE id = %s
            """, (carne_id,))
            
            conn.commit()
        
        logger.info("==== [GERA BOLETOS] Boletos gerados com sucesso para carnê ID: %s ====", carne_id)
        return {"message": "Boletos gerados com sucesso", "boletos": boletos}
    
    except Exception as e:
        logger.error("Erro ao gerar boletos: %s", traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar boletos: {str(e)}"
        )
    
@router.get("/{carne_id}/booklet/html", response_class=HTMLResponse)
def visualizar_carne_html(carne_id: int):
    """
    Retorna o HTML para visualização e impressão do carnê completo.
    """
    logger.info("Obtendo visualização HTML do carnê ID=%s", carne_id)
    
    # Buscar informações do carnê
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT recurring_invoice_id, unidade
            FROM carne_pagamento
            WHERE id = %s
        """, (carne_id,))
        result = cursor.fetchone()
        
        if not result:
            logger.error("Carnê ID=%s não encontrado", carne_id)
            raise HTTPException(status_code=404, detail="Carnê não encontrado")
        
        recurring_invoice_id, unidade = result
    
    try:
        # Obter token e seller_id para a unidade
        environment = get_current_environment()
        api_token, seller_id = get_token_and_seller_for_unidade(unidade, environment)
        
        # Instanciar SDK
        carne_sdk = CarneSDK(
            api_token=api_token,
            seller_id=seller_id,
            environment=environment
        )
        
        # Chamar API para obter HTML do carnê
        html_content = carne_sdk.get_booklet_html(recurring_invoice_id)
        
        return HTMLResponse(content=html_content)
    
    except Exception as e:
        logger.error("Erro ao obter HTML do carnê: %s", traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter visualização do carnê: {str(e)}"
        )
