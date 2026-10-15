from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal

from app.database.db import get_db
from app.models.empresa_regras_split import EmpresaRegrasSplit
from app.models.empresa_regras_split import (
    EmpresaRegrasSplitCreate,
    EmpresaRegrasSplitUpdate,
    EmpresaRegrasSplitRead,
    EmpresaRegrasSplitDetail
)
# Importar os modelos de Empresa e TipoOdontograma diretamente
from app.models.empresa import Empresa
from app.models.tipos_odontograma import TipoOdontograma

router = APIRouter(
    prefix="/api/empresa-regras-split",
    tags=["empresas", "regras-split"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[EmpresaRegrasSplitDetail])
def get_all_regras(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    unidade: Optional[str] = None,
    tipo_odontograma_id: Optional[int] = None,
    empresa_id: Optional[int] = None,
    ativo: Optional[bool] = None
):
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"[EMPRESA-REGRAS] Buscando regras - unidade: '{unidade}', tipo_odontograma: {tipo_odontograma_id}")

    query = db.query(EmpresaRegrasSplit)

    # Filtrar por tipo de odontograma se especificado
    if tipo_odontograma_id is not None:
        query = query.filter(EmpresaRegrasSplit.tipo_odontograma_id == tipo_odontograma_id)

    # Filtrar por empresa se especificado
    if empresa_id is not None:
        query = query.filter(EmpresaRegrasSplit.empresa_id == empresa_id)

    # Filtrar por status ativo se especificado
    if ativo is not None:
        query = query.filter(EmpresaRegrasSplit.ativo == ativo)

    # Filtrar por unidade se especificado
    if unidade is not None and unidade != "":
        logger.info(f"[EMPRESA-REGRAS] Filtrando por unidade específica: '{unidade}'")
        query = query.filter(EmpresaRegrasSplit.unidade == unidade)
    elif unidade == "":
        # String vazia significa filtrar por regras gerais (sem unidade)
        logger.info(f"[EMPRESA-REGRAS] Filtrando por regras gerais (unidade IS NULL)")
        query = query.filter(EmpresaRegrasSplit.unidade.is_(None))
    else:
        logger.info(f"[EMPRESA-REGRAS] Sem filtro de unidade - retornando todas as regras")

    regras = query.offset(skip).limit(limit).all()
    logger.info(f"[EMPRESA-REGRAS] Encontradas {len(regras)} regras")
    
    result = []
    for regra in regras:
        # Obter nome da empresa e tipo de odontograma
        empresa = db.query(Empresa).filter(
            Empresa.id == regra.empresa_id
        ).first()
        
        tipo_odontograma = db.query(TipoOdontograma).filter(
            TipoOdontograma.id == regra.tipo_odontograma_id
        ).first()
        
        # Adicionar ao resultado
        regra_dict = regra.__dict__.copy()
        if "_sa_instance_state" in regra_dict:
            regra_dict.pop("_sa_instance_state")
            
        regra_dict["empresa_nome"] = empresa.razao_social if empresa else None
        regra_dict["tipo_odontograma_nome"] = tipo_odontograma.nome if tipo_odontograma else None
        
        result.append(regra_dict)
    
    return result

@router.get("/empresa/{empresa_id}", response_model=List[EmpresaRegrasSplitDetail])
def get_regras_by_empresa(empresa_id: int, db: Session = Depends(get_db)):
    regras = db.query(EmpresaRegrasSplit).filter(
        EmpresaRegrasSplit.empresa_id == empresa_id
    ).all()
    
    if not regras:
        raise HTTPException(status_code=404, detail="Regras para esta empresa não encontradas")
    
    result = []
    for regra in regras:
        # Obter nome da empresa e tipo de odontograma
        empresa = db.query(Empresa).filter(
            Empresa.id == regra.empresa_id
        ).first()
        
        tipo_odontograma = db.query(TipoOdontograma).filter(
            TipoOdontograma.id == regra.tipo_odontograma_id
        ).first()
        
        # Adicionar ao resultado
        regra_dict = regra.__dict__.copy()
        if "_sa_instance_state" in regra_dict:
            regra_dict.pop("_sa_instance_state")
            
        regra_dict["empresa_nome"] = empresa.razao_social if empresa else None
        regra_dict["tipo_odontograma_nome"] = tipo_odontograma.nome if tipo_odontograma else None
        
        result.append(regra_dict)
    
    return result

