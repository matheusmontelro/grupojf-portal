"""Router para gerenciamento de faturas avulsas Delta"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import logging
from decimal import Decimal
import os
import json
import uuid
from datetime import datetime, timezone

from ..database.db import get_db
from ..models.fatura_avulsa import (
    FaturaAvulsaCreateRequest,
    FaturaAvulsaResponse,
    FaturaAvulsaSplit
)
from ..models.venda import Venda
from ..models.pacientes import PacienteRead
from ..delta_avulsa_sdk import DeltaAvulsaSDK
from ..delta_avulsa_sdk.environment import DeltaConfig
from ..services.split_service import SplitService
# from ..middleware.auth_middleware import get_current_user  # Not needed, using Optional pattern

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fatura-avulsa", tags=["fatura-avulsa"])

def get_delta_sdk(unidade: str = None):
    """Obtém SDK Delta configurado para a unidade específica"""
    try:
        if not unidade:
            unidade = "Nova Iguaçu 1"
        logger.info(f"Inicializando DeltaAvulsaSDK para unidade: {unidade}")
        config = DeltaConfig.from_env(unidade=unidade)
        return DeltaAvulsaSDK(config)
    except Exception as e:
        logger.error(f"Erro ao inicializar DeltaAvulsaSDK: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao configurar API Delta: {str(e)}"
        )

@router.get("/test")
async def test_endpoint():
    """Endpoint de teste para verificar logs"""
    logger.info("[FATURA_AVULSA] Test endpoint called")
    return {"status": "ok", "message": "Fatura avulsa router is working"}

@router.post("/test-post")
async def test_post_endpoint(data: FaturaAvulsaCreateRequest):
    """Endpoint de teste POST para verificar parsing"""
    logger.info(f"[FATURA_AVULSA] Test POST received: {data.dict()}")
    return {"received": data.dict()}

@router.post("/", response_model=FaturaAvulsaResponse)
async def create_fatura_avulsa(
    data: FaturaAvulsaCreateRequest,
    db: Session = Depends(get_db)
):
    """Cria uma nova fatura avulsa"""
    # Log detalhado para debug
    logger.info(f"[FATURA_AVULSA] ==========================")
    logger.info(f"[FATURA_AVULSA] NOVA REQUISIÇÃO RECEBIDA")
    logger.info(f"[FATURA_AVULSA] Request validado: {data.dict()}")
    logger.info(f"[FATURA_AVULSA] ==========================")
    
    try:
        # Busca dados da venda
        venda = db.query(Venda).filter(Venda.id == data.venda_id).first()
        if not venda:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venda não encontrada"
            )
            
        # Busca dados do paciente usando SQL direto
        paciente_query = text("""
            SELECT paciente_id, nome_paciente, cpf_cnpj, email, phone_country_code,
                   phone_area_code, phone_number, street, street_number, neighborhood,
                   city, state, zip_code
            FROM pacientes
            WHERE paciente_id = :paciente_id
        """)
        
        paciente_result = db.execute(paciente_query, {"paciente_id": venda.paciente_id}).first()
        if not paciente_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paciente não encontrado"
            )
            
        # Monta dados do cliente
        customer_data = {
            "name": paciente_result.nome_paciente,
            "document": paciente_result.cpf_cnpj,
            "email": paciente_result.email or f"{paciente_result.cpf_cnpj}@cliente.com",
        }
        
        # Adiciona telefone se disponível
        if paciente_result.phone_number:
            customer_data["phone"] = {
                "countryCode": int(paciente_result.phone_country_code or "55"),
                "areaCode": int(paciente_result.phone_area_code) if paciente_result.phone_area_code else 11,
                "number": int(paciente_result.phone_number)
            }
        
        # Se tiver endereço, adiciona
        if paciente_result.street:
            customer_data["address"] = {
                "street": paciente_result.street,
                "streetNumber": paciente_result.street_number or "S/N",
                "neighborhood": paciente_result.neighborhood or "Centro",
                "city": paciente_result.city or "São Paulo",
                "state": paciente_result.state or "SP",
                "zipCode": paciente_result.zip_code or "00000000"
            }
            
        # Implementar splits seguindo o padrão da fatura recorrente
        splits = None
        
        # Log dos dados recebidos para debug
        logger.info(f"[SPLITS DEBUG] criado_por: {getattr(data, 'criado_por', None)}")
        logger.info(f"[SPLITS DEBUG] unidade: {getattr(data, 'unidade', None)}")
        logger.info(f"[SPLITS DEBUG] venda.id: {venda.id}")
        logger.info(f"[SPLITS DEBUG] venda.odontograma_id: {getattr(venda, 'odontograma_id', None)}")
        
        # Se a venda tem odontograma, buscar tipo_odontograma_id através do tipo (nome)
        tipo_odontograma_id = None
        if hasattr(venda, 'odontograma') and venda.odontograma and venda.odontograma.tipo:
            # Buscar o ID do tipo baseado no nome
            from ..models.tipos_odontograma import TipoOdontograma
            tipo_odontograma = db.query(TipoOdontograma).filter(
                TipoOdontograma.nome == venda.odontograma.tipo
            ).first()
            
            if tipo_odontograma:
                tipo_odontograma_id = tipo_odontograma.id
                logger.info(f"[SPLITS DEBUG] tipo_odontograma_id obtido: {tipo_odontograma_id} (tipo: {venda.odontograma.tipo})")
            else:
                logger.warning(f"[SPLITS DEBUG] Tipo de odontograma '{venda.odontograma.tipo}' não encontrado na tabela tipos_odontograma")
        else:
            logger.info(f"[SPLITS DEBUG] Odontograma não encontrado ou sem tipo definido")
        
        # Se a venda tem tipo_odontograma_id (via odontograma), buscar splits configurados no banco
        if tipo_odontograma_id:
            logger.info("Buscando configuração de split para tipo_odontograma_id=%s", tipo_odontograma_id)
            
            # Se temos odontograma_id mas não temos dentista_id, obtê-lo do odontograma
            dentista_id = None
            if hasattr(venda, 'odontograma_id') and venda.odontograma_id:
                dentista_id = SplitService.obter_dentista_por_odontograma(venda.odontograma_id)
                logger.info(f"Dentista ID={dentista_id} obtido do odontograma ID={venda.odontograma_id}")
            
            # Usar o dentista_id explícito se fornecido
            if hasattr(venda, 'dentista_id') and venda.dentista_id:
                dentista_id = venda.dentista_id
            
            # Usar o usuário que está criando a fatura
            usuario_id = data.criado_por if hasattr(data, 'criado_por') else None
            
            # Calcular valor base para split
            # REGRA: Para pagamentos à vista ou parcelados no cartão, considerar se tem parcelas
            valor_base_split = data.valor_total
            
            # Verificar se é pagamento parcelado no cartão
            forma_pagamento = data.forma_pagamento.upper() if hasattr(data, 'forma_pagamento') else ""
            eh_parcelado = False
            
            if "CARTÃO" in forma_pagamento and "PARCELADO" in forma_pagamento:
                # Se for cartão parcelado, precisamos calcular o valor da parcela
                if hasattr(data, 'numero_parcelas') and data.numero_parcelas > 1:
                    eh_parcelado = True
                    valor_base_split = data.valor_total / data.numero_parcelas
                    logger.info(f"[SPLIT] Cartão parcelado - Base de cálculo: valor da parcela = R$ {valor_base_split:.2f}")
                    logger.info(f"[SPLIT] Valor total: R$ {data.valor_total} ({data.numero_parcelas} parcelas)")
                else:
                    logger.info(f"[SPLIT] Pagamento à vista - Base de cálculo: valor total = R$ {valor_base_split}")
            else:
                logger.info(f"[SPLIT] Pagamento à vista - Base de cálculo: valor total = R$ {valor_base_split}")
            
            # Obter unidade da venda ou usar padrão
            unidade = getattr(venda, 'unidade', None) or getattr(data, 'unidade', None)
            
            # NOVA LÓGICA: Verificar se esta fatura é especificamente uma entrada
            # Se é entrada específica, usar split completo (todos participantes)
            # Se não é entrada mas venda tem entrada, usar ciclos restantes pós-entrada
            eh_fatura_entrada = hasattr(data, 'tipo_fatura') and data.tipo_fatura == 'entrada'
            venda_tem_entrada = SplitService.verificar_venda_tem_entrada(venda.id)
            
            logger.info(f"[SPLIT VERIFICAÇÃO] tipo_fatura={getattr(data, 'tipo_fatura', None)}, venda_tem_entrada={venda_tem_entrada}, eh_fatura_entrada={eh_fatura_entrada}")
            
            if eh_fatura_entrada:
                logger.info(f"[SPLIT ENTRADA] Esta é uma fatura de entrada específica - usando split completo (todos participantes)")
                # Esta é uma fatura de entrada específica - usar split completo
                configuracao_splits = SplitService.obter_splits_para_venda(
                    tipo_odontograma_id,
                    dentista_id,
                    usuario_id,
                    valor_base_split,
                    unidade,
                    incluir_metadata=True
                )
            elif venda_tem_entrada:
                logger.info(f"[SPLIT PARCELAS] Venda com entrada - esta fatura são parcelas, usando splits pós-entrada")
                # A venda tem entrada, mas esta fatura não é a entrada - usar ciclos restantes.
                configuracao_splits = SplitService.obter_splits_para_parcelas_pos_entrada(
                    tipo_odontograma_id=tipo_odontograma_id,
                    dentista_id=dentista_id,
                    usuario_id=usuario_id,
                    valor_total_venda=valor_base_split,
                    unidade=unidade,
                    incluir_metadata=True
                )
            else:
                logger.info(f"[SPLIT NORMAL] Venda sem entrada - usando split completo (todos participantes)")
                # Venda sem entrada - usar split completo
                configuracao_splits = SplitService.obter_splits_para_venda(
                    tipo_odontograma_id,
                    dentista_id,
                    usuario_id,
                    valor_base_split,
                    unidade,
                    incluir_metadata=True
                )
            
            if configuracao_splits:
                logger.info("Usando configuração de split dinâmica baseada em hierarquia")
                splits = configuracao_splits
            else:
                logger.warning("Nenhuma configuração de split dinâmica encontrada. Verificando payload.")
        
        # Se não temos splits da configuração do banco, verificar se vieram no payload
        if splits is None and data.splits:
            logger.info("Usando configuração de split fornecida no payload")
            splits = [s.dict() for s in data.splits]
        
        # Se ainda não temos splits, usar lista vazia
        if splits is None:
            splits = []
            
        logger.info(f"[SPLITS DEBUG] Splits finais: {splits}")
        
        # Garantir que o split com absorbBalance=true seja o último
        if splits and len(splits) > 1:
            # Encontrar o split com absorbBalance=true
            absorb_split = None
            other_splits = []
            
            for split in splits:
                if split.get('absorbBalance', False):
                    absorb_split = split
                else:
                    other_splits.append(split)
            
            # Reordenar: outros primeiro, absorb por último
            if absorb_split:
                splits = other_splits + [absorb_split]
                logger.info(f"[SPLITS DEBUG] Splits reordenados (absorb por último): {splits}")
            
        # Converte valor para centavos
        amount_cents = int(data.valor_total * 100)
        
        # Mapeia forma de pagamento
        payment_method_map = {
            'CARTÃO CRÉDITO AVULSO DELTA': 'CREDIT_CARD',
            'PIX AVULSO DELTA': 'PIX',
            'BOLETO AVULSO DELTA': 'BANK_SLIP'
        }
        payment_method = payment_method_map.get(data.payment_method, 'CREDIT_CARD')
        
        # URLs de callback com token único (mesmo padrão do carnê)
        base_url = os.getenv("API_BASE_URL", "https://api.exemplo.com")
        unique_uuid = str(uuid.uuid4())
        my_unique_id = f"{venda.id}-{unique_uuid}"  # ID único para rastrear
        notification_url = f"{base_url}/webhook/fatura-avulsa?token={my_unique_id}"
        success_url = data.success_url or f"{base_url}/fatura-avulsa/success"
        
        # Cria fatura usando SDK com a unidade da venda
        sdk = get_delta_sdk(venda.unidade)
        with sdk as delta_sdk:
            result = delta_sdk.create_complete_invoice(
                customer_data=customer_data,
                amount_cents=amount_cents,
                payment_method=payment_method,
                splits=SplitService.sanitizar_splits_para_api(splits),
                notification_url=notification_url,
                success_url=success_url,
                seller_id=1,  # TODO: Obter seller_id da unidade
                max_installments=data.installments or 1
            )
            
        # Extrai invoice_id do resultado
        invoice_id = result.get('id')
        logger.info(f"[SPLITS DEBUG] invoice_id: {invoice_id}, tem splits: {bool(splits)}")
        
        # Salvar fatura no banco de dados
        if invoice_id:
            try:
                db.execute(text("""
                    INSERT INTO fatura_avulsa (
                        venda_id, invoice_id, uuid, status, valor_total, 
                        forma_pagamento, checkout_url
                    ) VALUES (
                        :venda_id, :invoice_id, :uuid, :status, :valor_total,
                        :forma_pagamento, :checkout_url
                    )
                """), {
                    'venda_id': venda.id,
                    'invoice_id': invoice_id,
                    'uuid': my_unique_id,
                    'status': result.get('status', 'PENDING'),
                    'valor_total': Decimal(str(amount_cents / 100)),
                    'forma_pagamento': data.payment_method,
                    'checkout_url': result.get('checkoutUrl')
                })
                db.commit()
                logger.info(f"Fatura avulsa {invoice_id} salva no banco com UUID: {my_unique_id}")
            except Exception as e:
                logger.error(f"Erro ao salvar fatura avulsa no banco: {e}")
                # Não falha a criação da fatura por causa disso
        
        # Salvar splits na tabela fatura_avulsa_splits
        if invoice_id and splits:
            try:
                # Importar SplitManager do carnê SDK para reutilizar lógica
                from ..carne_sdk.split_manager import SplitManager
                
                if isinstance(splits, list) and len(splits) > 0 and isinstance(splits[0], dict):
                    # Configuração dinâmica do banco (com metadados)
                    logger.info("Salvando splits dinâmicos para fatura avulsa")
                    
                    # Criar split_manager com base nos splits configurados
                    split_manager = SplitManager()
                    for split in splits:
                        # Extrair metadados (campos que não fazem parte da estrutura padrão de split)
                        metadata = {k: v for k, v in split.items() 
                                if k not in ['sellerId', 'percentage', 'cyclesToParticipate', 'absorbBalance', 'absorbFee']}
                        
                        split_manager.add_split(
                            seller_id=split['sellerId'],
                            percentage=float(split['percentage']),
                            cycles_to_participate=split.get('cyclesToParticipate', 1),
                            absorb_balance=split.get('absorbBalance', False),
                            **metadata  # Adiciona os campos adicionais como metadados
                        )
                        
                    # Salvar os splits com metadados na tabela
                    splits_com_metadata = split_manager.get_splits_with_metadata()
                    for split in splits_com_metadata:
                        db.execute(text("""
                            INSERT INTO fatura_avulsa_splits (
                                invoice_id, seller_id, cargo_id, user_id, empresa_id,
                                percentage, cycles_to_participate, absorb_balance
                            ) VALUES (:invoice_id, :seller_id, :cargo_id, :user_id, :empresa_id, :percentage, :cycles_to_participate, :absorb_balance)
                        """), {
                            'invoice_id': invoice_id,
                            'seller_id': split['sellerId'],
                            'cargo_id': split.get('cargo_id'),
                            'user_id': split.get('user_id'),
                            'empresa_id': split.get('empresa_id'),
                            'percentage': split['percentage'],
                            'cycles_to_participate': split.get('cyclesToParticipate', 1),
                            'absorb_balance': split.get('absorbBalance', False)
                        })
                        
                else:
                    # Splits do payload (sem metadados)
                    logger.info("Salvando splits do payload para fatura avulsa")
                    for split in splits:
                        db.execute(text("""
                            INSERT INTO fatura_avulsa_splits (
                                invoice_id, seller_id, percentage, 
                                cycles_to_participate, absorb_balance
                            ) VALUES (:invoice_id, :seller_id, :percentage, :cycles_to_participate, :absorb_balance)
                        """), {
                            'invoice_id': invoice_id,
                            'seller_id': split.get('seller_id') or split.get('sellerId'),
                            'percentage': split.get('percentage'),
                            'cycles_to_participate': split.get('cycles_to_participate', 1) or split.get('cyclesToParticipate', 1),
                            'absorb_balance': split.get('absorb_balance', False) or split.get('absorbBalance', False)
                        })
                        
                db.commit()
                logger.info(f"Splits salvos com sucesso para fatura avulsa {invoice_id}")
                
            except Exception as e:
                logger.error(f"Erro ao salvar splits: {e}")
                # Não falha a criação da fatura por causa dos splits
        
        # Retorna resposta
        return FaturaAvulsaResponse(
            id=result['id'],
            invoice_number=result.get('invoiceNumber', f"INV-{result['id']}"),
            status=result.get('status', 'PENDING'),
            checkout_url=result.get('checkoutUrl'),
            due_date=result.get('dueDate', datetime.now(timezone.utc).isoformat()),
            amount_cents=amount_cents,
            customer_id=result.get('customerId', venda.paciente_id),
            created_at=result.get('createdAt', datetime.now(timezone.utc).isoformat())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FATURA_AVULSA] Erro ao criar fatura avulsa: {e}")
        logger.error(f"[FATURA_AVULSA] Tipo do erro: {type(e).__name__}")
        import traceback
        logger.error(f"[FATURA_AVULSA] Stack trace: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{fatura_id}", response_model=FaturaAvulsaResponse)
async def get_fatura_avulsa(
    fatura_id: int,
    unidade: str = Query(..., description="Unidade para buscar a fatura"),
    db: Session = Depends(get_db),
    current_user: Optional[dict] = None
):
    """Busca uma fatura avulsa por ID"""
    try:
        sdk = get_delta_sdk(unidade)
        with sdk as delta_sdk:
            invoice = delta_sdk.get_invoice(seller_id=1, invoice_id=fatura_id)
            
        return FaturaAvulsaResponse(
            id=invoice['id'],
            invoice_number=invoice['invoiceNumber'],
            status=invoice['status'],
            checkout_url=invoice.get('checkoutUrl'),
            due_date=invoice['dueDate'],
            amount_cents=invoice['totalAmountInCents'],
            customer_id=invoice['customerId'],
            created_at=invoice['createdAt']
        )
        
    except Exception as e:
        logger.error(f"Erro ao buscar fatura {fatura_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fatura não encontrada"
        )

@router.post("/{fatura_id}/cancel")
async def cancel_fatura_avulsa(
    fatura_id: int,
    unidade: str = Query(..., description="Unidade da fatura"),
    db: Session = Depends(get_db),
    current_user: Optional[dict] = None
):
    """Cancela uma fatura avulsa"""
    try:
        sdk = get_delta_sdk(unidade)
        with sdk as delta_sdk:
            success = delta_sdk.cancel_invoice(seller_id=1, invoice_id=fatura_id)
            
        if success:
            # TODO: Atualizar status no banco local
            return {"message": "Fatura cancelada com sucesso"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não foi possível cancelar a fatura"
            )
            
    except Exception as e:
        logger.error(f"Erro ao cancelar fatura {fatura_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
