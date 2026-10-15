# Odontogram type routes.
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator # Field e validator não estão sendo usados aqui, mas mantidos do original
from datetime import datetime
import urllib.parse # Para decodificar o nome do tipo, se necessário

from app.database.db import get_db
from app.models.tipos_odontograma import TipoOdontograma # Modelo SQLAlchemy

router = APIRouter(
    prefix="/tipos-odontograma",
    tags=["tipos_odontograma"],
    responses={404: {"description": "Tipo de Odontograma não encontrado"}}
)

# --- Modelos Pydantic ---
class TipoOdontogramaBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    valor_base: Optional[float] = None
    qtd_parcelas: Optional[int] = None
    ativo: bool = True

class TipoOdontogramaCreate(TipoOdontogramaBase):
    pass

class TipoOdontogramaUpdate(TipoOdontogramaBase):
    nome: Optional[str] = None # Permite atualizar o nome
    # Mantém os outros campos como opcionais para atualização parcial
    descricao: Optional[str] = None
    valor_base: Optional[float] = None
    qtd_parcelas: Optional[int] = None
    ativo: Optional[bool] = None


class TipoOdontogramaResponse(TipoOdontogramaBase):
    id: int
    created_at: datetime # Supondo que o modelo SQLAlchemy tenha este campo

    class Config:
        orm_mode = True

# --- Operações CRUD ---

@router.post("/", response_model=TipoOdontogramaResponse, status_code=status.HTTP_201_CREATED)
def create_tipo_odontograma(tipo: TipoOdontogramaCreate, db: Session = Depends(get_db)):
    """
    Cria um novo tipo de odontograma.
    """
    # Verifica se já existe um tipo com o mesmo nome para evitar erro de constraint UNIQUE
    existing_tipo = db.query(TipoOdontograma).filter(TipoOdontograma.nome == tipo.nome).first()
    if existing_tipo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de odontograma com este nome já existe"
        )

    db_tipo = TipoOdontograma(**tipo.dict())
    db.add(db_tipo)
    try:
        db.commit()
        db.refresh(db_tipo)
        return db_tipo
    except Exception as e: # Captura exceções mais genéricas também
        db.rollback()
        # A verificação de constraint unique (como 'tipos_odontograma_nome_key')
        # pode variar dependendo do dialeto do banco de dados e da mensagem de erro exata.
        # A verificação acima para nome duplicado é mais robusta.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar tipo de odontograma: {str(e)}"
        )

@router.get("/", response_model=List[TipoOdontogramaResponse])
def get_tipos_odontograma(
    skip: int = 0, 
    limit: int = 100, 
    ativos: Optional[bool] = None, # Parâmetro para filtrar por status 'ativo'
    db: Session = Depends(get_db)
):
    """
    Lista todos os tipos de odontograma, com opção de filtrar por ativos/inativos.
    """
    query = db.query(TipoOdontograma)
    if ativos is not None:
        query = query.filter(TipoOdontograma.ativo == ativos)
    return query.offset(skip).limit(limit).all()

@router.get("/{tipo_id}", response_model=TipoOdontogramaResponse)
def get_tipo_odontograma_by_id(tipo_id: int, db: Session = Depends(get_db)): # Renomeado para clareza
    """
    Obtém um tipo de odontograma específico pelo seu ID.
    """
    db_tipo = db.query(TipoOdontograma).filter(TipoOdontograma.id == tipo_id).first()
    if db_tipo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tipo de odontograma com ID {tipo_id} não encontrado"
        )
    return db_tipo

# --- NOVA ROTA ---
@router.get("/por-nome/{nome_tipo_encoded}", response_model=TipoOdontogramaResponse)
def get_tipo_odontograma_by_name(nome_tipo_encoded: str, db: Session = Depends(get_db)):
    """
    Obtém um tipo de odontograma específico pelo seu nome.
    O nome do tipo é esperado estar URL-encoded no path.
    """
    try:
        # Decodifica o nome do tipo que vem da URL (ex: %20 para espaço, %2B para +)
        nome_tipo = urllib.parse.unquote(nome_tipo_encoded)
    except Exception as e:
        # Em caso de erro na decodificação, retorna um erro HTTP.
        # Isso é improvável com urllib.parse.unquote, mas é uma boa prática.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nome do tipo malformado na URL: {str(e)}"
        )
    
    print(f"Backend: Buscando tipo de odontograma por nome decodificado: '{nome_tipo}'") # Log para debug

    db_tipo = db.query(TipoOdontograma).filter(TipoOdontograma.nome == nome_tipo).first()
    
    if db_tipo is None:
        print(f"Backend: Tipo de odontograma com nome '{nome_tipo}' NÃO encontrado.") # Log para debug
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tipo de odontograma com nome '{nome_tipo}' não encontrado"
        )
    print(f"Backend: Tipo de odontograma com nome '{nome_tipo}' encontrado: {db_tipo}") # Log para debug
    return db_tipo
# --- FIM DA NOVA ROTA ---

@router.put("/{tipo_id}", response_model=TipoOdontogramaResponse)
def update_tipo_odontograma(tipo_id: int, tipo: TipoOdontogramaUpdate, db: Session = Depends(get_db)):
    """
    Atualiza um tipo de odontograma existente.
    """
    db_tipo = db.query(TipoOdontograma).filter(TipoOdontograma.id == tipo_id).first()
    if db_tipo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tipo de odontograma com ID {tipo_id} não encontrado"
        )
    
    update_data = tipo.dict(exclude_unset=True)

    # Se o nome está sendo atualizado, verificar se o novo nome já existe (exceto para o próprio objeto)
    if "nome" in update_data and update_data["nome"] != db_tipo.nome:
        existing_tipo_with_new_name = db.query(TipoOdontograma).filter(TipoOdontograma.nome == update_data["nome"]).first()
        if existing_tipo_with_new_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Outro tipo de odontograma já existe com o nome '{update_data['nome']}'"
            )

    for key, value in update_data.items():
        setattr(db_tipo, key, value)
    
    try:
        db.commit()
        db.refresh(db_tipo)
        return db_tipo
    except Exception as e:
        db.rollback()
        # A verificação de constraint unique de nome já foi feita acima de forma mais explícita
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar tipo de odontograma: {str(e)}"
        )

@router.delete("/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tipo_odontograma(tipo_id: int, db: Session = Depends(get_db)):
    """
    Deleta um tipo de odontograma.
    """
    db_tipo = db.query(TipoOdontograma).filter(TipoOdontograma.id == tipo_id).first()
    if db_tipo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tipo de odontograma com ID {tipo_id} não encontrado"
        )
    
    db.delete(db_tipo)
    db.commit()
    return None # Retorna None e status 204 como padrão para DELETE bem-sucedido