@router.get("/{id}", response_model=EmpresaRegrasSplitDetail)
def get_regra(id: int, db: Session = Depends(get_db)):
    regra = db.query(EmpresaRegrasSplit).filter(
        EmpresaRegrasSplit.id == id
    ).first()
    
    if not regra:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    
    # Obter nome da empresa e tipo de odontograma
    empresa = db.query(Empresa).filter(
        Empresa.id == regra.empresa_id
    ).first()
    
    tipo_odontograma = db.query(TipoOdontograma).filter(
        TipoOdontograma.id == regra.tipo_odontograma_id
    ).first()
    
    # Adicionar ao resultado
    regra_dict = regra.__dict__.copy()
    if "_sa_instance_state" in regra_dict:
        regra_dict.pop("_sa_instance_state")
        
    regra_dict["empresa_nome"] = empresa.razao_social if empresa else None
    regra_dict["tipo_odontograma_nome"] = tipo_odontograma.nome if tipo_odontograma else None
    
    return regra_dict

@router.post("/", response_model=EmpresaRegrasSplitRead, status_code=status.HTTP_201_CREATED)
def create_regra(regra: EmpresaRegrasSplitCreate, db: Session = Depends(get_db)):
    # Verificar se a empresa existe
    empresa = db.query(Empresa).filter(
        Empresa.id == regra.empresa_id
    ).first()
    
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    
    # Verificar se o tipo de odontograma existe
    tipo_odontograma = db.query(TipoOdontograma).filter(
        TipoOdontograma.id == regra.tipo_odontograma_id
    ).first()
    
    if not tipo_odontograma:
        raise HTTPException(status_code=404, detail="Tipo de odontograma não encontrado")
    
    # Verificar se já existe regra para esta empresa, tipo de odontograma E UNIDADE
    if regra.unidade:
        existing_regra = db.query(EmpresaRegrasSplit).filter(
            EmpresaRegrasSplit.empresa_id == regra.empresa_id,
            EmpresaRegrasSplit.tipo_odontograma_id == regra.tipo_odontograma_id,
            EmpresaRegrasSplit.unidade == regra.unidade
        ).first()
    else:
        # Se não tem unidade, verificar regras sem unidade (regras gerais)
        existing_regra = db.query(EmpresaRegrasSplit).filter(
            EmpresaRegrasSplit.empresa_id == regra.empresa_id,
            EmpresaRegrasSplit.tipo_odontograma_id == regra.tipo_odontograma_id,
            EmpresaRegrasSplit.unidade.is_(None)
        ).first()

    if existing_regra:
        unidade_msg = f" para a unidade '{regra.unidade}'" if regra.unidade else " (regra geral)"
        raise HTTPException(
            status_code=400,
            detail=f"Já existe uma regra para esta empresa e tipo de odontograma{unidade_msg}"
        )
    
    db_regra = EmpresaRegrasSplit(**regra.dict())
    db.add(db_regra)
    db.commit()
    db.refresh(db_regra)
    return db_regra

