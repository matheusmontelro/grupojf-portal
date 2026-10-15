"""Router para gerenciamento de faturas recorrentes Delta"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import logging
from decimal import Decimal
import os
import uuid
from datetime import datetime, timezone

from ..database.db import get_db
from ..models.fatura_recorrente import (
    FaturaRecorrenteCreateRequest,
    FaturaRecorrenteResponse,
    FaturaRecorrenteSplit,
    EntradaParcelamentoRequest
)
from ..models.venda import Venda
from ..models.pacientes import PacienteRead
from ..delta_recorrente_sdk import DeltaRecorrenteSDK
from ..delta_recorrente_sdk.environment import DeltaConfig
from ..services.split_service import SplitService
from ..services.everest_subscription_service import (
    find_matching_everest_subscription,
    get_local_everest_subscription_id,
    save_everest_subscription_id,
)
from ..services.venda_akimais_service import sync_venda_akimais_flags_session
# from ..middleware.auth_middleware import get_current_user  # Not needed, using Optional pattern

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fatura-recorrente", tags=["fatura-recorrente"])

def get_delta_config(unidade: str = "Nova Iguaçu 1"):
    """Obtém configuração da API Delta baseada na unidade"""
    try:
        # Usa o método from_env que já carrega o token correto baseado na unidade
        config = DeltaConfig.from_env(unidade=unidade)
        logger.info(f"Configuração Delta carregada para unidade: {unidade}")
        return config
    except Exception as e:
        logger.error(f"Erro ao carregar configuração Delta: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao configurar API Delta: {str(e)}"
        )

@router.post("/test", response_model=dict)
async def test_endpoint(data: FaturaRecorrenteCreateRequest):
    """Endpoint de teste para debug"""
    return {"message": "OK", "data": data.dict()}

@router.post("/", response_model=FaturaRecorrenteResponse)
async def create_fatura_recorrente(
    data: FaturaRecorrenteCreateRequest,
    db: Session = Depends(get_db)
):
    """Cria uma nova fatura recorrente (assinatura)"""
    logger.info(f"[FATURA_RECORRENTE] Requisição recebida: {data.dict()}")
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
            
        # Implementar splits seguindo o padrão do carne.py
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
            # REGRA: Para pagamentos recorrentes, split é sobre o valor da PARCELA MENSAL
            valor_base_split = data.valor_mensal  # Usar valor mensal para pagamentos recorrentes
            valor_total_contrato = data.valor_mensal * data.total_parcelas
            logger.info(f"[SPLIT] Fatura recorrente - Base de cálculo: valor mensal = R$ {valor_base_split}")
            logger.info(f"[SPLIT] Valor total do contrato: R$ {valor_total_contrato} ({data.total_parcelas} parcelas de R$ {data.valor_mensal})")
            
            # Obter unidade da venda ou usar padrão
            unidade = getattr(venda, 'unidade', None) or getattr(data, 'unidade', None)
            
            # NOVA LÓGICA: Verificar se a venda tem entrada
            # Se tem entrada, ela já consumiu o primeiro ciclo dos participantes.
            tem_entrada = SplitService.verificar_venda_tem_entrada(venda.id)
            
            if tem_entrada:
                logger.info(f"[SPLIT ENTRADA] Venda {venda.id} tem entrada - usando splits pós-entrada nas parcelas recorrentes")
                # Para parcelas quando há entrada, manter participantes com ciclos restantes.
                configuracao_splits = SplitService.obter_splits_para_parcelas_pos_entrada(
                    tipo_odontograma_id=tipo_odontograma_id,
                    dentista_id=dentista_id,
                    usuario_id=usuario_id,
                    valor_total_venda=valor_base_split,
                    unidade=unidade,
                    incluir_metadata=True
                )
            else:
                logger.info(f"[SPLIT NORMAL] Venda {venda.id} sem entrada - usando split completo")
                # Para vendas sem entrada, usar lógica existente (todos participantes)
                configuracao_splits = SplitService.obter_splits_para_venda(
                    tipo_odontograma_id,
                    dentista_id,
                    usuario_id,
                    valor_base_split,  # Usar valor mensal para recorrentes
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
        
        # Garantir que o split com absorbBalance=true seja o último e tenha cyclesToParticipate igual ao total
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
                # Ajustar cycles para o total de parcelas
                absorb_split['cyclesToParticipate'] = data.total_parcelas
                splits = other_splits + [absorb_split]
                logger.info(f"[SPLITS DEBUG] Splits reordenados (absorb por último com {data.total_parcelas} ciclos): {splits}")
            
        # Converte valor mensal para centavos
        amount_cents = int(data.valor_mensal * 100)
        
        # URLs de callback com token único (mesmo padrão do carnê)
        base_url = os.getenv("API_BASE_URL", "https://api.exemplo.com")
        unique_uuid = str(uuid.uuid4())
        my_unique_id = f"{venda.id}-{unique_uuid}"  # ID único para rastrear
        notification_url = f"{base_url}/webhook/fatura-recorrente?token={my_unique_id}"
        success_url = data.success_url or f"{base_url}/fatura-recorrente/success"
        
        # Cria assinatura usando SDK
        # Obtém unidade da requisição ou usa padrão
        unidade = data.unidade or getattr(venda, 'unidade', None) or "Nova Iguaçu 1"
        logger.info(f"Usando unidade para configuração Delta: {unidade}")
        config = get_delta_config(unidade=unidade)
        with DeltaRecorrenteSDK(config) as sdk:
            result = sdk.create_complete_subscription(
                customer_data=customer_data,
                amount_cents=amount_cents,
                total_cycles=data.total_parcelas,
                splits=SplitService.sanitizar_splits_para_api(splits),
                notification_url=notification_url,
                success_url=success_url,
                seller_id=1,  # TODO: Obter seller_id da unidade
                billing_frequency="MONTHLY"
            )
            
        created_reference_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Extrai customer_id do resultado ou usa o do paciente
        customer_id = result.get('customerId', venda.paciente_id)
        
        # Salvar splits na tabela fatura_recorrente_splits
        subscription_id = result.get('id')
        logger.info(f"[SPLITS DEBUG] subscription_id: {subscription_id}, tem splits: {bool(splits)}")
        fatura_recorrente_id = None
        everest_subscription_id = None
        
        # Salvar fatura recorrente no banco de dados
        if subscription_id:
            try:
                fatura_recorrente_id = db.execute(text("""
                    INSERT INTO fatura_recorrente (
                        venda_id, subscription_id, uuid, status, valor_mensal, 
                        total_parcelas, checkout_url
                    ) VALUES (
                        :venda_id, :subscription_id, :uuid, :status, :valor_mensal,
                        :total_parcelas, :checkout_url
                    )
                    RETURNING id
                """), {
                    'venda_id': venda.id,
                    'subscription_id': subscription_id,
                    'uuid': my_unique_id,
                    'status': result.get('status', 'ACTIVE'),
                    'valor_mensal': Decimal(str(amount_cents / 100)),
                    'total_parcelas': data.total_parcelas,
                    'checkout_url': result.get('checkoutUrl')
                }).scalar()
                db.commit()
                logger.info(f"Fatura recorrente {subscription_id} salva no banco com UUID: {my_unique_id}")
            except Exception as e:
                logger.error(f"Erro ao salvar fatura recorrente no banco: {e}")
                # Não falha a criação da fatura por causa disso

        # Sincronizar o ID da assinatura do endpoint Everest sem alterar o fluxo atual.
        if subscription_id and fatura_recorrente_id:
            try:
                matched_subscription = find_matching_everest_subscription(
                    config=config,
                    customer_document=customer_data["document"],
                    amount_cents=amount_cents,
                    total_cycles=data.total_parcelas,
                    created_reference_ms=created_reference_ms,
                    logger=logger,
                )

                if matched_subscription and matched_subscription.get("id"):
                    everest_subscription_id = int(matched_subscription["id"])
                    if save_everest_subscription_id(
                        db=db,
                        fatura_recorrente_id=fatura_recorrente_id,
                        everest_subscription_id=everest_subscription_id,
                    ):
                        logger.info(
                            "ID da assinatura Everest %s salvo para fatura recorrente local %s",
                            everest_subscription_id,
                            fatura_recorrente_id,
                        )
                    else:
                        logger.info(
                            "ID da assinatura Everest %s conciliado, mas coluna ainda não existe no banco",
                            everest_subscription_id,
                        )
                else:
                    logger.info(
                        "Assinatura Everest ainda não encontrada automaticamente para a fatura recorrente %s",
                        subscription_id,
                    )
            except Exception as e:
                logger.warning("Erro ao sincronizar assinatura Everest para fatura recorrente %s: %s", subscription_id, e)

        if subscription_id and splits:
            try:
                # Importar SplitManager do carnê SDK para reutilizar lógica
                from ..carne_sdk.split_manager import SplitManager
                
                if isinstance(splits, list) and len(splits) > 0 and isinstance(splits[0], dict):
                    # Configuração dinâmica do banco (com metadados)
                    logger.info("Salvando splits dinâmicos para fatura recorrente")
                    
                    # Criar split_manager com base nos splits configurados
                    split_manager = SplitManager()
                    for split in splits:
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
                        db.execute(text("""
                            INSERT INTO fatura_recorrente_splits (
                                subscription_id, seller_id, cargo_id, user_id, empresa_id,
                                percentage, cycles_to_participate, absorb_balance
                            ) VALUES (:subscription_id, :seller_id, :cargo_id, :user_id, :empresa_id, :percentage, :cycles_to_participate, :absorb_balance)
                        """), {
                            'subscription_id': subscription_id,
                            'seller_id': split['sellerId'],
                            'cargo_id': split.get('cargo_id'),
                            'user_id': split.get('user_id'),
                            'empresa_id': split.get('empresa_id'),
                            'percentage': split['percentage'],
                            'cycles_to_participate': split['cyclesToParticipate'],
                            'absorb_balance': split['absorbBalance']
                        })
                        
                else:
                    # Splits do payload (sem metadados)
                    logger.info("Salvando splits do payload para fatura recorrente")
                    for split in splits:
                        db.execute(text("""
                            INSERT INTO fatura_recorrente_splits (
                                subscription_id, seller_id, percentage, 
                                cycles_to_participate, absorb_balance
                            ) VALUES (:subscription_id, :seller_id, :percentage, :cycles_to_participate, :absorb_balance)
                        """), {
                            'subscription_id': subscription_id,
                            'seller_id': split.get('seller_id') or split.get('sellerId'),
                            'percentage': split.get('percentage'),
                            'cycles_to_participate': split.get('cycles_to_participate') or split.get('cyclesToParticipate'),
                            'absorb_balance': split.get('absorb_balance') or split.get('absorbBalance')
                        })
                        
                db.commit()
                logger.info(f"Splits salvos com sucesso para fatura recorrente {subscription_id}")

                try:
                    sync_venda_akimais_flags_session(
                        db=db,
                        venda_id=data.venda_id,
                        commit=True,
                    )
                except Exception as sync_error:
                    logger.warning(
                        "Erro ao sincronizar flags Aki Mais Saúde para venda %s após splits da recorrência: %s",
                        data.venda_id,
                        sync_error,
                    )
                
            except Exception as e:
                logger.error(f"Erro ao salvar splits: {e}")
                # Não falha a criação da fatura por causa dos splits
                
        # Se for parte de entrada+parcelamento, atualiza venda
        if data.is_parcelamento and data.valor_entrada:
            venda.tem_entrada = True
            venda.valor_entrada = data.valor_entrada
            venda.valor_parcelado = data.valor_mensal * data.total_parcelas
            db.commit()
            
        # TODO: Criar tabela específica para assinaturas se necessário
        
        # Retorna resposta
        return FaturaRecorrenteResponse(
            id=result.get('id', 0),
            subscription_id=str(result.get('id', 0)),
            everest_subscription_id=str(everest_subscription_id) if everest_subscription_id else None,
            status=result.get('status', 'CREATED'),
            checkout_url=result.get('checkoutUrl'),
            billing_cycle_start=result.get('billingCycleStartDate', int(datetime.now(timezone.utc).timestamp() * 1000)),
            billing_frequency=result.get('billingFrequency', 'MONTHLY'),
            total_cycles=data.total_parcelas,
            amount_cents_per_cycle=amount_cents,
            customer_id=result.get('customerId', customer_id),
            created_at=result.get('createdAt', datetime.now(timezone.utc).isoformat())
        )
        
    except Exception as e:
        logger.error(f"Erro ao criar fatura recorrente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/entrada-parcelamento")
async def create_entrada_parcelamento(
    venda_id: int,
    data: EntradaParcelamentoRequest,
    db: Session = Depends(get_db)
):
    """Cria venda com entrada + parcelamento (Particular/Ortodontia)"""
    try:
        # Busca venda
        venda = db.query(Venda).filter(Venda.id == venda_id).first()
        if not venda:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venda não encontrada"
            )
            
        # Valida tipo de odontograma
        # TODO: Verificar se é Particular ou Ortodontia
        
        # Atualiza venda com dados de entrada
        venda.tem_entrada = True
        venda.valor_entrada = data.valor_entrada
        venda.valor_parcelado = data.valor_parcelado
        # TODO: Salvar forma_pagamento_entrada_id
        
        # Calcula valor mensal
        valor_mensal = data.valor_parcelado / data.numero_parcelas
        
        # Cria fatura recorrente para o parcelamento
        recorrente_request = FaturaRecorrenteCreateRequest(
            customer_name=venda.paciente.nome,
            customer_document=venda.paciente.cpf,
            customer_email=venda.paciente.email,
            valor_mensal=valor_mensal,
            total_parcelas=data.numero_parcelas,
            venda_id=venda_id,
            is_parcelamento=True,
            valor_entrada=data.valor_entrada
        )
        
        # Chama endpoint de criação
        return await create_fatura_recorrente(recorrente_request, db)
        
    except Exception as e:
        logger.error(f"Erro ao criar entrada+parcelamento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{assinatura_id}", response_model=FaturaRecorrenteResponse)
async def get_fatura_recorrente(
    assinatura_id: int,
    db: Session = Depends(get_db)
):
    """Busca uma assinatura por ID"""
    try:
        config = get_delta_config()
        with DeltaRecorrenteSDK(config) as sdk:
            subscription = sdk.get_recurring_invoice(seller_id=1, invoice_id=assinatura_id)
            
        everest_subscription_id = get_local_everest_subscription_id(
            db=db,
            recurring_invoice_id=assinatura_id,
        )

        return FaturaRecorrenteResponse(
            id=subscription['id'],
            subscription_id=str(subscription['id']),
            everest_subscription_id=str(everest_subscription_id) if everest_subscription_id else None,
            status=subscription['status'],
            checkout_url=subscription.get('checkoutUrl'),
            billing_cycle_start=subscription['billingCycleStartDate'],
            billing_frequency=subscription['billingFrequency'],
            total_cycles=subscription.get('totalCycles'),
            amount_cents_per_cycle=subscription['recurringItems'][0]['unitPriceInCents'],
            customer_id=subscription['customerId'],
            created_at=subscription['createdAt']
        )
        
    except Exception as e:
        logger.error(f"Erro ao buscar assinatura {assinatura_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assinatura não encontrada"
        )

@router.delete("/{assinatura_id}")
async def cancel_fatura_recorrente(
    assinatura_id: int,
    db: Session = Depends(get_db)
):
    """Cancela uma assinatura"""
    try:
        config = get_delta_config()
        with DeltaRecorrenteSDK(config) as sdk:
            success = sdk.cancel_recurring_invoice(seller_id=1, invoice_id=assinatura_id)
            
        if success:
            # TODO: Atualizar status no banco local
            return {"message": "Assinatura cancelada com sucesso"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não foi possível cancelar a assinatura"
            )
            
    except Exception as e:
        logger.error(f"Erro ao cancelar assinatura {assinatura_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
