# app/digital_contracts/selfie_test_router.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import base64
import io
from ..database.db import DatabaseConnection

router = APIRouter(prefix="/public/selfie-test", tags=["selfie-test"])

@router.get("/{access_token}")
def download_raw_selfie(access_token: str):
    """
    Download da selfie crua (original) como foi salva no banco
    """
    try:
        # Buscar contrato no banco
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.contract_data, p.nome_paciente
                FROM digital_contracts c
                JOIN pacientes p ON c.paciente_id = p.paciente_id
                WHERE c.access_token = %s AND c.status = 'signed'
            """, (access_token,))
            
            result = cursor.fetchone()
            if not result:
                raise HTTPException(404, "Contrato não encontrado")
            
            contract_data, paciente_nome = result
        
        # Extrair selfie do JSON
        selfie_data = contract_data.get('selfie')
        if not selfie_data:
            raise HTTPException(404, "Selfie não encontrada neste contrato")
        
        # Verificar formato base64
        if not selfie_data.startswith('data:image/'):
            raise HTTPException(400, "Formato de selfie inválido")
        
        # Extrair dados base64
        if ',' in selfie_data:
            header, base64_data = selfie_data.split(',', 1)
        else:
            raise HTTPException(400, "Formato base64 inválido")
        
        # Decodificar imagem
        try:
            image_bytes = base64.b64decode(base64_data)
        except Exception as e:
            raise HTTPException(400, f"Erro ao decodificar base64: {e}")
        
        # Preparar nome do arquivo
        filename_safe = paciente_nome.replace(' ', '_').replace('/', '_').replace('\\', '_')
        filename = f"selfie_crua_{filename_safe}.jpg"
        
        # Retornar imagem como download
        return StreamingResponse(
            io.BytesIO(image_bytes),
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Selfie-Info": f"Size: {len(image_bytes)} bytes, Base64: {len(base64_data)} chars"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao processar selfie: {str(e)}")