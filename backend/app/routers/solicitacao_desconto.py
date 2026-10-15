# app/routers/solicitacao_desconto.py

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query, Body, Depends, Request
from datetime import datetime
from decimal import Decimal # Boa prática para valores monetários, mas Pydantic já converte para float
import psycopg2
from psycopg2 import extras # Para dict cursor, se preferir

from app.database.db import DatabaseConnection
# Importar conexão e Schemas Pydantic
from app.database.db import DatabaseConnection # Ajuste o caminho
# Importar Schemas Pydantic do arquivo de modelos
from app.models.solicitacao_desconto import (
    SolicitacaoDescontoRead, 
    SolicitacaoDescontoCreate, 
    SolicitacaoDescontoAction
)
# Supondo que User e Odontograma sejam validados de alguma forma ou seus IDs sejam suficientes
# from app.models.user import User # Para dependência de usuário autenticado
# from app.dependencies import get_current_active_user # Ajuste o caminho

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/solicitacoes-desconto", tags=["Solicitações de Desconto"])

# --- Constante para Colunas (ATUALIZADA) ---
# Adicionada a coluna odontograma_id
SOLICITACAO_COLS = "s.id, s.venda_id, s.unidade, s.valor_solicitado, s.percentual_solicitado, s.justificativa, s.usuario_solicitante_id, s.data_solicitacao, s.status_aprovacao, s.usuario_aprovador_id, s.data_aprovacao, s.observacao_aprovador, s.created_at, s.updated_at, s.odontograma_id"
# Adicionado alias 's.' para todas as colunas para evitar ambiguidade em JOINs futuros, se houver.

# --- Helper para Mapear Linha do Cursor (ATUALIZADO) ---
def _map_row_to_solicitacao_read(row_tuple: tuple) -> Optional[SolicitacaoDescontoRead]:
    """Mapeia uma tupla do banco para o schema SolicitacaoDescontoRead."""
    if not row_tuple:
        return None
    
    # A ordem deve corresponder exatamente a SOLICITACAO_COLS
    return SolicitacaoDescontoRead(
        id=row_tuple[0],
        venda_id=row_tuple[1],
        unidade=row_tuple[2],
        valor_solicitado=float(row_tuple[3]) if row_tuple[3] is not None else 0.0, # Converter Decimal para float
        percentual_solicitado=float(row_tuple[4]) if row_tuple[4] is not None else None, # Converter Decimal para float
        justificativa=row_tuple[5],
        usuario_solicitante_id=row_tuple[6],
        data_solicitacao=row_tuple[7],
        status_aprovacao=row_tuple[8],
        usuario_aprovador_id=row_tuple[9],
        data_aprovacao=row_tuple[10],
        observacao_aprovador=row_tuple[11],
        created_at=row_tuple[12],
        updated_at=row_tuple[13],
        odontograma_id=row_tuple[14] # Novo campo
        # Se você decidir carregar dados do odontograma via JOIN, adicione o mapeamento aqui
        # odontograma=OdontogramaReadSimple(...) # Exemplo
    )

# --- Endpoints ---

