from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field # Importar BaseModel do Pydantic
from typing import List, Optional
from datetime import datetime
from sqlalchemy import distinct
# Importar o Model SQLAlchemy correspondente
from ..models.produto import Produto
# Importar a dependência para obter a sessão do DB (ajuste o caminho se necessário)
from ..database.db import get_db # Supondo que get_db está em database/db.py

# --- Schemas Pydantic para Produtos ---

class ProdutoBase(BaseModel):
    # Usar Optional ou default para campos não obrigatórios na base
    codigo_interno: str = Field(..., max_length=50, description="Código único interno do produto/procedimento")
    nome: str = Field(..., description="Nome descritivo do produto/procedimento")
    tipo: Optional[str] = Field(None, max_length=50, description="Tipo ou especialidade (ex: Clínico, Prótese)")
    valor: float = Field(..., ge=0, description="Valor do produto/procedimento")
    ativo: bool = True

    # Para permitir que Pydantic leia dados de atributos ORM (como produto.id)
    class Config:
        from_attributes = True # Anteriormente orm_mode = True

class ProdutoCreate(ProdutoBase):
    # Herda de ProdutoBase, nenhum campo adicional necessário para criar
    pass

class ProdutoUpdate(BaseModel):
    # Todos os campos são opcionais na atualização
    codigo_interno: Optional[str] = Field(None, max_length=50)
    nome: Optional[str] = None
    tipo: Optional[str] = Field(None, max_length=50)
    valor: Optional[float] = Field(None, get_db=0)
    ativo: Optional[bool] = None

    class Config:
        from_attributes = True

class ProdutoRead(ProdutoBase):
    # Herda de ProdutoBase e adiciona campos lidos do DB
    id: int
    data_atualizacao_valor: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

# --- Router FastAPI ---

router = APIRouter(
    prefix="/produtos", # Prefixo para todas as rotas neste arquivo
    tags=["Produtos"]   # Agrupa na documentação da API
)

# --- Endpoints CRUD ---

@router.post("/", response_model=ProdutoRead, status_code=status.HTTP_201_CREATED)
def create_produto(produto: ProdutoCreate, db: Session = Depends(get_db)):
    """
    Cria um novo produto/procedimento no banco de dados.
    Verifica se o código interno já existe.
    """
    db_produto_check = db.query(Produto).filter(Produto.codigo_interno == produto.codigo_interno).first()
    if db_produto_check:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Código interno '{produto.codigo_interno}' já registrado.")

    # Cria instância do model SQLAlchemy a partir do schema Pydantic
    db_produto = Produto(**produto.model_dump())
    # Define a data de atualização do valor inicial (se necessário)
    db_produto.data_atualizacao_valor = datetime.now()

    try:
        db.add(db_produto)
        db.commit()
        db.refresh(db_produto) # Atualiza o objeto db_produto com dados do DB (como o ID gerado)
        return db_produto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao salvar produto: {e}")


@router.get("/", response_model=List[ProdutoRead])
def read_produtos(
    skip: int = 0,
    limit: int = 100,
    tipo: Optional[str] = None,
    ativo: Optional[bool] = None,
    nome: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna uma lista de produtos, com paginação e filtros opcionais.
    """
    query = db.query(Produto)
    if tipo:
        query = query.filter(Produto.tipo.ilike(f"%{tipo}%")) # Case-insensitive search
    if ativo is not None:
        query = query.filter(Produto.ativo == ativo)
    if nome:
         query = query.filter(Produto.nome.ilike(f"%{nome}%"))

    produtos = query.offset(skip).limit(limit).all()
    return produtos

@router.get("/{produto_id}", response_model=ProdutoRead)
def read_produto(produto_id: int, db: Session = Depends(get_db)):
    """
    Retorna um produto específico pelo seu ID.
    """
    db_produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if db_produto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
    return db_produto

@router.put("/{produto_id}", response_model=ProdutoRead)
def update_produto(produto_id: int, produto_update: ProdutoUpdate, db: Session = Depends(get_db)):
    """
    Atualiza um produto existente pelo seu ID.
    Apenas os campos fornecidos no corpo da requisição são atualizados.
    """
    db_produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if db_produto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")

    # Verifica se o novo codigo_interno (se fornecido) já existe em outro produto
    if produto_update.codigo_interno and produto_update.codigo_interno != db_produto.codigo_interno:
         existing_code = db.query(Produto).filter(Produto.codigo_interno == produto_update.codigo_interno).first()
         if existing_code:
              raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Código interno '{produto_update.codigo_interno}' já pertence a outro produto.")

    # Obtem os dados do schema de atualização, excluindo os não definidos
    update_data = produto_update.model_dump(exclude_unset=True)

    # Atualiza os campos no objeto do model SQLAlchemy
    for key, value in update_data.items():
        setattr(db_produto, key, value)

    # Atualiza a data de modificação do valor se o valor foi alterado
    if 'valor' in update_data:
        db_produto.data_atualizacao_valor = datetime.now()
    # Sempre atualiza o updated_at (feito pelo onupdate no model, mas pode forçar aqui se necessário)
    # db_produto.updated_at = datetime.now()

    try:
        db.add(db_produto) # Adiciona o objeto modificado à sessão
        db.commit()
        db.refresh(db_produto) # Recarrega o objeto com os dados atualizados
        return db_produto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar produto: {e}")


@router.delete("/{produto_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_produto(produto_id: int, db: Session = Depends(get_db)):
    """
    Exclui um produto pelo seu ID.
    (Alternativamente, poderia apenas marcar como inativo: db_produto.ativo = False)
    """
    db_produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if db_produto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")

    try:
        db.delete(db_produto)
        db.commit()
        # Retorna uma resposta vazia com status 204
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        db.rollback()
        # Considerar se o erro é por FK constraint (produto em uso)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao excluir produto: {e}")
    
# No arquivo de router produtos, adicione este endpoint
@router.get("/tipos", response_model=List[str])
def get_produto_tipos(db: Session = Depends(get_db)):
    """
    Retorna a lista de tipos únicos de produtos existentes no banco.
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    logger.info("Buscando tipos únicos de produtos")
    
    try:
        # Consulta SQL para buscar tipos únicos
        result = db.query(distinct(Produto.tipo)).filter(
            Produto.tipo.is_not(None),
            Produto.tipo != ''
        ).all()
        
        # Extrair os tipos do resultado
        tipos = [tipo[0] for tipo in result if tipo[0]]
        
        logger.info(f"Tipos encontrados: {tipos}")
        return tipos
    except Exception as e:
        logger.error(f"Erro ao buscar tipos de produtos: {str(e)}")
        logger.exception("Traceback completo:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Erro ao buscar tipos de produtos: {e}"
        )