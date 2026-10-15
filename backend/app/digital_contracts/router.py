# digital_contracts/router.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging
from .service import DigitalContractService
from .notification_service import send_contract_whatsapp
from ..database.db import DatabaseConnection
from .models import ContractCreateRequest
from .image_optimizer_simple import ImageOptimizer
from ..services.meta_whatsapp_official_service import (
    WhatsAppConfigurationError,
    WhatsAppDeliveryError,
)
from ..services.whatsapp_document_audit_service import MANUAL_ORIGIN

logger = logging.getLogger("digital_contracts")

router = APIRouter(prefix="/contratos-digitais", tags=["contratos-digitais"])
service = DigitalContractService()

# Configurações de limite
MAX_REQUEST_SIZE_KB = 1024  # 1MB
MAX_IMAGE_SIZE_KB = 500     # 500KB por imagem

def validate_request_size(request: Request, max_size_kb: int = MAX_REQUEST_SIZE_KB):
    """Valida o tamanho da requisição"""
    content_length = request.headers.get('content-length')
    if content_length:
        size_kb = int(content_length) / 1024
        if size_kb > max_size_kb:
            logger.error(f"🚨 Requisição muito grande: {size_kb:.2f} KB (máximo: {max_size_kb} KB)")
            raise HTTPException(413, f"Requisição muito grande. Máximo permitido: {max_size_kb} KB")
        logger.info(f"✅ Tamanho da requisição OK: {size_kb:.2f} KB")


class ContractViewResponse(BaseModel):
    id: int = 0
    odontograma_id: int
    contract_url: str = ""
    is_signed: bool = False
    signed_at: Optional[str] = None
    patient_name: Optional[str] = None
    signature_ip: Optional[str] = None
    created_at: str
    expires_at: str

def log_request_details(request: Request, endpoint: str, extra_data: dict = None):
    """Registra somente metadados não sensíveis da operação."""
    logger.info(
        "Requisição de contrato recebida (evento=%s, método=%s)",
        endpoint,
        request.method,
    )


def _authenticated_context(request: Request) -> dict:
    user_context = getattr(request.state, "user", None)
    if not isinstance(user_context, dict):
        raise HTTPException(401, "Usuário autenticado não identificado")
    return user_context

@router.get("/check/{odontograma_id}", response_model=ContractViewResponse)
def check_contract_status(odontograma_id: int, request: Request):
    """
    Verifica o status do contrato para um odontograma
    """
    log_request_details(request, "CHECK_CONTRACT_STATUS", {"odontograma_id": odontograma_id})
    
    try:
        logger.info(f"Verificando status do contrato para odontograma: {odontograma_id}")
        
        # Buscar contrato real no banco
        contract_status = service.check_contract_status(odontograma_id)
        
        if contract_status:
            logger.info("Contrato encontrado para o odontograma %s", odontograma_id)
            return contract_status
        else:
            # Se não há contrato, retornar resposta padrão
            response = ContractViewResponse(
                id=0,
                odontograma_id=odontograma_id,
                contract_url="",
                is_signed=False,
                signed_at=None,
                patient_name=None,
                signature_ip=None,
                created_at=datetime.now().isoformat(),
                expires_at=datetime.now().isoformat()
            )
            
            logger.info("Nenhum contrato encontrado para o odontograma %s", odontograma_id)
            return response
        
    except Exception as e:
        logger.error("Falha ao consultar status do contrato (%s)", type(e).__name__)
        raise HTTPException(400, str(e))

