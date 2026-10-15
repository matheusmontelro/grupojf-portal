# backend/app/digital_contracts/integration_examples.py
"""
Exemplos práticos de integração do sistema de templates
Baseado nos tipos de odontograma identificados no frontend
"""

from .template_registry import template_registry
from .template_admin import TemplateBuilder
import logging

logger = logging.getLogger(__name__)

# ==========================================
# TEMPLATES BASEADOS NO FRONTEND
# ==========================================

# Baseado em: tiposContratoComValorBasePorParcela do frontend
TIPOS_IDENTIFICADOS = [
    'Contrato Odontológico + Akimais',
    'Contrato Ortodôntico', 
    'Combo Orto + ODC'
]

def create_frontend_based_templates():
    """
    Cria templates baseados nos tipos identificados no frontend
    """
    builder = TemplateBuilder()
    success_count = 0
    
    # 1. Template para Contrato Odontológico + Akimais (já existente, melhorado)
    akimais_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contrato Digital Akimais</title>
    <style>
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0; padding: 20px; line-height: 1.6;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 210mm; margin: 0 auto; background: white;
            padding: 0; border-radius: 20px; overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        
        .akimais-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 40px 30px; text-align: center;
            position: relative;
        }}
        
        .akimais-header::before {{
            content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="20" cy="20" r="2" fill="rgba(255,255,255,0.1)"/><circle cx="80" cy="40" r="3" fill="rgba(255,255,255,0.05)"/><circle cx="40" cy="80" r="1" fill="rgba(255,255,255,0.1)"/></svg>');
        }}
        
        .akimais-logo {{
            font-size: 28px; font-weight: bold; margin-bottom: 15px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3); position: relative; z-index: 1;
        }}
        
        .digital-badge {{
            background: rgba(255,255,255,0.2); padding: 10px 20px;
            border-radius: 30px; font-size: 14px; display: inline-block;
            margin-top: 15px; backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.3); position: relative; z-index: 1;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .info-card {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 25px; margin: 25px 0; border-radius: 15px;
            border-left: 5px solid #667eea;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
        }}
        
        .info-card h3 {{
            color: #667eea; margin-top: 0; margin-bottom: 15px;
            font-size: 18px; font-weight: 600;
        }}
        
        .info-grid {{
            display: grid; grid-template-columns: 1fr 1fr;
            gap: 15px; margin-top: 15px;
        }}
        
        .info-item {{
            padding: 15px; background: white; border-radius: 10px;
            border: 1px solid #e9ecef;
        }}
        
        .info-label {{
            font-size: 12px; color: #6c757d; margin-bottom: 5px;
            text-transform: uppercase; font-weight: 600;
        }}
        
        .info-value {{
            font-size: 16px; color: #212529; font-weight: 500;
        }}
        
        .signature-section {{
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
            padding: 30px; margin: 40px 0; border-radius: 15px;
            text-align: center; border: 2px dashed #667eea;
        }}
        
        .signature-image {{
            max-width: 300px; max-height: 100px;
            border: 2px solid #667eea; border-radius: 10px;
            margin: 20px auto; display: block;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.2);
        }}
        
        .contract-terms {{
            background: #fff3cd; padding: 20px; margin: 30px 0;
            border-radius: 10px; border-left: 4px solid #ffc107;
        }}
        
        .terms-title {{
            color: #856404; font-weight: 600; margin-bottom: 15px;
            font-size: 16px;
        }}
        
        .digital-footer {{
            background: #f8f9fa; padding: 20px; text-align: center;
            font-size: 12px; color: #6c757d; margin-top: 40px;
        }}
        
        @media print {{
            body {{ background: white !important; }}
            .container {{ box-shadow: none; }}
        }}
        
        @media (max-width: 768px) {{
            .info-grid {{ grid-template-columns: 1fr; }}
            .container {{ margin: 10px; }}
            .content {{ padding: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="akimais-header">
            <div class="akimais-logo">🦷 CONTRATO DIGITAL AKIMAIS</div>
            <p style="margin: 10px 0; font-size: 16px;">Plataforma de Odontologia Digital</p>
            <div class="digital-badge">✅ Assinatura Digital Certificada</div>
        </div>
        
        <div class="content">
            <div class="info-card">
                <h3>👤 Dados do Contratante</h3>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Nome Completo</div>
                        <div class="info-value">{paciente_nome}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">CPF</div>
                        <div class="info-value">{paciente_cpf}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">E-mail</div>
                        <div class="info-value">{paciente_email}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Telefone</div>
                        <div class="info-value">{paciente_telefone1}</div>
                    </div>
                </div>
            </div>
            
            <div class="info-card">
                <h3>💰 Detalhes Financeiros</h3>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Valor Total</div>
                        <div class="info-value">R$ {valor_total:,.2f}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Parcelas</div>
                        <div class="info-value">{qtd_parcelas}x de R$ {valor_parcela:,.2f}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Vencimento</div>
                        <div class="info-value">Todo dia {dia_vencimento}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Vendedor</div>
                        <div class="info-value">{vendedor_nome}</div>
                    </div>
                </div>
            </div>
            
            <div class="contract-terms">
                <div class="terms-title">📋 Termos Principais do Contrato</div>
                <ul style="margin: 0; padding-left: 20px;">
                    <li>Contrato de prestação de serviços odontológicos digitais</li>
                    <li>Plataforma Akimais para gestão do tratamento</li>
                    <li>Acompanhamento digital integrado</li>
                    <li>Suporte técnico especializado</li>
                </ul>
            </div>
            
            <div class="signature-section">
                <h3 style="color: #667eea; margin-top: 0;">✍️ Assinatura Digital</h3>
                <p>Este contrato foi assinado digitalmente através da plataforma Akimais</p>
                {signature_html}
                <div style="margin-top: 20px;">
                    <strong style="font-size: 18px;">{paciente_nome}</strong><br>
                    <span style="color: #6c757d;">Assinado digitalmente em {data_contrato}</span>
                </div>
            </div>
        </div>
        
        <div class="digital-footer">
            <p>💻 Contrato processado digitalmente pela plataforma Akimais</p>
            <p>🔒 Documento com validade jurídica e criptografia de segurança</p>
        </div>
    </div>
</body>
</html>
"""
    
    # Registrar template Akimais
    if (builder.reset()
        .set_name("Contrato Digital Akimais Moderno")
        .set_tipo("Contrato Odontológico + Akimais")
        .set_html(akimais_template)
        .with_theme("#667eea", "#764ba2", "digital-modern")
        .set_config(
            digital_signature=True,
            akimais_platform=True,
            modern_design=True,
            responsive=True
        )
        .set_description("Template moderno e responsivo para contratos digitais Akimais")
        .build()):
        success_count += 1
    
    # 2. Template para Contrato Ortodôntico
    ortodontico_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Contrato de Tratamento Ortodôntico</title>
    <style>
        body {{ 
            font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 210mm; margin: 0 auto; background: white;
            border-radius: 20px; overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        
        .ortho-header {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white; padding: 40px 30px; text-align: center;
        }}
        
        .ortho-icons {{
            font-size: 48px; margin-bottom: 15px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .treatment-timeline {{
            background: #e3f2fd; padding: 25px; margin: 25px 40px;
            border-radius: 15px; border-left: 5px solid #2196f3;
        }}
        
        .timeline-item {{
            display: flex; align-items: center; margin: 15px 0;
        }}
        
        .timeline-icon {{
            background: #2196f3; color: white; width: 30px; height: 30px;
            border-radius: 50%; display: flex; align-items: center;
            justify-content: center; margin-right: 15px; font-size: 14px;
        }}
        
        .content {{ padding: 40px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="ortho-header">
            <div class="ortho-icons">🦷✨🔧</div>
            <h1 style="margin: 0; font-size: 28px;">CONTRATO DE TRATAMENTO ORTODÔNTICO</h1>
            <p style="margin: 15px 0 0 0; font-size: 16px;">Especializados em Sorrisos Perfeitos</p>
        </div>
        
        <div class="content">
            <div class="treatment-timeline">
                <h3 style="color: #2196f3; margin-top: 0;">📅 Cronograma do Tratamento</h3>
                <div class="timeline-item">
                    <div class="timeline-icon">1</div>
                    <div>
                        <strong>Instalação do Aparelho</strong><br>
                        <small style="color: #666;">Primeira consulta e colocação</small>
                    </div>
                </div>
                <div class="timeline-item">
                    <div class="timeline-icon">2</div>
                    <div>
                        <strong>Manutenções Mensais</strong><br>
                        <small style="color: #666;">Ajustes e acompanhamento (18-24 meses)</small>
                    </div>
                </div>
                <div class="timeline-item">
                    <div class="timeline-icon">3</div>
                    <div>
                        <strong>Remoção e Contenção</strong><br>
                        <small style="color: #666;">Finalização e aparelho de contenção</small>
                    </div>
                </div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 15px; margin: 25px 0;">
                <h3 style="color: #2196f3; margin-top: 0;">👤 Dados do Paciente</h3>
                <p><strong>Nome:</strong> {paciente_nome}</p>
                <p><strong>CPF:</strong> {paciente_cpf}</p>
                <p><strong>Telefone:</strong> {paciente_telefone1}</p>
            </div>
            
            <div style="background: #fff3e0; padding: 25px; border-radius: 15px; margin: 25px 0;">
                <h3 style="color: #f57c00; margin-top: 0;">💰 Investimento</h3>
                <p><strong>Valor Total:</strong> R$ {valor_total:,.2f}</p>
                <p><strong>Forma de Pagamento:</strong> {qtd_parcelas}x de R$ {valor_parcela:,.2f}</p>
                <p><strong>Vencimento:</strong> Todo dia {dia_vencimento} de cada mês</p>
            </div>
            
            <div style="text-align: center; margin-top: 50px; padding: 30px; background: #f8f9fa; border-radius: 15px;">
                <h3 style="color: #2196f3;">✍️ Assinatura do Contrato</h3>
                {signature_html}
                <p style="margin-top: 20px;">
                    <strong style="font-size: 18px;">{paciente_nome}</strong><br>
                    <span style="color: #666;">{data_contrato}</span>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    # Registrar template Ortodôntico
    if (builder.reset()
        .set_name("Contrato Ortodôntico com Timeline")
        .set_tipo("Contrato Ortodôntico")
        .set_html(ortodontico_template)
        .with_theme("#4facfe", "#00f2fe", "orthodontic")
        .set_config(
            show_timeline=True,
            orthodontic_specific=True,
            treatment_duration="18-24 meses"
        )
        .set_description("Template especializado para tratamentos ortodônticos com cronograma")
        .build()):
        success_count += 1
    
    # 3. Template para Combo Orto + ODC
    combo_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Combo Ortodontia + Odontologia Clínica</title>
    <style>
        body {{ 
            font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px;
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 210mm; margin: 0 auto; background: white;
            border-radius: 20px; overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        
        .combo-header {{
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
            color: white; padding: 40px 30px; text-align: center;
        }}
        
        .combo-benefits {{
            display: grid; grid-template-columns: 1fr 1fr;
            gap: 25px; margin: 30px 40px;
        }}
        
        .benefit-card {{
            background: white; padding: 25px; border-radius: 15px;
            border-left: 5px solid #fa709a; box-shadow: 0 5px 15px rgba(0,0,0,0.08);
        }}
        
        .benefit-icon {{
            font-size: 32px; margin-bottom: 15px;
        }}
        
        .benefit-title {{
            color: #fa709a; font-size: 18px; font-weight: 600;
            margin-bottom: 15px;
        }}
        
        .content {{ padding: 40px; }}
        
        @media (max-width: 768px) {{
            .combo-benefits {{ grid-template-columns: 1fr; margin: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="combo-header">
            <h1 style="margin: 0; font-size: 32px;">🦷 COMBO COMPLETO 🦷</h1>
            <h2 style="margin: 15px 0; font-size: 24px;">Ortodontia + Odontologia Clínica</h2>
            <p style="margin: 15px 0 0 0; font-size: 16px;">Solução Completa para seu Sorriso</p>
        </div>
        
        <div class="combo-benefits">
            <div class="benefit-card">
                <div class="benefit-icon">🔧</div>
                <div class="benefit-title">Ortodontia Completa</div>
                <ul style="margin: 0; padding-left: 20px; color: #555;">
                    <li>Aparelho ortodôntico fixo ou móvel</li>
                    <li>Manutenções mensais inclusas</li>
                    <li>Documentação ortodôntica</li>
                    <li>Aparelho de contenção</li>
                </ul>
            </div>
            
            <div class="benefit-card">
                <div class="benefit-icon">🔬</div>
                <div class="benefit-title">Clínica Geral</div>
                <ul style="margin: 0; padding-left: 20px; color: #555;">
                    <li>Limpezas e profilaxias</li>
                    <li>Restaurações em resina</li>
                    <li>Tratamentos de canal</li>
                    <li>Extrações simples</li>
                </ul>
            </div>
        </div>
        
        <div class="content">
            <div style="background: #f8f9fa; padding: 25px; border-radius: 15px; margin: 25px 0;">
                <h3 style="color: #fa709a; margin-top: 0;">👤 Dados do Contratante</h3>
                <p><strong>Nome:</strong> {paciente_nome}</p>
                <p><strong>CPF:</strong> {paciente_cpf}</p>
                <p><strong>E-mail:</strong> {paciente_email}</p>
            </div>
            
            <div style="background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%); padding: 25px; border-radius: 15px; margin: 25px 0;">
                <h3 style="color: #f57c00; margin-top: 0;">💎 Valor do Combo</h3>
                <div style="text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #f57c00;">
                        R$ {valor_total:,.2f}
                    </div>
                    <div style="margin: 10px 0; font-size: 18px;">
                        {qtd_parcelas}x de R$ {valor_parcela:,.2f}
                    </div>
                    <div style="color: #666;">
                        Vencimento todo dia {dia_vencimento}
                    </div>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 50px; padding: 30px; background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); border-radius: 15px; border: 2px dashed #fa709a;">
                <h3 style="color: #fa709a;">✍️ Assinatura do Combo</h3>
                <p>Concordo com os termos e condições do combo completo</p>
                {signature_html}
                <div style="margin-top: 20px;">
                    <strong style="font-size: 18px;">{paciente_nome}</strong><br>
                    <span style="color: #666;">{data_contrato}</span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    # Registrar template Combo
    if (builder.reset()
        .set_name("Combo Ortodontia + Clínica Completo")
        .set_tipo("Combo Orto + ODC")
        .set_html(combo_template)
        .with_theme("#fa709a", "#fee140", "combo")
        .set_config(
            show_benefits_grid=True,
            combo_services=True,
            highlight_value=True
        )
        .set_description("Template para combo completo de ortodontia e clínica geral")
        .build()):
        success_count += 1
    
    logger.info(f"Templates do frontend criados: {success_count}/3")
    return success_count == 3

# ==========================================
# INTEGRAÇÃO COM O SISTEMA EXISTENTE
# ==========================================

def update_existing_service():
    """
    Código para atualizar o service.py existente
    """
    
    service_integration = '''
# ADICIONAR NO INÍCIO DO service.py:
from .template_registry import template_registry

# SUBSTITUIR O MÉTODO _render_contract_html EXISTENTE:
def _render_contract_html(self, dados: dict, odontograma_id: int = None) -> str:
    """Renderiza HTML do contrato usando o novo sistema de templates"""
    logger.info(f"🎨 Renderizando HTML do contrato para: {dados.get('paciente_nome', 'N/A')}")
    
    try:
        if odontograma_id:
            # Buscar tipo do odontograma
            tipo_nome = self._get_tipo_nome_by_odontograma(odontograma_id)
            logger.info(f"🔍 Tipo de odontograma identificado: {tipo_nome}")
            
            if tipo_nome:
                # Tentar usar template específico do registry
                template_html, template_config = template_registry.get_template_for_tipo(tipo_nome)
                
                if template_html:
                    logger.info(f"✅ Usando template específico para tipo '{tipo_nome}'")
                    return self._render_with_template(template_html, dados, template_config)
                else:
                    logger.info(f"⚠️ Template específico não encontrado para '{tipo_nome}', usando padrão")
        
        # Fallback para template padrão
        logger.info("🔄 Usando template padrão existente")
        from .templates import render_contract
        return render_contract(dados)
        
    except Exception as e:
        logger.error(f"❌ Erro em _render_contract_html: {str(e)}", exc_info=True)
        # Fallback final
        from .templates import render_contract
        return render_contract(dados)

# ADICIONAR MÉTODOS AUXILIARES:
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
            tipo_nome = result[0] if result else None
            logger.info(f"🔍 Tipo encontrado para odontograma {odontograma_id}: {tipo_nome}")
            return tipo_nome
    except Exception as e:
        logger.error(f"❌ Erro ao buscar tipo do odontograma {odontograma_id}: {e}")
        return None

def _render_with_template(self, template_html: str, dados: dict, config: dict = None) -> str:
    """Renderiza template com dados e configurações"""
    logger.info(f"🎨 Renderizando template com config: {config}")
    
    # Preparar dados com valores padrão (usar método existente)
    defaults = self._get_default_values(dados)
    
    # Aplicar configurações específicas do template
    if config:
        logger.info(f"⚙️ Aplicando configurações do template: {list(config.keys())}")
        
        # Exemplo: ocultar seções baseado na config
        if not config.get('show_dependents', True):
            defaults['dependentes_rows'] = ''
            defaults['dependentes_mobile'] = ''
            
        # Adicionar dados específicos do template
        if config.get('digital_signature'):
            defaults['digital_signature_enabled'] = True
        if config.get('orthodontic_specific'):
            defaults['treatment_type'] = 'orthodontic'
    
    try:
        rendered_html = template_html.format(**defaults)
        logger.info(f"✅ Template renderizado com sucesso ({len(rendered_html)} chars)")
        return rendered_html
        
    except KeyError as e:
        logger.error(f"❌ Variável não encontrada no template: {e}")
        
        # Auto-correção: adicionar variáveis faltantes
        import re
        missing_vars = re.findall(r'\\{(\\w+)\\}', template_html)
        for var in missing_vars:
            if var not in defaults:
                defaults[var] = ''
                logger.warning(f"➕ Adicionada variável faltante: {var} = ''")
        
        return template_html.format(**defaults)
    
    except Exception as e:
        logger.error(f"❌ Erro geral na renderização: {e}")
        # Fallback para template padrão
        from .templates import render_contract
        return render_contract(dados)
'''
    
    return service_integration

# ==========================================
# SCRIPT DE SETUP COMPLETO
# ==========================================

def setup_complete_integration():
    """
    Setup completo da integração com templates específicos do frontend
    """
    logger.info("🚀 Iniciando setup completo da integração de templates...")
    
    try:
        # 1. Criar templates baseados no frontend
        logger.info("1️⃣ Criando templates baseados no frontend...")
        frontend_success = create_frontend_based_templates()
        
        # 2. Listar templates criados
        logger.info("2️⃣ Verificando templates criados...")
        templates = template_registry.list_templates()
        
        logger.info(f"📊 Total de templates disponíveis: {len(templates)}")
        for template in templates:
            status = "✅" if template['is_active'] else "❌"
            logger.info(f"  {status} {template['name']} → {template['tipo_odontograma']}")
        
        # 3. Mostrar código de integração
        logger.info("3️⃣ Código de integração gerado:")
        integration_code = update_existing_service()
        
        # 4. Verificar tipos específicos do frontend
        logger.info("4️⃣ Verificando tipos identificados no frontend:")
        for tipo in TIPOS_IDENTIFICADOS:
            template_html, config = template_registry.get_template_for_tipo(tipo)
            status = "✅ Configurado" if template_html else "❌ Faltando"
            logger.info(f"  {status} {tipo}")
        
        logger.info("🎉 Setup de integração concluído com sucesso!")
        
        return {
            'success': True,
            'templates_created': len(templates),
            'frontend_types_covered': sum(1 for tipo in TIPOS_IDENTIFICADOS 
                                        if template_registry.get_template_for_tipo(tipo)[0] is not None),
            'integration_ready': True
        }
        
    except Exception as e:
        logger.error(f"❌ Erro no setup de integração: {e}")
        return {'success': False, 'error': str(e)}

# ==========================================
# FUNÇÃO DE TESTE
# ==========================================

def test_template_system():
    """
    Testa o sistema de templates com dados de exemplo
    """
    logger.info("🧪 Testando sistema de templates...")
    
    # Dados de teste
    test_data = {
        'paciente_nome': 'João Silva dos Santos',
        'paciente_cpf': '123.456.789-00',
        'paciente_email': 'joao@email.com',
        'paciente_telefone1': '(11) 99999-9999',
        'valor_total': 1200.00,
        'qtd_parcelas': 12,
        'valor_parcela': 100.00,
        'dia_vencimento': '10',
        'vendedor_nome': 'Maria Vendedora',
        'data_contrato': '15 de dezembro de 2024',
        'signature_html': '<div style="text-align: center; padding: 20px; border: 1px solid #ccc;">Assinatura Digital</div>'
    }
    
    test_results = {}
    
    # Testar cada tipo identificado no frontend
    for tipo in TIPOS_IDENTIFICADOS:
        logger.info(f"🔍 Testando tipo: {tipo}")
        
        try:
            template_html, config = template_registry.get_template_for_tipo(tipo)
            
            if template_html:
                # Simular renderização
                rendered = template_html.format(**test_data)
                test_results[tipo] = {
                    'status': 'success',
                    'template_found': True,
                    'config': config,
                    'rendered_size': len(rendered)
                }
                logger.info(f"  ✅ Renderizado com sucesso ({len(rendered)} chars)")
            else:
                test_results[tipo] = {
                    'status': 'template_not_found',
                    'template_found': False
                }
                logger.warning(f"  ⚠️ Template não encontrado")
                
        except Exception as e:
            test_results[tipo] = {
                'status': 'error',
                'error': str(e)
            }
            logger.error(f"  ❌ Erro: {e}")
    
    logger.info("🧪 Teste concluído!")
    return test_results

if __name__ == "__main__":
    # Executar setup completo
    result = setup_complete_integration()
    
    if result['success']:
        # Executar teste
        test_results = test_template_system()
        
        print("\n" + "="*60)
        print("🎉 SISTEMA DE TEMPLATES CONFIGURADO COM SUCESSO!")
        print("="*60)
        print(f"📊 Templates criados: {result['templates_created']}")
        print(f"🎯 Tipos do frontend cobertos: {result['frontend_types_covered']}/{len(TIPOS_IDENTIFICADOS)}")
        print("\n📋 Próximos passos:")
        print("1. Copie o código de integração para service.py")
        print("2. Reinicie a aplicação")
        print("3. Teste com contratos reais")
        print("="*60)
    else:
        print(f"❌ Erro no setup: {result.get('error', 'Erro desconhecido')}")