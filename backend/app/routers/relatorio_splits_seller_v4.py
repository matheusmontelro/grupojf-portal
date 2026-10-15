# backend/app/routers/relatorio_splits_seller_v4.py

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import logging

from app.database.db import DatabaseConnection
from app.middleware.auth_middleware import get_current_user
from pydantic import BaseModel

# Configurar logging
logger = logging.getLogger(__name__)

# Criar router
router = APIRouter(
    prefix="/relatorio-splits-v4",
    tags=["Relatório de Splits V4"],
    responses={404: {"description": "Not found"}}
)

# Modelos de resposta
class BeneficiarioSplit(BaseModel):
    seller_id: str
    tipo: str  # 'usuario' ou 'empresa'
    id_beneficiario: Optional[int]  # ID do usuário ou empresa
    nome_beneficiario: str
    cpf_cnpj: Optional[str]
    percentage: float
    valor_calculado: float
    status_pagamento: Optional[str]  # 'pago', 'pendente', etc
    observacao: Optional[str]  # Para indicar se é o usuário que fez a venda
    
class SplitDetalhado(BaseModel):
    tipo_split: str  # 'pre_venda', 'venda', 'carne', 'fatura_avulsa', 'fatura_recorrente'
    id_referencia: str  # ID da pré-venda, carnê, fatura, etc
    data_criacao: date
    valor_base: float  # Valor sobre o qual o split é calculado
    status_geral: str  # Status do pagamento principal
    data_pagamento: Optional[date]
    beneficiarios: List[BeneficiarioSplit]
    
class VendaComTodosSplits(BaseModel):
    venda_id: int
    documento_venda: str
    data_venda: date
    paciente_nome: str
    paciente_cpf: str
    odontograma_tipo: Optional[str]
    valor_bruto: float
    valor_liquido: float
    unidade: str
    status_venda: str
    usuario_venda: Dict[str, Any]  # Informações do usuário que fez a venda
    splits_detalhados: List[SplitDetalhado]
    resumo_splits: Dict[str, Any]

def obter_beneficiario_por_seller_id_com_contexto(cursor, seller_id: str, usuario_venda_id: int = None) -> Dict[str, Any]:
    """
    Busca o beneficiário (usuário ou empresa) baseado no seller_id
    Prioriza o usuário que fez a venda se ele tiver o receiver_id correspondente
    """
    # Se temos o ID do usuário da venda, verificar se ele tem o receiver_id correto
    if usuario_venda_id:
        cursor.execute("""
            SELECT 
                id,
                nome,
                cpf,
                bempaggo_receiver_id
            FROM users 
            WHERE id = %s
            AND bempaggo_receiver_id = %s
            LIMIT 1
        """, (usuario_venda_id, seller_id))
        
        result = cursor.fetchone()
        if result:
            return {
                "tipo": "usuario",
                "id_beneficiario": result[0],
                "nome_beneficiario": result[1],
                "cpf_cnpj": result[2],
                "observacao": "Usuário que realizou a venda"
            }
    
    # Se não, buscar qualquer usuário com esse receiver_id
    cursor.execute("""
        SELECT 
            id,
            nome,
            cpf,
            'usuario' as tipo
        FROM users 
        WHERE bempaggo_receiver_id = %s
        ORDER BY id
        LIMIT 1
    """, (seller_id,))
    
    result = cursor.fetchone()
    if result:
        return {
            "tipo": "usuario",
            "id_beneficiario": result[0],
            "nome_beneficiario": result[1],
            "cpf_cnpj": result[2],
            "observacao": None
        }
    
    # Se não encontrou usuário, tentar buscar empresa
    cursor.execute("""
        SELECT 
            id,
            razao_social,
            cnpj,
            'empresa' as tipo
        FROM empresas 
        WHERE bempaggo_receiver_id = %s
        LIMIT 1
    """, (seller_id,))
    
    result = cursor.fetchone()
    if result:
        return {
            "tipo": "empresa",
            "id_beneficiario": result[0],
            "nome_beneficiario": result[1],
            "cpf_cnpj": result[2],
            "observacao": None
        }
    
    # Se não encontrou nem usuário nem empresa
    return {
        "tipo": "outro",
        "id_beneficiario": None,
        "nome_beneficiario": f"Seller {seller_id}",
        "cpf_cnpj": None,
        "observacao": None
    }

