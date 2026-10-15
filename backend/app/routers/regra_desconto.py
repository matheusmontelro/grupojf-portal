from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field, model_validator # Importar model_validator para Pydantic v2
from typing import List, Optional
from datetime import datetime
from decimal import Decimal # Usar Decimal para precisão monetária/percentual

# Importar Models SQLAlchemy
from ..models.regra_desconto import RegraDesconto
# Importar Schema de FormaPagamento (do seu respectivo arquivo de router agora)
from .forma_pagamento import FormaPagamentoRead
# Importar a dependência para obter a sessão do DB
from ..database.db import get_db # Ajuste se necessário

# --- Schemas Pydantic para Regras de Desconto ---

class RegraDescontoBase(BaseModel):
    forma_pagamento_id: int
    parcela_min: int = Field(..., ge=1, description="Número mínimo de parcelas para esta regra")
    parcela_max: int = Field(..., ge=1, description="Número máximo de parcelas para esta regra")
    percentual_desconto: Decimal = Field(..., ge=0, decimal_places=2, description="Percentual de desconto (ex: 10.00 para 10%)")
    ativo: bool = True

    # Validador Pydantic v2 para garantir min <= max
    @model_validator(mode='after')
    def check_parcela_min_max(self) -> 'RegraDescontoBase':
        if self.parcela_min is not None and self.parcela_max is not None and self.parcela_min > self.parcela_max:
            raise ValueError('parcela_min não pode ser maior que parcela_max')
        return self

    class Config:
        from_attributes = True

class RegraDescontoCreate(RegraDescontoBase):
    pass

class RegraDescontoUpdate(BaseModel):
    # Todos opcionais na atualização
    forma_pagamento_id: Optional[int] = None
    parcela_min: Optional[int] = Field(None, ge=1)
    parcela_max: Optional[int] = Field(None, ge=1)
    percentual_desconto: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    ativo: Optional[bool] = None

    # Validador Pydantic v2 para garantir min <= max se ambos forem fornecidos
    @model_validator(mode='after')
    def check_parcela_min_max_update(self) -> 'RegraDescontoUpdate':
        # Só valida se ambos min e max estão presentes na atualização
        p_min = self.parcela_min
        p_max = self.parcela_max
        # Se um for None, precisamos buscar o valor existente para validar corretamente (lógica complexa para schema)
        # Uma validação mais simples (mas incompleta) seria só validar se ambos estão presentes
        if p_min is not None and p_max is not None and p_min > p_max:
             raise ValueError('parcela_min não pode ser maior que parcela_max')
        # Uma validação completa exigiria acesso ao objeto existente no DB dentro do PUT
        return self

    class Config:
        from_attributes = True

class RegraDescontoRead(RegraDescontoBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # Incluir dados da forma de pagamento relacionada
    forma_pagamento: Optional[FormaPagamentoRead] = None # Usando o Schema importado

# --- Router FastAPI ---

router = APIRouter(
    prefix="/regras-desconto",
    tags=["Regras de Desconto"]
)

# --- Endpoints CRUD + Busca ---

@router.post("/", response_model=RegraDescontoRead, status_code=status.HTTP_201_CREATED)
def create_regra_desconto(regra: RegraDescontoCreate, db: Session = Depends(get_db)):
    """
    Cria uma nova regra de desconto.
    (Validação de sobreposição de regras não implementada aqui, pode ser complexa)
    """
    # Validação extra: verificar se forma_pagamento_id existe (boa prática)
    # db_fp = db.query(FormaPagamento).filter(FormaPagamento.id == regra.forma_pagamento_id).first()
    # if not db_fp:
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Forma de pagamento com ID {regra.forma_pagamento_id} não encontrada.")

    db_regra = RegraDesconto(**regra.model_dump())
    try:
        db.add(db_regra)
        db.commit()
        db.refresh(db_regra)
        # Carrega relacionamento para retornar no response_model
        db.query(RegraDesconto).options(joinedload(RegraDesconto.forma_pagamento)).filter(RegraDesconto.id == db_regra.id).first()
        return db_regra
    except Exception as e:
        db.rollback()
        # Verifica erro de constraint do DB (min <= max)
        if 'chk_parcela_min_max' in str(e):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erro de validação: parcela_min não pode ser maior que parcela_max")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao salvar regra de desconto: {e}")


