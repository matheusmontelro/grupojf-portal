from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from decimal import Decimal
import logging
from app.database.db import get_db
from app.models.configuracao_split import (
    # Models
    ParticipacaoEmpresaSplit,
    ParticipacaoCargoSplit,
    ConfigLimiteSplit,
    # Schemas
    ParticipacaoEmpresaSplitCreate,
    ParticipacaoEmpresaSplitUpdate,
    ParticipacaoEmpresaSplitRead,
    ParticipacaoEmpresaSplitDetail,
    ParticipacaoCargoSplitCreate,
    ParticipacaoCargoSplitUpdate,
    ParticipacaoCargoSplitRead,
    ParticipacaoCargoSplitDetail,
    ConfigLimiteSplitCreate,
    ConfigLimiteSplitUpdate,
    ConfigLimiteSplitRead,
    ConfigLimiteSplitDetail
)

from app.models.tipos_odontograma import TipoOdontograma
from app.models.empresa import Empresa
from app.models.cargos import Cargo
from app.services.split_validation_service import SplitValidationService

# Configure o logging no início do arquivo
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/configuracao-split",
    tags=["configuracao-split"],
    responses={404: {"description": "Not found"}},
)

# -------------------- Endpoints auxiliares --------------------

@router.get("/empresas-por-unidade")
def get_empresas_por_unidade(db: Session = Depends(get_db)):
    """
    Retorna todas as empresas agrupadas por unidade
    """
    return SplitValidationService.get_empresas_por_unidade()

@router.get("/jf-por-unidade/{unidade}")
def get_jf_por_unidade(unidade: str, db: Session = Depends(get_db)):
    """
    Retorna a empresa J&F de uma unidade específica
    """
    jf_empresa = SplitValidationService.get_jf_empresa_por_unidade(unidade)
    if not jf_empresa:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhuma empresa J&F encontrada para a unidade {unidade}"
        )
    return jf_empresa

