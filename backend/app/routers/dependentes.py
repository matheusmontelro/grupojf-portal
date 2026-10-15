# backend/app/routers/dependentes.py

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
import psycopg2
from datetime import date # Para DependenteUpdate

from app.database.db import DatabaseConnection
from app.models.pacientes import DependenteRead, DependenteUpdate # Importa os novos modelos

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/dependentes", 
    tags=["dependentes"],
    responses={404: {"description": "Não encontrado"}}
)

# Constante de colunas para SELECT na tabela dependentes
DEPENDENTE_COLS = """
    dependente_id, responsavel_paciente_id, nome_dependente, 
    data_nascimento_dependente, genero_dependente, parentesco, 
    observacoes_dependente, ativo, created_at, updated_at
"""

def _map_row_to_dependente_read(row) -> Optional[DependenteRead]:
    """ Mapeia uma linha do cursor para o schema DependenteRead. """
    if not row:
        return None
    return DependenteRead(
        dependente_id=row[0],
        responsavel_paciente_id=row[1],
        nome_dependente=row[2],
        data_nascimento_dependente=row[3],
        genero_dependente=row[4],
        parentesco=row[5],
        observacoes_dependente=row[6],
        ativo=row[7],
        created_at=row[8],
        updated_at=row[9]
    )

@router.get("/{dependente_id}", response_model=DependenteRead)
async def obter_dependente(dependente_id: int):
    """ Obtém os dados de um dependente específico. """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            query = f"SELECT {DEPENDENTE_COLS} FROM dependentes WHERE dependente_id = %s"
            cursor.execute(query, (dependente_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Dependente não encontrado")
            dependente = _map_row_to_dependente_read(row)
            return dependente
    except psycopg2.Error as e:
        logger.error(f"Erro de banco de dados ao obter dependente: {e}")
        raise HTTPException(status_code=500, detail=f"Erro de banco de dados: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao obter dependente: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@router.put("/{dependente_id}", response_model=DependenteRead)
async def atualizar_dependente(dependente_id: int, data: DependenteUpdate):
    """ Atualiza os dados de um dependente. """
    logger.info(f"Atualizando dependente ID={dependente_id} com dados: {data.model_dump(exclude_unset=True)}")
    
    if not data.model_dump(exclude_unset=True): # Verifica se há pelo menos um campo para atualizar
        raise HTTPException(
            status_code=400, 
            detail="Nenhum dado fornecido para atualização."
        )

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Primeiro, buscar o dependente para garantir que existe
            cursor.execute(f"SELECT {DEPENDENTE_COLS} FROM dependentes WHERE dependente_id = %s FOR UPDATE", (dependente_id,))
            current_row = cursor.fetchone()
            if not current_row:
                raise HTTPException(status_code=404, detail="Dependente não encontrado para atualização.")
            
            # Construir a query de atualização dinamicamente
            update_fields = []
            update_values = []
            
            update_data_dict = data.model_dump(exclude_unset=True) # Pega só os campos enviados
            
            for key, value in update_data_dict.items():
                update_fields.append(f"{key} = %s")
                update_values.append(value)
            
            if not update_fields:
                 # Se por alguma razão (ex: todos os valores são None e exclude_none foi usado)
                 # ou se o modelo de update só tem campos opcionais e nenhum foi passado.
                 # Esta checagem já foi feita no início, mas é uma segurança.
                logger.info("Nenhum campo válido para atualizar após processamento.")
                return _map_row_to_dependente_read(current_row) # Retorna o dependente sem alterações

            update_values.append(dependente_id) # Para a cláusula WHERE
            
            query = f"""
                UPDATE dependentes
                SET {', '.join(update_fields)}
                WHERE dependente_id = %s
                RETURNING {DEPENDENTE_COLS};
            """
            
            logger.debug(f"Query de atualização do dependente: {query}")
            logger.debug(f"Valores para atualização: {update_values}")

            cursor.execute(query, tuple(update_values))
            updated_row = cursor.fetchone()
            conn.commit() # Commit é feito pelo __exit__ da DatabaseConnection se não houver erro
            
            if not updated_row:
                # Isso não deveria acontecer se a busca inicial (FOR UPDATE) encontrou o registro
                # e a query de update está correta.
                raise HTTPException(status_code=500, detail="Falha ao atualizar o dependente após a execução da query.")

            logger.info(f"Dependente ID={dependente_id} atualizado com sucesso.")
            return _map_row_to_dependente_read(updated_row)
            
    except psycopg2.Error as db_err:
        logger.error(f"Erro de banco de dados ao atualizar dependente: {db_err}")
        # conn.rollback() é feito pelo __exit__
        raise HTTPException(status_code=500, detail=f"Erro de banco de dados ao atualizar: {str(db_err)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao atualizar dependente: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno inesperado ao atualizar: {str(e)}")

@router.delete("/{dependente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_dependente(dependente_id: int):
    """ Deleta um dependente (ou marca como inativo). Por ora, marca como inativo. """
    logger.info(f"Tentando marcar como inativo o dependente ID={dependente_id}")
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            # Marcar como inativo em vez de deletar permanentemente
            cursor.execute("UPDATE dependentes SET ativo = FALSE WHERE dependente_id = %s RETURNING dependente_id", (dependente_id,))
            deleted_row = cursor.fetchone()
            # conn.commit() é gerenciado pelo context manager
            
            if not deleted_row:
                raise HTTPException(status_code=404, detail="Dependente não encontrado para desativar.")
            
            logger.info(f"Dependente ID={dependente_id} marcado como inativo.")
            return # Retorna 204 No Content implicitamente
            
    except psycopg2.Error as db_err:
        logger.error(f"Erro de banco de dados ao desativar dependente: {db_err}")
        raise HTTPException(status_code=500, detail=f"Erro de banco de dados ao desativar: {str(db_err)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao desativar dependente: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno ao desativar: {str(e)}") 