@router.put("/{id}", response_model=EmpresaRegrasSplitRead)
def update_regra(id: int, regra_update: EmpresaRegrasSplitUpdate, db: Session = Depends(get_db)):
    db_regra = db.query(EmpresaRegrasSplit).filter(EmpresaRegrasSplit.id == id).first()
    if not db_regra:
        raise HTTPException(status_code=404, detail="Regra não encontrada")

    update_data = regra_update.dict(exclude_unset=True)

    # Se está tentando mudar empresa_id, tipo_odontograma_id ou unidade, verificar duplicidade
    if any(key in update_data for key in ['empresa_id', 'tipo_odontograma_id', 'unidade']):
        # Pegar valores atuais ou novos
        new_empresa_id = update_data.get('empresa_id', db_regra.empresa_id)
        new_tipo_id = update_data.get('tipo_odontograma_id', db_regra.tipo_odontograma_id)
        new_unidade = update_data.get('unidade', db_regra.unidade)

        # Verificar se já existe outra regra com essa combinação
        if new_unidade:
            existing = db.query(EmpresaRegrasSplit).filter(
                EmpresaRegrasSplit.empresa_id == new_empresa_id,
                EmpresaRegrasSplit.tipo_odontograma_id == new_tipo_id,
                EmpresaRegrasSplit.unidade == new_unidade,
                EmpresaRegrasSplit.id != id
            ).first()
        else:
            existing = db.query(EmpresaRegrasSplit).filter(
                EmpresaRegrasSplit.empresa_id == new_empresa_id,
                EmpresaRegrasSplit.tipo_odontograma_id == new_tipo_id,
                EmpresaRegrasSplit.unidade.is_(None),
                EmpresaRegrasSplit.id != id
            ).first()

        if existing:
            unidade_msg = f" para a unidade '{new_unidade}'" if new_unidade else " (regra geral)"
            raise HTTPException(
                status_code=400,
                detail=f"Já existe uma regra para esta empresa e tipo de odontograma{unidade_msg}"
            )

    for key, value in update_data.items():
        setattr(db_regra, key, value)

    db.commit()
    db.refresh(db_regra)
    return db_regra

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_regra(id: int, db: Session = Depends(get_db)):
    db_regra = db.query(EmpresaRegrasSplit).filter(EmpresaRegrasSplit.id == id).first()
    if not db_regra:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    
    db.delete(db_regra)
    db.commit()
    return None

@router.post("/bulk-create/{empresa_id}", response_model=List[EmpresaRegrasSplitRead])
def create_regras_bulk(
    empresa_id: int, 
    percentual: Decimal, 
    ciclos_participacao: int = 1,
    absorve_saldo: bool = False,
    db: Session = Depends(get_db)
):
    """Cria regras de split para todos os tipos de odontograma para uma empresa específica."""
    
    # Verificar se a empresa existe
    empresa = db.query(Empresa).filter(
        Empresa.id == empresa_id
    ).first()
    
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    
    # Validar percentual
    if percentual < 0 or percentual > 100:
        raise HTTPException(
            status_code=400,
            detail="Percentual deve ser entre 0 e 100"
        )
    
    # Obter todos os tipos de odontograma
    tipos_odontograma = db.query(TipoOdontograma).filter(
        TipoOdontograma.ativo == True
    ).all()
    
    created_regras = []
    for tipo in tipos_odontograma:
        # Verificar se já existe regra para esta empresa e tipo de odontograma
        existing_regra = db.query(EmpresaRegrasSplit).filter(
            EmpresaRegrasSplit.empresa_id == empresa_id,
            EmpresaRegrasSplit.tipo_odontograma_id == tipo.id
        ).first()
        
        if existing_regra:
            continue  # Pula se já existir
        
        # Criar nova regra
        nova_regra = EmpresaRegrasSplit(
            empresa_id=empresa_id,
            tipo_odontograma_id=tipo.id,
            percentual=percentual,
            ciclos_participacao=ciclos_participacao,
            absorve_saldo=absorve_saldo
        )
        
        db.add(nova_regra)
        created_regras.append(nova_regra)
    
    db.commit()
    
    # Atualizar os objetos com IDs
    for regra in created_regras:
        db.refresh(regra)
    
    return created_regras