@router.post("/", response_model=SolicitacaoDescontoRead, status_code=status.HTTP_201_CREATED)
def create_solicitacao_desconto(
    solicitacao_data: SolicitacaoDescontoCreate,
    request: Request
):
    """
    Cria uma nova solicitação de desconto, opcionalmente vinculada a um odontograma.
    O ID do usuário solicitante é obtido do usuário autenticado.
    Envia notificação via WhatsApp para aprovação.
    """
    # Obter usuário do contexto de autenticação
    user_data = getattr(request.state, 'user', None)
    usuario_email = None
    current_user_id = 1  # Default fallback
    
    if user_data:
        # O token JWT tem o email no campo 'sub'
        usuario_email = user_data.get('sub')
        logger.info(f"Usuário autenticado (email): {usuario_email}")
        
        # Buscar ID do usuário pelo email
        if usuario_email:
            try:
                with DatabaseConnection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE email = %s", (usuario_email,))
                    result = cursor.fetchone()
                    if result:
                        current_user_id = result[0]
                        logger.info(f"ID do usuário encontrado: {current_user_id}")
            except Exception as e:
                logger.error(f"Erro ao buscar ID do usuário: {str(e)}")
    
    logger.info(f"Usuário ID {current_user_id} criando solicitação para venda ID {solicitacao_data.venda_id}")

    # Validação básica pode ser implementada aqui
    
    insert_query = """
        INSERT INTO solicitacoes_desconto (
            venda_id, unidade, valor_solicitado, percentual_solicitado, justificativa, 
            usuario_solicitante_id, odontograma_id, 
            data_solicitacao, status_aprovacao, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, venda_id, unidade, valor_solicitado, percentual_solicitado, justificativa, 
                  usuario_solicitante_id, data_solicitacao, status_aprovacao, usuario_aprovador_id, 
                  data_aprovacao, observacao_aprovador, created_at, updated_at, odontograma_id;
    """
    now = datetime.now() # Para data_solicitacao, created_at, updated_at
    default_status = 'Pendente'

    try:
        # Variáveis para armazenar dados complementares
        created_solicitacao = None
        paciente_nome = "Cliente"  # Valor padrão
        odontograma_data = None
        
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Insere a nova solicitação
            cursor.execute(insert_query, (
                solicitacao_data.venda_id,
                solicitacao_data.unidade,
                solicitacao_data.valor_solicitado,
                solicitacao_data.percentual_solicitado,
                solicitacao_data.justificativa,
                current_user_id, # ID do usuário solicitante
                solicitacao_data.odontograma_id,
                now, # data_solicitacao
                default_status, # status_aprovacao
                now, # created_at
                now  # updated_at
            ))
            created_row_tuple = cursor.fetchone()
            
            # Se existe um odontograma associado, buscar dados do paciente
            if solicitacao_data.odontograma_id:
                # Query para buscar dados do paciente e do odontograma
                cursor.execute("""
                    SELECT 
                        p.nome_paciente as paciente_nome,
                        o.id as odontograma_id,
                        tipo_odon.nome as tipo_odontograma,
                        tipo_odon.valor_base as valor_base_tipo,
                        tipo_odon.qtd_parcelas as qtd_parcelas_tipo
                    FROM odontogramas o
                    JOIN pacientes p ON o.paciente_id = p.paciente_id
                    LEFT JOIN tipos_odontograma tipo_odon ON o.tipo = tipo_odon.nome
                    WHERE o.id = %s
                """, (solicitacao_data.odontograma_id,))
                odonto_paciente_data = cursor.fetchone()
                
            # Substitua a consulta de tratamentos por odontograma_itens
            if odonto_paciente_data:
                paciente_nome = odonto_paciente_data[0]  # Nome do paciente
                tipo_odontograma = odonto_paciente_data[2]  # Tipo do odontograma
                valor_base_tipo = odonto_paciente_data[3]  # Valor base do tipo
                qtd_parcelas_tipo = odonto_paciente_data[4]  # Quantidade de parcelas do tipo
                
                # Verificar se é um tipo de contrato/combo
                tipos_contrato = ['Contrato Ortodôntico', 'Contrato Odontológico + Akimais', 'Combo Orto + ODC']
                eh_tipo_contrato = tipo_odontograma in tipos_contrato
                
                if eh_tipo_contrato and valor_base_tipo and qtd_parcelas_tipo:
                    # Para contratos, usar valor_base * qtd_parcelas
                    valor_total_contrato = float(valor_base_tipo) * int(qtd_parcelas_tipo)
                    
                    # Criar dados simulando um "tratamento" para compatibilidade
                    itens_list = [{
                        "id": 1,
                        "nome": f"{tipo_odontograma} ({qtd_parcelas_tipo}x {valor_base_tipo})",
                        "valor": valor_total_contrato
                    }]
                    
                    odontograma_data = {
                        "id": solicitacao_data.odontograma_id,
                        "tratamentos": itens_list,
                        "tipo": tipo_odontograma,
                        "eh_contrato": True,
                        "valor_total_contrato": valor_total_contrato
                    }
                else:
                    # Para tipos normais, buscar dados dos itens do odontograma
                    cursor.execute("""
                        SELECT oi.id, p.nome, oi.valor_registrado
                        FROM odontograma_itens oi
                        JOIN produtos p ON oi.produto_id = p.id
                        WHERE oi.odontograma_id = %s
                    """, (solicitacao_data.odontograma_id,))
                    itens = cursor.fetchall()
                    
                    if itens:
                        # Formatar os itens como uma lista de dicionários
                        itens_list = [
                            {
                                "id": item[0],
                                "nome": item[1],
                                "valor": float(item[2]) if item[2] else 0.0
                            }
                            for item in itens
                        ]
                        
                        odontograma_data = {
                            "id": solicitacao_data.odontograma_id,
                            "tratamentos": itens_list,
                            "tipo": tipo_odontograma,
                            "eh_contrato": False
                        }
            
            # Commit das alterações no banco
            conn.commit()
            
            if not created_row_tuple:
                raise HTTPException(status_code=500, detail="Falha ao criar solicitação de desconto e retornar dados.")
            
            # Mapear a linha retornada para o schema de leitura
            created_solicitacao = _map_row_to_solicitacao_read(created_row_tuple)
        
        # Retornar a solicitação criada
        return created_solicitacao

    except psycopg2.Error as db_err:
        logger.error(f"Erro de DB ao criar solicitação: {db_err}", exc_info=True)
        # Tratar erros específicos de FK, unique constraint, etc.
        if "solicitacoes_desconto_venda_id_key" in str(db_err): # Exemplo de unique constraint
             raise HTTPException(status_code=409, detail=f"Já existe uma solicitação de desconto para a venda ID {solicitacao_data.venda_id}.")
        if "violates foreign key constraint" in str(db_err).lower():
            detail_msg = "Erro de referência: Verifique se a venda, usuário ou odontograma existem."
            if "fk_solicitacoes_desconto_venda_id" in str(db_err): detail_msg = f"Venda com ID {solicitacao_data.venda_id} não encontrada."
            elif "fk_solicitacoes_desconto_odontograma_id" in str(db_err): detail_msg = f"Odontograma com ID {solicitacao_data.odontograma_id} não encontrado."
            elif "fk_solicitacoes_desconto_usuario_solicitante_id" in str(db_err): detail_msg = "Usuário solicitante inválido."
            raise HTTPException(status_code=400, detail=detail_msg)
        raise HTTPException(status_code=500, detail=f"Erro interno do banco de dados ao criar solicitação.")
    except Exception as e:
        logger.error(f"Erro inesperado ao criar solicitação: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno inesperado no servidor.")


