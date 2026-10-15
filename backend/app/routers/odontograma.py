# Odontogram routes.
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy import bindparam, text
import json
import logging
# Importar Models SQLAlchemy
from ..models.odontograma import Odontograma
from ..models.odontograma_item import OdontogramaItem # Definido no final deste arquivo no seu exemplo
from ..models.produto import Produto # Para verificar existência e schema aninhado
from ..models.dentista import Dentista # Para verificar existência e schema aninhado
from ..models.dependente import Dependente
# Importar Schemas de outros módulos/routers
from .produto import ProdutoRead # Assumindo que está em routers/produto.py
from .dentista import DentistaRead # Assumindo que está em routers/dentista.py
# Importar dependências
from ..database.db import get_db # Ajuste se necessário
# from ..dependencies import get_current_active_user # Descomente se tiver autenticação

# --- Schemas Pydantic para Odontograma Itens ---

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

class OdontogramaItemBase(BaseModel):
    produto_id: int
    dente_numero: Optional[str] = Field(None, max_length=2)
    face_vestibular: bool = False
    face_lingual_palatina: bool = False
    face_mesial: bool = False
    face_distal: bool = False
    face_oclusal_incisal: bool = False
    valor_registrado: float = Field(..., description="Valor do produto no momento do registro no odontograma")
    observacao: Optional[str] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: float
        }

class OdontogramaItemCreate(OdontogramaItemBase):
    pass

class OdontogramaItemRead(OdontogramaItemBase):
    id: int
    created_at: datetime
    produto: Optional[ProdutoRead] = None

# --- Schemas Pydantic para Odontogramas ---

class OdontogramaBase(BaseModel):
    paciente_id: int
    dentista_orcamentista_id: int
    unidade: str = Field(..., description="Unidade onde o odontograma foi criado")
    Tipo: Optional[str] = Field(None, description="tipode odontograma (Contrato, Particular, Ortodontia)") # CAMPO tipoADICIONADO
    dependente_id: Optional[int] = Field(None, description="ID do dependente quando o odontograma é para um dependente")
    ativo: bool = True

    class Config:
        from_attributes = True

class OdontogramaCreate(OdontogramaBase):
    # usuario_criacao_id será pego do usuário logado na rota
    # tipoé herdado de OdontogramaBase
    pass

class OdontogramaUpdate(BaseModel):
    ativo: Optional[bool] = None
    Tipo: Optional[str] = Field(None, description="Novo tipode odontograma") # CAMPO tipoADICIONADO PARA ATUALIZAÇÃO
    # paciente_id: Optional[int] = None
    # dentista_orcamentista_id: Optional[int] = None
    # unidade: Optional[str] = None

    class Config:
        from_attributes = True

class OdontogramaRead(OdontogramaBase): # tipoé herdado de OdontogramaBase
    id: int
    data_criacao: datetime
    usuario_criacao_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    # tipojá está incluído por herança de OdontogramaBase e será populado se presente no modelo Odontograma

    itens: List[OdontogramaItemRead] = []
    dentista_orcamentista: Optional[DentistaRead] = None
    disponivel_para_venda: Optional[bool] = None
    venda_ativa_id: Optional[int] = None
    # paciente: Optional[PacienteRead] = None


def _active_sale_ids_by_odontogram(
    db: Session,
    odontogramas: List[Odontograma],
) -> dict[int, int]:
    """Replica em lote a mesma condição usada na criação da venda Asaas."""
    odontogram_ids = [odontograma.id for odontograma in odontogramas]
    if not odontogram_ids:
        return {}

    query = text(
        """
        SELECT odontograma_id, MAX(id) AS venda_id
        FROM vendas
        WHERE odontograma_id IN :odontogram_ids
          AND status_venda <> 'Cancelada'
        GROUP BY odontograma_id
        """
    ).bindparams(bindparam("odontogram_ids", expanding=True))
    rows = db.execute(query, {"odontogram_ids": odontogram_ids}).fetchall()
    return {int(row[0]): int(row[1]) for row in rows}


def _with_sale_availability(
    odontogramas: List[Odontograma],
    active_sale_ids: dict[int, int],
) -> List[OdontogramaRead]:
    result: List[OdontogramaRead] = []
    for odontograma in odontogramas:
        active_sale_id = active_sale_ids.get(odontograma.id)
        result.append(
            OdontogramaRead.model_validate(odontograma).model_copy(
                update={
                    "disponivel_para_venda": active_sale_id is None,
                    "venda_ativa_id": active_sale_id,
                }
            )
        )
    return result

