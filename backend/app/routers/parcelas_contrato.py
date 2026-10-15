from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from datetime import date, datetime

from app.database.db import get_db
from app.models.parcelas_contrato import ParcelaContrato

router = APIRouter(
    prefix="/parcelas-contrato",
    tags=["parcelas_contrato"],
    responses={404: {"description": "Parcela de contrato não encontrada"}}
)

# Pydantic model para validação
class ParcelaContratoBase(BaseModel):
    contrato_id: Optional[int]
    numero_parcela: int
    valor_parcela: float
    data_vencimento: date
    status: Optional[str] = "Pendente"
    data_pagamento: Optional[datetime] = None
    valor_pago: Optional[float] = None
    metodo_pagamento: Optional[str] = None
    documento_ref: Optional[str] = None
    observacao: Optional[str] = None

class ParcelaContratoCreate(ParcelaContratoBase):
    contrato_id: int

class ParcelaContratoUpdate(BaseModel):
    numero_parcela: Optional[int] = None
    valor_parcela: Optional[float] = None
    data_vencimento: Optional[date] = None
    status: Optional[str] = None
    data_pagamento: Optional[datetime] = None
    valor_pago: Optional[float] = None
    metodo_pagamento: Optional[str] = None
    documento_ref: Optional[str] = None
    observacao: Optional[str] = None

class ParcelaContratoResponse(ParcelaContratoBase):
    parcela_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# CRUD operations
@router.post("/", response_model=ParcelaContratoResponse, status_code=status.HTTP_201_CREATED)
def create_parcela_contrato(parcela: ParcelaContratoCreate, db: Session = Depends(get_db)):
    # Verificar se o contrato existe (opcional)
    from app.models.contratos import Contrato
    db_contrato = db.query(Contrato).filter(Contrato.contrato_id == parcela.contrato_id).first()
    if not db_contrato:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contrato com ID {parcela.contrato_id} não existe"
        )

    # Verificar se já existe uma parcela com o mesmo número para este contrato
    existing_parcela = db.query(ParcelaContrato).filter(
        ParcelaContrato.contrato_id == parcela.contrato_id,
        ParcelaContrato.numero_parcela == parcela.numero_parcela
    ).first()
    
    if existing_parcela:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe uma parcela {parcela.numero_parcela} para o contrato {parcela.contrato_id}"
        )

    db_parcela = ParcelaContrato(**parcela.dict())
    db.add(db_parcela)
    try:
        db.commit()
        db.refresh(db_parcela)
        return db_parcela
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar parcela de contrato: {str(e)}"
        )

@router.get("/", response_model=List[ParcelaContratoResponse])
def get_parcelas_contrato(
    skip: int = 0, 
    limit: int = 100,
    contrato_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ParcelaContrato)
    
    if contrato_id:
        query = query.filter(ParcelaContrato.contrato_id == contrato_id)
    
    if status:
        query = query.filter(ParcelaContrato.status == status)
    
    return query.offset(skip).limit(limit).all()

@router.get("/{parcela_id}", response_model=ParcelaContratoResponse)
def get_parcela_contrato(parcela_id: int, db: Session = Depends(get_db)):
    db_parcela = db.query(ParcelaContrato).filter(ParcelaContrato.parcela_id == parcela_id).first()
    if db_parcela is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela de contrato com ID {parcela_id} não encontrada"
        )
    return db_parcela

@router.put("/{parcela_id}", response_model=ParcelaContratoResponse)
def update_parcela_contrato(parcela_id: int, parcela: ParcelaContratoUpdate, db: Session = Depends(get_db)):
    db_parcela = db.query(ParcelaContrato).filter(ParcelaContrato.parcela_id == parcela_id).first()
    if db_parcela is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela de contrato com ID {parcela_id} não encontrada"
        )
    
    update_data = parcela.dict(exclude_unset=True)
    
    # Se o número da parcela for atualizado, precisamos verificar a unicidade
    if "numero_parcela" in update_data and update_data["numero_parcela"] != db_parcela.numero_parcela:
        existing_parcela = db.query(ParcelaContrato).filter(
            ParcelaContrato.contrato_id == db_parcela.contrato_id,
            ParcelaContrato.numero_parcela == update_data["numero_parcela"]
        ).first()
        
        if existing_parcela:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe uma parcela {update_data['numero_parcela']} para o contrato {db_parcela.contrato_id}"
            )
    
    for key, value in update_data.items():
        setattr(db_parcela, key, value)
    
    try:
        db.commit()
        db.refresh(db_parcela)
        return db_parcela
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar parcela de contrato: {str(e)}"
        )

@router.delete("/{parcela_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcela_contrato(parcela_id: int, db: Session = Depends(get_db)):
    db_parcela = db.query(ParcelaContrato).filter(ParcelaContrato.parcela_id == parcela_id).first()
    if db_parcela is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela de contrato com ID {parcela_id} não encontrada"
        )
    
    db.delete(db_parcela)
    db.commit()
    return None

# Endpoints adicionais

@router.get("/contrato/{contrato_id}", response_model=List[ParcelaContratoResponse])
def get_parcelas_by_contrato(contrato_id: int, db: Session = Depends(get_db)):
    """Obter todas as parcelas de um contrato específico"""
    parcelas = db.query(ParcelaContrato).filter(
        ParcelaContrato.contrato_id == contrato_id
    ).order_by(ParcelaContrato.numero_parcela).all()
    
    return parcelas

@router.post("/pagamento/{parcela_id}", response_model=ParcelaContratoResponse)
def registrar_pagamento(
    parcela_id: int, 
    db: Session = Depends(get_db),
    valor_pago: float = None,
    metodo_pagamento: str = None,
    documento_ref: str = None,
    observacao: str = None
):
    """Registrar o pagamento de uma parcela"""
    db_parcela = db.query(ParcelaContrato).filter(ParcelaContrato.parcela_id == parcela_id).first()
    if db_parcela is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parcela de contrato com ID {parcela_id} não encontrada"
        )
    
    # Atualizar os dados de pagamento
    db_parcela.status = "Pago"
    db_parcela.data_pagamento = datetime.now()
    
    if valor_pago is not None:
        db_parcela.valor_pago = valor_pago
    else:
        db_parcela.valor_pago = db_parcela.valor_parcela
    
    if metodo_pagamento:
        db_parcela.metodo_pagamento = metodo_pagamento
    
    if documento_ref:
        db_parcela.documento_ref = documento_ref
    
    if observacao:
        db_parcela.observacao = observacao
    
    try:
        db.commit()
        db.refresh(db_parcela)
        return db_parcela
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao registrar pagamento: {str(e)}"
        )