@router.post("/", response_model=dict)
def create_contract_endpoint(request_data: ContractCreateRequest, request: Request):
    """
    Cria um novo contrato digital
    """
    log_request_details(request, "CREATE_CONTRACT_ENDPOINT", {
        "odontograma_id": request_data.odontograma_id,
        "forma_pagamento": request_data.forma_pagamento,
        "dia_vencimento": request_data.dia_vencimento,
        "qtd_parcelas": request_data.qtd_parcelas,
        "dependente_id": request_data.dependente_id,
        "valor_total": request_data.valor_total
    })
    
    try:
        logger.info(f"Criando contrato para odontograma: {request_data.odontograma_id}")
        
        # Buscar paciente pelo odontograma
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            logger.info("Executando query para buscar paciente...")
            cursor.execute("""
                SELECT p.paciente_id, p.nome_paciente 
                FROM odontogramas o
                JOIN pacientes p ON p.paciente_id = o.paciente_id
                WHERE o.id = %s
            """, (request_data.odontograma_id,))
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"❌ Odontograma {request_data.odontograma_id} não encontrado")
                raise HTTPException(404, "Odontograma não encontrado")
            
            paciente_id, paciente_nome = row
            logger.info("Paciente localizado para criação do contrato (id=%s)", paciente_id)
        
        # Obter nome do vendedor do token JWT
        vendedor_nome = None
        if hasattr(request.state, 'user'):
            user_data = request.state.user
            logger.info("Contexto autenticado disponível para criação do contrato")
            
            # Tentar diferentes campos possíveis para o nome
            vendedor_nome = (
                user_data.get('nome') or 
                user_data.get('name') or 
                user_data.get('username') or 
                user_data.get('sub', '')
            )
            
            logger.info("Vendedor identificado no contexto autenticado")
        else:
            logger.warning("⚠️ Nenhum dado de usuário encontrado no request.state")
        
        # Criar contrato
        logger.info("Chamando service.create_contract...")
        logger.info(
            "Parâmetros operacionais validados (odontograma_id=%s, dependente_id=%s)",
            request_data.odontograma_id,
            request_data.dependente_id,
        )
        link = service.create_contract(
            paciente_id, 
            request_data.odontograma_id, 
            vendedor_nome,
            request_data.forma_pagamento,
            request_data.dia_vencimento,
            request_data.qtd_parcelas,
            request_data.dependente_id,
            request_data.valor_total
        )
        logger.info("Contrato criado para o odontograma %s", request_data.odontograma_id)

        whatsapp_sent = False
        whatsapp_status = "error"
        whatsapp_message = "Contrato gerado, mas o link não foi enviado pelo WhatsApp"
        try:
            delivery = send_contract_whatsapp(
                request_data.odontograma_id,
                _authenticated_context(request),
            )
            whatsapp_sent = delivery.sent
            whatsapp_status = delivery.status
            whatsapp_message = delivery.message
        except (WhatsAppConfigurationError, WhatsAppDeliveryError) as exc:
            whatsapp_message = str(exc)
            logger.warning(
                "Contrato criado sem envio pelo WhatsApp (odontograma_id=%s, tipo=%s)",
                request_data.odontograma_id,
                type(exc).__name__,
            )
        except Exception as exc:
            logger.error(
                "Falha inesperada no envio do contrato (odontograma_id=%s, tipo=%s)",
                request_data.odontograma_id,
                type(exc).__name__,
            )
        
        response = {
            "success": True,
            "contract_url": link,
            "message": "Contrato criado com sucesso",
            "odontograma_id": request_data.odontograma_id,
            "patient_name": paciente_nome,
            "whatsapp_sent": whatsapp_sent,
            "whatsapp_status": whatsapp_status,
            "whatsapp_message": whatsapp_message,
        }
        
        logger.info("Resposta de criação do contrato preparada")
        return response
        
    except Exception as e:
        logger.error("Falha ao criar contrato (%s)", type(e).__name__)
        raise HTTPException(400, str(e))


@router.post("/{odontograma_id}/enviar-whatsapp", response_model=dict)
def send_contract_whatsapp_endpoint(odontograma_id: int, request: Request):
    """Tenta novamente o envio do contrato pelo WhatsApp oficial da unidade."""
    try:
        delivery = send_contract_whatsapp(
            odontograma_id,
            _authenticated_context(request),
            origin=MANUAL_ORIGIN,
        )
        return {
            "success": delivery.sent,
            "whatsapp_sent": delivery.sent,
            "whatsapp_status": delivery.status,
            "whatsapp_message": delivery.message,
        }
    except (WhatsAppConfigurationError, WhatsAppDeliveryError) as exc:
        logger.warning(
            "Reenvio de contrato recusado (odontograma_id=%s, tipo=%s)",
            odontograma_id,
            type(exc).__name__,
        )
        raise HTTPException(status_code=502, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Falha inesperada no reenvio do contrato (odontograma_id=%s, tipo=%s)",
            odontograma_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Não foi possível enviar o contrato pelo WhatsApp",
        )

