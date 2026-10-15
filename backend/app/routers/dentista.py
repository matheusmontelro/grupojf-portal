from fastapi import APIRouter, Depends, HTTPException, status, Response, Query  
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import logging
# Importar o Model SQLAlchemy correspondente
from ..models.dentista import Dentista
# Importar a dependência para obter a sessão do DB
from ..database.db import get_db # Ajuste se necessário
from sqlalchemy.orm import joinedload
from ..models.odontograma import Odontograma
from ..models.dependente import Dependente
# --- Schemas Pydantic para Dentistas ---

class DentistaBase(BaseModel):
    nome: str = Field(..., description="Nome completo do dentista/profissional")
    # Código pode ser opcional ou gerado pela aplicação
    codigo_dentista: Optional[str] = Field(None, max_length=10, description="Código identificador (opcional)")
    funcao: Optional[str] = Field(None, max_length=100, description="Função (ex: Ortodontista, Clínico Geral)")
    ativo: bool = True

    class Config:
        from_attributes = True

class DentistaCreate(DentistaBase):
    # Nenhum campo adicional para criar, herda tudo de Base
    pass

class DentistaUpdate(BaseModel):
    # Todos os campos são opcionais na atualização
    nome: Optional[str] = None
    codigo_dentista: Optional[str] = Field(None, max_length=10)
    funcao: Optional[str] = Field(None, max_length=100)
    ativo: Optional[bool] = None
    user_id: Optional[int] = Field(None, description="ID do usuário do sistema vinculado")

    class Config:
        from_attributes = True

class DentistaRead(DentistaBase):
    # Adiciona campos lidos do DB
    id: int
    user_id: Optional[int] = Field(None, description="ID do usuário do sistema vinculado")
    created_at: datetime
    updated_at: datetime

# --- Router FastAPI ---

router = APIRouter(
    prefix="/dentistas",
    tags=["Dentistas"]
)

# --- Endpoints CRUD ---

@router.post("/", response_model=DentistaRead, status_code=status.HTTP_201_CREATED)
def create_dentista(dentista: DentistaCreate, db: Session = Depends(get_db)):
    """
    Cria um novo dentista/profissional.
    Verifica se o código_dentista (se fornecido) já existe.
    """
    if dentista.codigo_dentista:
        db_dentista_check = db.query(Dentista).filter(Dentista.codigo_dentista == dentista.codigo_dentista).first()
        if db_dentista_check:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Código de dentista '{dentista.codigo_dentista}' já registrado.")

    db_dentista = Dentista(**dentista.model_dump())
    try:
        db.add(db_dentista)
        db.commit()
        db.refresh(db_dentista)
        return db_dentista
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao salvar dentista: {e}")