@router.post("/validar-participacao")
def validar_participacao_empresas(
    tipo_odontograma_id: int,
    empresa_ids: List[int],
    unidade_referencia: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Valida se uma configuração de empresas participantes é válida
    """
    is_valid, error_msg = SplitValidationService.validate_participacao_empresas(
        tipo_odontograma_id,
        empresa_ids,
        unidade_referencia
    )
    
    return {
        "valid": is_valid,
        "error": error_msg
    }

# -------------------- Endpoints para ParticipacaoEmpresaSplit --------------------

@router.get("/empresas", response_model=List[ParticipacaoEmpresaSplitDetail])
def get_all_participacoes_empresa(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    tipo_odontograma_id: Optional[int] = None,
    empresa_id: Optional[int] = None,
    ativo: Optional[bool] = None,
    unidade: Optional[str] = None
):
    """
    Retorna todas as participações de empresas em splits, com opções de filtro.
    Agora com filtro por unidade para isolar configurações.
    """
    query = db.query(ParticipacaoEmpresaSplit)

    # Aplicar filtros se fornecidos
    if tipo_odontograma_id is not None:
        query = query.filter(ParticipacaoEmpresaSplit.tipo_odontograma_id == tipo_odontograma_id)
    if empresa_id is not None:
        query = query.filter(ParticipacaoEmpresaSplit.empresa_id == empresa_id)
    if ativo is not None:
        query = query.filter(ParticipacaoEmpresaSplit.ativo == ativo)

    # NOVO: Filtrar por unidade
    if unidade is not None:
        # Buscar empresas da unidade especificada ou "Todas as unidades"
        empresas_da_unidade = db.query(Empresa.id).filter(
            (Empresa.unidade == unidade) | (Empresa.unidade == "Todas as unidades")
        ).subquery()
        query = query.filter(ParticipacaoEmpresaSplit.empresa_id.in_(empresas_da_unidade))
    
    participacoes = query.order_by(
        ParticipacaoEmpresaSplit.tipo_odontograma_id,
        ParticipacaoEmpresaSplit.ordem_prioridade
    ).offset(skip).limit(limit).all()
    
    # Adicionar informações detalhadas
    result = []
    for p in participacoes:
        # Obter nome do tipo de odontograma
        tipo_obj = db.query(TipoOdontograma).filter(TipoOdontograma.id == p.tipo_odontograma_id).first()
        tipo_nome = tipo_obj.nome if tipo_obj else ""
        
        # Obter nome da empresa
        empresa_obj = db.query(Empresa).filter(Empresa.id == p.empresa_id).first()
        empresa_nome = empresa_obj.razao_social if empresa_obj else ""
        
        # Criar objeto com detalhes
        p_dict = {
            **vars(p),
            "tipo_odontograma_nome": tipo_nome,
            "empresa_nome": empresa_nome
        }
        result.append(p_dict)
    
    return result

@router.get("/empresas/{id}", response_model=ParticipacaoEmpresaSplitDetail)
def get_participacao_empresa(id: int, db: Session = Depends(get_db)):
    """
    Retorna uma participação de empresa específica pelo ID.
    """
    p = db.query(ParticipacaoEmpresaSplit).filter(ParticipacaoEmpresaSplit.id == id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Participação de empresa não encontrada")
    
    # Obter nome do tipo de odontograma
    tipo_obj = db.query(TipoOdontograma).filter(TipoOdontograma.id == p.tipo_odontograma_id).first()
    tipo_nome = tipo_obj.nome if tipo_obj else ""
    
    # Obter nome da empresa
    empresa_obj = db.query(Empresa).filter(Empresa.id == p.empresa_id).first()
    empresa_nome = empresa_obj.razao_social if empresa_obj else ""
    
    # Criar objeto com detalhes
    p_dict = {
        **vars(p),
        "tipo_odontograma_nome": tipo_nome,
        "empresa_nome": empresa_nome
    }
    
    return p_dict

@router.post("/empresas", response_model=ParticipacaoEmpresaSplitRead, status_code=status.HTTP_201_CREATED)
def create_participacao_empresa(
    participacao: ParticipacaoEmpresaSplitCreate, 
    db: Session = Depends(get_db)
):
    """
    Cria uma nova participação de empresa em split.
    """
    # Verificar se o tipo de odontograma existe
    tipo_exists = db.query(TipoOdontograma).filter(
        TipoOdontograma.id == participacao.tipo_odontograma_id
    ).first()
    if not tipo_exists:
        raise HTTPException(status_code=404, detail="Tipo de odontograma não encontrado")
    
    # Verificar se a empresa existe
    empresa_exists = db.query(Empresa).filter(
        Empresa.id == participacao.empresa_id
    ).first()
    if not empresa_exists:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    
    # Verificar se já existe essa combinação
    existing = db.query(ParticipacaoEmpresaSplit).filter(
        ParticipacaoEmpresaSplit.tipo_odontograma_id == participacao.tipo_odontograma_id,
        ParticipacaoEmpresaSplit.empresa_id == participacao.empresa_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail="Já existe uma participação para esta empresa neste tipo de odontograma"
        )
    
    # Validar se não há conflito de empresas J&F
    # Primeiro, buscar todas as empresas já participantes ativas
    participacoes_existentes = db.query(ParticipacaoEmpresaSplit).filter(
        ParticipacaoEmpresaSplit.tipo_odontograma_id == participacao.tipo_odontograma_id,
        ParticipacaoEmpresaSplit.ativo == True
    ).all()
    
    empresa_ids_existentes = [p.empresa_id for p in participacoes_existentes]
    empresa_ids_para_validar = empresa_ids_existentes + [participacao.empresa_id]
    
    # Validar
    is_valid, error_msg = SplitValidationService.validate_participacao_empresas(
        participacao.tipo_odontograma_id,
        empresa_ids_para_validar
    )
    
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Criar nova participação
    db_participacao = ParticipacaoEmpresaSplit(**participacao.dict())
    db.add(db_participacao)
    db.commit()
    db.refresh(db_participacao)
    return db_participacao

@router.put("/empresas/{id}", response_model=ParticipacaoEmpresaSplitRead)
def update_participacao_empresa(
    id: int, 
    participacao: ParticipacaoEmpresaSplitUpdate, 
    db: Session = Depends(get_db)
):
    """
    Atualiza uma participação de empresa existente.
    """
    db_participacao = db.query(ParticipacaoEmpresaSplit).filter(ParticipacaoEmpresaSplit.id == id).first()
    if not db_participacao:
        raise HTTPException(status_code=404, detail="Participação de empresa não encontrada")
    
    # Atualizar campos
    update_data = participacao.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_participacao, key, value)
    
    db.commit()
    db.refresh(db_participacao)
    return db_participacao

@router.delete("/empresas/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_participacao_empresa(id: int, db: Session = Depends(get_db)):
    """
    Remove uma participação de empresa.
    """
    db_participacao = db.query(ParticipacaoEmpresaSplit).filter(ParticipacaoEmpresaSplit.id == id).first()
    if not db_participacao:
        raise HTTPException(status_code=404, detail="Participação de empresa não encontrada")
    
    db.delete(db_participacao)
    db.commit()
    return None


# -------------------- Endpoints para ParticipacaoCargoSplit --------------------

@router.get("/cargos", response_model=List[ParticipacaoCargoSplitDetail])
def get_all_participacoes_cargo(
    db: Session = Depends(get_db), 
    skip: int = 0, 
    limit: int = 100,
    tipo_odontograma_id: Optional[int] = None,
    cargo_id: Optional[int] = None,
    ativo: Optional[bool] = None
):
    """
    Retorna todas as participações de cargos em splits, com opções de filtro.
    """
    query = db.query(ParticipacaoCargoSplit)
    
    # Aplicar filtros se fornecidos
    if tipo_odontograma_id is not None:
        query = query.filter(ParticipacaoCargoSplit.tipo_odontograma_id == tipo_odontograma_id)
    if cargo_id is not None:
        query = query.filter(ParticipacaoCargoSplit.cargo_id == cargo_id)
    if ativo is not None:
        query = query.filter(ParticipacaoCargoSplit.ativo == ativo)
    
    participacoes = query.order_by(
        ParticipacaoCargoSplit.tipo_odontograma_id,
        ParticipacaoCargoSplit.ordem_prioridade
    ).offset(skip).limit(limit).all()
    
    # Adicionar informações detalhadas
    result = []
    for p in participacoes:
        # Obter nome do tipo de odontograma
        tipo_obj = db.query(TipoOdontograma).filter(TipoOdontograma.id == p.tipo_odontograma_id).first()
        tipo_nome = tipo_obj.nome if tipo_obj else ""
        
        # Obter nome do cargo
        cargo_obj = db.query(Cargo).filter(Cargo.id == p.cargo_id).first()
        cargo_nome = cargo_obj.nome if cargo_obj else ""
        
        # Criar objeto com detalhes
        p_dict = {
            **vars(p),
            "tipo_odontograma_nome": tipo_nome,
            "cargo_nome": cargo_nome
        }
        result.append(p_dict)
    
    return result

@router.get("/cargos/{id}", response_model=ParticipacaoCargoSplitDetail)
def get_participacao_cargo(id: int, db: Session = Depends(get_db)):
    """
    Retorna uma participação de cargo específica pelo ID.
    """
    p = db.query(ParticipacaoCargoSplit).filter(ParticipacaoCargoSplit.id == id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Participação de cargo não encontrada")
    
    # Obter nome do tipo de odontograma
    tipo_obj = db.query(TipoOdontograma).filter(TipoOdontograma.id == p.tipo_odontograma_id).first()
    tipo_nome = tipo_obj.nome if tipo_obj else ""
    
    # Obter nome do cargo
    cargo_obj = db.query(Cargo).filter(Cargo.id == p.cargo_id).first()
    cargo_nome = cargo_obj.nome if cargo_obj else ""
    
    # Criar objeto com detalhes
    p_dict = {
        **vars(p),
        "tipo_odontograma_nome": tipo_nome,
        "cargo_nome": cargo_nome
    }
    
    return p_dict

@router.post("/cargos", response_model=ParticipacaoCargoSplitRead, status_code=status.HTTP_201_CREATED)
def create_participacao_cargo(
    participacao: ParticipacaoCargoSplitCreate, 
    db: Session = Depends(get_db)
):
    """
    Cria uma nova participação de cargo em split.
    """
    # Verificar se o tipo de odontograma existe
    tipo_exists = db.query(TipoOdontograma).filter(
        TipoOdontograma.id == participacao.tipo_odontograma_id
    ).first()
    if not tipo_exists:
        raise HTTPException(status_code=404, detail="Tipo de odontograma não encontrado")
    
    # Verificar se o cargo existe
    cargo_exists = db.query(Cargo).filter(
        Cargo.id == participacao.cargo_id
    ).first()
    if not cargo_exists:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    
    # Verificar se já existe essa combinação
    existing = db.query(ParticipacaoCargoSplit).filter(
        ParticipacaoCargoSplit.tipo_odontograma_id == participacao.tipo_odontograma_id,
        ParticipacaoCargoSplit.cargo_id == participacao.cargo_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail="Já existe uma participação para este cargo neste tipo de odontograma"
        )
    
    # Criar nova participação
    db_participacao = ParticipacaoCargoSplit(**participacao.dict())
    db.add(db_participacao)
    db.commit()
    db.refresh(db_participacao)
    return db_participacao

@router.put("/cargos/{id}", response_model=ParticipacaoCargoSplitRead)
def update_participacao_cargo(
    id: int, 
    participacao: ParticipacaoCargoSplitUpdate, 
    db: Session = Depends(get_db)
):
    """
    Atualiza uma participação de cargo existente.
    """
    db_participacao = db.query(ParticipacaoCargoSplit).filter(ParticipacaoCargoSplit.id == id).first()
    if not db_participacao:
        raise HTTPException(status_code=404, detail="Participação de cargo não encontrada")
    
    # Atualizar campos
    update_data = participacao.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_participacao, key, value)
    
    db.commit()
    db.refresh(db_participacao)
    return db_participacao

@router.delete("/cargos/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_participacao_cargo(id: int, db: Session = Depends(get_db)):
    """
    Remove uma participação de cargo.
    """
    db_participacao = db.query(ParticipacaoCargoSplit).filter(ParticipacaoCargoSplit.id == id).first()
    if not db_participacao:
        raise HTTPException(status_code=404, detail="Participação de cargo não encontrada")
    
    db.delete(db_participacao)
    db.commit()
    return None


# -------------------- Endpoints para ConfigLimiteSplit --------------------

@router.get("/limites", response_model=List[ConfigLimiteSplitDetail])
def get_all_limites(
    db: Session = Depends(get_db), 
    skip: int = 0, 
    limit: int = 100,
    tipo_odontograma_id: Optional[int] = None
):
    """
    Retorna todas as configurações de limite de split, com opções de filtro.
    """
    query = db.query(ConfigLimiteSplit)
    
    # Aplicar filtro se fornecido
    if tipo_odontograma_id is not None:
        query = query.filter(ConfigLimiteSplit.tipo_odontograma_id == tipo_odontograma_id)
    
    limites = query.order_by(ConfigLimiteSplit.tipo_odontograma_id).offset(skip).limit(limit).all()
    
    # Adicionar informações detalhadas
    result = []
    for limite in limites:
        # Obter nome do tipo de odontograma
        tipo_obj = db.query(TipoOdontograma).filter(TipoOdontograma.id == limite.tipo_odontograma_id).first()
        tipo_nome = tipo_obj.nome if tipo_obj else ""
        
        # Criar objeto com detalhes
        limite_dict = {
            **vars(limite),
            "tipo_odontograma_nome": tipo_nome
        }
        result.append(limite_dict)
    
    return result

@router.get("/limites/{id}", response_model=ConfigLimiteSplitDetail)
def get_limite(id: int, db: Session = Depends(get_db)):
    """
    Retorna uma configuração de limite específica pelo ID.
    """
    limite = db.query(ConfigLimiteSplit).filter(ConfigLimiteSplit.id == id).first()
    if not limite:
        raise HTTPException(status_code=404, detail="Configuração de limite não encontrada")
    
    # Obter nome do tipo de odontograma
    tipo_obj = db.query(TipoOdontograma).filter(TipoOdontograma.id == limite.tipo_odontograma_id).first()
    tipo_nome = tipo_obj.nome if tipo_obj else ""
    
    # Criar objeto com detalhes
    limite_dict = {
        **vars(limite),
        "tipo_odontograma_nome": tipo_nome
    }
    
    return limite_dict

@router.post("/limites", response_model=ConfigLimiteSplitRead, status_code=status.HTTP_201_CREATED)
def create_limite(
    limite: ConfigLimiteSplitCreate, 
    db: Session = Depends(get_db)
):
    """
    Cria uma nova configuração de limite de split.
    """
    # Verificar se o tipo de odontograma existe
    tipo_exists = db.query(TipoOdontograma).filter(
        TipoOdontograma.id == limite.tipo_odontograma_id
    ).first()
    if not tipo_exists:
        raise HTTPException(status_code=404, detail="Tipo de odontograma não encontrado")
    
    # Verificar se já existe configuração para este tipo
    existing = db.query(ConfigLimiteSplit).filter(
        ConfigLimiteSplit.tipo_odontograma_id == limite.tipo_odontograma_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail="Já existe uma configuração de limite para este tipo de odontograma"
        )
    
    # Criar nova configuração
    db_limite = ConfigLimiteSplit(**limite.dict())
    db.add(db_limite)
    db.commit()
    db.refresh(db_limite)
    return db_limite

@router.put("/limites/{id}", response_model=ConfigLimiteSplitRead)
def update_limite(
    id: int, 
    limite: ConfigLimiteSplitUpdate, 
    db: Session = Depends(get_db)
):
    """
    Atualiza uma configuração de limite existente.
    """
    db_limite = db.query(ConfigLimiteSplit).filter(ConfigLimiteSplit.id == id).first()
    if not db_limite:
        raise HTTPException(status_code=404, detail="Configuração de limite não encontrada")
    
    # Atualizar campos
    update_data = limite.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_limite, key, value)
    
    db.commit()
    db.refresh(db_limite)
    return db_limite

@router.delete("/limites/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_limite(id: int, db: Session = Depends(get_db)):
    """
    Remove uma configuração de limite.
    """
    db_limite = db.query(ConfigLimiteSplit).filter(ConfigLimiteSplit.id == id).first()
    if not db_limite:
        raise HTTPException(status_code=404, detail="Configuração de limite não encontrada")
    
    db.delete(db_limite)
    db.commit()
    return None


# -------------------- Endpoints para operações em lote --------------------

@router.post("/tipos-odontograma/{tipo_id}/configuracao-completa", status_code=status.HTTP_201_CREATED)
def create_configuracao_completa(
    tipo_id: int,
    max_empresas: int = Query(1, ge=0),
    max_cargos: int = Query(3, ge=0),
    empresas_ids: List[int] = Query(None),
    cargos_ids: List[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Cria uma configuração completa para um tipo de odontograma, incluindo limites e participações.
    """
    logger.debug(f"Iniciando configuração completa - Tipo ID: {tipo_id}")
    logger.debug(f"Parâmetros: max_empresas={max_empresas}, max_cargos={max_cargos}")
    logger.debug(f"Empresas IDs: {empresas_ids}")
    logger.debug(f"Cargos IDs: {cargos_ids}")
    
    # Verificar se o tipo de odontograma existe
    tipo_exists = db.query(TipoOdontograma).filter(
        TipoOdontograma.id == tipo_id
    ).first()
    if not tipo_exists:
        logger.error(f"Tipo de odontograma {tipo_id} não encontrado")
        raise HTTPException(status_code=404, detail="Tipo de odontograma não encontrado")
    
    logger.debug(f"Tipo de odontograma {tipo_id} ({tipo_exists.nome}) encontrado")
    
    # Criar/atualizar configuração de limite
    existing_limite = db.query(ConfigLimiteSplit).filter(
        ConfigLimiteSplit.tipo_odontograma_id == tipo_id
    ).first()
    
    if existing_limite:
        logger.debug(f"Atualizando limite existente ID: {existing_limite.id}")
        # Atualizar existente
        existing_limite.max_empresas = max_empresas
        existing_limite.max_cargos = max_cargos
        db.commit()
        db.refresh(existing_limite)
        logger.debug(f"Limite atualizado: max_empresas={max_empresas}, max_cargos={max_cargos}")
    else:
        logger.debug("Criando novo limite")
        # Criar novo
        new_limite = ConfigLimiteSplit(
            tipo_odontograma_id=tipo_id,
            max_empresas=max_empresas,
            max_cargos=max_cargos
        )
        db.add(new_limite)
        db.commit()
        logger.debug("Novo limite criado com sucesso")
    
    # Identificar a unidade sendo configurada pela J&F presente
    unidade_atual = None
    if empresas_ids:
        for emp_id in empresas_ids:
            empresa = db.query(Empresa).filter(
                Empresa.id == emp_id
            ).first()
            if empresa and ('J & F ODONTOLOGIA' in empresa.razao_social.upper() or 'J&F ODONTOLOGIA' in empresa.razao_social.upper()):
                unidade_atual = empresa.unidade
                logger.debug(f"Configurando para unidade: {unidade_atual} (J&F ID: {emp_id})")
                break

    # Desativar apenas participações da unidade atual
    if unidade_atual:
        # Buscar todas as empresas da unidade atual
        empresas_da_unidade = db.query(Empresa).filter(
            Empresa.unidade == unidade_atual
        ).all()
        empresas_ids_unidade = [e.id for e in empresas_da_unidade]

        # Desativar apenas participações dessas empresas
        empresas_count = db.query(ParticipacaoEmpresaSplit).filter(
            ParticipacaoEmpresaSplit.tipo_odontograma_id == tipo_id,
            ParticipacaoEmpresaSplit.empresa_id.in_(empresas_ids_unidade)
        ).update({"ativo": False})
        logger.debug(f"Desativadas {empresas_count} participações da unidade {unidade_atual}")
    else:
        # Se não identificou unidade, desativar todas (comportamento antigo)
        logger.warning("Unidade não identificada, desativando todas as participações")
        empresas_count = db.query(ParticipacaoEmpresaSplit).filter(
            ParticipacaoEmpresaSplit.tipo_odontograma_id == tipo_id
        ).update({"ativo": False})
        logger.debug(f"Desativadas {empresas_count} participações de empresas existentes")
    
    # Adicionar/atualizar participações de empresas
    empresas_ativadas = 0
    empresas_criadas = 0
    empresas_nao_encontradas = 0
    
    if empresas_ids:
        logger.debug(f"Processando {len(empresas_ids)} empresas")
        
        for i, empresa_id in enumerate(empresas_ids, 1):
            # Verificar se a empresa existe
            empresa_exists = db.query(Empresa).filter(
                Empresa.id == empresa_id
            ).first()
            
            if not empresa_exists:
                logger.warning(f"Empresa ID {empresa_id} não encontrada, pulando...")
                empresas_nao_encontradas += 1
                continue  # Pular empresas inexistentes
            
            # Verificar se já existe participação
            existing_part = db.query(ParticipacaoEmpresaSplit).filter(
                ParticipacaoEmpresaSplit.tipo_odontograma_id == tipo_id,
                ParticipacaoEmpresaSplit.empresa_id == empresa_id
            ).first()
            
            if existing_part:
                # Atualizar existente
                logger.debug(f"Atualizando participação da empresa {empresa_id} ({empresa_exists.razao_social}), ordem {i}")
                existing_part.ativo = True
                existing_part.ordem_prioridade = i
                empresas_ativadas += 1
            else:
                # Criar nova participação
                logger.debug(f"Criando nova participação para empresa {empresa_id} ({empresa_exists.razao_social}), ordem {i}")
                new_part = ParticipacaoEmpresaSplit(
                    tipo_odontograma_id=tipo_id,
                    empresa_id=empresa_id,
                    ativo=True,
                    ordem_prioridade=i
                )
                db.add(new_part)
                empresas_criadas += 1
    else:
        logger.debug("Nenhuma empresa fornecida para configuração")
    
    logger.info(f"Processamento de empresas concluído: {empresas_ativadas} reativadas, {empresas_criadas} novas, {empresas_nao_encontradas} não encontradas")
    db.commit()
    
    # NÃO desativar cargos - eles são compartilhados entre unidades
    # Apenas atualizar/criar os cargos especificados
    logger.debug("Mantendo participações de cargos existentes")
    
    # Adicionar/atualizar participações de cargos
    cargos_ativados = 0
    cargos_criados = 0
    cargos_nao_encontrados = 0
    
    if cargos_ids:
        logger.debug(f"Processando {len(cargos_ids)} cargos")
        
        for i, cargo_id in enumerate(cargos_ids, 1):
            # Verificar se o cargo existe
            cargo_exists = db.query(Cargo).filter(
                Cargo.id == cargo_id
            ).first()
            
            if not cargo_exists:
                logger.warning(f"Cargo ID {cargo_id} não encontrado, pulando...")
                cargos_nao_encontrados += 1
                continue  # Pular cargos inexistentes
            
            # Verificar se já existe participação
            existing_part = db.query(ParticipacaoCargoSplit).filter(
                ParticipacaoCargoSplit.tipo_odontograma_id == tipo_id,
                ParticipacaoCargoSplit.cargo_id == cargo_id
            ).first()
            
            if existing_part:
                # Atualizar existente
                logger.debug(f"Atualizando participação do cargo {cargo_id} ({cargo_exists.nome}), ordem {i}")
                existing_part.ativo = True
                existing_part.ordem_prioridade = i
                cargos_ativados += 1
            else:
                # Criar nova participação
                logger.debug(f"Criando nova participação para cargo {cargo_id} ({cargo_exists.nome}), ordem {i}")
                new_part = ParticipacaoCargoSplit(
                    tipo_odontograma_id=tipo_id,
                    cargo_id=cargo_id,
                    ativo=True,
                    ordem_prioridade=i
                )
                db.add(new_part)
                cargos_criados += 1
    else:
        logger.debug("Nenhum cargo fornecido para configuração")
    
    logger.info(f"Processamento de cargos concluído: {cargos_ativados} reativados, {cargos_criados} novos, {cargos_nao_encontrados} não encontrados")
    db.commit()
    
    logger.info(f"Configuração completa finalizada com sucesso para tipo ID {tipo_id} ({tipo_exists.nome})")
    return {"message": "Configuração completa criada com sucesso"}

@router.get("/empresas-participantes/{tipo_odontograma_id}")
def listar_empresas_participantes(tipo_odontograma_id: int, db: Session = Depends(get_db)):
    # Obter IDs de empresas participantes
    participantes = db.query(ParticipacaoEmpresaSplit).filter(
        ParticipacaoEmpresaSplit.tipo_odontograma_id == tipo_odontograma_id,
        ParticipacaoEmpresaSplit.ativo == True
    ).all()
    
    # Obter detalhes das empresas participantes
    empresa_ids = [p.empresa_id for p in participantes]
    if not empresa_ids:
        return []
    
    empresas = db.query(Empresa).filter(Empresa.id.in_(empresa_ids)).all()
    return empresas