@router.post("/create")
def create_contract(odontograma_id: int, request: Request):
    """
    [SISTEMA] Cria contrato e retorna link
    """
    log_request_details(request, "CREATE_CONTRACT", {"odontograma_id": odontograma_id})
    
    try:
        logger.info(f"[SISTEMA] Criando contrato para odontograma: {odontograma_id}")
        
        # Buscar paciente pelo odontograma
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT paciente_id FROM odontogramas WHERE id = %s
            """, (odontograma_id,))
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"❌ Odontograma {odontograma_id} não encontrado")
                raise HTTPException(404, "Odontograma não encontrado")
            
            paciente_id = row[0]
            logger.info(f"✅ Paciente ID encontrado: {paciente_id}")
        
        # Obter nome do vendedor do token JWT
        vendedor_nome = None
        if hasattr(request.state, 'user'):
            user_data = request.state.user
            logger.info("Contexto autenticado disponível para criação do contrato")
            
            # Tentar diferentes campos possíveis para o nome
            vendedor_nome = (
                user_data.get('nome') or 
                user_data.get('name') or 
                user_data.get('username') or 
                user_data.get('sub', '')
            )
            
            logger.info("Vendedor identificado no contexto autenticado")
        else:
            logger.warning("⚠️ Nenhum dado de usuário encontrado no request.state")
        
        link = service.create_contract(paciente_id, odontograma_id, vendedor_nome)
        logger.info("Link de contrato gerado para o odontograma %s", odontograma_id)
        
        response = {
            "success": True,
            "contract_link": link,
            "message": "Contrato criado. Envie o link para o cliente."
        }
        
        logger.info("Resposta de criação do contrato preparada")
        return response
        
    except Exception as e:
        logger.error("Falha ao criar contrato simplificado (%s)", type(e).__name__)
        raise HTTPException(400, str(e))

@router.get("/view/{token}")
def view_contract(token: str, request: Request):
    """
    [CLIENTE] Visualiza contrato no celular
    """
    log_request_details(request, "VIEW_CONTRACT")
    
    try:
        contract = service.get_contract_for_client(token)
        logger.info("Contrato recuperado para visualização pública")
        
        return contract
        
    except Exception as e:
        logger.error("Falha ao visualizar contrato (%s)", type(e).__name__)
        raise HTTPException(404, str(e))

@router.post("/selfie/{token}")
def upload_selfie(token: str, data: dict, request: Request):
    """
    [CLIENTE] Envia selfie obrigatória
    """
    try:
        # Validar tamanho da requisição
        validate_request_size(request, MAX_REQUEST_SIZE_KB)
        
        # Obter e validar selfie
        selfie_data = data.get('selfie', '')
        if not selfie_data:
            raise HTTPException(400, "Selfie é obrigatória")
            
        # Obter informações da imagem original
        image_info = ImageOptimizer.get_image_info(selfie_data)
        logger.info("Selfie recebida (tamanho_kb=%.2f)", image_info.get('size_kb', 0))
        
        # Comprimir selfie se necessário
        if image_info.get('size_kb', 0) > MAX_IMAGE_SIZE_KB:
            logger.info(f"🔄 Comprimindo selfie de {image_info['size_kb']:.2f} KB...")
            compressed_selfie, compression_info = ImageOptimizer.compress_base64_image(
                selfie_data, MAX_IMAGE_SIZE_KB
            )
            logger.info("Selfie comprimida para o limite configurado")
            final_selfie = compressed_selfie
        else:
            logger.info("✅ Selfie já está no tamanho adequado")
            final_selfie = selfie_data
            
        log_request_details(request, "UPLOAD_SELFIE")
        
        result = service.save_selfie(
            token, 
            final_selfie, 
            data.get('device_info', {})
        )
        
        logger.info("Selfie salva com sucesso")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Falha ao salvar selfie (%s)", type(e).__name__)
        raise HTTPException(400, str(e))

@router.post("/sign/{token}")
def sign_contract(token: str, data: dict, request: Request):
    """
    [CLIENTE] Finaliza assinatura
    """
    try:
        # Validar tamanho da requisição
        validate_request_size(request, MAX_REQUEST_SIZE_KB)
        
        # Obter e validar assinatura
        signature_data = data.get('signature', '')
        if not signature_data:
            raise HTTPException(400, "Assinatura é obrigatória")
            
        # Obter informações da imagem original
        image_info = ImageOptimizer.get_image_info(signature_data)
        logger.info("Assinatura recebida (tamanho_kb=%.2f)", image_info.get('size_kb', 0))
        
        # Comprimir assinatura se necessário
        if image_info.get('size_kb', 0) > MAX_IMAGE_SIZE_KB:
            logger.info(f"🔄 Comprimindo assinatura de {image_info['size_kb']:.2f} KB...")
            compressed_signature, compression_info = ImageOptimizer.compress_base64_image(
                signature_data, MAX_IMAGE_SIZE_KB
            )
            logger.info("Assinatura comprimida para o limite configurado")
            final_signature = compressed_signature
        else:
            logger.info("✅ Assinatura já está no tamanho adequado")
            final_signature = signature_data
            
        log_request_details(request, "SIGN_CONTRACT")
        
        logger.info("🔄 Chamando service.sign_contract...")
        result = service.sign_contract(token, final_signature)
        logger.info("Contrato assinado com sucesso")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Falha ao assinar contrato (%s)", type(e).__name__)
        raise HTTPException(400, str(e))

@router.get("/signed/{odontograma_id}")
def get_signed_contract_data(odontograma_id: int, request: Request):
    """
    Retorna dados completos do contrato assinado incluindo selfie e assinatura
    """
    log_request_details(request, "GET_SIGNED_CONTRACT_DATA", {"odontograma_id": odontograma_id})
    
    try:
        logger.info(f"Buscando dados do contrato assinado para odontograma: {odontograma_id}")
        
        contract_data = service.get_signed_contract_data(odontograma_id)
        
        if not contract_data:
            logger.warning(f"❌ Contrato assinado não encontrado para odontograma {odontograma_id}")
            raise HTTPException(404, "Contrato assinado não encontrado")
        
        logger.info(f"✅ Dados do contrato assinado recuperados com sucesso")
        return contract_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Falha ao obter contrato assinado (%s)", type(e).__name__)
        raise HTTPException(400, str(e))

@router.get("/search")
def search_digital_contracts(
    request: Request,
    cpf: Optional[str] = None,
    nome: Optional[str] = None,
    unidade: Optional[str] = None
):
    """
    Busca contratos digitais por CPF, nome, telefone ou status
    Usado para segunda via de contratos
    """
    log_request_details(request, "SEARCH_DIGITAL_CONTRACTS")
    
    try:
        if not any([cpf, nome, unidade]):
            raise HTTPException(400, "Pelo menos um filtro deve ser informado (CPF, nome ou unidade)")
        
        logger.info(
            "Busca de contratos iniciada (cpf=%s, nome=%s, unidade=%s)",
            bool(cpf),
            bool(nome),
            bool(unidade),
        )
        
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Construir query dinamicamente
            where_conditions = []
            params = []
            
            base_query = """
                SELECT 
                    c.id, c.paciente_id, c.odontograma_id, c.valor_total, 
                    c.status, c.signed_at, c.created_at, c.access_token,
                    p.nome_paciente, p.cpf_cnpj, p.phone_country_code, p.phone_area_code, p.phone_number,
                    d.nome_dependente as dependente_nome, d.parentesco as dependente_parentesco
                FROM digital_contracts c
                JOIN pacientes p ON c.paciente_id = p.paciente_id
                LEFT JOIN dependentes d ON c.dependente_id = d.dependente_id
            """
            
            if cpf:
                where_conditions.append("p.cpf_cnpj = %s")
                params.append(cpf.replace('.', '').replace('-', ''))
            
            if nome:
                where_conditions.append("LOWER(p.nome_paciente) LIKE LOWER(%s)")
                params.append(f"%{nome}%")
            
            if unidade:
                where_conditions.append("p.unidade = %s")
                params.append(unidade)
            
            # Adicionar WHERE se há condições
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)
            
            # Ordenar por data de criação (mais recente primeiro)
            base_query += " ORDER BY c.created_at DESC LIMIT 50"
            
            cursor.execute(base_query, params)
            results = cursor.fetchall()
            
            contratos = []
            for row in results:
                contract_id, paciente_id, odontograma_id, valor_total, status, signed_at, created_at, access_token, paciente_nome, paciente_cpf, phone_country_code, phone_area_code, phone_number, dependente_nome, dependente_parentesco = row
                
                # Construir telefone principal a partir dos componentes
                telefone_principal = None
                if phone_number:
                    if phone_area_code:
                        telefone_principal = f"({phone_area_code}) {phone_number}"
                    else:
                        telefone_principal = phone_number
                
                contratos.append({
                    "id": contract_id,
                    "paciente_id": paciente_id,
                    "paciente_nome": paciente_nome,
                    "paciente_cpf": paciente_cpf,
                    "paciente_telefone": telefone_principal,
                    "dependente_nome": dependente_nome,
                    "dependente_parentesco": dependente_parentesco,
                    "valor_total": float(valor_total),
                    "status": status,
                    "signed_at": signed_at.isoformat() if signed_at else None,
                    "created_at": created_at.isoformat() if created_at else None,
                    "access_token": access_token,
                    "odontograma_id": odontograma_id
                })
            
            logger.info(f"✅ Encontrados {len(contratos)} contratos")
            return contratos
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Falha ao buscar contratos (%s)", type(e).__name__)
        raise HTTPException(500, str(e))
