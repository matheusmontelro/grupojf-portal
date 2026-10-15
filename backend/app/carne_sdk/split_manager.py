class SplitManager:
    """
    Gerencia os splits para carnês de pagamento.
    """
    
    def __init__(self):
        self.splits = []
        self.metadata = {}

    def add_split(self, seller_id, percentage, cycles_to_participate, absorb_balance=False, **metadata):
        """
        Adiciona um novo split.
        
        Args:
            seller_id (int): ID do seller que participará da divisão.
            percentage (float): Percentual da receita destinado ao seller.
            cycles_to_participate (int): Quantidade de ciclos (faturas) que o seller participará.
            absorb_balance (bool): Define se esse seller absorverá qualquer saldo residual.
            
        Returns:
            int: Índice do split adicionado.
        """
        split = {
            "sellerId": str(seller_id),  # Garantir que seja string
            "percentage": float(percentage),  # Converter para float
            "cyclesToParticipate": int(cycles_to_participate),  # Garantir que seja int
            "absorbBalance": bool(absorb_balance),  # Garantir que seja bool
            "absorbFee": bool(absorb_balance)  # Adicionar absorbFee com mesmo valor de absorbBalance
        }
        
        self.splits.append(split)
        index = len(self.splits) - 1
        
        # Armazenar metadados adicionais se houver
        if metadata:
            self.metadata[index] = metadata
            
        return index
        
    def remove_split(self, index):
        """
        Remove um split pelo índice.
        
        Args:
            index (int): Índice do split a ser removido.
            
        Raises:
            IndexError: Se o índice não existir.
        """
        if 0 <= index < len(self.splits):
            self.splits.pop(index)
        else:
            raise IndexError(f"Índice {index} não existe nos splits.")
            
    def update_split(self, index, seller_id=None, percentage=None, 
                     cycles_to_participate=None, absorb_balance=None):
        """
        Atualiza um split existente.
        
        Args:
            index (int): Índice do split a ser atualizado.
            seller_id (int, optional): Novo ID do seller.
            percentage (float, optional): Novo percentual.
            cycles_to_participate (int, optional): Nova quantidade de ciclos.
            absorb_balance (bool, optional): Novo valor para absorção de saldo.
            
        Raises:
            IndexError: Se o índice não existir.
        """
        if 0 <= index < len(self.splits):
            split = self.splits[index]
            
            if seller_id is not None:
                split["sellerId"] = str(seller_id)
            if percentage is not None:
                split["percentage"] = float(percentage)
            if cycles_to_participate is not None:
                split["cyclesToParticipate"] = int(cycles_to_participate)
            if absorb_balance is not None:
                split["absorbBalance"] = bool(absorb_balance)
        else:
            raise IndexError(f"Índice {index} não existe nos splits.")
            
    def get_splits(self):
        """
        Retorna a lista de splits.
        
        Returns:
            list: Lista de splits.
        """
        return self.splits
        
    def validate_total_percentage(self):
        """
        Valida se a soma dos percentuais é 100%.
        
        Returns:
            bool: True se a soma for 100%, False caso contrário.
        """
        total = sum(float(split["percentage"]) for split in self.splits)
        return abs(total - 100.0) < 0.01  # Tolerância para erros de ponto flutuante
    
    def get_metadata(self, index=None):
        """
        Obtém metadados para um split específico ou todos os metadados.
        
        Args:
            index (int, optional): Índice do split. Se None, retorna todos os metadados.
            
        Returns:
            dict: Metadados do split ou dicionário com todos os metadados.
        """
        if index is not None:
            return self.metadata.get(index, {})
        return self.metadata
    
    def get_splits_with_metadata(self):
        """
        Retorna a lista de splits com seus metadados.
        
        Returns:
            list: Lista de splits com metadados anexados.
        """
        result = []
        for i, split in enumerate(self.splits):
            # Criar uma cópia do split
            enriched_split = split.copy()
            # Adicionar metadados se existirem
            if i in self.metadata:
                for key, value in self.metadata[i].items():
                    enriched_split[key] = value
            result.append(enriched_split)
        return result