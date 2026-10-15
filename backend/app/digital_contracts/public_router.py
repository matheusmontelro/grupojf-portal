# app/digital_contracts/public_router.py

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from datetime import datetime
import logging
import io
from ..database.db import DatabaseConnection
from ..services.html_contract_pdf_generator import HTMLContractPDFGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public/contratos", tags=["contratos-public"])

@router.get("/{access_token}/pdf")
def download_contract_pdf_public(access_token: str):
    """
    Download público do PDF do contrato assinado via token de acesso
    """
    try:
        logger.info("Download público de PDF de contrato solicitado")
        
        # Buscar contrato assinado pelo token de acesso
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id, c.paciente_id, c.odontograma_id, c.valor_total, 
                       c.status, c.contract_data, c.signed_at, c.dependente_id,
                       p.nome_paciente, p.cpf_cnpj, p.unidade
                FROM digital_contracts c
                JOIN pacientes p ON c.paciente_id = p.paciente_id
                WHERE c.access_token = %s AND c.status = 'signed'
            """, (access_token,))
            
            result = cursor.fetchone()
            if not result:
                logger.warning("Contrato não encontrado ou não assinado para download")
                raise HTTPException(404, "Contrato não encontrado ou não assinado")
            
            contract_id, paciente_id, odontograma_id, valor_total, status, contract_data_json, signed_at, dependente_id, paciente_nome, paciente_cpf, unidade = result
            logger.info("Contrato assinado localizado para geração do PDF (id=%s)", contract_id)
        
        # Gerar PDF usando o HTML real do contrato assinado
        logger.info("Gerando PDF do HTML do contrato assinado...")
        pdf_generator = HTMLContractPDFGenerator()
        pdf_bytes = pdf_generator.generate_pdf_from_contract_html(access_token)
        logger.info(f"✅ PDF gerado com {len(pdf_bytes)} bytes")
        
        # Preparar nome do arquivo
        filename_safe = paciente_nome.replace(' ', '_').replace('/', '_').replace('\\', '_')
        filename = f"contrato_{filename_safe}.pdf"
        
        # Retornar PDF como download
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Falha no download público do contrato (%s)", type(e).__name__)
        raise HTTPException(500, f"Erro ao gerar PDF: {str(e)}")
