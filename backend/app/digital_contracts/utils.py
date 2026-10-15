# backend/app/digital_contracts/utils.py
import hashlib
import uuid
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any
import re

def generate_access_token() -> str:
    """
    Gera token único e seguro para acesso ao contrato
    """
    # Combina UUID + timestamp + random para garantir unicidade
    base_string = f"{uuid.uuid4()}{datetime.now().isoformat()}{secrets.token_hex(16)}"
    return hashlib.sha256(base_string.encode()).hexdigest()[:32]

def generate_contract_uuid() -> str:
    """
    Gera UUID para o contrato
    """
    return str(uuid.uuid4())

def validate_base64_image(base64_string: str, max_size_mb: int = 5) -> bool:
    """
    Valida se string base64 é uma imagem válida
    """
    if not base64_string:
        return False
    
    # Verificar formato base64 de imagem
    if not base64_string.startswith('data:image/'):
        return False
    
    # Verificar tamanho (aproximado)
    # Base64 aumenta ~33% o tamanho original
    estimated_size_mb = len(base64_string) * 0.75 / (1024 * 1024)
    if estimated_size_mb > max_size_mb:
        return False
    
    return True

def clean_and_validate_cpf(cpf: str) -> str:
    """
    Limpa e valida CPF
    """
    if not cpf:
        return ""
    
    # Remove pontos, traços e espaços
    clean_cpf = re.sub(r'[^0-9]', '', cpf)
    
    # Validar tamanho
    if len(clean_cpf) != 11:
        raise ValueError("CPF deve ter 11 dígitos")
    
    # Validação básica (evitar sequências como 111.111.111-11)
    if len(set(clean_cpf)) == 1:
        raise ValueError("CPF inválido")
    
    return clean_cpf

def get_contract_expiry() -> datetime:
    """
    Retorna data de expiração padrão do contrato (72 horas)
    """
    return datetime.now() + timedelta(hours=72)

def extract_device_info(request_headers: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai informações do dispositivo dos headers da requisição
    """
    user_agent = request_headers.get('user-agent', '')
    
    # Detectar tipo de dispositivo
    device_type = 'desktop'
    if 'Mobile' in user_agent or 'Android' in user_agent:
        device_type = 'mobile'
    elif 'Tablet' in user_agent or 'iPad' in user_agent:
        device_type = 'tablet'
    
    # Detectar OS
    os_name = 'unknown'
    if 'Windows' in user_agent:
        os_name = 'windows'
    elif 'Mac OS' in user_agent or 'macOS' in user_agent:
        os_name = 'macos'
    elif 'Android' in user_agent:
        os_name = 'android'
    elif 'iPhone' in user_agent or 'iOS' in user_agent:
        os_name = 'ios'
    elif 'Linux' in user_agent:
        os_name = 'linux'
    
    # Detectar browser
    browser = 'unknown'
    if 'Chrome' in user_agent:
        browser = 'chrome'
    elif 'Firefox' in user_agent:
        browser = 'firefox'
    elif 'Safari' in user_agent and 'Chrome' not in user_agent:
        browser = 'safari'
    elif 'Edge' in user_agent:
        browser = 'edge'
    
    return {
        'user_agent': user_agent,
        'device_type': device_type,
        'os': os_name,
        'browser': browser,
        'timestamp': datetime.now().isoformat()
    }

def validate_token_format(token: str) -> bool:
    """
    Valida formato do token de acesso
    """
    if not token:
        return False
    
    # Token deve ter 32 caracteres hexadecimais
    if len(token) != 32:
        return False
    
    # Verificar se contém apenas caracteres válidos
    if not re.match(r'^[a-f0-9]{32}$', token):
        return False
    
    return True

def format_currency(value: float) -> str:
    """
    Formata valor monetário para exibição
    """
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def log_contract_action(contract_id: int, action: str, details: str = "", ip: str = "") -> Dict[str, Any]:
    """
    Prepara dados para log de ação no contrato
    """
    return {
        'contract_id': contract_id,
        'action': action,
        'details': details,
        'ip': ip,
        'timestamp': datetime.now().isoformat()
    }

def is_token_expired(expires_at: datetime) -> bool:
    """
    Verifica se token está expirado
    """
    return datetime.now() > expires_at

def mask_sensitive_data(data: str, show_chars: int = 4) -> str:
    """
    Mascara dados sensíveis para logs
    """
    if not data or len(data) <= show_chars:
        return "*" * len(data) if data else ""
    
    return data[:show_chars] + "*" * (len(data) - show_chars)

# Constantes
CONTRACT_STATUS_CHOICES = [
    'draft',        # Criado, não enviado
    'sent',         # Enviado para cliente
    'opened',       # Cliente visualizou
    'selfie_taken', # Selfie capturada
    'signed',       # Assinado
    'completed',    # Finalizado
    'expired',      # Expirado
    'cancelled'     # Cancelado
]

DEFAULT_TOKEN_EXPIRY_HOURS = 72
MAX_SELFIE_SIZE_MB = 5
MAX_SIGNATURE_SIZE_MB = 2