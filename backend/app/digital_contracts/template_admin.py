# backend/app/digital_contracts/template_admin.py
"""
Sistema de administração de templates - Interface simples para criar/editar templates
"""
import json
import logging
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .template_registry import template_registry
from ..database.db import DatabaseConnection

logger = logging.getLogger(__name__)

# ==========================================
# MODELOS PYDANTIC
# ==========================================

class TemplateCreateRequest(BaseModel):
    name: str
    tipo_odontograma_nome: str
    template_html: str
    template_config: Optional[Dict] = None
    description: Optional[str] = ""

class TemplateResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    tipo_odontograma: str
    is_active: bool
    is_default: bool
    version: int
    created_at: str

class TemplateDetailResponse(TemplateResponse):
    template_html: str
    template_config: Dict

# ==========================================
# ROUTER PARA ADMINISTRAÇÃO
# ==========================================

admin_router = APIRouter(prefix="/admin/templates", tags=["admin-templates"])

@admin_router.get("/", response_model=List[TemplateResponse])
def list_templates():
    """Lista todos os templates disponíveis"""
    templates = template_registry.list_templates()
    return [TemplateResponse(**template) for template in templates]

@admin_router.post("/", response_model=Dict)
def create_template(request: TemplateCreateRequest):
    """Cria um novo template"""
    success = template_registry.register_template(
        template_name=request.name,
        tipo_odontograma_nome=request.tipo_odontograma_nome,
        template_html=request.template_html,
        template_config=request.template_config or {},
        description=request.description
    )
    
    if success:
        return {"success": True, "message": "Template criado com sucesso"}
    else:
        raise HTTPException(400, "Erro ao criar template")

@admin_router.get("/tipos")
def list_tipos_odontograma():
    """Lista todos os tipos de odontograma disponíveis"""
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome FROM tipos_odontograma ORDER BY nome")
            results = cursor.fetchall()
            
            return [{"id": row[0], "nome": row[1]} for row in results]
    except Exception as e:
        logger.error(f"Erro ao listar tipos: {e}")
        raise HTTPException(500, "Erro ao buscar tipos de odontograma")

# ==========================================
# HELPER PARA CRIAR TEMPLATES FACILMENTE
# ==========================================

class TemplateBuilder:
    """
    Builder pattern para criar templates facilmente
    """
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self._template_data = {
            'name': '',
            'tipo': '',
            'html': '',
            'config': {},
            'description': ''
        }
        return self
    
    def set_name(self, name: str):
        self._template_data['name'] = name
        return self
    
    def set_tipo(self, tipo_nome: str):
        self._template_data['tipo'] = tipo_nome
        return self
    
    def set_html(self, html: str):
        self._template_data['html'] = html
        return self
    
    def set_config(self, **config):
        self._template_data['config'].update(config)
        return self
    
    def set_description(self, description: str):
        self._template_data['description'] = description
        return self
    
    def with_theme(self, primary_color: str, secondary_color: str, theme_name: str = "custom"):
        self._template_data['config'].update({
            'theme': theme_name,
            'color_primary': primary_color,
            'color_secondary': secondary_color
        })
        return self
    
    def with_signature_required(self, required: bool = True):
        self._template_data['config']['require_signature'] = required
        return self
    
    def build(self) -> bool:
        """Constrói e registra o template"""
        if not all([self._template_data['name'], self._template_data['tipo'], self._template_data['html']]):
            raise ValueError("Nome, tipo e HTML são obrigatórios")
        
        return template_registry.register_template(
            self._template_data['name'],
            self._template_data['tipo'],
            self._template_data['html'],
            self._template_data['config'],
            self._template_data['description']
        )

# ==========================================
# EXEMPLOS DE USO DO TEMPLATE BUILDER
# ==========================================