# --- Router FastAPI ---

router = APIRouter(
    prefix="/odontogramas",
    tags=["Odontogramas"]
)

# --- Endpoints Odontograma ---

@router.post("/", response_model=OdontogramaRead, status_code=status.HTTP_201_CREATED)
def create_odontograma(
    odontograma: OdontogramaCreate, # OdontogramaCreate agora inclui 'Tipo'
    db: Session = Depends(get_db),
    # current_user: models.User = Depends(get_current_active_user)
):
    """
    Cria um novo cabeçalho de odontograma.
    """
    # Mantenha os imports de logging e a obtenção do logger como estavam,
    # preferencialmente no topo do módulo para evitar reimportações.
    logger = logging.getLogger("uvicorn") # Assumindo que logging já foi importado no topo
    
    logger.info(f"Iniciando criação de odontograma: {odontograma.model_dump()}")
    
    try:
        logger.info(f"Validando dentista com ID: {odontograma.dentista_orcamentista_id}")
        db_dentista = db.query(Dentista).filter(Dentista.id == odontograma.dentista_orcamentista_id).first()
        
        if not db_dentista:
            logger.error(f"Dentista com ID {odontograma.dentista_orcamentista_id} não encontrado.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dentista com ID {odontograma.dentista_orcamentista_id} não encontrado.")
        
        logger.info(f"Dentista encontrado: {db_dentista.nome}")

        # Validação de paciente
        logger.info(f"Validando paciente com ID: {odontograma.paciente_id}")
        result_paciente = db.execute(text("SELECT paciente_id, nome_paciente FROM pacientes WHERE paciente_id = :paciente_id"), {"paciente_id": odontograma.paciente_id})
        db_paciente = result_paciente.fetchone()

        if not db_paciente:
            logger.error(f"Paciente com ID {odontograma.paciente_id} não encontrado no banco de dados.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Paciente com ID {odontograma.paciente_id} não encontrado. Por favor, cadastre o paciente antes de criar o odontograma."
            )

        logger.info(f"Paciente encontrado: {db_paciente[1]} (ID: {db_paciente[0]})")

        logger.info("Buscando usuário para associar ao odontograma")
        result = db.execute(text("SELECT id FROM users LIMIT 1"))
        user_id = result.scalar_one_or_none()
        
        if not user_id:
            logger.error("Nenhum usuário encontrado para associar ao odontograma")
            user_id = None 
        else:
            logger.info(f"Usuário encontrado com ID: {user_id}")
        
        logger.info("Inserindo odontograma usando SQL direto")
        
        # ATUALIZAR A CONSULTA SQL DE INSERÇÃO PARA INCLUIR O CAMPO 'Tipo'
        # Use "Tipo" se a coluna no banco de dados foi criada com case sensitive (ex: ALTER TABLE ... ADD COLUMN "Tipo" ...)
        # ou tipo(minúsculo) se foi criada sem aspas e o PostgreSQL a converteu para minúsculo.
        # Assumindo que a coluna no banco de dados é 'Tipo' (correspondendo ao modelo SQLAlchemy)
        insert_sql = text("""
            INSERT INTO odontogramas
            (paciente_id, dentista_orcamentista_id, unidade, ativo, usuario_criacao_id, tipo, dependente_id) 
            VALUES (:paciente_id, :dentista_id, :unidade, :ativo, :usuario_id, :tipo_odontograma, :dependente_id)
            RETURNING id
        """)
        
        params = {
            "paciente_id": odontograma.paciente_id,
            "dentista_id": odontograma.dentista_orcamentista_id,
            "unidade": odontograma.unidade,
            "ativo": odontograma.ativo if hasattr(odontograma, "ativo") else True,
            "usuario_id": user_id,
            "tipo_odontograma": odontograma.Tipo,# Adicionar o novo campo tipoaos parâmetros
            "dependente_id": odontograma.dependente_id if hasattr(odontograma, "dependente_id") else None
        }
        
        result = db.execute(insert_sql, params)
        odontograma_id = result.scalar_one()
        db.commit()
        logger.info(f"Odontograma criado com ID: {odontograma_id}")
        
        logger.info("Buscando odontograma criado com relacionamentos")
        # O campo tiposerá carregado automaticamente pelo ORM se estiver no modelo Odontograma
        db_odontograma = db.query(Odontograma).options(
            joinedload(Odontograma.dentista_orcamentista)
        ).filter(Odontograma.id == odontograma_id).first()
        
        if not db_odontograma:
            logger.error(f"Não foi possível encontrar o odontograma com ID {odontograma_id} após criação")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao buscar odontograma após criação")
        
        db_odontograma.itens = []
        
        logger.info("Retornando odontograma criado com sucesso")
        return db_odontograma
    
    except HTTPException as he:
        logger.error(f"HTTPException: {he.detail}")
        raise
    
    except Exception as e:
        logger.error(f"Erro ao salvar odontograma: {str(e)}")
        logger.exception("Traceback completo:")
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao salvar odontograma: {str(e)}")
    
