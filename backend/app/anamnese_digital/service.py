# app/anamnese_digital/service.py

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from sqlalchemy import text
import json

from app.database.db import DatabaseConnection
from .models import AnamneseStatus, AnamneseCreate, AnamneseResponse
from .token_service import TokenService

logger = logging.getLogger(__name__)

class AnamneseService:
    """Serviço principal para gerenciamento de anamneses"""
    
    @staticmethod
    def verificar_anamnese_valida(paciente_id: int, dependente_id: Optional[int] = None) -> Dict[str, Any]:
        """Verifica se o paciente/dependente tem anamnese válida"""
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Buscar anamnese mais recente assinada
                if dependente_id is None:
                    query = """
                        SELECT id, signed_at, validade_ate, status
                        FROM anamneses_digitais
                        WHERE paciente_id = %s 
                        AND dependente_id IS NULL
                        AND status = %s
                        ORDER BY signed_at DESC
                        LIMIT 1
                    """
                    cursor.execute(query, (paciente_id, AnamneseStatus.ASSINADO))
                else:
                    query = """
                        SELECT id, signed_at, validade_ate, status
                        FROM anamneses_digitais
                        WHERE paciente_id = %s 
                        AND dependente_id = %s
                        AND status = %s
                        ORDER BY signed_at DESC
                        LIMIT 1
                    """
                    cursor.execute(query, (paciente_id, dependente_id, AnamneseStatus.ASSINADO))
                
                result = cursor.fetchone()
                
                if not result:
                    return {
                        "possui_anamnese": False,
                        "valida": False,
                        "mensagem": "Paciente não possui anamnese"
                    }
                
                anamnese_id, signed_at, validade_ate, status = result
                
                # Verificar validade
                if validade_ate and datetime.now() > validade_ate:
                    return {
                        "possui_anamnese": True,
                        "valida": False,
                        "anamnese_id": anamnese_id,
                        "signed_at": signed_at,
                        "validade_ate": validade_ate,
                        "mensagem": "Anamnese expirada"
                    }
                
                # Calcular dias restantes
                dias_restantes = (validade_ate - datetime.now()).days if validade_ate else 365
                
                return {
                    "possui_anamnese": True,
                    "valida": True,
                    "anamnese_id": anamnese_id,
                    "signed_at": signed_at,
                    "validade_ate": validade_ate,
                    "dias_restantes": dias_restantes,
                    "mensagem": "Anamnese válida"
                }
                
        except Exception as e:
            logger.error(f"Erro ao verificar anamnese: {str(e)}")
            raise
    
    @staticmethod
    def criar_anamnese(data: AnamneseCreate, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Cria uma nova anamnese"""
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Validar dependente se fornecido
                if data.dependente_id:
                    cursor.execute("""
                        SELECT 1 FROM dependentes 
                        WHERE dependente_id = %s 
                        AND responsavel_paciente_id = %s
                        AND ativo = true
                    """, (data.dependente_id, data.paciente_id))
                    
                    if not cursor.fetchone():
                        raise ValueError(f"Dependente {data.dependente_id} não pertence ao paciente {data.paciente_id} ou está inativo")
                
                # Preparar dados para JSON
                dados_anamnese = {
                    "dados_identificacao": data.dados_identificacao.model_dump(),
                    "saude_geral": data.saude_geral.model_dump(),
                    "saude_bucal": data.saude_bucal.model_dump()
                }
                
                query = """
                    INSERT INTO anamneses_digitais (
                        paciente_id, dependente_id, status, dados_anamnese, observacoes_profissional,
                        created_by, ip_address, user_agent
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id, created_at
                """
                
                cursor.execute(query, (
                    data.paciente_id,
                    data.dependente_id,
                    AnamneseStatus.RASCUNHO,
                    json.dumps(dados_anamnese),
                    data.observacoes,
                    user_id,
                    None,  # IP será capturado no router
                    None   # User agent será capturado no router
                ))
                
                anamnese_id, created_at = cursor.fetchone()
                conn.commit()
                
                logger.info(f"Anamnese {anamnese_id} criada para paciente {data.paciente_id}")
                
                return {
                    "id": anamnese_id,
                    "paciente_id": data.paciente_id,
                    "status": AnamneseStatus.RASCUNHO,
                    "created_at": created_at
                }
                
        except Exception as e:
            logger.error(f"Erro ao criar anamnese: {str(e)}")
            raise
    
    @staticmethod
    def gerar_link_anamnese(paciente_id: int, dependente_id: Optional[int] = None, validade_horas: int = 72) -> Dict[str, Any]:
        """Gera link público para preenchimento da anamnese"""
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Verificar se já existe token ativo
                if dependente_id is None:
                    check_query = """
                        SELECT token, expires_at, used
                        FROM anamnese_tokens
                        WHERE paciente_id = %s
                        AND dependente_id IS NULL
                        AND used = false
                        AND expires_at > NOW()
                        ORDER BY created_at DESC
                        LIMIT 1
                    """
                    cursor.execute(check_query, (paciente_id,))
                else:
                    check_query = """
                        SELECT token, expires_at, used
                        FROM anamnese_tokens
                        WHERE paciente_id = %s
                        AND dependente_id = %s
                        AND used = false
                        AND expires_at > NOW()
                        ORDER BY created_at DESC
                        LIMIT 1
                    """
                    cursor.execute(check_query, (paciente_id, dependente_id))
                
                existing = cursor.fetchone()
                
                if existing:
                    token, expires_at, _ = existing
                    link = TokenService.generate_link(token)
                    
                    return {
                        "token": token,
                        "link_publico": link,
                        "expires_at": expires_at,
                        "reaproveitado": True
                    }
                
                # Gerar novo token
                token = TokenService.generate_token()
                expires_at = TokenService.calculate_expiration(validade_horas)
                link = TokenService.generate_link(token)
                
                # Salvar token
                insert_query = """
                    INSERT INTO anamnese_tokens (
                        token, paciente_id, dependente_id, expires_at
                    ) VALUES (
                        %s, %s, %s, %s
                    ) RETURNING id
                """
                
                cursor.execute(insert_query, (token, paciente_id, dependente_id, expires_at))
                token_id = cursor.fetchone()[0]
                conn.commit()
                
                logger.info(f"Token {token_id} gerado para paciente {paciente_id}")
                
                return {
                    "token": token,
                    "link_publico": link,
                    "expires_at": expires_at,
                    "token_id": token_id,
                    "reaproveitado": False
                }
                
        except Exception as e:
            logger.error(f"Erro ao gerar link: {str(e)}")
            raise
    
    @staticmethod
    def obter_anamnese_por_token(token: str) -> Optional[Dict[str, Any]]:
        """Obtém dados da anamnese através do token público"""
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Verificar token
                query = """
                    SELECT 
                        t.paciente_id,
                        t.dependente_id,
                        t.anamnese_id,
                        t.expires_at,
                        t.used,
                        p.nome_paciente,
                        p.cpf_cnpj
                    FROM anamnese_tokens t
                    JOIN pacientes p ON p.paciente_id = t.paciente_id
                    WHERE t.token = %s
                """
                
                cursor.execute(query, (token,))
                result = cursor.fetchone()
                
                if not result:
                    return None
                
                paciente_id, dependente_id, anamnese_id, expires_at, used, nome, cpf = result
                
                # Validar token
                is_valid, error_msg = TokenService.is_token_valid(expires_at, used)
                if not is_valid:
                    return {
                        "valido": False,
                        "erro": error_msg
                    }
                
                # Se tem anamnese_id, buscar dados
                dados_preenchidos = None
                status_anamnese = None
                if anamnese_id:
                    cursor.execute(
                        "SELECT dados_anamnese, status FROM anamneses_digitais WHERE id = %s",
                        (anamnese_id,)
                    )
                    anamnese_data = cursor.fetchone()
                    if anamnese_data:
                        dados_preenchidos = anamnese_data[0]
                        status_anamnese = anamnese_data[1]
                
                # Marcar token como acessado (atualizar última visualização)
                update_query = """
                    UPDATE anamnese_envios
                    SET visualizado_em = NOW()
                    WHERE token_id = (
                        SELECT id FROM anamnese_tokens WHERE token = %s
                    )
                    AND visualizado_em IS NULL
                """
                cursor.execute(update_query, (token,))
                conn.commit()
                
                return {
                    "valido": True,
                    "paciente_id": paciente_id,
                    "dependente_id": dependente_id,
                    "paciente_nome": nome,
                    "paciente_cpf": cpf,
                    "anamnese_id": anamnese_id,
                    "dados_preenchidos": dados_preenchidos,
                    "pode_editar": anamnese_id is None or status_anamnese in [AnamneseStatus.RASCUNHO, AnamneseStatus.AGUARDANDO_ASSINATURA]
                }
                
        except Exception as e:
            logger.error(f"Erro ao obter anamnese por token: {str(e)}")
            raise
    
    @staticmethod
    def assinar_anamnese(anamnese_id: int, assinatura_data: Dict[str, Any]) -> bool:
        """Registra assinatura digital da anamnese"""
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Inserir assinatura
                insert_query = """
                    INSERT INTO anamnese_assinaturas (
                        anamnese_id, tipo_assinatura, nome_assinante,
                        cpf_assinante, foto_selfie, assinatura_digital,
                        ip_address, user_agent, geolocalizacao
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """
                
                cursor.execute(insert_query, (
                    anamnese_id,
                    assinatura_data['tipo_assinatura'],
                    assinatura_data['nome_assinante'],
                    assinatura_data['cpf_assinante'],
                    assinatura_data['foto_selfie'],
                    assinatura_data['assinatura_digital'],
                    assinatura_data.get('ip_address'),
                    assinatura_data.get('user_agent'),
                    json.dumps(assinatura_data.get('geolocalizacao', {}))
                ))
                
                # Atualizar status da anamnese
                validade_ate = datetime.now() + timedelta(days=365)  # 1 ano
                
                update_query = """
                    UPDATE anamneses_digitais
                    SET status = %s,
                        signed_at = NOW(),
                        validade_ate = %s
                    WHERE id = %s
                """
                
                cursor.execute(update_query, (
                    AnamneseStatus.ASSINADO,
                    validade_ate,
                    anamnese_id
                ))
                
                # Marcar token como usado se foi via link público
                if 'token' in assinatura_data:
                    token_query = """
                        UPDATE anamnese_tokens
                        SET used = true,
                            used_at = NOW(),
                            ip_usado = %s,
                            user_agent_usado = %s
                        WHERE token = %s
                    """
                    cursor.execute(token_query, (
                        assinatura_data.get('ip_address'),
                        assinatura_data.get('user_agent'),
                        assinatura_data['token']
                    ))
                
                conn.commit()
                logger.info(f"Anamnese {anamnese_id} assinada com sucesso")
                
                return True
                
        except Exception as e:
            logger.error(f"Erro ao assinar anamnese: {str(e)}")
            raise