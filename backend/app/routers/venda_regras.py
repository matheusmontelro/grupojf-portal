"""
Extensões dos endpoints de venda para aplicar as novas regras de negócio
"""
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from ..services.regras_vendas_service import RegrasVendasService
from ..routers.fatura_avulsa import create_fatura_avulsa
from ..models.fatura_avulsa import FaturaAvulsaCreateRequest

logger = logging.getLogger(__name__)

def processar_regras_ortodontico(
    venda_id: int,
    forma_pagamento: str,
    valor_total: Decimal,
    qtd_parcelas: int,
    unidade: str,
    db: Session,
    conn: Any
) -> Dict[str, Any]:
    """
    Aplica regras específicas para Contrato Ortodôntico
    - Se carnê: gerar entrada = valor_parcela via PIX/Boleto/Cartão
    - Se à vista: possibilidade de desconto
    """
    resultado = {
        "entrada_criada": False,
        "fatura_entrada_id": None,
        "valor_entrada": None,
        "data_inicio_carne": None
    }
    
    try:
        # Buscar tipo_odontograma_id para Ortodôntico
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM tipos_odontograma 
            WHERE nome = 'Contrato Ortodôntico' AND ativo = TRUE
        """)
        tipo_id = cursor.fetchone()
        if not tipo_id:
            logger.warning("Tipo Contrato Ortodôntico não encontrado")
            return resultado
            
        tipo_odontograma_id = tipo_id[0]
        
        # Se for carnê, aplicar regras especiais
        if "CARNÊ" in forma_pagamento:
            # 1. Calcular valor da entrada (= valor da parcela)
            valor_entrada = RegrasVendasService.calcular_valor_entrada_automatica(
                valor_total, qtd_parcelas
            )
            
            # 2. Calcular data início do carnê
            data_inicio_carne = RegrasVendasService.calcular_data_inicio_carne()
            
            # 3. Atualizar venda com informações da entrada
            cursor.execute("""
                UPDATE vendas SET
                    tipo_cobranca_inicial = 'entrada',
                    valor_entrada = %s,
                    entrada_automatica = TRUE,
                    data_inicio_carne = %s
                WHERE id = %s
            """, (valor_entrada, data_inicio_carne, venda_id))
            conn.commit()
            
            # 4. Criar fatura avulsa para entrada
            logger.info(f"Criando entrada automática de R$ {valor_entrada} para venda {venda_id}")
            
            # Preparar dados para fatura de entrada
            fatura_entrada_data = FaturaAvulsaCreateRequest(
                venda_id=venda_id,
                valor_total=float(valor_entrada),
                payment_method="PIX AVULSO DELTA",  # Padrão PIX para entrada
                unidade=unidade,
                criado_por=1,  # TODO: Usar usuário atual
                installments=1  # Entrada sempre à vista
            )
            
            # Criar fatura usando o endpoint existente
            try:
                fatura_response = create_fatura_avulsa(fatura_entrada_data, db)
                
                # Marcar como fatura de entrada
                if fatura_response and hasattr(fatura_response, 'id'):
                    db.execute(text("""
                        UPDATE fatura_avulsa 
                        SET tipo_fatura = 'entrada',
                            carne_id = (SELECT MAX(id) FROM carne_pagamento WHERE venda_id = :venda_id)
                        WHERE invoice_id = :invoice_id
                    """), {
                        'invoice_id': fatura_response.id,
                        'venda_id': venda_id
                    })
                    db.commit()
                    
                    resultado["entrada_criada"] = True
                    resultado["fatura_entrada_id"] = fatura_response.id
                    resultado["valor_entrada"] = float(valor_entrada)
                    
            except Exception as e:
                logger.error(f"Erro ao criar fatura de entrada: {e}")
                # Não falhar a venda por causa da entrada
            
            resultado["data_inicio_carne"] = data_inicio_carne
            
        # Se for à vista, verificar desconto
        elif forma_pagamento in ["PIX AVULSO DELTA", "BOLETO AVULSO DELTA", "CARTÃO CRÉDITO AVULSO DELTA"]:
            # Por enquanto, desconto será aplicado manualmente
            # TODO: Implementar interface para aplicar desconto
            pass
            
    except Exception as e:
        logger.error(f"Erro ao processar regras ortodôntico: {e}")
        
    return resultado


def processar_regras_odc_combo(
    venda_id: int,
    forma_pagamento: str,
    tipo_contrato: str,
    unidade: str,
    db: Session,
    conn: Any
) -> Dict[str, Any]:
    """
    Aplica regras específicas para ODC + Akimais e Combo
    - Se carnê: gerar taxa de adesão
    - Se à vista: possibilidade de desconto
    """
    resultado = {
        "taxa_criada": False,
        "fatura_taxa_id": None,
        "valor_taxa": None,
        "data_inicio_carne": None
    }
    
    try:
        # Buscar tipo_odontograma_id
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM tipos_odontograma 
            WHERE nome = %s AND ativo = TRUE
        """, (tipo_contrato,))
        tipo_id = cursor.fetchone()
        if not tipo_id:
            logger.warning(f"Tipo {tipo_contrato} não encontrado")
            return resultado
            
        tipo_odontograma_id = tipo_id[0]
        
        # Buscar configuração de taxa de adesão
        config = RegrasVendasService.get_config_regras(tipo_odontograma_id, db)
        if not config:
            return resultado
        
        # Se for carnê e tem taxa de adesão
        if "CARNÊ" in forma_pagamento and config.get("taxa_adesao_carne"):
            # 1. Obter valor da taxa
            valor_taxa = Decimal(str(config.get("valor_taxa_adesao_padrao", 150)))  # Padrão R$ 150
            
            # 2. Calcular data início do carnê
            data_inicio_carne = RegrasVendasService.calcular_data_inicio_carne()
            
            # 3. Atualizar venda com informações da taxa
            cursor.execute("""
                UPDATE vendas SET
                    tipo_cobranca_inicial = 'taxa_adesao',
                    valor_taxa_adesao = %s,
                    data_inicio_carne = %s
                WHERE id = %s
            """, (valor_taxa, data_inicio_carne, venda_id))
            conn.commit()
            
            # 4. Criar fatura avulsa para taxa de adesão
            logger.info(f"Criando taxa de adesão de R$ {valor_taxa} para venda {venda_id}")
            
            # Preparar dados para fatura de taxa
            fatura_taxa_data = FaturaAvulsaCreateRequest(
                venda_id=venda_id,
                valor_total=float(valor_taxa),
                payment_method="PIX AVULSO DELTA",  # Padrão PIX para taxa
                unidade=unidade,
                criado_por=1,  # TODO: Usar usuário atual
                installments=1  # Taxa sempre à vista
            )
            
            # Criar fatura usando o endpoint existente
            try:
                fatura_response = create_fatura_avulsa(fatura_taxa_data, db)
                
                # Marcar como fatura de taxa de adesão
                if fatura_response and hasattr(fatura_response, 'id'):
                    db.execute(text("""
                        UPDATE fatura_avulsa 
                        SET tipo_fatura = 'taxa_adesao',
                            carne_id = (SELECT MAX(id) FROM carne_pagamento WHERE venda_id = :venda_id)
                        WHERE invoice_id = :invoice_id
                    """), {
                        'invoice_id': fatura_response.id,
                        'venda_id': venda_id
                    })
                    db.commit()
                    
                    resultado["taxa_criada"] = True
                    resultado["fatura_taxa_id"] = fatura_response.id
                    resultado["valor_taxa"] = float(valor_taxa)
                    
            except Exception as e:
                logger.error(f"Erro ao criar fatura de taxa: {e}")
                # Não falhar a venda por causa da taxa
            
            resultado["data_inicio_carne"] = data_inicio_carne
            
    except Exception as e:
        logger.error(f"Erro ao processar regras ODC/Combo: {e}")
        
    return resultado


def ajustar_split_carne_com_entrada(
    venda_id: int,
    tem_entrada_ou_taxa: bool,
    db: Session
) -> None:
    """
    Ajusta configuração de split do carnê quando há entrada/taxa
    NOVA REGRA: 
    - Split na entrada/taxa: TODOS os participantes (cargos + empresas)
    - Split no carnê: APENAS empresas
    """
    if not tem_entrada_ou_taxa:
        return
        
    try:
        # NOVA LÓGICA: Configurar carnê para usar split apenas empresas
        db.execute(text("""
            UPDATE carne_pagamento 
            SET aplicar_split_principal = FALSE,
                aplicar_split_empresas = TRUE,
                tem_entrada_separada = TRUE
            WHERE venda_id = :venda_id
        """), {'venda_id': venda_id})
        db.commit()
        
        logger.info(f"Carnê configurado para split apenas empresas na venda {venda_id} (entrada/taxa com split completo)")
        
    except Exception as e:
        logger.error(f"Erro ao ajustar split do carnê: {e}")
        # Não falhar por causa disso