@router.get("/", response_model=List[SolicitacaoDescontoRead])
def read_solicitacoes(
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, ge=1, le=500), # Adicionado validação para limit
    status_aprovacao: Optional[str] = Query(None, description="Filtrar por status (ex: Pendente, Aprovado, Rejeitado)"),
    unidade: Optional[str] = Query(None, description="Filtrar por unidade (case-insensitive)."),
    venda_id: Optional[int] = Query(None, description="Filtrar por ID da venda."),
    odontograma_id: Optional[int] = Query(None, description="Filtrar por ID do odontograma."), # Novo filtro
    # db: Session = Depends(get_db) # Removido, pois usa SQL puro
):
    """ Lista solicitações de desconto com filtros e paginação. (SQL PURO) """
    logger.info(f"Listando solicitações com filtros: status={status_aprovacao}, unidade={unidade}, venda_id={venda_id}, odontograma_id={odontograma_id}")
    
    # Usar alias 's.' para a tabela principal na query
    query = f"SELECT {SOLICITACAO_COLS} FROM solicitacoes_desconto s"
    filters = []
    params = []

    if status_aprovacao: 
        filters.append("s.status_aprovacao = %s")
        params.append(status_aprovacao)
    if unidade: 
        filters.append("s.unidade ILIKE %s") # ILIKE para case-insensitive
        params.append(f"%{unidade}%")
    if venda_id is not None:
        filters.append("s.venda_id = %s")
        params.append(venda_id)
    if odontograma_id is not None: # Novo filtro
        filters.append("s.odontograma_id = %s")
        params.append(odontograma_id)
    
    if filters: 
        query += " WHERE " + " AND ".join(filters)
    
    query += " ORDER BY s.data_solicitacao DESC OFFSET %s LIMIT %s"
    params.extend([skip, limit])

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall() # Retorna uma lista de tuplas
            # Mapear cada tupla para o schema Pydantic
            results = [_map_row_to_solicitacao_read(row_tuple) for row_tuple in rows if row_tuple]
            return results
    except Exception as e:
        logger.error(f"Erro ao listar solicitações de desconto: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao buscar solicitações de desconto.")


