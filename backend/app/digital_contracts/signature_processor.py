# digital_contracts/signature_processor.py
import base64
import io
import logging
from PIL import Image, ImageOps
import numpy as np

logger = logging.getLogger("signature_processor")

class SignatureProcessor:
    """
    Processa assinaturas para padronizar formato e remover fundos
    """
    
    @staticmethod
    def process_signature(signature_data_url: str) -> str:
        """
        Processa assinatura para PNG com transparência
        
        Args:
            signature_data_url: Data URL da assinatura (JPEG ou PNG)
            
        Returns:
            Data URL da assinatura processada em PNG com transparência
        """
        logger.info("🎨 Iniciando processamento da assinatura...")
        
        try:
            # Validar formato
            if not signature_data_url or not signature_data_url.startswith('data:image/'):
                logger.error("❌ Formato de assinatura inválido")
                raise ValueError("Formato de assinatura inválido")
            
            # Extrair tipo e dados base64
            header, base64_data = signature_data_url.split(',', 1)
            image_type = SignatureProcessor._get_image_type(header)
            
            logger.info(f"📋 Tipo detectado: {image_type}")
            logger.info(f"📊 Tamanho original: {len(base64_data)} chars")
            
            # Se já é PNG, verificar se precisa de processamento
            if image_type == 'png':
                logger.info("🔍 PNG detectado, verificando se precisa de processamento...")
                
                # Converter para verificar se há transparência
                image_bytes = base64.b64decode(base64_data)
                image = Image.open(io.BytesIO(image_bytes))
                
                if image.mode == 'RGBA' and SignatureProcessor._has_transparency(image):
                    logger.info("✅ PNG já tem transparência adequada, usando original")
                    return signature_data_url
                else:
                    logger.info("🔄 PNG sem transparência adequada, processando...")
            
            # Processar imagem (JPEG ou PNG sem transparência)
            processed_png = SignatureProcessor._convert_to_transparent_png(base64_data, image_type)
            
            logger.info(f"✅ Processamento concluído: {len(processed_png)} chars")
            return f"data:image/png;base64,{processed_png}"
            
        except Exception as e:
            logger.error(f"❌ Erro no processamento da assinatura: {str(e)}")
            logger.error(f"❌ Retornando assinatura original como fallback")
            # Fallback: retornar original se houver erro
            return signature_data_url
    
    @staticmethod
    def _get_image_type(header: str) -> str:
        """Extrai o tipo de imagem do header"""
        if 'image/png' in header:
            return 'png'
        elif 'image/jpeg' in header or 'image/jpg' in header:
            return 'jpeg'
        else:
            return 'unknown'
    
    @staticmethod
    def _has_transparency(image: Image.Image) -> bool:
        """Verifica se a imagem PNG tem transparência útil"""
        if image.mode != 'RGBA':
            return False
        
        # Converter para array numpy
        img_array = np.array(image)
        alpha_channel = img_array[:, :, 3]  # Canal alpha
        
        # Verificar se há pixels transparentes (alpha < 255)
        transparent_pixels = np.sum(alpha_channel < 255)
        total_pixels = alpha_channel.size
        
        transparency_ratio = transparent_pixels / total_pixels
        logger.info(f"📊 Transparência: {transparency_ratio:.2%} dos pixels")
        
        # Considerar útil se mais de 10% dos pixels são transparentes
        return transparency_ratio > 0.1
    
    @staticmethod
    def _convert_to_transparent_png(base64_data: str, image_type: str) -> str:
        """
        Converte imagem para PNG com transparência removendo fundo branco
        """
        logger.info(f"🔄 Convertendo {image_type} para PNG transparente...")
        
        try:
            # Decodificar base64
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            logger.info(f"📷 Imagem original: {image.size}, modo: {image.mode}")
            
            # Converter para RGBA se necessário
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # Converter para array numpy para processamento
            img_array = np.array(image)
            
            # Método 1: Remover fundo branco/claro
            # Definir threshold para pixels "brancos" (RGB > 240)
            white_threshold = 240
            
            # Identificar pixels brancos/claros
            white_mask = (
                (img_array[:, :, 0] > white_threshold) &  # R > 240
                (img_array[:, :, 1] > white_threshold) &  # G > 240  
                (img_array[:, :, 2] > white_threshold)    # B > 240
            )
            
            # Tornar pixels brancos transparentes
            img_array[white_mask, 3] = 0  # Alpha = 0 (transparente)
            
            # Método 2: Melhorar contraste dos pixels escuros (assinatura)
            # Identificar pixels não-brancos
            non_white_mask = ~white_mask
            
            # Para pixels escuros, aumentar contraste (tornar mais preto)
            dark_pixels = img_array[non_white_mask]
            if len(dark_pixels) > 0:
                # Aplicar threshold para tornar mais preto
                for i in range(3):  # RGB channels
                    dark_pixels[:, i] = np.where(
                        dark_pixels[:, i] < 128,  # Se for escuro
                        np.maximum(dark_pixels[:, i] - 50, 0),  # Tornar mais escuro
                        dark_pixels[:, i]  # Manter como está
                    )
                
                img_array[non_white_mask] = dark_pixels
            
            # Método 3: Aplicar anti-aliasing suave nas bordas
            # Detectar bordas entre transparente e opaco
            from scipy.ndimage import binary_erosion, binary_dilation
            
            opaque_mask = img_array[:, :, 3] > 0
            eroded = binary_erosion(opaque_mask)
            edge_mask = opaque_mask & ~eroded
            
            # Suavizar bordas
            img_array[edge_mask, 3] = np.clip(img_array[edge_mask, 3] * 0.8, 0, 255)
            
            # Converter de volta para PIL Image
            processed_image = Image.fromarray(img_array.astype(np.uint8), 'RGBA')
            
            # Salvar como PNG
            output_buffer = io.BytesIO()
            processed_image.save(output_buffer, format='PNG', optimize=True)
            output_buffer.seek(0)
            
            # Converter para base64
            processed_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
            
            # Log estatísticas
            original_size = len(base64_data)
            processed_size = len(processed_base64)
            compression_ratio = processed_size / original_size
            
            logger.info(f"📊 Conversão concluída:")
            logger.info(f"   📏 Tamanho original: {original_size} chars")
            logger.info(f"   📏 Tamanho processado: {processed_size} chars")
            logger.info(f"   📈 Ratio: {compression_ratio:.2f}")
            logger.info(f"   🖼️ Dimensões: {processed_image.size}")
            
            return processed_base64
            
        except Exception as e:
            logger.error(f"❌ Erro na conversão: {str(e)}")
            raise
    
    @staticmethod
    def validate_signature_quality(signature_data_url: str) -> dict:
        """
        Valida a qualidade da assinatura processada
        """
        logger.info("🔍 Validando qualidade da assinatura...")
        
        try:
            # Extrair dados
            header, base64_data = signature_data_url.split(',', 1)
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            img_array = np.array(image)
            
            # Métricas de qualidade
            total_pixels = img_array.shape[0] * img_array.shape[1]
            opaque_pixels = np.sum(img_array[:, :, 3] > 0)
            transparent_pixels = total_pixels - opaque_pixels
            
            # Calcular densidade da assinatura
            signature_density = opaque_pixels / total_pixels
            
            # Verificar se há conteúdo suficiente
            min_density = 0.01  # Pelo menos 1% de pixels visíveis
            has_content = signature_density > min_density
            
            # Verificar dimensões
            width, height = image.size
            good_dimensions = width >= 100 and height >= 50
            
            # Resultado da validação
            quality = {
                'is_valid': has_content and good_dimensions,
                'signature_density': signature_density,
                'opaque_pixels': int(opaque_pixels),
                'transparent_pixels': int(transparent_pixels), 
                'dimensions': {'width': width, 'height': height},
                'file_size_kb': len(base64_data) * 3 / 4 / 1024,
                'warnings': []
            }
            
            # Adicionar warnings se necessário
            if not has_content:
                quality['warnings'].append('Assinatura pode estar vazia ou muito clara')
            if not good_dimensions:
                quality['warnings'].append('Dimensões muito pequenas')
            if signature_density > 0.5:
                quality['warnings'].append('Assinatura muito densa - pode ter problemas de fundo')
            
            logger.info(f"✅ Validação concluída: válida={quality['is_valid']}, densidade={signature_density:.2%}")
            
            return quality
            
        except Exception as e:
            logger.error(f"❌ Erro na validação: {str(e)}")
            return {
                'is_valid': False,
                'error': str(e),
                'warnings': ['Erro ao validar assinatura']
            }