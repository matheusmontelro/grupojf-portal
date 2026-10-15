"""Serviço de validação de produtos por template"""
import re
import logging
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session

from ..models.odontograma import Odontograma
from ..models.odontograma_item import OdontogramaItem
from ..models.produto import Produto
from ..digital_contracts.templates import (
    TEMPLATE_PARTICULAR,
    TEMPLATE_ORTODONTIA
)

logger = logging.getLogger(__name__)

class TemplateValidationService:
    """Serviço para validar produtos de odontograma contra templates"""
    
    # Mapeamento de tipos de odontograma para templates
    TEMPLATE_MAPPING = {
        'Particular': TEMPLATE_PARTICULAR,
        'Ortodontia': TEMPLATE_ORTODONTIA
    }
    
    @staticmethod
    def extract_products_from_template(template_content: str) -> Set[str]:
        """
        Extrai lista de produtos mencionados no template
        
        Args:
            template_content: Conteúdo HTML do template
            
        Returns:
            Set com nomes de produtos encontrados
        """
        # Se o template tem placeholders para produtos dinâmicos, retornar conjunto vazio
        # indicando que qualquer produto é válido
        if '{produtos_table_desktop}' in template_content or '{produtos_table_mobile}' in template_content:
            logger.info("Template tem tabela dinâmica de produtos - qualquer produto é válido")
            return set()
        
        produtos_encontrados = set()
        
        # Padrões para buscar produtos no template
        # Busca por tabelas de produtos/procedimentos
        table_pattern = r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?</tr>'
        tables = re.findall(table_pattern, template_content, re.DOTALL | re.IGNORECASE)
        
        # Padrões comuns de produtos odontológicos
        produto_patterns = [
            r'(?i)(restauração|restauracao)',
            r'(?i)(extração|extracao|exodontia)',
            r'(?i)(limpeza|profilaxia)',
            r'(?i)(canal|endodontia|tratamento\s+de\s+canal)',
            r'(?i)(coroa|protese|prótese)',
            r'(?i)(implante)',
            r'(?i)(clareamento)',
            r'(?i)(ortodontia|aparelho)',
            r'(?i)(radiografia|raio[\s-]?x)',
            r'(?i)(periodontia|raspagem)',
            r'(?i)(cirurgia)',
            r'(?i)(enxerto)',
            r'(?i)(faceta)',
            r'(?i)(consulta|avaliação|avaliacao)',
            r'(?i)(manutenção|manutencao)',
            r'(?i)(contenção|contencao)',
            r'(?i)(documentação|documentacao\s+ortodontica)',
            r'(?i)(gengivoplastia)',
            r'(?i)(frenectomia)',
            r'(?i)(emergência|emergencia|urgência|urgencia)'
        ]
        
        # Buscar produtos no conteúdo completo do template
        for pattern in produto_patterns:
            matches = re.findall(pattern, template_content)
            for match in matches:
                produtos_encontrados.add(match.lower().strip())
        
        # Buscar também em listas específicas de procedimentos
        procedimento_list_pattern = r'(?i)(?:procedimento|tratamento|serviço|servico)[s]?[:\s]*([^<\.]+)'
        proc_matches = re.findall(procedimento_list_pattern, template_content)
        
        for match in proc_matches:
            # Limpar e adicionar cada procedimento encontrado
            cleaned = match.strip().lower()
            # Ignorar se contém placeholders
            if '{' in cleaned or '}' in cleaned:
                continue
            if len(cleaned) > 3:  # Evitar matches muito pequenos
                produtos_encontrados.add(cleaned)
        
        logger.info(f"Produtos extraídos do template: {produtos_encontrados}")
        return produtos_encontrados
    
    def validar_produtos_odontograma(
        self, 
        db: Session,
        odontograma_id: int,
        tipo_odontograma: str
    ) -> Dict[str, any]:
        """
        Valida se todos os produtos do odontograma estão no template correspondente
        
        Args:
            db: Sessão do banco de dados
            odontograma_id: ID do odontograma
            tipo_odontograma: Tipo do odontograma (Particular, Ortodontia)
            
        Returns:
            Dict com resultado da validação:
                - valido: bool
                - produtos_invalidos: List[str]
                - mensagem: str
        """
        # Verificar se o tipo requer validação
        if tipo_odontograma not in self.TEMPLATE_MAPPING:
            return {
                'valido': True,
                'produtos_invalidos': [],
                'mensagem': f'Tipo {tipo_odontograma} não requer validação de template'
            }
        
        # Obter template correspondente
        template = self.TEMPLATE_MAPPING[tipo_odontograma]
        
        # Se o template tem tabela dinâmica de produtos, aceitar qualquer produto
        if '{produtos_table_desktop}' in template or '{produtos_table_mobile}' in template:
            logger.info(f"Template {tipo_odontograma} tem tabela dinâmica - validação desabilitada")
            return {
                'valido': True,
                'produtos_invalidos': [],
                'mensagem': f'Template {tipo_odontograma} aceita produtos dinâmicos do odontograma'
            }
        
        # Buscar odontograma e seus itens
        odontograma = db.query(Odontograma).filter(
            Odontograma.id == odontograma_id
        ).first()
        
        if not odontograma:
            return {
                'valido': False,
                'produtos_invalidos': [],
                'mensagem': 'Odontograma não encontrado'
            }
        
        # Buscar itens do odontograma com produtos
        itens = db.query(OdontogramaItem).filter(
            OdontogramaItem.odontograma_id == odontograma_id
        ).all()
        
        if not itens:
            return {
                'valido': True,
                'produtos_invalidos': [],
                'mensagem': 'Odontograma sem itens'
            }
        
        # Buscar produtos dos itens
        produto_ids = [item.produto_id for item in itens if item.produto_id]
        produtos = db.query(Produto).filter(
            Produto.id.in_(produto_ids)
        ).all() if produto_ids else []
        
        # Obter template correspondente
        template = self.TEMPLATE_MAPPING[tipo_odontograma]
        produtos_permitidos = self.extract_products_from_template(template)
        
        # Se não há produtos permitidos específicos (template dinâmico), aceitar todos
        if not produtos_permitidos:
            logger.info(f"Template {tipo_odontograma} aceita qualquer produto (dinâmico)")
            return {
                'valido': True,
                'produtos_invalidos': [],
                'mensagem': f'Template {tipo_odontograma} aceita produtos dinâmicos do odontograma'
            }
        
        # Validar cada produto
        produtos_invalidos = []
        
        for produto in produtos:
            nome_produto = produto.nome.lower().strip()
            
            # Verificar se o produto está na lista permitida
            produto_valido = False
            
            # Verificação exata
            if nome_produto in produtos_permitidos:
                produto_valido = True
            else:
                # Verificação parcial (produto contém termo permitido ou vice-versa)
                for permitido in produtos_permitidos:
                    if permitido in nome_produto or nome_produto in permitido:
                        produto_valido = True
                        break
            
            if not produto_valido:
                produtos_invalidos.append(produto.nome)
        
        # Retornar resultado
        if produtos_invalidos:
            return {
                'valido': False,
                'produtos_invalidos': produtos_invalidos,
                'mensagem': f'Os seguintes produtos não estão previstos no template {tipo_odontograma}: {", ".join(produtos_invalidos)}'
            }
        
        return {
            'valido': True,
            'produtos_invalidos': [],
            'mensagem': 'Todos os produtos estão de acordo com o template'
        }
    
    def listar_produtos_permitidos(self, tipo_odontograma: str) -> List[str]:
        """
        Lista todos os produtos permitidos para um tipo de odontograma
        
        Args:
            tipo_odontograma: Tipo do odontograma
            
        Returns:
            Lista de produtos permitidos
        """
        if tipo_odontograma not in self.TEMPLATE_MAPPING:
            return []
        
        template = self.TEMPLATE_MAPPING[tipo_odontograma]
        produtos = self.extract_products_from_template(template)
        
        return sorted(list(produtos))