@router.get("/{solicitacao_id}", response_model=SolicitacaoDescontoRead)
def read_solicitacao(
    solicitacao_id: int,
    # db: Session = Depends(get_db) # Removido
):
    """ Retorna os detalhes de uma solicitação específica. (SQL PURO) """
    logger.info(f"Buscando solicitação ID={solicitacao_id}")
    # Usar alias 's.'
    query = f"SELECT {SOLICITACAO_COLS} FROM solicitacoes_desconto s WHERE s.id = %s"
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (solicitacao_id,))
            row_tuple = cursor.fetchone() # Retorna uma tupla
            if not row_tuple:
                raise HTTPException(status_code=404, detail="Solicitação de desconto não encontrada")
            return _map_row_to_solicitacao_read(row_tuple)
    except HTTPException as http_exc: 
        raise http_exc
    except Exception as e:
        logger.error(f"Erro ao buscar solicitação ID {solicitacao_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao buscar detalhes da solicitação.")


# Modificar a função approve_solicitacao para enviar notificação após aprovação
@router.put("/{solicitacao_id}/aprovar", response_model=SolicitacaoDescontoRead)
def approve_solicitacao(
    solicitacao_id: int,
    action_payload: SolicitacaoDescontoAction, # Usando o schema SolicitacaoDescontoAction
    # current_user: User = Depends(get_current_active_user) # Adapte autenticação
):
    """
    Aprova uma solicitação de desconto pendente. (SQL PURO)
    Atualiza a solicitação e a venda relacionada.
    Envia notificação via WhatsApp após aprovação.
    """
    current_user_id = 1 # Substitua pela lógica real: current_user.id
    logger.info(f"Usuário ID {current_user_id} aprovando solicitação ID={solicitacao_id}")
    now = datetime.now()
    
    # A constante SOLICITACAO_COLS já tem alias 's.'
    # Para o RETURNING, não precisamos do alias, apenas os nomes das colunas da tabela que está sendo atualizada.
    returning_cols = SOLICITACAO_COLS.replace("s.", "") # Remove 's.' para o RETURNING

    # Usar alias 's.' na cláusula WHERE da subconsulta ou na query principal
    select_sql = f"SELECT s.venda_id, s.valor_solicitado, s.status_aprovacao, s.odontograma_id FROM solicitacoes_desconto s WHERE s.id = %s FOR UPDATE;"
    update_solicitacao_sql = f"""
        UPDATE solicitacoes_desconto 
        SET status_aprovacao = 'Aprovado', 
            usuario_aprovador_id = %s, 
            data_aprovacao = %s, 
            observacao_aprovador = %s, 
            updated_at = %s 
        WHERE id = %s 
        RETURNING {returning_cols}; 
    """ # Colunas sem alias para RETURNING
    update_venda_sql = "UPDATE vendas SET valor_desconto_aprovado = valor_desconto_aprovado + %s, valor_liquido_total = valor_liquido_total - %s, updated_at = %s WHERE id = %s;"

    try:
        # Variáveis para armazenar dados para notificação
        paciente_nome = "Cliente"  # Valor padrão
        updated_solicitacao = None
        
        with DatabaseConnection() as conn:
            cursor = conn.cursor()

            # 1. Buscar e bloquear solicitação
            cursor.execute(select_sql, (solicitacao_id,))
            solicitacao_atual_tuple = cursor.fetchone()
            if not solicitacao_atual_tuple: 
                raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

            venda_id, valor_solicitado_decimal, status_atual, odontograma_id = solicitacao_atual_tuple
            valor_solicitado = float(valor_solicitado_decimal) # Converter Decimal para float

            if status_atual != 'Pendente': 
                raise HTTPException(status_code=400, detail=f"Solicitação não está mais pendente (status: {status_atual}).")

            # 2. Atualizar Solicitação
            cursor.execute(update_solicitacao_sql, (
                current_user_id, 
                now, 
                action_payload.observacao_aprovador, 
                now, 
                solicitacao_id
            ))
            solicitacao_row_tuple = cursor.fetchone()
            if not solicitacao_row_tuple: 
                raise HTTPException(status_code=500, detail="Falha ao atualizar status da solicitação.")

            # 3. Atualizar Venda
            cursor.execute(update_venda_sql, (valor_solicitado, valor_solicitado, now, venda_id))
            if cursor.rowcount == 0:
                conn.rollback() # Importante reverter a atualização da solicitação
                raise HTTPException(status_code=500, detail="Falha ao atualizar totais da venda associada. Venda não encontrada ou erro na atualização.")
            
            # 4. Buscar dados do paciente (se o odontograma_id estiver disponível)
            if odontograma_id:
                cursor.execute("""
                    SELECT p.nome_paciente FROM pacientes p
                    JOIN odontogramas o ON p.paciente_id = o.paciente_id
                    WHERE o.id = %s
                """, (odontograma_id,))
                paciente_row = cursor.fetchone()
                if paciente_row:
                    paciente_nome = paciente_row[0]

            # 5. Commit
            conn.commit()
            logger.info(f"Solicitação ID {solicitacao_id} aprovada e Venda ID {venda_id} atualizada.")

            # 6. Mapear o resultado
            updated_solicitacao = _map_row_to_solicitacao_read(solicitacao_row_tuple)
        
        if updated_solicitacao:
            return updated_solicitacao

    except HTTPException as http_exc:
        raise http_exc
    except psycopg2.Error as db_err:
        logger.error(f"Erro de DB ao aprovar solicitação ID {solicitacao_id}: {db_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno do banco de dados: {db_err}")
    except Exception as e:
        logger.error(f"Erro inesperado ao aprovar solicitação ID {solicitacao_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno inesperado no servidor.")

