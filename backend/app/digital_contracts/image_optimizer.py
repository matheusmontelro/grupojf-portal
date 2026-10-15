import base64
import io
import logging
from typing import Tuple, Optional
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger("image_optimizer")

class ImageOptimizer:
    """
    Classe para otimização de imagens base64
    """
    
    # Configurações padrão
    MAX_WIDTH = 800
    MAX_HEIGHT = 600
    JPEG_QUALITY = 85
    PNG_COMPRESS_LEVEL = 6
    MAX_FILE_SIZE_KB = 500  # 500KB máximo
    
    @staticmethod
    def compress_base64_image(base64_data: str, max_size_kb: int = MAX_FILE_SIZE_KB) -> Tuple[str, dict]:
        """
        Comprime uma imagem base64 mantendo qualidade adequada
        
        Args:
            base64_data: Imagem em formato base64
            max_size_kb: Tamanho máximo em KB
            
        Returns:
            Tuple[str, dict]: (imagem_comprimida, info_compressao)
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
            
            logger.info(f"📸 Comprimindo imagem: {original_size_kb:.2f} KB ({mime_type})")
            
            # Se já está no tamanho adequado, retornar original
            if original_size_kb <= max_size_kb:
                logger.info("✅ Imagem já está no tamanho adequado")
                return base64_data, {
                    'compressed': False,
                    'original_size_kb': original_size_kb,
                    'final_size_kb': original_size_kb,
                    'compression_ratio': 1.0
                }
            
            # Verificar se PIL está disponível
            if not PIL_AVAILABLE:
                logger.warning("⚠️ PIL não disponível, usando compressão básica")
                # Compressão básica: truncar dados se necessário
                if original_size_kb > max_size_kb * 2:
                    # Se a imagem for muito grande, rejeitar
                    raise ValueError(f"Imagem muito grande ({original_size_kb:.2f} KB) e PIL não disponível para compressão")
                else:
                    # Retornar como está
                    return base64_data, {
                        'compressed': False,
                        'original_size_kb': original_size_kb,
                        'final_size_kb': original_size_kb,
                        'compression_ratio': 1.0,
                        'note': 'PIL não disponível'
                    }
            
            # Decodificar imagem
            image_data = base64.b64decode(data)
            image = Image.open(io.BytesIO(image_data))
            
            # Converter para RGB se necessário
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Redimensionar se necessário
            original_width, original_height = image.size
            if original_width > ImageOptimizer.MAX_WIDTH or original_height > ImageOptimizer.MAX_HEIGHT:
                image.thumbnail((ImageOptimizer.MAX_WIDTH, ImageOptimizer.MAX_HEIGHT), Image.Resampling.LANCZOS)
                logger.info(f"🔄 Redimensionado de {original_width}x{original_height} para {image.size}")
            
            # Tentar diferentes níveis de compressão
            for quality in [ImageOptimizer.JPEG_QUALITY, 75, 60, 45, 30]:
                output = io.BytesIO()
                image.save(output, format='JPEG', quality=quality, optimize=True)
                compressed_data = output.getvalue()
                compressed_size_kb = len(compressed_data) / 1024
                
                if compressed_size_kb <= max_size_kb:
                    # Converter para base64
                    compressed_base64 = base64.b64encode(compressed_data).decode('utf-8')
                    final_base64 = f"data:image/jpeg;base64,{compressed_base64}"
                    
                    compression_ratio = compressed_size_kb / original_size_kb
                    
                    logger.info(f"✅ Compressão bem-sucedida: {original_size_kb:.2f} KB → {compressed_size_kb:.2f} KB (qualidade: {quality})")
                    
                    return final_base64, {
                        'compressed': True,
                        'original_size_kb': original_size_kb,
                        'final_size_kb': compressed_size_kb,
                        'compression_ratio': compression_ratio,
                        'quality_used': quality,
                        'dimensions': image.size
                    }
            
            # Se não conseguiu comprimir suficientemente, retornar erro
            raise ValueError(f"Não foi possível comprimir a imagem para menos de {max_size_kb} KB")
            
        except Exception as e:
            logger.error(f"❌ Erro na compressão da imagem: {str(e)}")
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
            
            # Tentar obter dimensões
            try:
                if PIL_AVAILABLE:
                    image_data = base64.b64decode(data)
                    image = Image.open(io.BytesIO(image_data))
                    dimensions = image.size
                    format_info = image.format
                else:
                    dimensions = None
                    format_info = None
            except Exception:
                dimensions = None
                format_info = None
            
            return {
                'mime_type': mime_type,
                'size_kb': size_kb,
                'dimensions': dimensions,
                'format': format_info,
                'is_valid_size': size_kb <= ImageOptimizer.MAX_FILE_SIZE_KB
            }
            
        except Exception as e:
            return {'error': str(e)}