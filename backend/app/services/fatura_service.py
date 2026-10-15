# backend/app/services/fatura_service.py

import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
import os
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _normalizar_telefone_delta(customer_phone: Any) -> Optional[Dict[str, int]]:
    """Converte um telefone brasileiro para o formato numérico exigido pela Delta."""
    if customer_phone is None:
        return None

    digits = "".join(character for character in str(customer_phone) if character.isdigit())

    if digits.startswith("55") and len(digits) in (12, 13):
        national_number = digits[2:]
    elif len(digits) in (10, 11):
        national_number = digits
    else:
        return None

    area_code = national_number[:2]
    phone_number = national_number[2:]

    if len(phone_number) not in (8, 9):
        return None

    area_code_value = int(area_code)
    phone_number_value = int(phone_number)
    if not 11 <= area_code_value <= 99:
        return None
    if not 10_000_000 <= phone_number_value <= 999_999_999:
        return None

    return {
        "countryCode": 55,
        "areaCode": area_code_value,
        "number": phone_number_value,
    }

def obter_usuario_id(usuario_id_ou_email: Optional[str], db: Session = None) -> Optional[int]:
    """
    Obtém o ID numérico do usuário.
    
    Se o parâmetro for um ID numérico (como string), retorna como int.
    Se for um email, busca o ID no banco de dados.
    
    Args:
        usuario_id_ou_email: ID do usuário ou email
        db: Sessão do banco de dados
        
    Returns:
        ID numérico do usuário ou None
    """
    if not usuario_id_ou_email:
        return None
        
    # Verificar se é um número
    try:
        return int(usuario_id_ou_email)
    except ValueError:
        pass
        
    # Se não é número, assumir que é email e buscar no banco
    if db:
        try:
            result = db.execute(text("""
                SELECT id FROM users WHERE email = :email
            """), {"email": usuario_id_ou_email})
            row = result.fetchone()
            if row:
                return row[0]
        except Exception as e:
            logger.error(f"Erro ao buscar usuário por email: {str(e)}")
            
    return None

