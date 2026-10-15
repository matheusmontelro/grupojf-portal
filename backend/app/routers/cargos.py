from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import logging
from sqlalchemy.orm import Session

# Importando nossos modelos Pydantic
from ..models.cargos import CargoCreate, CargoUpdate, CargoRead, Cargo
from ..database.db import DatabaseConnection

# Criando logger para o módulo
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cargos", tags=["cargos"])

@router.get("/", response_model=List[CargoRead])
def list_all_cargos():
    """
    Retorna todos os cargos.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id, nome, codigo, descricao, ativo, created_at, updated_at
            FROM cargos 
            ORDER BY nome
        """)
        rows = cursor.fetchall()
    
    # Converter cada row em um dicionário compatível com CargoRead
    cargos = []
    for row in rows:
        cargos.append({
            "id": row[0],
            "nome": row[1],
            "codigo": row[2],
            "descricao": row[3],
            "ativo": row[4],
            "created_at": row[5],
            "updated_at": row[6]
        })
    return cargos

@router.get("/{cargo_id}", response_model=CargoRead)
def get_cargo_by_id(cargo_id: int):
    """
    Retorna um cargo pelo ID.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id, nome, codigo, descricao, ativo, created_at, updated_at
            FROM cargos
            WHERE id = %s
        """, (cargo_id,))
        row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Cargo não encontrado.")
    
    return {
        "id": row[0],
        "nome": row[1],
        "codigo": row[2],
        "descricao": row[3],
        "ativo": row[4],
        "created_at": row[5],
        "updated_at": row[6]
    }

@router.post("/", response_model=CargoRead, status_code=status.HTTP_201_CREATED)
def create_cargo(cargo_data: CargoCreate):
    """
    Cria um novo cargo.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se nome já existe
        cursor.execute("SELECT id FROM cargos WHERE nome = %s", (cargo_data.nome,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Nome de cargo já cadastrado.")

        # Verificar se código já existe (se fornecido)
        if cargo_data.codigo:
            cursor.execute("SELECT id FROM cargos WHERE codigo = %s", (cargo_data.codigo,))
            existing = cursor.fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Código de cargo já cadastrado.")

        # Construir campos e valores
        fields = ["nome"]
        values = [cargo_data.nome]
        
        if cargo_data.codigo is not None:
            fields.append("codigo")
            values.append(cargo_data.codigo)
            
        if cargo_data.descricao is not None:
            fields.append("descricao")
            values.append(cargo_data.descricao)
            
        if cargo_data.ativo is not None:
            fields.append("ativo")
            values.append(cargo_data.ativo)
        
        # Construir a query
        placeholders = ", ".join(["%s"] * len(values))
        field_names = ", ".join(fields)
        
        query = f"""
            INSERT INTO cargos ({field_names})
            VALUES ({placeholders})
            RETURNING id, created_at, updated_at
        """
        
        # Executar a query
        cursor.execute(query, values)
        new_id, created_at, updated_at = cursor.fetchone()
        conn.commit()
        
        # Retornar o cargo completo
        return {
            "id": new_id,
            "nome": cargo_data.nome,
            "codigo": cargo_data.codigo,
            "descricao": cargo_data.descricao,
            "ativo": cargo_data.ativo if cargo_data.ativo is not None else True,
            "created_at": created_at,
            "updated_at": updated_at
        }

@router.put("/{cargo_id}", response_model=CargoRead)
def update_cargo(cargo_id: int, cargo_data: CargoUpdate):
    """
    Atualiza um cargo existente.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se o cargo existe
        cursor.execute("SELECT id FROM cargos WHERE id = %s", (cargo_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Cargo não encontrado.")
        
        # Verificar unicidade do nome (se fornecido)
        if cargo_data.nome is not None:
            cursor.execute("SELECT id FROM cargos WHERE nome = %s AND id != %s", (cargo_data.nome, cargo_id))
            nome_exists = cursor.fetchone()
            if nome_exists:
                raise HTTPException(status_code=400, detail="Nome de cargo já utilizado.")
        
        # Verificar unicidade do código (se fornecido)
        if cargo_data.codigo is not None:
            cursor.execute("SELECT id FROM cargos WHERE codigo = %s AND id != %s", (cargo_data.codigo, cargo_id))
            codigo_exists = cursor.fetchone()
            if codigo_exists:
                raise HTTPException(status_code=400, detail="Código de cargo já utilizado.")
        
        # Preparar campos para atualização
        updates = []
        values = []
        
        if cargo_data.nome is not None:
            updates.append("nome = %s")
            values.append(cargo_data.nome)
        
        if cargo_data.codigo is not None:
            updates.append("codigo = %s")
            values.append(cargo_data.codigo)
        
        if cargo_data.descricao is not None:
            updates.append("descricao = %s")
            values.append(cargo_data.descricao)
        
        if cargo_data.ativo is not None:
            updates.append("ativo = %s")
            values.append(cargo_data.ativo)
        
        # Se não houver campos para atualizar
        if not updates:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
        
        # Sempre atualizar updated_at
        updates.append("updated_at = CURRENT_TIMESTAMP")
        
        # Construir a query
        update_query = f"""
            UPDATE cargos
            SET {", ".join(updates)}
            WHERE id = %s
            RETURNING id, nome, codigo, descricao, ativo, created_at, updated_at
        """
        
        # Adicionar ID no final para WHERE
        values.append(cargo_id)
        
        # Executar a query
        cursor.execute(update_query, values)
        updated_row = cursor.fetchone()
        conn.commit()
        
        # Retornar o cargo atualizado
        return {
            "id": updated_row[0],
            "nome": updated_row[1],
            "codigo": updated_row[2],
            "descricao": updated_row[3],
            "ativo": updated_row[4],
            "created_at": updated_row[5],
            "updated_at": updated_row[6]
        }

@router.delete("/{cargo_id}")
def delete_cargo(cargo_id: int):
    """
    Exclui um cargo pelo ID.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se o cargo existe
        cursor.execute("SELECT id FROM cargos WHERE id = %s", (cargo_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Cargo não encontrado.")
        
        # Verificar se o cargo está sendo usado por algum usuário
        cursor.execute("SELECT id FROM users WHERE cargo_id = %s LIMIT 1", (cargo_id,))
        has_users = cursor.fetchone()
        if has_users:
            raise HTTPException(
                status_code=400, 
                detail="Não é possível excluir o cargo porque está associado a usuários."
            )
        
        # Excluir o cargo
        cursor.execute("DELETE FROM cargos WHERE id = %s", (cargo_id,))
        conn.commit()
        
        return {"message": f"Cargo ID {cargo_id} excluído com sucesso."}