# backend/app/digital_contracts/template_registry.py
"""
Sistema simples para gerenciar templates de contratos por tipo de odontograma
"""
import json
import logging
from typing import Dict, Optional, Tuple
from ..database.db import DatabaseConnection

logger = logging.getLogger(__name__)

class ContractTemplateRegistry:
    """
    Registry simples para gerenciar templates de contratos
    """
    
    def __init__(self):
        self._templates_cache = {}
    
    def register_template(self, 
                         template_name: str,
                         tipo_odontograma_nome: str,
                         template_html: str,
                         template_config: dict = None,
                         description: str = "") -> bool:
        """
        Registra um novo template no banco de dados
        
        Args:
            template_name: Nome do template
            tipo_odontograma_nome: Nome do tipo de odontograma (ex: "Contrato Odontológico + Akimais")
            template_html: HTML do template
            template_config: Configurações do template
            description: Descrição do template
        """
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Buscar o ID do tipo de odontograma
                cursor.execute("""
                    SELECT id FROM tipos_odontograma 
                    WHERE LOWER(nome) = LOWER(%s)
                """, (tipo_odontograma_nome,))
                
                tipo_result = cursor.fetchone()
                if not tipo_result:
                    logger.error(f"Tipo de odontograma '{tipo_odontograma_nome}' não encontrado")
                    return False
                
                tipo_id = tipo_result[0]
                
                # Criar slug do template
                slug = template_name.lower().replace(' ', '-').replace('ç', 'c').replace('ã', 'a')
                
                # Inserir ou atualizar template
                cursor.execute("""
                    INSERT INTO contract_templates (
                        name, slug, description, tipo_odontograma_id,
                        template_html, template_config, is_active, is_default,
                        created_by, version
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (slug) DO UPDATE SET
                        template_html = EXCLUDED.template_html,
                        template_config = EXCLUDED.template_config,
                        description = EXCLUDED.description,
                        version = contract_templates.version + 1,
                        updated_at = NOW(),
                        updated_by = 'system'
                """, (
                    template_name,
                    slug,
                    description,
                    tipo_id,
                    template_html,
                    json.dumps(template_config or {}),
                    True,  # is_active
                    False, # is_default (será definido manualmente se necessário)
                    'system',
                    1
                ))
                
                conn.commit()
                logger.info(f"Template '{template_name}' registrado com sucesso para tipo '{tipo_odontograma_nome}'")
                
                # Limpar cache
                self._templates_cache.clear()
                return True
                
        except Exception as e:
            logger.error(f"Erro ao registrar template: {e}")
            return False
    
    def get_template_for_tipo(self, tipo_odontograma_nome: str) -> Tuple[Optional[str], Optional[dict]]:
        """
        Busca o template apropriado para um tipo de odontograma
        
        Returns:
            Tuple[template_html, template_config] ou (None, None) se não encontrado
        """
        cache_key = tipo_odontograma_nome.lower()
        
        # Verificar cache primeiro
        if cache_key in self._templates_cache:
            return self._templates_cache[cache_key]
        
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                # Buscar template específico para o tipo
                cursor.execute("""
                    SELECT ct.template_html, ct.template_config
                    FROM contract_templates ct
                    JOIN tipos_odontograma tod ON ct.tipo_odontograma_id = tod.id
                    WHERE LOWER(tod.nome) = LOWER(%s) 
                    AND ct.is_active = true
                    ORDER BY ct.version DESC
                    LIMIT 1
                """, (tipo_odontograma_nome,))
                
                result = cursor.fetchone()
                if result:
                    template_html, template_config = result
                    config = json.loads(template_config) if template_config else {}
                    
                    # Armazenar no cache
                    self._templates_cache[cache_key] = (template_html, config)
                    
                    logger.info(f"Template encontrado para tipo '{tipo_odontograma_nome}'")
                    return template_html, config
                
                # Se não encontrou, buscar template padrão
                cursor.execute("""
                    SELECT template_html, template_config
                    FROM contract_templates
                    WHERE is_default = true AND is_active = true
                    ORDER BY version DESC
                    LIMIT 1
                """)
                
                default_result = cursor.fetchone()
                if default_result:
                    template_html, template_config = default_result
                    config = json.loads(template_config) if template_config else {}
                    
                    logger.info(f"Usando template padrão para tipo '{tipo_odontograma_nome}'")
                    return template_html, config
                
                logger.warning(f"Nenhum template encontrado para tipo '{tipo_odontograma_nome}'")
                return None, None
                
        except Exception as e:
            logger.error(f"Erro ao buscar template: {e}")
            return None, None
    
    def list_templates(self) -> list:
        """Lista todos os templates disponíveis"""
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT ct.name, ct.slug, ct.description, tod.nome as tipo_nome,
                           ct.is_active, ct.is_default, ct.version, ct.created_at
                    FROM contract_templates ct
                    LEFT JOIN tipos_odontograma tod ON ct.tipo_odontograma_id = tod.id
                    ORDER BY ct.created_at DESC
                """)
                
                results = cursor.fetchall()
                templates = []
                
                for row in results:
                    templates.append({
                        'name': row[0],
                        'slug': row[1],
                        'description': row[2],
                        'tipo_odontograma': row[3],
                        'is_active': row[4],
                        'is_default': row[5],
                        'version': row[6],
                        'created_at': row[7]
                    })
                
                return templates
                
        except Exception as e:
            logger.error(f"Erro ao listar templates: {e}")
            return []

# Instância global do registry
template_registry = ContractTemplateRegistry()

# ==========================================
# TEMPLATES ESPECÍFICOS POR TIPO
# ==========================================

# Template para Contrato Odontológico + Akimais (já existente, melhorado)
TEMPLATE_AKIMAIS = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contrato Odontológico Digital + Akimais</title>
    <style>
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0;
            padding: 20px;
            line-height: 1.6;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
        }}
        
        .container {{
            max-width: 210mm;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        
        .akimais-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            margin: -30px -30px 30px -30px;
            border-radius: 15px 15px 0 0;
            text-align: center;
        }}
        
        .akimais-logo {{
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .digital-badge {{
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 25px;
            font-size: 14px;
            display: inline-block;
            margin-top: 10px;
        }}
        
        .info-section {{
            background: #f8f9fa;
            padding: 20px;
            margin: 20px 0;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }}
        
        .signature-area {{
            margin-top: 50px;
            text-align: center;
        }}
        
        .signature-image {{
            max-width: 300px;
            max-height: 100px;
            border: 2px solid #667eea;
            border-radius: 8px;
            margin: 20px auto;
            display: block;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="akimais-header">
            <div class="akimais-logo">CONTRATO DIGITAL AKIMAIS</div>
            <p>Plataforma de Odontologia Digital</p>
            <div class="digital-badge">✓ Assinatura Digital Certificada</div>
        </div>
        
        <div class="info-section">
            <h3>Dados do Contratante</h3>
            <p><strong>Nome:</strong> {paciente_nome}</p>
            <p><strong>CPF:</strong> {paciente_cpf}</p>
            <p><strong>E-mail:</strong> {paciente_email}</p>
            <p><strong>Telefone:</strong> {paciente_telefone1}</p>
        </div>
        
        <div class="info-section">
            <h3>Detalhes do Contrato</h3>
            <p><strong>Valor Total:</strong> R$ {valor_total:,.2f}</p>
            <p><strong>Parcelas:</strong> {qtd_parcelas}x de R$ {valor_parcela:,.2f}</p>
            <p><strong>Vencimento:</strong> Todo dia {dia_vencimento}</p>
            <p><strong>Vendedor:</strong> {vendedor_nome}</p>
        </div>
        
        <!-- Conteúdo do contrato aqui -->
        <p>Este contrato foi assinado digitalmente através da plataforma Akimais...</p>
        
        <div class="signature-area">
            <p><strong>Assinatura Digital do Cliente:</strong></p>
            {signature_html}
            <p><strong>{paciente_nome}</strong><br>
            Assinado digitalmente em {data_contrato}</p>
        </div>
    </div>
</body>
</html>
"""

