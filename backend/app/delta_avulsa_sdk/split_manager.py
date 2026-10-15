"""Gerenciador de splits para faturas avulsas"""
import logging
from typing import List, Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

class SplitManager:
    """Gerencia splits de pagamento para faturas avulsas"""
    
    def __init__(self):
        self.splits: List[Dict] = []
        
    def add_split(self, seller_id: int, percentage: float, absorb_balance: bool = False,
                  cycles_to_participate: int = 1, metadata: Optional[Dict] = None) -> None:
        """
        Adiciona um split à lista
        
        Args:
            seller_id: ID do vendedor/recebedor
            percentage: Percentual do split (0-100)
            absorb_balance: Se absorve diferenças de arredondamento
            cycles_to_participate: Número de ciclos (1 para avulso)
            metadata: Dados adicionais (cargo_id, user_id, etc)
        """
        if percentage <= 0 or percentage > 100:
            raise ValueError("Percentual deve estar entre 0 e 100")
            
        split = {
            "sellerId": seller_id,
            "percentage": round(float(percentage), 2),
            "cyclesToParticipate": cycles_to_participate,
            "absorbBalance": absorb_balance,
            "absorbFee": absorb_balance  # Adicionar absorbFee com mesmo valor de absorbBalance
        }
        
        if metadata:
            split["metadata"] = metadata
            
        self.splits.append(split)
        logger.debug(f"Split adicionado: {split}")
        
    def remove_split(self, seller_id: int) -> bool:
        """Remove um split pelo seller_id"""
        initial_count = len(self.splits)
        self.splits = [s for s in self.splits if s["sellerId"] != seller_id]
        removed = len(self.splits) < initial_count
        
        if removed:
            logger.debug(f"Split removido para seller_id: {seller_id}")
            
        return removed
        
    def validate_splits(self) -> bool:
        """
        Valida se os splits estão corretos
        
        Returns:
            True se válido, False caso contrário
        """
        if not self.splits:
            logger.warning("Nenhum split configurado")
            return False
            
        total_percentage = sum(Decimal(str(s["percentage"])) for s in self.splits)
        
        if abs(total_percentage - Decimal("100.00")) > Decimal("0.01"):
            logger.error(f"Soma dos percentuais inválida: {total_percentage}")
            return False
            
        # Verifica se há apenas um absorb_balance = True
        absorb_count = sum(1 for s in self.splits if s.get("absorbBalance", False))
        if absorb_count != 1:
            logger.error(f"Deve haver exatamente 1 split com absorbBalance=True, encontrado: {absorb_count}")
            return False
            
        return True
        
    def get_splits(self) -> List[Dict]:
        """Retorna lista de splits configurados"""
        return self.splits.copy()
        
    def clear_splits(self) -> None:
        """Limpa todos os splits"""
        self.splits.clear()
        logger.debug("Todos os splits foram removidos")
        
    def calculate_splits_from_rules(self, split_rules: List[Dict], total_amount: Decimal) -> List[Dict]:
        """
        Calcula splits baseado em regras do sistema
        
        Args:
            split_rules: Lista de regras de split do banco
            total_amount: Valor total da transação
            
        Returns:
            Lista de splits calculados
        """
        self.clear_splits()
        
        for idx, rule in enumerate(split_rules):
            # Converte valor fixo para percentual se necessário
            if rule.get('valor_fixo'):
                percentage = (Decimal(str(rule['valor_fixo'])) / total_amount) * 100
            else:
                percentage = rule.get('percentual', 0)
                
            # Define quem absorve o balanço (último da lista)
            absorb_balance = (idx == len(split_rules) - 1)
            
            self.add_split(
                seller_id=rule['seller_id'],
                percentage=float(percentage),
                absorb_balance=absorb_balance,
                metadata={
                    'cargo_id': rule.get('cargo_id'),
                    'user_id': rule.get('user_id'),
                    'empresa_id': rule.get('empresa_id')
                }
            )
            
        return self.get_splits()
        
    def to_api_format(self) -> List[Dict]:
        """
        Converte splits para formato da API Delta
        
        Returns:
            Lista de splits no formato esperado pela API
        """
        if not self.validate_splits():
            raise ValueError("Splits inválidos")
            
        return self.splits