async def criar_fatura_avulsa_service(fatura_request: Any, db: Session = None) -> Dict[str, Any]:
    """
    Serviço simplificado para criar checkout de entrada (sem criar venda).
    
    Args:
        fatura_request: Dados da fatura a ser criada
        db: Sessão do banco de dados (opcional)
        
    Returns:
        Dict com checkout_url e checkout_id
    """
    try:
        # Importar aqui para evitar importação circular
        from ..delta_avulsa_sdk import DeltaAvulsaSDK
        from ..delta_avulsa_sdk.environment import DeltaConfig
        from ..services.split_service import SplitService
        
        # Configurar SDK Delta
        unidade = fatura_request.unidade or "Nova Iguaçu 1"
        config = DeltaConfig.from_env(unidade=unidade)
        
        # Preparar dados do cliente
        customer_data = {
            "name": fatura_request.customer_name,
            "document": fatura_request.customer_document,
            "email": fatura_request.customer_email or f"{fatura_request.customer_document}@cliente.com",
        }
        
        # Adicionar apenas telefones completos no formato numérico exigido pela Delta.
        customer_phone = _normalizar_telefone_delta(
            getattr(fatura_request, "customer_phone", None)
        )
        if customer_phone:
            customer_data["phone"] = customer_phone
            
        # Adicionar endereço se disponível
        if hasattr(fatura_request, 'customer_address') and fatura_request.customer_address:
            customer_data["address"] = fatura_request.customer_address
            
        # Mapear forma de pagamento
        payment_method_map = {
            'CARTÃO CRÉDITO AVULSO DELTA': 'CREDIT_CARD',
            'PIX AVULSO DELTA': 'PIX',
            'BOLETO AVULSO DELTA': 'BANK_SLIP'
        }
        payment_method = payment_method_map.get(fatura_request.payment_method, 'PIX')
        
        # Converter valor para centavos
        amount_cents = int(float(fatura_request.valor_total) * 100)
        
        # URLs de callback
        base_url = os.getenv("API_BASE_URL", "https://api.exemplo.com")
        unique_id = str(uuid.uuid4())
        
        # Usar webhook específico para entrada se tiver pre_venda_id
        pre_venda_id = None
        tipo_pagamento = None
        tipo_odontograma_id = None
        dentista_id = None
        criado_por_raw = getattr(fatura_request, 'criado_por', None)
        criado_por = obter_usuario_id(criado_por_raw, db)
        
        if hasattr(fatura_request, 'metadata') and fatura_request.metadata.get('pre_venda_id'):
            pre_venda_id = fatura_request.metadata.get('pre_venda_id')
            tipo_pagamento = fatura_request.metadata.get('tipo_pagamento')
            tipo_odontograma = fatura_request.metadata.get('tipo_odontograma')
            # Incluir pre_venda_id no URL para identificação
            notification_url = f"{base_url}/api/webhooks/entrada/delta?pre_venda_id={pre_venda_id}"
        else:
            notification_url = f"{base_url}/webhook/fatura-avulsa?token={unique_id}"
            
        # Extrair tipo_odontograma_id
        if hasattr(fatura_request, 'tipo_odontograma_id'):
            tipo_odontograma_id = fatura_request.tipo_odontograma_id
        elif tipo_odontograma:
            # Extrair ID se vier como string "4 - Contrato Ortodôntico"
            try:
                tipo_odontograma_id = int(tipo_odontograma.split(' - ')[0])
            except:
                pass
                
        # Extrair dentista_id se disponível
        if hasattr(fatura_request, 'dentista_id'):
            dentista_id = fatura_request.dentista_id
            
        success_url = f"{base_url}/fatura-avulsa/success"
        
        # Calcular splits para entrada quando for tipo_pagamento='entrada_venda'
        splits = []
        logger.info(f"DEBUG SPLIT: tipo_pagamento={tipo_pagamento}, tipo_odontograma_id={tipo_odontograma_id}, db={db is not None}")
        if tipo_pagamento == 'entrada_venda' and tipo_odontograma_id and db:
            try:
                # Usar o valor da entrada como base para cálculo do split
                valor_entrada = float(fatura_request.valor_total)
                
                # Obter configuração de splits
                configuracao_splits = SplitService.obter_splits_para_venda(
                    tipo_odontograma_id=tipo_odontograma_id,
                    dentista_id=dentista_id,
                    usuario_id=criado_por,
                    valor_total_venda=valor_entrada,  # Usar valor da entrada
                    unidade=unidade,
                    incluir_metadata=True
                )
                
                if configuracao_splits:
                    splits = SplitService.sanitizar_splits_para_api(configuracao_splits)
                    logger.info(f"Splits calculados para entrada: {splits}")
                    
                    # Salvar splits na tabela pre_venda_splits
                    if pre_venda_id:
                        try:
                            logger.info(f"Salvando splits para pré-venda {pre_venda_id}")
                            
                            for split in configuracao_splits:
                                # Calcular valor em reais
                                valor_calculado = (valor_entrada * float(split.get('percentage', 0))) / 100
                                
                                # Inserir split no banco
                                db.execute(text("""
                                    INSERT INTO pre_venda_splits (
                                        pre_venda_id, seller_id, percentage, absorb_balance,
                                        valor_calculado, empresa_id, cargo_id, user_id
                                    ) VALUES (
                                        :pre_venda_id, :seller_id, :percentage, :absorb_balance,
                                        :valor_calculado, :empresa_id, :cargo_id, :user_id
                                    )
                                """), {
                                    'pre_venda_id': pre_venda_id,
                                    'seller_id': str(split.get('sellerId', '')),
                                    'percentage': float(split.get('percentage', 0)),
                                    'absorb_balance': split.get('absorbBalance', False),
                                    'valor_calculado': valor_calculado,
                                    'empresa_id': split.get('empresa_id'),
                                    'cargo_id': split.get('cargo_id'),
                                    'user_id': split.get('user_id')
                                })
                            
                            db.commit()
                            logger.info(f"Splits salvos com sucesso para pré-venda {pre_venda_id}")
                            
                        except Exception as e:
                            logger.error(f"Erro ao salvar splits da pré-venda: {str(e)}")
                            db.rollback()
                            # Continuar mesmo se falhar ao salvar splits
                            
                else:
                    logger.warning("Nenhuma configuração de split encontrada para entrada")
                    
            except Exception as e:
                logger.error(f"Erro ao calcular splits para entrada: {str(e)}")
                # Continuar sem splits em caso de erro
                splits = []
        
        # Criar checkout usando SDK
        with DeltaAvulsaSDK(config) as sdk:
            result = sdk.create_complete_invoice(
                customer_data=customer_data,
                amount_cents=amount_cents,
                payment_method=payment_method,
                splits=splits,  # Agora incluindo splits quando for entrada
                notification_url=notification_url,
                success_url=success_url,
                seller_id=1,
                max_installments=1  # Entrada sempre à vista
                # metadata removido - SDK não suporta
            )
            
        logger.info(f"Checkout de entrada criado com sucesso: {result.get('id')}")

        return {
            'checkout_url': result.get('checkoutUrl'),
            'checkout_id': result.get('id'),
            'status': 'success'
        }
        
    except Exception as e:
        logger.error(f"Erro ao criar checkout de entrada: {str(e)}")
        raise
