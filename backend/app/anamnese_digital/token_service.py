# app/anamnese_digital/token_service.py

import secrets
import string
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class TokenService:
    """Serviço para geração e validação de tokens seguros"""
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Gera um token seguro e único"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def generate_link(token: str, base_url: str = None) -> str:
        """Gera o link público para a anamnese"""
        if not base_url:
            base_url = os.getenv("PUBLIC_BASE_URL", "https://api.exemplo.com")
        
        return f"{base_url}/anamnese/{token}"
    
    @staticmethod
    def calculate_expiration(hours: int = 72) -> datetime:
        """Calcula a data de expiração do token"""
        return datetime.now() + timedelta(hours=hours)
    
    @staticmethod
    def is_token_valid(expires_at: datetime, used: bool = False) -> Tuple[bool, Optional[str]]:
        """Verifica se o token ainda é válido"""
        if used:
            return False, "Token já foi utilizado"
        
        if datetime.now() > expires_at:
            return False, "Token expirado"
        
        return True, None
    
    @staticmethod
    def format_whatsapp_message(nome_paciente: str, link: str, clinica: str = "GrupoJF", 
                               nome_dependente: str = None, parentesco: str = None) -> str:
        """Formata mensagem para WhatsApp"""
        if nome_dependente:
            return f"""Olá {nome_paciente}! 👋

Solicitamos o preenchimento da ficha de anamnese digital do(a) seu(sua) {parentesco or 'dependente'} *{nome_dependente}*.

📋 *O que é?*
A anamnese é um questionário sobre a saúde do(a) {nome_dependente} que nos ajuda a oferecer um atendimento mais seguro e personalizado.

🔗 *Acesse o link abaixo para preencher:*
{link}

⏰ *Importante:* Este link é válido por 72 horas.

✅ Após o preenchimento, você poderá prosseguir com o atendimento do(a) {nome_dependente}.

Assim que finalizar, de um 'ok' aqui em baixo."""
        else:
            return f"""Olá {nome_paciente}! 👋

Solicitamos o preenchimento da sua ficha de anamnese digital.

📋 *O que é?*
A anamnese é um questionário sobre sua saúde que nos ajuda a oferecer um atendimento mais seguro e personalizado.

🔗 *Acesse o link abaixo para preencher:*
{link}

⏰ *Importante:* Este link é válido por 72 horas.

✅ Após o preenchimento, você poderá prosseguir com seu atendimento.

Assim que finalizar, de um 'ok' aqui em baixo."""

    # Métodos de SMS e Email removidos - apenas WhatsApp é suportado