@router.get("/", response_model=List[RegraDescontoRead])
def read_regras_desconto(
    skip: int = 0,
    limit: int = 100,
    forma_pagamento_id: Optional[int] = None,
    ativo: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna uma lista de regras de desconto, com paginação e filtros opcionais.
    Inclui dados da forma de pagamento relacionada.
    """
    query = db.query(RegraDesconto).options(joinedload(RegraDesconto.forma_pagamento)) # Eager loading
    if forma_pagamento_id is not None:
        query = query.filter(RegraDesconto.forma_pagamento_id == forma_pagamento_id)
    if ativo is not None:
        query = query.filter(RegraDesconto.ativo == ativo)

    regras = query.order_by(RegraDesconto.forma_pagamento_id, RegraDesconto.parcela_min).offset(skip).limit(limit).all()
    return regras

@router.get("/buscar", response_model=Optional[RegraDescontoRead], summary="Busca Regra Aplicável")
def buscar_regra_aplicavel(
    forma_pagamento_id: int,
    qtd_parcelas: int = Query(..., ge=1, description="Quantidade de parcelas desejada"),
    db: Session = Depends(get_db)
):
    """
    Encontra a regra de desconto ativa aplicável para uma dada forma de
    pagamento e quantidade de parcelas. Retorna a regra ou null se nenhuma for encontrada.
    """
    regra = db.query(RegraDesconto)\
        .options(joinedload(RegraDesconto.forma_pagamento))\
        .filter(
            RegraDesconto.forma_pagamento_id == forma_pagamento_id,
            RegraDesconto.ativo == True,
            RegraDesconto.parcela_min <= qtd_parcelas,
            RegraDesconto.parcela_max >= qtd_parcelas
        ).first()

    # Não precisa de 404 aqui, retornar None (null no JSON) é o comportamento esperado se não achar
    return regra


@router.get("/{regra_id}", response_model=RegraDescontoRead)
def read_regra_desconto(regra_id: int, db: Session = Depends(get_db)):
    """
    Retorna uma regra de desconto específica pelo seu ID.
    Inclui dados da forma de pagamento relacionada.
    """
    db_regra = db.query(RegraDesconto).options(joinedload(RegraDesconto.forma_pagamento)).filter(RegraDesconto.id == regra_id).first()
    if db_regra is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regra de desconto não encontrada")
    return db_regra

@router.put("/{regra_id}", response_model=RegraDescontoRead)
def update_regra_desconto(regra_id: int, regra_update: RegraDescontoUpdate, db: Session = Depends(get_db)):
    """
    Atualiza uma regra de desconto existente pelo seu ID.
    """
    db_regra = db.query(RegraDesconto).filter(RegraDesconto.id == regra_id).first()
    if db_regra is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regra de desconto não encontrada")

    update_data = regra_update.model_dump(exclude_unset=True)

    # Validação min <= max se ambos forem alterados
    p_min = update_data.get('parcela_min', db_regra.parcela_min)
    p_max = update_data.get('parcela_max', db_regra.parcela_max)
    if p_min > p_max:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erro de validação: parcela_min não pode ser maior que parcela_max")

    for key, value in update_data.items():
        setattr(db_regra, key, value)

    try:
        db.add(db_regra)
        db.commit()
        db.refresh(db_regra)
        # Recarrega com relacionamento para o retorno
        db.query(RegraDesconto).options(joinedload(RegraDesconto.forma_pagamento)).filter(RegraDesconto.id == db_regra.id).first()
        return db_regra
    except Exception as e:
        db.rollback()
        if 'chk_parcela_min_max' in str(e):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erro de validação: parcela_min não pode ser maior que parcela_max")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar regra de desconto: {e}")

@router.delete("/{regra_id}", response_model=RegraDescontoRead)
def delete_regra_desconto(regra_id: int, db: Session = Depends(get_db)):
    """
    Marca uma regra de desconto como inativa (soft delete).
    """
    db_regra = db.query(RegraDesconto).filter(RegraDesconto.id == regra_id).first()
    if db_regra is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regra de desconto não encontrada")

    if not db_regra.ativo:
        db.query(RegraDesconto).options(joinedload(RegraDesconto.forma_pagamento)).filter(RegraDesconto.id == db_regra.id).first()
        return db_regra # Já inativa

    db_regra.ativo = False
    try:
        db.add(db_regra)
        db.commit()
        db.refresh(db_regra)
        db.query(RegraDesconto).options(joinedload(RegraDesconto.forma_pagamento)).filter(RegraDesconto.id == db_regra.id).first()
        return db_regra # Retorna o objeto atualizado (agora inativo)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao inativar regra de desconto: {e}")
    
def get_regra_desconto_aplicavel(db: Session, forma_pagamento_id: int, qtd_parcelas: int) -> Optional[RegraDesconto]:
    """
    Função auxiliar para obter a regra de desconto aplicável com base na forma de pagamento
    e quantidade de parcelas. Retorna None se não houver regra aplicável.
    """
    regra = db.query(RegraDesconto).filter(
        RegraDesconto.forma_pagamento_id == forma_pagamento_id,
        RegraDesconto.ativo == True,
        RegraDesconto.parcela_min <= qtd_parcelas,
        RegraDesconto.parcela_max >= qtd_parcelas
    ).first()
    
    return regra