@router.get("/", response_model=List[OdontogramaRead])
def read_odontogramas(
    skip: int = 0,
    limit: int = 100,
    paciente_id: Optional[int] = None,
    dentista_orcamentista_id: Optional[int] = None,
    unidade: Optional[str] = None,
    ativo: Optional[bool] = None,
    tipo: Optional[str] = Query(None, description="Filtrar por tipo de odontograma (Contrato, Particular, Ortodontia)"),
    db: Session = Depends(get_db)
):
    """
    Retorna uma lista de odontogramas, com paginação e filtros.
    NOTA: Por padrão, NÃO inclui os itens detalhados para performance.
    """
    logger = logging.getLogger("uvicorn") # Adicione esta linha se precisar de logs aqui
    query = db.query(Odontograma).options(joinedload(Odontograma.dentista_orcamentista)) # Carrega dentista
    
    if paciente_id is not None:
        query = query.filter(Odontograma.paciente_id == paciente_id)
    if dentista_orcamentista_id is not None:
        query = query.filter(Odontograma.dentista_orcamentista_id == dentista_orcamentista_id)
    if unidade:
        query = query.filter(Odontograma.unidade.ilike(f"%{unidade}%"))
    if ativo is not None:
        query = query.filter(Odontograma.ativo == ativo)

    # CORREÇÃO AQUI:
    # Certifique-se de que o nome do parâmetro na assinatura da função (acima) é 'tipo'.
    # E use 'tipo' (minúsculo) consistentemente na condição e no filtro.
    if tipo is not None:
        # Usar 'tipo' minúsculo aqui, pois é o nome real da coluna no banco de dados
        query = query.filter(Odontograma.tipo == tipo)
                                            # ^--- aqui deve ser 'tipo' minúsculo (o parâmetro da função)
    try:
        odontogramas = query.order_by(Odontograma.id.desc()).offset(skip).limit(limit).all()
        # Para esta rota de lista, explicitamente não populamos os itens
        for odonto in odontogramas:
            odonto.itens = []
        return odontogramas
    except Exception as e: 
        logger.error(f"Erro ao buscar odontogramas: {str(e)}")
        logger.exception("Traceback completo:")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao buscar odontogramas: {str(e)}")

