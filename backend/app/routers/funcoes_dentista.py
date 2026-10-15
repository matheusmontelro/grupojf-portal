from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# Importar o Model SQLAlchemy correspondente
from ..models.funcao_dentista import FuncaoDentista
# Importar a dependência para obter a sessão do DB
from ..database.db import get_db

# --- Schemas Pydantic para Funções de Dentista ---

class FuncaoDentistaBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100, description="Nome da função/especialidade")
    descricao: Optional[str] = Field(None, description="Descrição da função")
    ativo: bool = True

    class Config:
        from_attributes = True

class FuncaoDentistaCreate(FuncaoDentistaBase):
    pass

class FuncaoDentistaUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=1, max_length=100)
    descricao: Optional[str] = None
    ativo: Optional[bool] = None

    class Config:
        from_attributes = True

class FuncaoDentistaRead(FuncaoDentistaBase):
    id: int
    created_at: datetime
    updated_at: datetime

# --- Router FastAPI ---

router = APIRouter(
    prefix="/funcoes-dentista",
    tags=["Funções de Dentista"]
)

# --- Endpoints CRUD ---

@router.post("/", response_model=FuncaoDentistaRead, status_code=status.HTTP_201_CREATED)
def create_funcao_dentista(funcao: FuncaoDentistaCreate, db: Session = Depends(get_db)):
    """
    Cria uma nova função/especialidade de dentista.
    Verifica se o nome já existe.
    """
    # Verificar se já existe uma função com o mesmo nome
    db_funcao_check = db.query(FuncaoDentista).filter(FuncaoDentista.nome.ilike(funcao.nome)).first()
    if db_funcao_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Função '{funcao.nome}' já está registrada."
        )

    db_funcao = FuncaoDentista(**funcao.model_dump())
    try:
        db.add(db_funcao)
        db.commit()
        db.refresh(db_funcao)
        return db_funcao
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Erro ao salvar função: {e}"
        )

@router.get("/", response_model=List[FuncaoDentistaRead])
def read_funcoes_dentista(
    skip: int = 0,
    limit: int = 100,
    ativo: Optional[bool] = None,
    nome: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna uma lista de funções de dentista, com paginação e filtros opcionais.
    """
    query = db.query(FuncaoDentista)
    
    if ativo is not None:
        query = query.filter(FuncaoDentista.ativo == ativo)
    
    if nome:
        query = query.filter(FuncaoDentista.nome.ilike(f"%{nome}%"))
    
    # Ordenar por nome
    query = query.order_by(FuncaoDentista.nome)
    
    funcoes = query.offset(skip).limit(limit).all()
    return funcoes

@router.get("/{funcao_id}", response_model=FuncaoDentistaRead)
def read_funcao_dentista(funcao_id: int, db: Session = Depends(get_db)):
    """
    Retorna uma função específica pelo seu ID.
    """
    db_funcao = db.query(FuncaoDentista).filter(FuncaoDentista.id == funcao_id).first()
    if db_funcao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Função não encontrada"
        )
    return db_funcao

@router.put("/{funcao_id}", response_model=FuncaoDentistaRead)
def update_funcao_dentista(funcao_id: int, funcao_update: FuncaoDentistaUpdate, db: Session = Depends(get_db)):
    """
    Atualiza uma função existente pelo seu ID.
    """
    db_funcao = db.query(FuncaoDentista).filter(FuncaoDentista.id == funcao_id).first()
    if db_funcao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Função não encontrada"
        )

    # Verifica se o novo nome (se fornecido e diferente do atual) já existe
    if funcao_update.nome and funcao_update.nome != db_funcao.nome:
        existing_nome = db.query(FuncaoDentista).filter(
            FuncaoDentista.nome.ilike(funcao_update.nome)
        ).first()
        if existing_nome:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Função '{funcao_update.nome}' já pertence a outro registro."
            )

    update_data = funcao_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_funcao, key, value)

    try:
        db.add(db_funcao)
        db.commit()
        db.refresh(db_funcao)
        return db_funcao
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Erro ao atualizar função: {e}"
        )

@router.delete("/{funcao_id}", response_model=FuncaoDentistaRead)
def delete_funcao_dentista(funcao_id: int, db: Session = Depends(get_db)):
    """
    Marca uma função como inativa (soft delete).
    Não exclui o registro permanentemente.
    """
    db_funcao = db.query(FuncaoDentista).filter(FuncaoDentista.id == funcao_id).first()
    if db_funcao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Função não encontrada"
        )

    if not db_funcao.ativo:
        return db_funcao

    db_funcao.ativo = False
    try:
        db.add(db_funcao)
        db.commit()
        db.refresh(db_funcao)
        return db_funcao
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Erro ao inativar função: {e}"
        )