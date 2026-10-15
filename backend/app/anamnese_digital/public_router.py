# app/anamnese_digital/public_router.py

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import json
import io

from app.database.db import DatabaseConnection
from .models import (
    AnamnesePublicData, AnamnesePublicSave, 
    AnamnesePublicSign, AnamneseStatus
)
from .service import AnamneseService
from .pdf_generator import AnamnesePDFGenerator

logger = logging.getLogger(__name__)

# Router público - sem autenticação
router = APIRouter(prefix="/public/anamnese", tags=["anamnese-public"])

@router.get("/{token}")
async def obter_anamnese_publica(token: str):
    """Obtém dados da anamnese para preenchimento público"""
    try:
        result = AnamneseService.obter_anamnese_por_token(token)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Link inválido ou expirado"
            )
        
        if not result.get("valido"):
            raise HTTPException(
                status_code=400,
                detail=result.get("erro", "Token inválido")
            )
        
        # Se houver dependente, buscar dados dele
        dependente_nome = None
        dependente_parentesco = None
        if result.get("dependente_id"):
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT nome_dependente, parentesco
                    FROM dependentes
                    WHERE dependente_id = %s
                """, (result["dependente_id"],))
                dep_data = cursor.fetchone()
                if dep_data:
                    dependente_nome, dependente_parentesco = dep_data
        
        return AnamnesePublicData(
            token=token,
            paciente_nome=result["paciente_nome"],
            paciente_cpf=result["paciente_cpf"],
            dependente_nome=dependente_nome,
            dependente_parentesco=dependente_parentesco,
            dados_preenchidos=result["dados_preenchidos"],
            pode_editar=result["pode_editar"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter anamnese pública: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{token}/salvar")
async def salvar_anamnese_publica(
    token: str,
    data: AnamnesePublicSave,
    request: Request
):
    """Salva dados da anamnese preenchida publicamente"""
    try:
        # Verificar token
        token_data = AnamneseService.obter_anamnese_por_token(token)
        
        if not token_data or not token_data.get("valido"):
            raise HTTPException(
                status_code=400,
                detail="Token inválido ou expirado"
            )
        
        if not token_data.get("pode_editar"):
            raise HTTPException(
                status_code=400,
                detail="Esta anamnese não pode mais ser editada"
            )
        
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Se for dependente, buscar o nome dele para usar nos dados de identificação
            if token_data.get("dependente_id"):
                cursor.execute("""
                    SELECT nome_dependente 
                    FROM dependentes 
                    WHERE dependente_id = %s
                """, (token_data["dependente_id"],))
                dep_result = cursor.fetchone()
                if dep_result:
                    # Substituir o nome nos dados de identificação
                    dados_identificacao = data.dados_identificacao.model_dump()
                    dados_identificacao['nome'] = dep_result[0]
                else:
                    dados_identificacao = data.dados_identificacao.model_dump()
            else:
                dados_identificacao = data.dados_identificacao.model_dump()
            
            # Preparar dados
            dados_anamnese = {
                "dados_identificacao": dados_identificacao,
                "saude_geral": data.saude_geral.model_dump(),
                "saude_bucal": data.saude_bucal.model_dump()
            }
            
            anamnese_id = token_data.get("anamnese_id")
            update_query = """
                UPDATE anamneses_digitais
                SET dados_anamnese = %s,
                    observacoes_profissional = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
            """
            
            if anamnese_id:
                # Atualizar existente
                cursor.execute(update_query, (
                    json.dumps(dados_anamnese),
                    data.observacoes,
                    AnamneseStatus.AGUARDANDO_ASSINATURA,
                    anamnese_id
                ))
            else:
                # Se ja existe uma ficha editavel para o mesmo titular/dependente,
                # o token novo deve continuar nela em vez de criar duplicidade.
                if token_data.get("dependente_id") is None:
                    cursor.execute("""
                        SELECT id
                        FROM anamneses_digitais
                        WHERE paciente_id = %s
                        AND dependente_id IS NULL
                        AND status IN (%s, %s)
                        ORDER BY
                            CASE WHEN status = %s THEN 0 ELSE 1 END,
                            created_at DESC
                        LIMIT 1
                    """, (
                        token_data["paciente_id"],
                        AnamneseStatus.AGUARDANDO_ASSINATURA,
                        AnamneseStatus.RASCUNHO,
                        AnamneseStatus.AGUARDANDO_ASSINATURA
                    ))
                else:
                    cursor.execute("""
                        SELECT id
                        FROM anamneses_digitais
                        WHERE paciente_id = %s
                        AND dependente_id = %s
                        AND status IN (%s, %s)
                        ORDER BY
                            CASE WHEN status = %s THEN 0 ELSE 1 END,
                            created_at DESC
                        LIMIT 1
                    """, (
                        token_data["paciente_id"],
                        token_data.get("dependente_id"),
                        AnamneseStatus.AGUARDANDO_ASSINATURA,
                        AnamneseStatus.RASCUNHO,
                        AnamneseStatus.AGUARDANDO_ASSINATURA
                    ))

                anamnese_existente = cursor.fetchone()

                if anamnese_existente:
                    anamnese_id = anamnese_existente[0]
                    cursor.execute(update_query, (
                        json.dumps(dados_anamnese),
                        data.observacoes,
                        AnamneseStatus.AGUARDANDO_ASSINATURA,
                        anamnese_id
                    ))

                    cursor.execute(
                        "UPDATE anamnese_tokens SET anamnese_id = %s WHERE token = %s",
                        (anamnese_id, token)
                    )
                else:
                    # Criar nova
                    insert_query = """
                        INSERT INTO anamneses_digitais (
                            paciente_id, dependente_id, status, dados_anamnese,
                            observacoes_profissional, ip_address, user_agent
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s
                        ) RETURNING id
                    """
                    
                    cursor.execute(insert_query, (
                        token_data["paciente_id"],
                        token_data.get("dependente_id"),
                        AnamneseStatus.AGUARDANDO_ASSINATURA,
                        json.dumps(dados_anamnese),
                        data.observacoes,
                        request.client.host,
                        request.headers.get("user-agent", "")
                    ))
                    
                    anamnese_id = cursor.fetchone()[0]
                    
                    # Associar ao token
                    cursor.execute(
                        "UPDATE anamnese_tokens SET anamnese_id = %s WHERE token = %s",
                        (anamnese_id, token)
                    )
            
            # Marcar como preenchido no envio
            update_envio = """
                UPDATE anamnese_envios
                SET preenchido_em = NOW()
                WHERE token_id = (
                    SELECT id FROM anamnese_tokens WHERE token = %s
                )
                AND preenchido_em IS NULL
            """
            cursor.execute(update_envio, (token,))
            
            conn.commit()
            
            return {
                "success": True,
                "anamnese_id": anamnese_id,
                "message": "Anamnese salva com sucesso. Prossiga para assinatura."
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao salvar anamnese pública: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{token}/assinar")
async def assinar_anamnese_publica(
    token: str,
    data: AnamnesePublicSign,
    request: Request
):
    """Registra assinatura digital da anamnese pública"""
    try:
        # Verificar token e obter anamnese_id
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT t.anamnese_id, t.paciente_id, t.dependente_id, a.status
                FROM anamnese_tokens t
                LEFT JOIN anamneses_digitais a ON a.id = t.anamnese_id
                WHERE t.token = %s
            """
            
            cursor.execute(query, (token,))
            result = cursor.fetchone()
            
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail="Token não encontrado"
                )
            
            anamnese_id, paciente_id, dependente_id, status = result
            
            if not anamnese_id:
                raise HTTPException(
                    status_code=400,
                    detail="Anamnese não foi preenchida ainda"
                )
            
            if status == AnamneseStatus.ASSINADO:
                raise HTTPException(
                    status_code=400,
                    detail="Esta anamnese já foi assinada"
                )
        
        # Preparar dados da assinatura
        assinatura_data = data.assinatura.model_dump()
        assinatura_data["token"] = token
        assinatura_data["ip_address"] = request.client.host
        assinatura_data["user_agent"] = request.headers.get("user-agent", "")
        
        # Assinar
        success = AnamneseService.assinar_anamnese(anamnese_id, assinatura_data)
        
        if success:
            return {
                "success": True,
                "message": "Anamnese assinada com sucesso!",
                "anamnese_id": anamnese_id
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Erro ao assinar anamnese"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao assinar anamnese pública: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{token}/status")
async def verificar_status_publico(token: str):
    """Verifica status da anamnese pública"""
    try:
        result = AnamneseService.obter_anamnese_por_token(token)
        
        if not result:
            return {
                "valido": False,
                "mensagem": "Token não encontrado"
            }
        
        if not result.get("valido"):
            return {
                "valido": False,
                "mensagem": result.get("erro", "Token inválido")
            }
        
        # Verificar status da anamnese
        status = "pendente"
        if result.get("anamnese_id"):
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT status FROM anamneses_digitais WHERE id = %s",
                    (result["anamnese_id"],)
                )
                anamnese_status = cursor.fetchone()
                if anamnese_status:
                    status = anamnese_status[0]
        
        return {
            "valido": True,
            "status": status,
            "paciente_nome": result["paciente_nome"],
            "pode_editar": result["pode_editar"]
        }
        
    except Exception as e:
        logger.error(f"Erro ao verificar status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{token}/pdf")