@router.get("/{odontograma_id}", response_model=OdontogramaRead)
def read_odontograma(odontograma_id: int, db: Session = Depends(get_db)):
    """
    Retorna um odontograma específico pelo seu ID, incluindo todos os seus itens.
    """
    # Mantenha os imports de logging e a obtenção do logger como estavam
    logger = logging.getLogger("uvicorn")
    
    logger.info(f"Buscando odontograma ID: {odontograma_id}")
    
    # O campo tiposerá carregado automaticamente pelo ORM se estiver no modelo Odontograma
    # e o schema OdontogramaRead estiver atualizado.
    db_odontograma = db.query(Odontograma).options(
        joinedload(Odontograma.itens).joinedload(OdontogramaItem.produto),
        joinedload(Odontograma.dentista_orcamentista)
    ).filter(Odontograma.id == odontograma_id).first()

    if db_odontograma is None:
        logger.error(f"Odontograma ID: {odontograma_id} não encontrado")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Odontograma não encontrado")
    
    # Seu bloco de log de resposta existente
    try:
        # from pydantic import json # Já importado como 'json'
        import json as standard_json # Para evitar conflito com o alias 'json' de pydantic
        # from datetime import datetime # Já importado
        # from decimal import Decimal # Já importado
        
        class CustomJSONEncoder(standard_json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                if isinstance(obj, Decimal):
                    return float(obj)
                return super().default(obj)
        
        response_data_model = OdontogramaRead.model_validate(db_odontograma)
        # Usar model_dump_json() diretamente do Pydantic que usa o json_encoders configurado
        response_data_json = response_data_model.model_dump_json()

        logger.info(f"Resposta de odontograma JSON válida, tamanho: {len(response_data_json)} bytes")
        
        logger.info(f"Número de itens no odontograma: {len(db_odontograma.itens)}")
        if db_odontograma.itens:
            item_exemplo = db_odontograma.itens[0]
            item_dump = OdontogramaItemRead.model_validate(item_exemplo).model_dump()
            logger.info(f"Estrutura do primeiro item: {standard_json.dumps(item_dump, cls=CustomJSONEncoder)}")
    except Exception as e:
        logger.error(f"Erro ao serializar resposta: {str(e)}")
        logger.exception("Traceback completo:")
    
    return db_odontograma

@router.put("/{odontograma_id}", response_model=OdontogramaRead)
def update_odontograma(odontograma_id: int, odontograma_update: OdontogramaUpdate, db: Session = Depends(get_db)):
    """
    Atualiza o cabeçalho de um odontograma (ex: marcar como inativo, ou atualizar Tipo).
    """
    db_odontograma = db.query(Odontograma).filter(Odontograma.id == odontograma_id).first()
    if db_odontograma is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Odontograma não encontrado")

    # OdontogramaUpdate agora inclui 'Tipo', então será atualizado se presente no payload
    update_data = odontograma_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_odontograma, key, value)

    try:
        db.add(db_odontograma)
        db.commit()
        db.refresh(db_odontograma)
        # Recarregar relacionamentos para a resposta
        # O campo tiposerá carregado automaticamente
        db_odontograma_refreshed = db.query(Odontograma).options(
            joinedload(Odontograma.itens).joinedload(OdontogramaItem.produto),
            joinedload(Odontograma.dentista_orcamentista)
        ).filter(Odontograma.id == db_odontograma.id).first()
        return db_odontograma_refreshed # Retornar a instância com dados possivelmente atualizados
    except Exception as e:
        db.rollback()
        # Adicione log de erro aqui também se desejar
        logger = logging.getLogger("uvicorn")
        logger.error(f"Erro ao atualizar odontograma ID {odontograma_id}: {str(e)}")
        logger.exception("Traceback completo:")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar odontograma: {str(e)}")


@router.delete("/{odontograma_id}", status_code=status.HTTP_200_OK, response_model=OdontogramaRead)
def delete_odontograma(odontograma_id: int, db: Session = Depends(get_db)):
    """
    Marca um odontograma como inativo (soft delete) usando SQL direto para evitar problemas de FK.
    """
    # Mantenha os imports de logging e a obtenção do logger como estavam
    logger = logging.getLogger("uvicorn")
    
    logger.info(f"Iniciando soft delete do odontograma ID: {odontograma_id}")
    
    db_odontograma_check = db.query(Odontograma).filter(Odontograma.id == odontograma_id).first()
    if db_odontograma_check is None:
        logger.error(f"Odontograma ID: {odontograma_id} não encontrado para delete")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Odontograma não encontrado")
    
    try:
        itens_count = db.query(OdontogramaItem).filter(OdontogramaItem.odontograma_id == odontograma_id).count()
        logger.info(f"O odontograma possui {itens_count} itens associados")
        
        logger.info(f"Atualizando status do odontograma ID {odontograma_id} usando SQL direto...")
        sql = text("UPDATE odontogramas SET ativo = false WHERE id = :id")
        db.execute(sql, {"id": odontograma_id})
        db.commit()
        
        logger.info(f"SQL executado com sucesso, recarregando odontograma...")
        
        # Recarregar o odontograma para a resposta, tiposerá incluído se presente no modelo
        db_odontograma_deleted = db.query(Odontograma).options(
            joinedload(Odontograma.itens).joinedload(OdontogramaItem.produto),
            joinedload(Odontograma.dentista_orcamentista)
        ).filter(Odontograma.id == odontograma_id).first()
        
        logger.info(f"Odontograma ID: {odontograma_id} marcado como inativo com sucesso")
        return db_odontograma_deleted
    
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao inativar odontograma ID {odontograma_id}: {str(e)}")
        logger.exception("Traceback completo:")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao inativar odontograma: {str(e)}")


# --- Endpoints Odontograma Itens ---
# Nenhuma alteração necessária nesses endpoints para a coluna 'Tipo' da tabela 'odontogramas'
# a menos que a lógica interna deles precise referenciar o Odontograma.Tipo.

