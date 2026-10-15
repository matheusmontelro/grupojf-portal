from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# Importar o Model SQLAlchemy correspondente
from ..models.forma_pagamento import FormaPagamento
# Importar a dependência para obter a sessão do DB
from ..database.db import get_db # Ajuste se necessário

# --- Schemas Pydantic para Formas de Pagamento ---

class FormaPagamentoBase(BaseModel):
    nome: str = Field(..., max_length=100, description="Nome da forma de pagamento (ex: Dinheiro, Pix, Cartão Crédito)")
    # No schema Pydantic, representamos o JSONB como uma lista opcional de strings
    categorias: Optional[List[str]] = Field(None, description="Lista de categorias associadas (ex: ['À Vista', 'Cartão'])")
    ativo: bool = True

    class Config:
        from_attributes = True

class FormaPagamentoCreate(FormaPagamentoBase):
    # Nenhum campo adicional necessário para criar, herda de Base
    pass

class FormaPagamentoUpdate(BaseModel):
    # Todos os campos são opcionais na atualização
    nome: Optional[str] = Field(None, max_length=100)
    categorias: Optional[List[str]] = None
    ativo: Optional[bool] = None

    class Config:
        from_attributes = True

class FormaPagamentoRead(FormaPagamentoBase):
    # Adiciona campos lidos do DB
    id: int
    created_at: datetime
    updated_at: datetime

# --- Router FastAPI ---

router = APIRouter(
    prefix="/formas-pagamento",
    tags=["Formas de Pagamento"]
)

# --- Endpoints CRUD ---

@router.post("/", response_model=FormaPagamentoRead, status_code=status.HTTP_201_CREATED)
def create_forma_pagamento(forma_pagamento: FormaPagamentoCreate, db: Session = Depends(get_db)):
    """
    Cria uma nova forma de pagamento.
    Verifica se o nome já existe.
    """
    db_fp_check = db.query(FormaPagamento).filter(FormaPagamento.nome == forma_pagamento.nome).first()
    if db_fp_check:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Forma de pagamento com nome '{forma_pagamento.nome}' já existe.")

    # SQLAlchemy geralmente lida com a conversão list -> JSONB automaticamente para PG
    db_fp = FormaPagamento(**forma_pagamento.model_dump())
    try:
        db.add(db_fp)
        db.commit()
        db.refresh(db_fp)
        return db_fp
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao salvar forma de pagamento: {e}")

@router.get("/", response_model=List[FormaPagamentoRead])
def read_formas_pagamento(
    skip: int = 0,
    limit: int = 100,
    ativo: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna uma lista de formas de pagamento, com paginação e filtro opcional por status 'ativo'.
    """
    query = db.query(FormaPagamento)
    if ativo is not None:
        query = query.filter(FormaPagamento.ativo == ativo)

    formas_pagamento = query.offset(skip).limit(limit).all()
    return formas_pagamento

@router.get("/{fp_id}", response_model=FormaPagamentoRead)
def read_forma_pagamento(fp_id: int, db: Session = Depends(get_db)):
    """
    Retorna uma forma de pagamento específica pelo seu ID.
    """
    db_fp = db.query(FormaPagamento).filter(FormaPagamento.id == fp_id).first()
    if db_fp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forma de pagamento não encontrada")
    return db_fp

@router.put("/{fp_id}", response_model=FormaPagamentoRead)
def update_forma_pagamento(fp_id: int, forma_pagamento_update: FormaPagamentoUpdate, db: Session = Depends(get_db)):
    """
    Atualiza uma forma de pagamento existente pelo seu ID.
    """
    db_fp = db.query(FormaPagamento).filter(FormaPagamento.id == fp_id).first()
    if db_fp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forma de pagamento não encontrada")

    # Verifica se o novo nome (se fornecido e diferente do atual) já existe
    if forma_pagamento_update.nome and forma_pagamento_update.nome != db_fp.nome:
         existing_name = db.query(FormaPagamento).filter(FormaPagamento.nome == forma_pagamento_update.nome).first()
         if existing_name:
              raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Forma de pagamento com nome '{forma_pagamento_update.nome}' já existe.")

    update_data = forma_pagamento_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        # O SQLAlchemy deve lidar com a atribuição da lista Python à coluna JSONB
        setattr(db_fp, key, value)

    try:
        db.add(db_fp)
        db.commit()
        db.refresh(db_fp)
        return db_fp
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar forma de pagamento: {e}")

@router.delete("/{fp_id}", response_model=FormaPagamentoRead)
def delete_forma_pagamento(fp_id: int, db: Session = Depends(get_db)):
    """
    Marca uma forma de pagamento como inativa (soft delete).
    """
    db_fp = db.query(FormaPagamento).filter(FormaPagamento.id == fp_id).first()
    if db_fp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forma de pagamento não encontrada")

    if not db_fp.ativo:
        return db_fp # Já está inativa, apenas retorna

    db_fp.ativo = False
    try:
        db.add(db_fp)
        db.commit()
        db.refresh(db_fp)
        return db_fp # Retorna o objeto atualizado (agora inativo)
    except Exception as e:
        db.rollback()
        # É improvável ter erro aqui, mas por segurança
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao inativar forma de pagamento: {e}")