@router.get("/", response_model=List[DentistaRead])
def read_dentistas(
    skip: int = 0,
    limit: int = 100,
    funcao: Optional[str] = None,
    nome: Optional[str] = None,
    ativo: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna uma lista de dentistas, com paginação e filtros opcionais.
    """
    query = db.query(Dentista)
    if funcao:
        query = query.filter(Dentista.funcao.ilike(f"%{funcao}%"))
    if nome:
        query = query.filter(Dentista.nome.ilike(f"%{nome}%"))
    if ativo is not None:
        query = query.filter(Dentista.ativo == ativo)

    dentistas = query.offset(skip).limit(limit).all()
    return dentistas

@router.get("/{dentista_id}", response_model=DentistaRead)
def read_dentista(dentista_id: int, db: Session = Depends(get_db)):
    """
    Retorna um dentista específico pelo seu ID.
    """
    db_dentista = db.query(Dentista).filter(Dentista.id == dentista_id).first()
    if db_dentista is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dentista não encontrado")
    return db_dentista

@router.put("/{dentista_id}", response_model=DentistaRead)
def update_dentista(dentista_id: int, dentista_update: DentistaUpdate, db: Session = Depends(get_db)):
    """
    Atualiza um dentista existente pelo seu ID.
    """
    db_dentista = db.query(Dentista).filter(Dentista.id == dentista_id).first()
    if db_dentista is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dentista não encontrado")

    # Verifica se o novo codigo_dentista (se fornecido e diferente do atual) já existe
    if dentista_update.codigo_dentista and dentista_update.codigo_dentista != db_dentista.codigo_dentista:
         existing_code = db.query(Dentista).filter(Dentista.codigo_dentista == dentista_update.codigo_dentista).first()
         if existing_code:
              raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Código de dentista '{dentista_update.codigo_dentista}' já pertence a outro profissional.")

    update_data = dentista_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_dentista, key, value)

    try:
        db.add(db_dentista)
        db.commit()
        db.refresh(db_dentista)
        return db_dentista
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar dentista: {e}")

@router.delete("/{dentista_id}", response_model=DentistaRead)
def delete_dentista(dentista_id: int, db: Session = Depends(get_db)):
    """
    Marca um dentista como inativo (soft delete).
    Não exclui o registro permanentemente.
    """
    db_dentista = db.query(Dentista).filter(Dentista.id == dentista_id).first()
    if db_dentista is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dentista não encontrado")

    if not db_dentista.ativo:
         # Pode retornar o objeto inativo ou um 304 Not Modified, ou apenas o objeto.
         # Retornar o objeto é consistente com PUT.
         return db_dentista

    db_dentista.ativo = False
    try:
        db.add(db_dentista)
        db.commit()
        db.refresh(db_dentista)
        return db_dentista # Retorna o objeto atualizado (agora inativo)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao inativar dentista: {e}")

@router.delete("/{dentista_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def delete_dentista_permanent(dentista_id: int, db: Session = Depends(get_db)):
    """
    Exclui um dentista permanentemente do banco de dados (hard delete).
    ⚠️ ATENÇÃO: Esta ação é irreversível!
    """
    db_dentista = db.query(Dentista).filter(Dentista.id == dentista_id).first()
    if db_dentista is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dentista não encontrado")

    try:
        db.delete(db_dentista)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao excluir dentista permanentemente: {e}")
    
@router.get("/por-paciente-odontograma/{paciente_id}", response_model=List[DentistaRead])
def get_dentistas_por_paciente_odontograma(
    paciente_id: int,
    ativo: bool = Query(True, description="Filtrar apenas dentistas com odontogramas ativos"),
    dependente_id: Optional[int] = Query(None, description="Filtrar por dependente ID"),
    db: Session = Depends(get_db)
):
    """
    Retorna todos os dentistas que criaram odontogramas para um paciente específico.
    Útil para o fluxo de vendas onde é necessário selecionar o dentista responsável.

    PRIORIDADE: Busca primeiro como paciente titular, depois como dependente.
    Isso resolve conflitos quando o mesmo ID existe em ambas as tabelas.
    """
    from sqlalchemy import text

    logger = logging.getLogger("uvicorn")
    logger.info(f"🔍 Buscando dentistas para ID {paciente_id}")

    # O fluxo de vendas informa ambos os IDs para evitar que um dependente com
    # ID igual ao de outro titular seja resolvido pela prioridade legada.
    if dependente_id is not None:
        dependente_vinculado = db.query(Dependente).filter(
            Dependente.dependente_id == dependente_id,
            Dependente.responsavel_paciente_id == paciente_id,
        ).first()

        if not dependente_vinculado:
            logger.warning(
                "Dependente %s não pertence ao paciente responsável %s",
                dependente_id,
                paciente_id,
            )
            return []

        query_dependente_explicito = db.query(Dentista).distinct().join(
            Odontograma,
            Odontograma.dentista_orcamentista_id == Dentista.id,
        ).filter(
            Odontograma.paciente_id == paciente_id,
            Odontograma.dependente_id == dependente_id,
        )

        if ativo:
            query_dependente_explicito = query_dependente_explicito.filter(Odontograma.ativo == True)

        return query_dependente_explicito.all()

    # Verificar se existe como paciente titular
    paciente_existe = db.execute(
        text("SELECT paciente_id, nome_paciente FROM pacientes WHERE paciente_id = :id"),
        {"id": paciente_id}
    ).fetchone()

    # Verificar se existe como dependente
    dependente_existe = db.execute(
        text("SELECT dependente_id, nome_dependente FROM dependentes WHERE dependente_id = :id"),
        {"id": paciente_id}
    ).fetchone()

    if paciente_existe and dependente_existe:
        logger.warning(f"⚠️ CONFLITO DE IDs: ID {paciente_id} existe como PACIENTE ({paciente_existe[1]}) e DEPENDENTE ({dependente_existe[1]})")
        logger.info(f"   → Priorizando busca como PACIENTE TITULAR")
    elif paciente_existe:
        logger.info(f"   ✅ ID {paciente_id} identificado como PACIENTE: {paciente_existe[1]}")
    elif dependente_existe:
        logger.info(f"   ✅ ID {paciente_id} identificado como DEPENDENTE: {dependente_existe[1]}")
    else:
        logger.error(f"   ❌ ID {paciente_id} não encontrado em pacientes nem dependentes")
        return []

    # PRIORIDADE 1: Buscar como paciente titular
    query_titular = db.query(Dentista).distinct().join(
        Odontograma,
        Odontograma.dentista_orcamentista_id == Dentista.id
    ).filter(
        Odontograma.paciente_id == paciente_id,
        Odontograma.dependente_id.is_(None)  # Garante que é do titular, não de dependente
    )

    if ativo:
        query_titular = query_titular.filter(Odontograma.ativo == True)

    dentistas_titular = query_titular.all()
    logger.info(f"   📊 Odontogramas do TITULAR (dependente_id NULL): {len(dentistas_titular)} dentistas encontrados")

    # Se encontrou dentistas como titular, retorna
    if dentistas_titular:
        logger.info(f"   ✅ Retornando {len(dentistas_titular)} dentistas do paciente titular {paciente_id}")
        return dentistas_titular

    # PRIORIDADE 2: Se não encontrou como titular, tenta como dependente
    if dependente_existe:
        logger.info(f"   🔄 Nenhum dentista encontrado como titular. Buscando como dependente...")

        query_dependente = db.query(Dentista).distinct().join(
            Odontograma,
            Odontograma.dentista_orcamentista_id == Dentista.id
        ).filter(
            Odontograma.dependente_id == paciente_id
        )

        if ativo:
            query_dependente = query_dependente.filter(Odontograma.ativo == True)

        dentistas_dependente = query_dependente.all()
        logger.info(f"   📊 Odontogramas do DEPENDENTE (dependente_id = {paciente_id}): {len(dentistas_dependente)} dentistas encontrados")

        if dentistas_dependente:
            logger.info(f"   ✅ Retornando {len(dentistas_dependente)} dentistas do dependente {paciente_id}")
            return dentistas_dependente

    # Nenhum dentista encontrado
    logger.warning(f"   ⚠️ Nenhum dentista encontrado para ID {paciente_id} (nem como titular nem como dependente)")
    return []