def create_example_templates():
    """
    Exemplos de como criar templates usando o Builder
    """
    builder = TemplateBuilder()
    
    # Template para Clínica Geral
    html_clinica_geral = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Contrato de Clínica Geral</title>
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
                margin: 0; padding: 20px;
            }}
            .container {{
                max-width: 210mm; margin: 0 auto; background: white;
                padding: 30px; border-radius: 15px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            }}
            .header {{
                background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
                color: white; padding: 25px; margin: -30px -30px 25px -30px;
                border-radius: 15px 15px 0 0; text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🦷 CONTRATO DE CLÍNICA GERAL 🦷</h1>
                <p>Cuidado Completo para sua Saúde Bucal</p>
            </div>
            
            <h3>Dados do Paciente</h3>
            <p><strong>Nome:</strong> {paciente_nome}</p>
            <p><strong>CPF:</strong> {paciente_cpf}</p>
            
            <h3>Detalhes Financeiros</h3>
            <p><strong>Valor Total:</strong> R$ {valor_total:,.2f}</p>
            <p><strong>Parcelas:</strong> {qtd_parcelas}x de R$ {valor_parcela:,.2f}</p>
            
            <div style="margin-top: 50px; text-align: center;">
                {signature_html}
                <p><strong>{paciente_nome}</strong><br>{data_contrato}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Criar template de Clínica Geral
    success1 = (builder
                .reset()
                .set_name("Contrato Clínica Geral")
                .set_tipo("Clínica Geral")
                .set_html(html_clinica_geral)
                .with_theme("#74b9ff", "#0984e3", "clinical")
                .set_description("Template para contratos de clínica geral")
                .build())
    
    # Template para Implante
    html_implante = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Contrato de Implante Dentário</title>
        <style>
            body {{ 
                font-family: 'Georgia', serif;
                background: linear-gradient(135deg, #fd79a8 0%, #fdcb6e 100%);
                margin: 0; padding: 20px;
            }}
            .container {{
                max-width: 210mm; margin: 0 auto; background: white;
                padding: 30px; border-radius: 15px;
                box-shadow: 0 15px 35px rgba(0,0,0,0.2);
            }}
            .premium-header {{
                background: linear-gradient(135deg, #fd79a8 0%, #fdcb6e 100%);
                color: white; padding: 30px; margin: -30px -30px 30px -30px;
                border-radius: 15px 15px 0 0; text-align: center;
            }}
            .warranty-badge {{
                background: rgba(255,255,255,0.2);
                padding: 10px 20px; border-radius: 25px;
                display: inline-block; margin-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="premium-header">
                <h1>👑 CONTRATO DE IMPLANTE PREMIUM 👑</h1>
                <p>Qualidade e Garantia Estendida</p>
                <div class="warranty-badge">✓ Garantia de 10 Anos</div>
            </div>
            
            <h3>Informações do Tratamento</h3>
            <p><strong>Paciente:</strong> {paciente_nome}</p>
            <p><strong>Tipo de Implante:</strong> Titânio Grau 5</p>
            <p><strong>Investimento:</strong> R$ {valor_total:,.2f}</p>
            
            <div style="margin-top: 50px; text-align: center;">
                {signature_html}
                <p><strong>{paciente_nome}</strong><br>{data_contrato}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Criar template de Implante
    success2 = (builder
                .reset()
                .set_name("Contrato Implante Premium")
                .set_tipo("Implante")
                .set_html(html_implante)
                .with_theme("#fd79a8", "#fdcb6e", "premium")
                .set_config(warranty_years=10, premium_service=True)
                .set_description("Template premium para contratos de implante")
                .build())
    
    logger.info(f"Templates de exemplo criados: Clínica Geral={success1}, Implante={success2}")
    return success1 and success2

# ==========================================
# MODIFICAÇÃO NO SERVICE PRINCIPAL
# ==========================================

# Em backend/app/digital_contracts/service.py - adicionar este método:

def update_service_to_use_registry():
    """
    Código para adicionar ao DigitalContractService
    """
    service_update_code = '''
    # Adicionar no início do arquivo service.py
    from .template_registry import template_registry
    
    # Modificar o método _render_contract_html
    def _render_contract_html(self, dados: dict, odontograma_id: int = None) -> str:
        """Renderiza HTML do contrato usando o novo sistema de templates"""
        logger.info(f"🎨 Renderizando HTML do contrato para: {dados.get('paciente_nome', 'N/A')}")
        
        try:
            if odontograma_id:
                # Buscar tipo do odontograma
                tipo_nome = self._get_tipo_nome_by_odontograma(odontograma_id)
                
                if tipo_nome:
                    # Tentar usar template específico do registry
                    template_html, template_config = template_registry.get_template_for_tipo(tipo_nome)
                    
                    if template_html:
                        logger.info(f"✅ Usando template específico para tipo '{tipo_nome}'")
                        return self._render_with_template(template_html, dados, template_config)
            
            # Fallback para template padrão
            logger.info("🔄 Usando template padrão")
            from .templates import render_contract
            return render_contract(dados)
            
        except Exception as e:
            logger.error(f"❌ Erro em _render_contract_html: {str(e)}", exc_info=True)
            # Fallback final
            from .templates import render_contract
            return render_contract(dados)
    
    def _get_tipo_nome_by_odontograma(self, odontograma_id: int) -> str | None:
        """Busca o nome do tipo de odontograma"""
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT tod.nome 
                    FROM odontogramas o
                    JOIN tipos_odontograma tod ON o.tipo_id = tod.id
                    WHERE o.id = %s
                """, (odontograma_id,))
                
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Erro ao buscar tipo do odontograma: {e}")
            return None
    
    def _render_with_template(self, template_html: str, dados: dict, config: dict = None) -> str:
        """Renderiza template com dados"""
        # Preparar dados com valores padrão
        defaults = self._get_default_values(dados)
        
        # Aplicar configurações se existirem
        if config:
            if not config.get('show_dependents', True):
                defaults['dependentes_rows'] = ''
                defaults['dependentes_mobile'] = ''
        
        try:
            return template_html.format(**defaults)
        except KeyError as e:
            logger.error(f"Variável não encontrada no template: {e}")
            # Adicionar variáveis faltantes
            import re
            missing_vars = re.findall(r'\\{(\\w+)\\}', template_html)
            for var in missing_vars:
                if var not in defaults:
                    defaults[var] = ''
            return template_html.format(**defaults)
    '''
    
    return service_update_code

# ==========================================
# SCRIPT DE MIGRAÇÃO/SETUP
# ==========================================

def setup_complete_template_system():
    """
    Setup completo do sistema de templates
    """
    from .template_registry import init_contract_templates
    
    logger.info("🚀 Configurando sistema completo de templates...")
    
    # 1. Configurar templates padrão
    init_contract_templates()
    
    # 2. Criar templates de exemplo
    create_example_templates()
    
    # 3. Listar todos os templates
    templates = template_registry.list_templates()
    logger.info(f"📋 Sistema configurado com {len(templates)} templates:")
    
    for template in templates:
        logger.info(f"  ✅ {template['name']} → {template['tipo_odontograma']}")
    
    logger.info("🎉 Sistema de templates configurado com sucesso!")
    
    return len(templates) > 0

if __name__ == "__main__":
    setup_complete_template_system()