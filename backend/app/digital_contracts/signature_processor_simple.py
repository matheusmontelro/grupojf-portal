import base64
import logging

logger = logging.getLogger("signature_processor")

class SignatureProcessor:
    """
    Processador simplificado de assinaturas
    """
    
    @staticmethod
    def process_signature(signature_data_url: str) -> str:
        """
        Processa assinatura de forma básica (sem processamento de imagem)
        
        Args:
            signature_data_url: Data URL da assinatura
            
        Returns:
            Data URL da assinatura (sem processamento)
        """
        logger.info("🎨 Processamento simplificado da assinatura...")
        
        try:
            # Validar formato
            if not signature_data_url or not signature_data_url.startswith('data:image/'):
                logger.error("❌ Formato de assinatura inválido")
                raise ValueError("Formato de assinatura inválido")
            
            # Extrair informações básicas
            header, base64_data = signature_data_url.split(',', 1)
            logger.info(f"📋 Header: {header}")
            logger.info(f"📊 Tamanho: {len(base64_data)} chars")
            
            # Retornar a assinatura original sem processamento
            logger.info("✅ Usando assinatura original (processamento simplificado)")
            return signature_data_url
            
        except Exception as e:
            logger.error(f"❌ Erro no processamento da assinatura: {str(e)}")
            raise
    
    @staticmethod
    def _get_image_type(header: str) -> str:
        """
        Extrai tipo de imagem do header
        """
        if 'image/png' in header:
            return 'png'
        elif 'image/jpeg' in header or 'image/jpg' in header:
            return 'jpeg'
        else:
            return 'unknown'
    
    @staticmethod
    def _has_transparency(image) -> bool:
        """
        Verifica se a imagem tem transparência (simplificado)
        """
        # Sem PIL, sempre retorna False
        return False