# Template para Contrato Ortodôntico
TEMPLATE_ORTODONTICO = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Contrato de Tratamento Ortodôntico</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0; padding: 20px;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }}
        
        .container {{
            max-width: 210mm; margin: 0 auto;
            background: white; padding: 30px;
            border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }}
        
        .ortho-header {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white; padding: 25px; margin: -30px -30px 25px -30px;
            border-radius: 15px 15px 0 0; text-align: center;
        }}
        
        .ortho-icon {{ font-size: 48px; margin-bottom: 10px; }}
        .treatment-info {{
            background: #e3f2fd; padding: 20px; margin: 20px 0;
            border-radius: 10px; border-left: 4px solid #2196f3;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="ortho-header">
            <div class="ortho-icon">🦷✨</div>
            <h1>CONTRATO DE TRATAMENTO ORTODÔNTICO</h1>
            <p>Especializados em Sorrisos Perfeitos</p>
        </div>
        
        <div class="treatment-info">
            <h3>Informações do Tratamento</h3>
            <p><strong>Paciente:</strong> {paciente_nome}</p>
            <p><strong>Duração Estimada:</strong> 18 a 24 meses</p>
            <p><strong>Valor Total:</strong> R$ {valor_total:,.2f}</p>
            <p><strong>Forma de Pagamento:</strong> {qtd_parcelas}x de R$ {valor_parcela:,.2f}</p>
        </div>
        
        <p>O presente contrato tem por objeto o tratamento ortodôntico completo...</p>
        
        <div style="margin-top: 50px; text-align: center;">
            {signature_html}
            <p><strong>{paciente_nome}</strong><br>{data_contrato}</p>
        </div>
    </div>
</body>
</html>
"""

# Template para Combo Orto + ODC
TEMPLATE_COMBO = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Combo Ortodontia + Odontologia Clínica</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; margin: 0; padding: 20px;
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        }}
        
        .container {{
            max-width: 210mm; margin: 0 auto; background: white;
            padding: 30px; border-radius: 15px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }}
        
        .combo-header {{
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
            color: white; padding: 25px; margin: -30px -30px 25px -30px;
            border-radius: 15px 15px 0 0; text-align: center;
        }}
        
        .combo-benefits {{
            display: grid; grid-template-columns: 1fr 1fr;
            gap: 20px; margin: 25px 0;
        }}
        
        .benefit-card {{
            background: #fff3e0; padding: 20px; border-radius: 10px;
            border-left: 4px solid #ff9800;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="combo-header">
            <h1>🦷 COMBO COMPLETO 🦷</h1>
            <h2>Ortodontia + Odontologia Clínica</h2>
            <p>Solução Completa para seu Sorriso</p>
        </div>
        
        <div class="combo-benefits">
            <div class="benefit-card">
                <h4>🔧 Ortodontia Inclusa</h4>
                <ul>
                    <li>Aparelho ortodôntico</li>
                    <li>Manutenções mensais</li>
                    <li>Contenção</li>
                </ul>
            </div>
            <div class="benefit-card">
                <h4>🔬 Clínica Geral</h4>
                <ul>
                    <li>Limpezas e profilaxias</li>
                    <li>Restaurações</li>
                    <li>Tratamentos de canal</li>
                </ul>
            </div>
        </div>
        
        <p><strong>Paciente:</strong> {paciente_nome}</p>
        <p><strong>Investimento:</strong> R$ {valor_total:,.2f} em {qtd_parcelas}x</p>
        
        <div style="margin-top: 50px; text-align: center;">
            {signature_html}
            <p><strong>{paciente_nome}</strong><br>{data_contrato}</p>
        </div>
    </div>
</body>
</html>
"""

def setup_default_templates():
    """
    Configura os templates padrão no banco de dados
    """
    templates = [
        {
            'name': 'Contrato Digital Akimais',
            'tipo': 'Contrato Odontológico + Akimais',
            'html': TEMPLATE_AKIMAIS,
            'config': {
                'theme': 'digital',
                'color_primary': '#667eea',
                'color_secondary': '#764ba2',
                'show_digital_badge': True,
                'require_signature': True
            },
            'description': 'Template moderno para contratos digitais com Akimais'
        },
        {
            'name': 'Contrato Ortodôntico Especializado',
            'tipo': 'Contrato Ortodôntico',
            'html': TEMPLATE_ORTODONTICO,
            'config': {
                'theme': 'orthodontic',
                'color_primary': '#4facfe',
                'color_secondary': '#00f2fe',
                'show_treatment_duration': True,
                'orthodontic_specific': True
            },
            'description': 'Template específico para tratamentos ortodônticos'
        },
        {
            'name': 'Combo Ortodontia + Clínica',
            'tipo': 'Combo Orto + ODC',
            'html': TEMPLATE_COMBO,
            'config': {
                'theme': 'combo',
                'color_primary': '#fa709a',
                'color_secondary': '#fee140',
                'show_benefits_grid': True,
                'combo_specific': True
            },
            'description': 'Template para combo de ortodontia e clínica geral'
        }
    ]
    
    success_count = 0
    for template in templates:
        if template_registry.register_template(
            template['name'],
            template['tipo'], 
            template['html'],
            template['config'],
            template['description']
        ):
            success_count += 1
    
    logger.info(f"Templates configurados: {success_count}/{len(templates)}")
    return success_count == len(templates)

# ==========================================
# MODIFICAÇÃO NO TEMPLATE MANAGER
# ==========================================

# backend/app/digital_contracts/template_manager.py (modificação)
"""
Modificar a classe TemplateManager para usar o registry
"""

class TemplateManager:
    def __init__(self):
        from .templates import CONTRACT_TEMPLATE
        self.default_template = CONTRACT_TEMPLATE
        self.registry = template_registry
    
    def render_contract_with_template(self, odontograma_id: int, dados: dict) -> str:
        """
        Renderiza o contrato usando o template apropriado
        """
        # Primeiro, tentar buscar pelo tipo de odontograma
        tipo_nome = self._get_tipo_nome_by_odontograma(odontograma_id)
        
        if tipo_nome:
            template_html, template_config = self.registry.get_template_for_tipo(tipo_nome)
            
            if template_html:
                logger.info(f"Usando template específico para tipo '{tipo_nome}'")
                return self._render_template(template_html, dados, template_config)
        
        # Fallback para template padrão
        logger.info("Usando template padrão")
        from .templates import render_contract
        return render_contract(dados)
    
    def _get_tipo_nome_by_odontograma(self, odontograma_id: int) -> Optional[str]:
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
    
    def _render_template(self, template: str, dados: dict, config: dict = None) -> str:
        """Renderiza um template com os dados"""
        # Aplicar configurações se existirem
        if config:
            # Exemplo: ocultar/mostrar seções baseado na config
            if not config.get('show_dependents', True):
                dados['dependentes_rows'] = ''
                dados['dependentes_mobile'] = ''
        
        # Preparar dados com valores padrão
        defaults = self._get_default_values(dados)
        
        try:
            return template.format(**defaults)
        except KeyError as e:
            logger.error(f"Variável não encontrada no template: {e}")
            # Adicionar variáveis faltantes como vazias
            import re
            missing_vars = re.findall(r'\{(\w+)\}', template)
            for var in missing_vars:
                if var not in defaults:
                    defaults[var] = ''
            return template.format(**defaults)

# ==========================================
# SCRIPT DE INICIALIZAÇÃO
# ==========================================

def init_contract_templates():
    """
    Script para inicializar os templates de contratos
    Execute este script após criar a tabela contract_templates
    """
    logger.info("Inicializando sistema de templates de contratos...")
    
    if setup_default_templates():
        logger.info("✅ Templates de contratos configurados com sucesso!")
        
        # Listar templates configurados
        templates = template_registry.list_templates()
        logger.info(f"📋 Total de templates disponíveis: {len(templates)}")
        
        for template in templates:
            logger.info(f"  - {template['name']} ({template['tipo_odontograma']})")
    else:
        logger.error("❌ Erro ao configurar templates de contratos")

if __name__ == "__main__":
    init_contract_templates()