@router.post("/{odontograma_id}/itens/", response_model=OdontogramaItemRead, status_code=status.HTTP_201_CREATED)
def create_odontograma_item(
    odontograma_id: int,
    item: OdontogramaItemCreate,
    db: Session = Depends(get_db)
):
    """
    Adiciona um novo item (procedimento/produto) a um odontograma existente.
    """
    logger = logging.getLogger("uvicorn") # Mantenha como estava
    
    logger.info(f"Iniciando adição de item ao odontograma ID: {odontograma_id}")
    logger.info(f"Dados do item: {item.model_dump()}")
    
    try:
        logger.info(f"Verificando existência do odontograma ID: {odontograma_id}")
        db_odontograma = db.query(Odontograma).filter(Odontograma.id == odontograma_id).first()
        if not db_odontograma:
            logger.error(f"Odontograma ID: {odontograma_id} não encontrado")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Odontograma não encontrado")

        logger.info(f"Odontograma encontrado: {db_odontograma.id}") # Aqui você poderia logar db_odontograma.tipose quisesse
        
        logger.info(f"Verificando existência do produto ID: {item.produto_id}")
        db_produto = db.query(Produto).filter(Produto.id == item.produto_id).first()
        if not db_produto:
            logger.error(f"Produto ID: {item.produto_id} não encontrado")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Produto com ID {item.produto_id} não encontrado.")

        logger.info(f"Produto encontrado: {db_produto.nome}")
        
        logger.info("Criando instância do OdontogramaItem")
        db_item_instance = OdontogramaItem( # Renomeado para evitar confusão com db_item de query
            odontograma_id=odontograma_id,
            **item.model_dump() # Usar desempacotamento para os campos de OdontogramaItemCreate
        )
        
        logger.info("Adicionando item ao banco de dados")
        db.add(db_item_instance)
        
        logger.info("Fazendo commit das alterações")
        db.commit()
        
        logger.info("Atualizando instância do item com dados do banco")
        db.refresh(db_item_instance)
        
        logger.info("Carregando relacionamentos para a resposta")
        # Usar a instância já atualizada e carregar o produto nela, se necessário.
        # A query abaixo é mais para re-buscar com joins específicos, mas refresh já atualiza os campos.
        # Se OdontogramaItemRead precisa do produto carregado, esta é uma forma.
        db_item_loaded = db.query(OdontogramaItem).options(
            joinedload(OdontogramaItem.produto)
        ).filter(OdontogramaItem.id == db_item_instance.id).first()
        
        logger.info(f"Item adicionado com sucesso, ID: {db_item_loaded.id if db_item_loaded else db_item_instance.id}")
        return db_item_loaded if db_item_loaded else db_item_instance # Retorna a instância carregada ou a original
    
    except HTTPException as he:
        logger.error(f"HTTPException: {he.detail}")
        raise
        
    except Exception as e:
        logger.error(f"Erro ao salvar item do odontograma: {str(e)}")
        logger.exception("Traceback completo:")
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao salvar item do odontograma: {e}")


@router.delete("/{odontograma_id}/itens/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_odontograma_item(
    odontograma_id: int,
    item_id: int,
    db: Session = Depends(get_db)
):
    """
    Exclui um item específico de um odontograma.
    """
    logger = logging.getLogger("uvicorn") # Mantenha como estava
    
    logger.info(f"Iniciando exclusão do item ID: {item_id} do odontograma ID: {odontograma_id}")
    
    db_item = db.query(OdontogramaItem).filter(
        OdontogramaItem.id == item_id,
        OdontogramaItem.odontograma_id == odontograma_id
    ).first()

    if db_item is None:
        logger.error(f"Item ID: {item_id} não encontrado no odontograma ID: {odontograma_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado neste odontograma")
    
    logger.info(f"Item encontrado: produto_id={db_item.produto_id}, dente={db_item.dente_numero}")
    
    try:
        logger.info(f"Tentando excluir o item...")
        db.delete(db_item)
        db.commit()
        logger.info(f"Item ID: {item_id} excluído com sucesso!")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao excluir item ID {item_id}: {str(e)}")
        logger.exception("Traceback completo:")
        error_str = str(e).lower()
        if "foreign key" in error_str or "constraint" in error_str:
            logger.error("ERRO DE CHAVE ESTRANGEIRA DETECTADO: O item possui referências em outras tabelas!")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, 
                detail="Não foi possível excluir o item pois existem registros associados a ele em outras tabelas."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Erro ao excluir item do odontograma: {str(e)}"
        )
    