@router.get("/venda-completa/{venda_id}")
async def obter_todos_splits_venda_v4(
    venda_id: int,
    current_user: dict = Depends(get_current_user)
) -> VendaComTodosSplits:
    """
    Obter TODOS os splits de uma venda com mapeamento correto de beneficiários.
    
    **Melhorias V4:**
    - Considera o contexto da venda ao mapear beneficiários
    - Prioriza o usuário que fez a venda quando há múltiplos usuários com mesmo receiver_id
    - Inclui informações detalhadas do usuário que realizou a venda
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # 1. Buscar informações da venda e do usuário que a realizou
            cursor.execute("""
                SELECT 
                    v.id,
                    v.documento_venda,
                    v.data_venda,
                    p.nome_paciente,
                    p.cpf_cnpj,
                    od.tipo,
                    v.valor_bruto_total,
                    v.valor_liquido_total,
                    v.unidade,
                    v.status_venda,
                    v.pre_venda_id,
                    v.carne_id,
                    v.usuario_venda_id,
                    u.nome as usuario_nome,
                    u.email as usuario_email,
                    u.bempaggo_receiver_id as usuario_receiver_id
                FROM vendas v
                JOIN pacientes p ON v.paciente_id = p.paciente_id
                LEFT JOIN odontogramas od ON v.odontograma_id = od.id
                LEFT JOIN users u ON v.usuario_venda_id = u.id
                WHERE v.id = %s
            """, (venda_id,))
            
            venda = cursor.fetchone()
            if not venda:
                raise HTTPException(status_code=404, detail="Venda não encontrada")
            
            # Extrair dados da venda
            pre_venda_id = venda[10]
            carne_id = venda[11]
            usuario_venda_id = venda[12]
            
            # Informações do usuário que fez a venda
            usuario_venda = {
                "id": usuario_venda_id,
                "nome": venda[13],
                "email": venda[14],
                "receiver_id": venda[15]
            }
            
            # Preparar resposta
            splits_detalhados = []
            resumo_splits = {
                "total_beneficiarios": 0,
                "total_splits": 0,
                "valor_total_splits": 0,
                "splits_por_tipo": {},
                "beneficiarios_unicos": set()
            }
            
            # 2. Buscar splits da pré-venda
            if pre_venda_id:
                cursor.execute("""
                    SELECT 
                        pvs.seller_id,
                        pvs.percentage,
                        pvs.valor_calculado,
                        pvs.user_id,
                        pvs.empresa_id,
                        pve.valor_pago,
                        pve.status,
                        pve.updated_at as data_pagamento,
                        pve.created_at
                    FROM pre_venda_splits pvs
                    LEFT JOIN pre_vendas_entradas pve ON pvs.pre_venda_id = pve.pre_venda_id
                    WHERE pvs.pre_venda_id = %s
                    ORDER BY pvs.percentage DESC
                """, (pre_venda_id,))
                
                pre_venda_splits = cursor.fetchall()
                if pre_venda_splits:
                    # Pegar informações da primeira linha
                    primeira_linha = pre_venda_splits[0]
                    valor_pago = float(primeira_linha[5]) if primeira_linha[5] else 0
                    status_pagamento = primeira_linha[6]
                    data_pagamento = primeira_linha[7]
                    data_criacao = primeira_linha[8]
                    
                    beneficiarios = []
                    for split in pre_venda_splits:
                        # Buscar beneficiário com contexto do usuário da venda
                        beneficiario_info = obter_beneficiario_por_seller_id_com_contexto(
                            cursor, split[0], usuario_venda_id
                        )
                        
                        beneficiarios.append(BeneficiarioSplit(
                            seller_id=split[0],
                            tipo=beneficiario_info["tipo"],
                            id_beneficiario=beneficiario_info["id_beneficiario"],
                            nome_beneficiario=beneficiario_info["nome_beneficiario"],
                            cpf_cnpj=beneficiario_info["cpf_cnpj"],
                            percentage=float(split[1]),
                            valor_calculado=float(split[2]) if split[2] else 0,
                            status_pagamento=status_pagamento,
                            observacao=beneficiario_info.get("observacao")
                        ))
                        
                        # Atualizar resumo
                        if beneficiario_info["id_beneficiario"]:
                            resumo_splits["beneficiarios_unicos"].add(
                                f"{beneficiario_info['tipo']}_{beneficiario_info['id_beneficiario']}"
                            )
                    
                    splits_detalhados.append(SplitDetalhado(
                        tipo_split="pre_venda",
                        id_referencia=pre_venda_id,
                        data_criacao=data_criacao.date() if data_criacao else venda[2],
                        valor_base=valor_pago,
                        status_geral=status_pagamento or "pendente",
                        data_pagamento=data_pagamento.date() if data_pagamento else None,
                        beneficiarios=beneficiarios
                    ))
                    
                    resumo_splits["splits_por_tipo"]["pre_venda"] = {
                        "quantidade": len(beneficiarios),
                        "valor_total": sum(b.valor_calculado for b in beneficiarios)
                    }
            
            # 3. Buscar splits do carnê (similar com contexto)
            if carne_id:
                cursor.execute("""
                    SELECT 
                        cs.seller_id,
                        cs.percentage,
                        cs.user_id,
                        cs.empresa_id,
                        cp.valor_parcela,
                        cp.total_parcelas,
                        cp.created_at,
                        (SELECT COUNT(*) FROM carne_parcelas WHERE carne_id = cp.id AND status = 'paid') as parcelas_pagas
                    FROM carne_splits cs
                    LEFT JOIN carne_pagamento cp ON cs.carne_id = cp.id
                    WHERE cs.carne_id = %s
                    ORDER BY cs.percentage DESC
                """, (carne_id,))
                
                carne_splits = cursor.fetchall()
                if carne_splits:
                    primeira_linha = carne_splits[0]
                    valor_parcela = float(primeira_linha[4]) if primeira_linha[4] else 0
                    qtd_parcelas = primeira_linha[5]
                    data_criacao = primeira_linha[6]
                    parcelas_pagas = primeira_linha[7]
                    valor_total = valor_parcela * qtd_parcelas
                    
                    beneficiarios = []
                    for split in carne_splits:
                        # Buscar beneficiário com contexto
                        beneficiario_info = obter_beneficiario_por_seller_id_com_contexto(
                            cursor, str(split[0]), usuario_venda_id
                        )
                        
                        valor_split_total = valor_total * float(split[1]) / 100
                        
                        beneficiarios.append(BeneficiarioSplit(
                            seller_id=str(split[0]),
                            tipo=beneficiario_info["tipo"],
                            id_beneficiario=beneficiario_info["id_beneficiario"],
                            nome_beneficiario=beneficiario_info["nome_beneficiario"],
                            cpf_cnpj=beneficiario_info["cpf_cnpj"],
                            percentage=float(split[1]),
                            valor_calculado=round(valor_split_total, 2),
                            status_pagamento=f"{parcelas_pagas}/{qtd_parcelas} pagas",
                            observacao=beneficiario_info.get("observacao")
                        ))
                        
                        if beneficiario_info["id_beneficiario"]:
                            resumo_splits["beneficiarios_unicos"].add(
                                f"{beneficiario_info['tipo']}_{beneficiario_info['id_beneficiario']}"
                            )
                    
                    splits_detalhados.append(SplitDetalhado(
                        tipo_split="carne",
                        id_referencia=str(carne_id),
                        data_criacao=data_criacao.date() if data_criacao else venda[2],
                        valor_base=valor_total,
                        status_geral=f"{parcelas_pagas}/{qtd_parcelas} parcelas pagas",
                        data_pagamento=None,
                        beneficiarios=beneficiarios
                    ))
                    
                    resumo_splits["splits_por_tipo"]["carne"] = {
                        "quantidade": len(beneficiarios),
                        "valor_total": sum(b.valor_calculado for b in beneficiarios)
                    }
            
            # Calcular totais do resumo
            resumo_splits["total_beneficiarios"] = len(resumo_splits["beneficiarios_unicos"])
            resumo_splits["beneficiarios_unicos"] = list(resumo_splits["beneficiarios_unicos"])
            
            for tipo_data in resumo_splits["splits_por_tipo"].values():
                resumo_splits["total_splits"] += tipo_data["quantidade"]
                resumo_splits["valor_total_splits"] += tipo_data["valor_total"]
            
            resumo_splits["valor_total_splits"] = round(resumo_splits["valor_total_splits"], 2)
            
            # Montar resposta final
            return VendaComTodosSplits(
                venda_id=venda[0],
                documento_venda=venda[1],
                data_venda=venda[2].date() if hasattr(venda[2], 'date') else venda[2],
                paciente_nome=venda[3],
                paciente_cpf=venda[4],
                odontograma_tipo=venda[5],
                valor_bruto=float(venda[6]) if venda[6] else 0,
                valor_liquido=float(venda[7]) if venda[7] else 0,
                unidade=venda[8],
                status_venda=venda[9],
                usuario_venda=usuario_venda,
                splits_detalhados=splits_detalhados,
                resumo_splits=resumo_splits
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter todos os splits da venda {venda_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter splits da venda: {str(e)}"
        )