"""
Serviço para aplicar regras de negócio específicas por tipo de contrato
"""
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

class RegrasVendasService:
    """Serviço para aplicar regras de vendas por tipo de contrato"""
    
    @staticmethod
    def get_config_regras(tipo_odontograma_id: int, db: Session) -> Optional[Dict[str, Any]]:
        """Busca configurações de regras para um tipo de contrato"""
        try:
            result = db.execute(text("""
                SELECT entrada_obrigatoria_carne, valor_entrada_automatico, 
                       taxa_adesao_carne, valor_taxa_adesao_padrao,
                       permite_desconto_avista, percentual_desconto_avista_padrao,
                       parcelas_minimas, observacoes
                FROM config_regras_contratos
                WHERE tipo_odontograma_id = :tipo_id
            """), {"tipo_id": tipo_odontograma_id})
            
            row = result.fetchone()
            if row:
                return {
                    "entrada_obrigatoria_carne": row[0],
                    "valor_entrada_automatico": row[1],
                    "taxa_adesao_carne": row[2],
                    "valor_taxa_adesao_padrao": row[3],
                    "permite_desconto_avista": row[4],
                    "percentual_desconto_avista_padrao": row[5],
                    "parcelas_minimas": row[6],
                    "observacoes": row[7]
                }
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar config regras: {e}")
            return None
    
    @staticmethod
    def calcular_data_inicio_carne(data_venda: date = None) -> date:
        """Calcula data de início do carnê (sempre mês seguinte)"""
        if not data_venda:
            data_venda = date.today()
            
        # Se venda após dia 20, carnê começa em 2 meses
        if data_venda.day > 20:
            return data_venda.replace(day=1) + relativedelta(months=2)
        else:
            # Senão, começa no próximo mês
            return data_venda.replace(day=1) + relativedelta(months=1)
    
    @staticmethod
    def calcular_valor_entrada_automatica(valor_total: Decimal, qtd_parcelas: int) -> Decimal:
        """Calcula valor da entrada automática (igual ao valor da parcela)"""
        if qtd_parcelas <= 0:
            return Decimal('0')
        return round(valor_total / qtd_parcelas, 2)
    
    @staticmethod
    def recalcular_parcelas_com_entrada(
        valor_total: Decimal, 
        valor_entrada: Decimal, 
        qtd_parcelas: int
    ) -> Dict[str, Decimal]:
        """Recalcula valores das parcelas considerando entrada"""
        if qtd_parcelas <= 1:
            return {
                "valor_parcela": valor_total - valor_entrada,
                "valor_restante": valor_total - valor_entrada
            }
        
        valor_restante = valor_total - valor_entrada
        valor_parcela = round(valor_restante / (qtd_parcelas - 1), 2)
        
        return {
            "valor_parcela": valor_parcela,
            "valor_restante": valor_restante,
            "qtd_parcelas_restantes": qtd_parcelas - 1
        }
    
    @staticmethod
    def aplicar_desconto_avista(valor_total: Decimal, percentual_desconto: Decimal) -> Dict[str, Decimal]:
        """Aplica desconto para pagamento à vista"""
        if percentual_desconto <= 0:
            return {
                "valor_original": valor_total,
                "valor_desconto": Decimal('0'),
                "valor_final": valor_total
            }
        
        valor_desconto = round(valor_total * (percentual_desconto / 100), 2)
        valor_final = valor_total - valor_desconto
        
        return {
            "valor_original": valor_total,
            "valor_desconto": valor_desconto,
            "valor_final": valor_final
        }
    
    @staticmethod
    def validar_regras_contrato(
        tipo_odontograma_id: int,
        forma_pagamento: str,
        valor_entrada: Optional[Decimal],
        qtd_parcelas: int,
        db: Session
    ) -> Dict[str, Any]:
        """Valida se a venda está de acordo com as regras do tipo de contrato"""
        config = RegrasVendasService.get_config_regras(tipo_odontograma_id, db)
        if not config:
            return {"valido": True, "mensagens": []}
        
        mensagens = []
        valido = True
        
        # Validar entrada obrigatória para carnê
        if (forma_pagamento == "CARNÊ" and 
            config["entrada_obrigatoria_carne"] and 
            (not valor_entrada or valor_entrada <= 0)):
            mensagens.append("Entrada obrigatória para carnê neste tipo de contrato")
            valido = False
        
        # Validar parcelas mínimas
        if qtd_parcelas < config["parcelas_minimas"]:
            mensagens.append(f"Mínimo de {config['parcelas_minimas']} parcelas para este tipo de contrato")
            valido = False
        
        return {
            "valido": valido,
            "mensagens": mensagens,
            "config": config
        }
    
    @staticmethod
    def preparar_dados_venda_com_regras(
        venda_data: Dict[str, Any],
        tipo_odontograma_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """Prepara dados da venda aplicando regras do tipo de contrato"""
        config = RegrasVendasService.get_config_regras(tipo_odontograma_id, db)
        if not config:
            return venda_data
        
        forma_pagamento = venda_data.get("forma_pagamento", "")
        
        # Se for carnê, calcular data de início
        if "CARNÊ" in forma_pagamento:
            venda_data["data_inicio_carne"] = RegrasVendasService.calcular_data_inicio_carne()
            
            # Se tem entrada automática (Ortodontia)
            if config["valor_entrada_automatico"] and not venda_data.get("valor_entrada"):
                valor_entrada = RegrasVendasService.calcular_valor_entrada_automatica(
                    Decimal(str(venda_data["valor_total"])),
                    venda_data["qtd_parcelas"]
                )
                venda_data["valor_entrada"] = float(valor_entrada)
                venda_data["entrada_automatica"] = True
                venda_data["tipo_cobranca_inicial"] = "entrada"
                
                # Recalcular parcelas
                recalculo = RegrasVendasService.recalcular_parcelas_com_entrada(
                    Decimal(str(venda_data["valor_total"])),
                    valor_entrada,
                    venda_data["qtd_parcelas"]
                )
                venda_data["valor_parcela_recalculado"] = float(recalculo["valor_parcela"])
            
            # Se tem taxa de adesão (ODC/Combo)
            elif config["taxa_adesao_carne"]:
                venda_data["tipo_cobranca_inicial"] = "taxa_adesao"
                if config["valor_taxa_adesao_padrao"]:
                    venda_data["valor_taxa_adesao"] = float(config["valor_taxa_adesao_padrao"])
        
        # Se é pagamento à vista e permite desconto
        elif forma_pagamento in ["PIX AVULSO DELTA", "BOLETO AVULSO DELTA", "CARTÃO CRÉDITO AVULSO DELTA"]:
            if config["permite_desconto_avista"] and venda_data.get("aplicar_desconto_avista"):
                percentual = venda_data.get("percentual_desconto_avista") or config["percentual_desconto_avista_padrao"]
                if percentual:
                    desconto_info = RegrasVendasService.aplicar_desconto_avista(
                        Decimal(str(venda_data["valor_total"])),
                        Decimal(str(percentual))
                    )
                    venda_data["valor_com_desconto"] = float(desconto_info["valor_final"])
                    venda_data["valor_desconto_aplicado"] = float(desconto_info["valor_desconto"])
                    venda_data["percentual_desconto_avista"] = float(percentual)
        
        return venda_data
    
    @staticmethod
    def deve_criar_entrada_separada(
        forma_pagamento: str,
        tipo_cobranca_inicial: Optional[str],
        valor_entrada: Optional[Decimal],
        valor_taxa_adesao: Optional[Decimal]
    ) -> bool:
        """Determina se deve criar uma fatura separada para entrada/taxa"""
        if "CARNÊ" not in forma_pagamento:
            return False
            
        if tipo_cobranca_inicial == "entrada" and valor_entrada and valor_entrada > 0:
            return True
            
        if tipo_cobranca_inicial == "taxa_adesao" and valor_taxa_adesao and valor_taxa_adesao > 0:
            return True
            
        return False
    
    @staticmethod
    def preparar_split_entrada_taxa(
        venda_id: int,
        tipo_cobranca: str,
        splits_originais: list,
        db: Session
    ) -> list:
        """
        Prepara splits para entrada/taxa de adesão
        IMPORTANTE: Split deve ocorrer APENAS na entrada/taxa, não no carnê principal
        """
        if not splits_originais:
            return []
        
        logger.info(f"Preparando splits para {tipo_cobranca} da venda {venda_id}")
        
        # Para entrada/taxa, usar os splits normalmente
        # Para o carnê principal, NÃO aplicar splits
        return splits_originais if tipo_cobranca in ["entrada", "taxa_adesao"] else []