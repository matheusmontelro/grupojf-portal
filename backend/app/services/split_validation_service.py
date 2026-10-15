"""
Serviço de validação para regras de split
Garante que não haja conflitos entre empresas J&F
"""
import logging
from typing import List, Dict, Optional, Tuple
from ..database.db import DatabaseConnection

logger = logging.getLogger(__name__)

class SplitValidationService:
    """
    Serviço para validar configurações de split
    """
    
    @staticmethod
    def is_jf_company(razao_social: str) -> bool:
        """
        Verifica se uma empresa é J&F baseado na razão social
        """
        razao_upper = razao_social.upper()
        return 'J&F' in razao_upper or 'J & F' in razao_upper
    
    @staticmethod
    def validate_participacao_empresas(
        tipo_odontograma_id: int,
        empresas_ids: List[int],
        unidade_referencia: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Valida se a configuração de empresas participantes é válida.
        
        Regras:
        1. Não pode ter mais de uma empresa J&F no mesmo split
        2. Se especificar unidade, a J&F deve ser da mesma unidade
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Buscar informações das empresas
                placeholders = ','.join(['%s'] * len(empresas_ids))
                cursor.execute(f"""
                    SELECT id, razao_social, unidade
                    FROM empresas
                    WHERE id IN ({placeholders})
                """, empresas_ids)
                
                empresas = cursor.fetchall()
                
                # Verificar empresas J&F
                jf_empresas = []
                for emp_id, razao_social, unidade in empresas:
                    if SplitValidationService.is_jf_company(razao_social):
                        jf_empresas.append({
                            'id': emp_id,
                            'razao_social': razao_social,
                            'unidade': unidade
                        })
                
                # Validação 1: Não pode ter mais de uma J&F
                if len(jf_empresas) > 1:
                    unidades = [jf['unidade'] for jf in jf_empresas]
                    return False, f"Não é permitido ter múltiplas empresas J&F no mesmo split. Encontradas J&F das unidades: {', '.join(unidades)}"
                
                # Validação 2: Se tem unidade de referência, J&F deve ser da mesma unidade
                if unidade_referencia and jf_empresas:
                    jf_unidade = jf_empresas[0]['unidade']
                    if jf_unidade != unidade_referencia:
                        return False, f"A empresa J&F deve ser da unidade {unidade_referencia}, mas foi encontrada J&F da unidade {jf_unidade}"
                
                return True, None
                
        except Exception as e:
            logger.error(f"Erro ao validar participação de empresas: {str(e)}")
            return False, f"Erro ao validar: {str(e)}"
    
    @staticmethod
    def get_jf_empresa_por_unidade(unidade: str) -> Optional[Dict[str, any]]:
        """
        Retorna a empresa J&F de uma unidade específica
        """
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, razao_social, nome_fantasia
                    FROM empresas
                    WHERE unidade = %s
                    AND (UPPER(razao_social) LIKE '%J&F%' OR UPPER(razao_social) LIKE '%J & F%')
                    LIMIT 1
                """, (unidade,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'razao_social': row[1],
                        'nome_fantasia': row[2],
                        'unidade': unidade
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Erro ao buscar J&F da unidade {unidade}: {str(e)}")
            return None
    
    @staticmethod
    def get_empresas_por_unidade() -> Dict[str, List[Dict]]:
        """
        Retorna todas as empresas agrupadas por unidade
        """
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, razao_social, nome_fantasia, unidade
                    FROM empresas
                    WHERE unidade IS NOT NULL
                    ORDER BY unidade, razao_social
                """)
                
                empresas_por_unidade = {}
                for row in cursor.fetchall():
                    emp = {
                        'id': row[0],
                        'razao_social': row[1],
                        'nome_fantasia': row[2],
                        'unidade': row[3],
                        'is_jf': SplitValidationService.is_jf_company(row[1])
                    }
                    
                    if row[3] not in empresas_por_unidade:
                        empresas_por_unidade[row[3]] = []
                    
                    empresas_por_unidade[row[3]].append(emp)
                
                return empresas_por_unidade
                
        except Exception as e:
            logger.error(f"Erro ao buscar empresas por unidade: {str(e)}")
            return {}
    
    @staticmethod
    def validate_regra_split(
        tipo_odontograma_id: int,
        empresa_ids: List[int],
        cargo_ids: List[int]
    ) -> Tuple[bool, Optional[str]]:
        """
        Valida uma configuração completa de split (empresas + cargos)
        """
        # Primeiro valida as empresas
        is_valid, error_msg = SplitValidationService.validate_participacao_empresas(
            tipo_odontograma_id, 
            empresa_ids
        )
        
        if not is_valid:
            return False, error_msg
        
        # Aqui podemos adicionar outras validações no futuro
        # Por exemplo: verificar se os percentuais somam 100%
        
        return True, None