@router.get("/por-paciente/{paciente_id}", response_model=List[OdontogramaRead])
def get_odontogramas_por_paciente(
    paciente_id: int,
    ativo: bool = Query(True, description="Filtrar apenas odontogramas ativos"),
    tipo: Optional[str] = Query(None, description="Filtrar por tipo de odontograma"),
    dependente_id: Optional[int] = Query(None, description="Filtrar por dependente ID"),
    db: Session = Depends(get_db)
):
    """
    Retorna todos os odontogramas de um paciente específico, com detalhes completos
    incluindo itens e produtos associados.
    Por padrão, retorna apenas odontogramas ativos.

    PRIORIDADE: Busca primeiro como paciente titular, depois como dependente.
    Isso resolve conflitos quando o mesmo ID existe em ambas as tabelas.
    """
    from sqlalchemy import text

    logger = logging.getLogger("uvicorn")
    logger.info(f"🔍 Buscando odontogramas para ID {paciente_id}")

    # Quando o fluxo já conhece o titular e o dependente, a relação explícita
    # elimina a ambiguidade de IDs que podem existir nas duas tabelas.
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

        query_dependente_explicito = db.query(Odontograma).options(
            joinedload(Odontograma.dentista_orcamentista),
            joinedload(Odontograma.itens).joinedload(OdontogramaItem.produto),
        ).filter(
            Odontograma.paciente_id == paciente_id,
            Odontograma.dependente_id == dependente_id,
        )

        if ativo is not None:
            query_dependente_explicito = query_dependente_explicito.filter(Odontograma.ativo == ativo)

        if tipo is not None:
            query_dependente_explicito = query_dependente_explicito.filter(Odontograma.tipo == tipo)

        odontogramas_dependente = query_dependente_explicito.order_by(
            Odontograma.data_criacao.desc()
        ).all()
        return _with_sale_availability(
            odontogramas_dependente,
            _active_sale_ids_by_odontogram(db, odontogramas_dependente),
        )

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
    query_titular = db.query(Odontograma).options(
        joinedload(Odontograma.dentista_orcamentista),
        joinedload(Odontograma.itens).joinedload(OdontogramaItem.produto),
    ).filter(
        Odontograma.paciente_id == paciente_id,
        Odontograma.dependente_id.is_(None)  # Garante que é do titular
    )

    if ativo is not None:
        query_titular = query_titular.filter(Odontograma.ativo == ativo)

    if tipo is not None:
        query_titular = query_titular.filter(Odontograma.tipo == tipo)

    odontogramas_titular = query_titular.order_by(Odontograma.data_criacao.desc()).all()
    logger.info(f"   📊 Odontogramas do TITULAR (dependente_id NULL): {len(odontogramas_titular)} encontrados")

    # Se encontrou como titular, retorna
    if odontogramas_titular:
        logger.info(f"   ✅ Retornando {len(odontogramas_titular)} odontogramas do paciente titular {paciente_id}")
        return _with_sale_availability(
            odontogramas_titular,
            _active_sale_ids_by_odontogram(db, odontogramas_titular),
        )

    # PRIORIDADE 2: Se não encontrou como titular, tenta como dependente
    if dependente_existe:
        logger.info(f"   🔄 Nenhum odontograma encontrado como titular. Buscando como dependente...")

        query_dependente = db.query(Odontograma).options(
            joinedload(Odontograma.dentista_orcamentista),
            joinedload(Odontograma.itens).joinedload(OdontogramaItem.produto),
        ).filter(
            Odontograma.dependente_id == paciente_id
        )

        if ativo is not None:
            query_dependente = query_dependente.filter(Odontograma.ativo == ativo)

        if tipo is not None:
            query_dependente = query_dependente.filter(Odontograma.tipo == tipo)

        odontogramas_dependente = query_dependente.order_by(Odontograma.data_criacao.desc()).all()
        logger.info(f"   📊 Odontogramas do DEPENDENTE (dependente_id = {paciente_id}): {len(odontogramas_dependente)} encontrados")

        if odontogramas_dependente:
            logger.info(f"   ✅ Retornando {len(odontogramas_dependente)} odontogramas do dependente {paciente_id}")
            return _with_sale_availability(
                odontogramas_dependente,
                _active_sale_ids_by_odontogram(db, odontogramas_dependente),
            )

    # Nenhum odontograma encontrado
    logger.warning(f"   ⚠️ Nenhum odontograma encontrado para ID {paciente_id} (nem como titular nem como dependente)")
    return []