async def baixar_pdf_publico(token: str):
    """Permite download do PDF após assinatura"""
    try:
        # Verificar token e status
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    a.id, 
                    a.status, 
                    a.dados_anamnese, 
                    a.dependente_id,
                    a.validade_ate,
                    a.signed_at,
                    p.nome_paciente,
                    p.cpf_cnpj,
                    d.nome_dependente,
                    d.parentesco
                FROM anamnese_tokens t
                JOIN anamneses_digitais a ON a.id = t.anamnese_id
                JOIN pacientes p ON p.paciente_id = t.paciente_id
                LEFT JOIN dependentes d ON d.dependente_id = a.dependente_id
                WHERE t.token = %s
            """
            
            cursor.execute(query, (token,))
            result = cursor.fetchone()
            
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail="Anamnese não encontrada"
                )
            
            (anamnese_id, status, dados, dependente_id, validade_ate, signed_at,
             nome_paciente, cpf_paciente, nome_dependente, parentesco) = result
            
            if status != AnamneseStatus.ASSINADO:
                raise HTTPException(
                    status_code=400,
                    detail="PDF disponível apenas após assinatura"
                )
        
        # Gerar PDF
        pdf_generator = AnamnesePDFGenerator()
        pdf_data = {
            "id": anamnese_id,
            "dados_anamnese": dados,
            "paciente_nome": nome_paciente,
            "paciente_cpf": cpf_paciente,
            "dependente_id": dependente_id,
            "dependente_nome": nome_dependente,
            "dependente_parentesco": parentesco,
            "validade_ate": validade_ate,
            "signed_at": signed_at or datetime.now()
        }
        
        
        pdf_buffer = pdf_generator.generate(pdf_data)
        
        return StreamingResponse(
            io.BytesIO(pdf_buffer),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=anamnese_{(nome_dependente or nome_paciente).replace(' ', '_')}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar PDF público: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
