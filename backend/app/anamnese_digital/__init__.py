# app/anamnese_digital/__init__.py
"""
Sistema de Anamnese Digital
Gerenciamento de fichas de anamnese com assinatura digital
"""

from .models import *
from .router import router as anamnese_router
from .public_router import router as anamnese_public_router