# Modificar a função reject_solicitacao para enviar notificação após rejeição
@router.put("/{solicitacao_id}/rejeitar", response_model=SolicitacaoDescontoRead)
def reject_solicitacao(
    solicitacao_id: int,
    action_payload: SolicitacaoDescontoAction, # Usando o schema SolicitacaoDescontoAction
    # current_user: User = Depends(get_current_active_user) # Adapte
):
    """
    Rejeita uma solicitação de desconto pendente. (SQL PURO)
    Apenas atualiza a solicitação.
    Envia notificação via WhatsApp após rejeição.
    """
    current_user_id = 1 # Substitua pela lógica real: current_user.id
    logger.info(f"Usuário ID {current_user_id} rejeitando solicitação ID={solicitacao_id}")
    now = datetime.now()

    returning_cols = SOLICITACAO_COLS.replace("s.", "")

    select_sql = f"SELECT s.status_aprovacao, s.odontograma_id FROM solicitacoes_desconto s WHERE s.id = %s FOR UPDATE;"
    update_solicitacao_sql = f"""
        UPDATE solicitacoes_desconto 
        SET status_aprovacao = 'Rejeitado', 
            usuario_aprovador_id = %s, 
            data_aprovacao = %s, 
            observacao_aprovador = %s, 
            updated_at = %s 
        WHERE id = %s 
        RETURNING {returning_cols};
    """

    try:
        # Variáveis para armazenar dados para notificação
        paciente_nome = "Cliente"  # Valor padrão
        updated_solicitacao = None
        
        with DatabaseConnection() as conn:
            cursor = conn.cursor()

            # 1. Buscar e bloquear solicitação
            cursor.execute(select_sql, (solicitacao_id,))
            solicitacao_atual_tuple = cursor.fetchone()
            if not solicitacao_atual_tuple: 
                raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

            status_atual, odontograma_id = solicitacao_atual_tuple
            if status_atual != 'Pendente': 
                raise HTTPException(status_code=400, detail=f"Solicitação não está mais pendente (status: {status_atual}).")

            # 2. Atualizar Solicitação
            cursor.execute(update_solicitacao_sql, (
                current_user_id, 
                now, 
                action_payload.observacao_aprovador, 
                now, 
                solicitacao_id
            ))
            solicitacao_row_tuple = cursor.fetchone()
            if not solicitacao_row_tuple: 
                raise HTTPException(status_code=500, detail="Falha ao atualizar status da solicitação.")

            # 3. Buscar dados do paciente (se o odontograma_id estiver disponível)
            if odontograma_id:
                cursor.execute("""
                    SELECT p.nome_paciente FROM pacientes p
                    JOIN odontogramas o ON p.paciente_id = o.paciente_id
                    WHERE o.id = %s
                """, (odontograma_id,))
                paciente_row = cursor.fetchone()
                if paciente_row:
                    paciente_nome = paciente_row[0]

            # 4. Commit
            conn.commit()
            logger.info(f"Solicitação ID {solicitacao_id} rejeitada com sucesso.")

            # 5. Mapear o resultado
            updated_solicitacao = _map_row_to_solicitacao_read(solicitacao_row_tuple)
        
        if updated_solicitacao:
            return updated_solicitacao

    except HTTPException as http_exc:
        raise http_exc
    except psycopg2.Error as db_err:
        logger.error(f"Erro de DB ao rejeitar solicitação ID {solicitacao_id}: {db_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno do banco de dados: {db_err}")
    except Exception as e:
        logger.error(f"Erro inesperado ao rejeitar solicitação ID {solicitacao_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno inesperado no servidor.")
