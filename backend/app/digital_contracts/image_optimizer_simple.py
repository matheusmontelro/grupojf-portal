import base64
import logging
from typing import Tuple, Optional

logger = logging.getLogger("image_optimizer")

class ImageOptimizer:
    """
    Classe para otimização básica de imagens base64
    """
    
    # Configurações padrão
    MAX_FILE_SIZE_KB = 500  # 500KB máximo
    
    @staticmethod
    def compress_base64_image(base64_data: str, max_size_kb: int = MAX_FILE_SIZE_KB) -> Tuple[str, dict]:
        """
        Valida e limita o tamanho da imagem base64
        
        Args:
            base64_data: Imagem em formato base64
            max_size_kb: Tamanho máximo em KB
            
        Returns:
            Tuple[str, dict]: (imagem_validada, info_validacao)
        """
        try:
            if not base64_data:
                raise ValueError("Imagem vazia")
                
            # Extrair dados da imagem
            if ',' in base64_data:
                header, data = base64_data.split(',', 1)
                mime_type = header.split(';')[0].split(':')[1] if ':' in header else 'image/jpeg'
            else:
                data = base64_data
                mime_type = 'image/jpeg'
                
            # Calcular tamanho original
            original_size_kb = len(data) * 3 / 4 / 1024
            
            logger.info(f"📸 Validando imagem: {original_size_kb:.2f} KB ({mime_type})")
            
            # Se já está no tamanho adequado, retornar original
            if original_size_kb <= max_size_kb:
                logger.info("✅ Imagem já está no tamanho adequado")
                return base64_data, {
                    'compressed': False,
                    'original_size_kb': original_size_kb,
                    'final_size_kb': original_size_kb,
                    'compression_ratio': 1.0
                }
            
            # Se a imagem for muito grande, rejeitar
            logger.warning(f"⚠️ Imagem muito grande: {original_size_kb:.2f} KB (máximo: {max_size_kb} KB)")
            raise ValueError(f"Imagem muito grande ({original_size_kb:.2f} KB). Máximo permitido: {max_size_kb} KB")
            
        except Exception as e:
            logger.error(f"❌ Erro na validação da imagem: {str(e)}")
            raise
    
    @staticmethod
    def validate_image_size(base64_data: str, max_size_kb: int = MAX_FILE_SIZE_KB) -> bool:
        """
        Valida se uma imagem base64 está dentro do tamanho permitido
        
        Args:
            base64_data: Imagem em formato base64
            max_size_kb: Tamanho máximo em KB
            
        Returns:
            bool: True se válida, False caso contrário
        """
        try:
            if not base64_data:
                return False
                
            # Extrair dados da imagem
            if ',' in base64_data:
                _, data = base64_data.split(',', 1)
            else:
                data = base64_data
                
            # Calcular tamanho
            size_kb = len(data) * 3 / 4 / 1024
            
            return size_kb <= max_size_kb
            
        except Exception:
            return False
    
    @staticmethod
    def get_image_info(base64_data: str) -> dict:
        """
        Obtém informações sobre uma imagem base64
        
        Args:
            base64_data: Imagem em formato base64
            
        Returns:
            dict: Informações da imagem
        """
        try:
            if not base64_data:
                return {'error': 'Imagem vazia'}
                
            # Extrair dados da imagem
            if ',' in base64_data:
                header, data = base64_data.split(',', 1)
                mime_type = header.split(';')[0].split(':')[1] if ':' in header else 'unknown'
            else:
                data = base64_data
                mime_type = 'unknown'
                
            # Calcular tamanho
            size_kb = len(data) * 3 / 4 / 1024
            
            return {
                'mime_type': mime_type,
                'size_kb': size_kb,
                'dimensions': None,  # Não disponível sem PIL
                'format': mime_type.split('/')[-1].upper() if '/' in mime_type else 'UNKNOWN',
                'is_valid_size': size_kb <= ImageOptimizer.MAX_FILE_SIZE_KB
            }
            
        except Exception as e:
            return {'error': str(e)}