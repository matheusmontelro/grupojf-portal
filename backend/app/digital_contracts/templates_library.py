# backend/app/digital_contracts/templates_library.py
"""
Biblioteca de Templates de Contratos Odontológicos
Exemplos prontos para diferentes especialidades
"""

# 1. Template para Tratamento Infantil/Pediátrico
TEMPLATE_PEDIATRICO = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Contrato de Tratamento Odontopediátrico</title>
    <style>
        body {
            font-family: 'Comic Sans MS', Arial, sans-serif;
            background: linear-gradient(to bottom, #ffefba, #ffffff);
            margin: 0;
            padding: 20px;
        }
        
        .container {
            max-width: 210mm;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        
        .header-kids {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            color: white;
            margin-bottom: 30px;
        }
        
        .header-kids h1 {
            margin: 0;
            font-size: 28px;
        }
        
        .mascot {
            font-size: 48px;
            margin: 10px;
        }
        
        .info-box {
            background: #e3f2fd;
            border: 2px solid #2196f3;
            border-radius: 15px;
            padding: 20px;
            margin: 20px 0;
        }
        
        .benefits {
            background: #f3e5f5;
            border-radius: 15px;
            padding: 20px;
            margin: 20px 0;
        }
        
        .benefits ul {
            list-style: none;
            padding: 0;
        }
        
        .benefits li:before {
            content: "🌟 ";
            font-size: 20px;
        }
        
        .parent-section {
            background: #fff9c4;
            border: 2px dashed #f9a825;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        
        @media print {
            body { background: white; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-kids">
            <div class="mascot">🦷 😊 🦷</div>
            <h1>CONTRATO DE TRATAMENTO ODONTOPEDIÁTRICO</h1>
            <p>Cuidando do sorriso do seu pequeno com carinho!</p>
        </div>
        
        <div class="info-box">
            <h2>👦 DADOS DA CRIANÇA 👧</h2>
            <p><strong>Nome:</strong> {paciente_nome}</p>
            <p><strong>Data de Nascimento:</strong> {paciente_data_nascimento}</p>
            <p><strong>Responsável:</strong> {responsavel_nome}</p>
            <p><strong>CPF do Responsável:</strong> {responsavel_cpf}</p>
        </div>
        
        <div class="benefits">
            <h2>🎯 O QUE ESTÁ INCLUÍDO NO TRATAMENTO:</h2>
            <ul>
                <li>Primeira consulta com aplicação de flúor</li>
                <li>Orientação de higiene bucal para pais e criança</li>
                <li>Tratamento preventivo completo</li>
                <li>Acompanhamento do desenvolvimento dental</li>
                <li>Ambiente lúdico e acolhedor</li>
                <li>Brindes educativos após cada consulta</li>
            </ul>
        </div>
        
        <div class="parent-section">
            <h3>📋 ORIENTAÇÕES AOS PAIS/RESPONSÁVEIS:</h3>
            <ul>
                <li>✅ Acompanhar a criança em todas as consultas</li>
                <li>✅ Supervisionar a escovação em casa</li>
                <li>✅ Seguir as orientações alimentares</li>
                <li>✅ Manter consultas de prevenção em dia</li>
            </ul>
        </div>
        
        <div class="info-box">
            <h3>💰 INVESTIMENTO NO SORRISO DO SEU FILHO:</h3>
            <p>Valor Total: <strong>R$ {valor_total:,.2f}</strong></p>
            <p>Forma de Pagamento: <strong>{qtd_parcelas}x de R$ {valor_parcela:,.2f}</strong></p>
        </div>
        
        <!-- Assinaturas -->
        <div style="margin-top: 50px;">
            <p style="text-align: center;">
                <strong>{cidade_contrato}, {data_contrato}</strong>
            </p>
            
            <div style="display: flex; justify-content: space-between; margin-top: 50px;">
                <div style="text-align: center; width: 45%;">
                    <div style="border-bottom: 2px solid #000; margin-bottom: 10px;"></div>
                    <p><strong>Responsável Legal</strong></p>
                </div>
                <div style="text-align: center; width: 45%;">
                    <div style="border-bottom: 2px solid #000; margin-bottom: 10px;"></div>
                    <p><strong>{empresa_razao_social}</strong></p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# 2. Template para Implantes Premium
TEMPLATE_IMPLANTE_PREMIUM = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Contrato de Implante Dentário Premium</title>
    <style>
        body {
            font-family: 'Georgia', serif;
            background: #fafafa;
            margin: 0;
            padding: 20px;
            color: #2c3e50;
        }
        
        .container {
            max-width: 210mm;
            margin: 0 auto;
            background: white;
            padding: 40px;
            box-shadow: 0 0 30px rgba(0,0,0,0.1);
        }
        
        .luxury-header {
            text-align: center;
            border-bottom: 3px double #c9302c;
            padding-bottom: 30px;
            margin-bottom: 40px;
        }
        
        .luxury-header h1 {
            color: #c9302c;
            font-size: 32px;
            margin: 20px 0;
            letter-spacing: 2px;
        }
        
        .gold-seal {
            display: inline-block;
            background: linear-gradient(135deg, #f9d71c 0%, #ffa000 100%);
            color: #2c3e50;
            padding: 15px 30px;
            border-radius: 50px;
            font-weight: bold;
            box-shadow: 0 4px 15px rgba(255,160,0,0.3);
        }
        
        .premium-box {
            background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%);
            border: 1px solid #ddd;
            padding: 30px;
            margin: 30px 0;
            position: relative;
        }
        
        .premium-box:before {
            content: "PREMIUM";
            position: absolute;
            top: -15px;
            right: 20px;
            background: #c9302c;
            color: white;
            padding: 5px 20px;
            font-size: 12px;
            letter-spacing: 2px;
        }
        
        .warranty-section {
            background: #2c3e50;
            color: white;
            padding: 30px;
            margin: 30px 0;
            text-align: center;
        }
        
        .warranty-section h2 {
            color: #f9d71c;
            font-size: 28px;
            margin: 0 0 20px 0;
        }
        
        .specs-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        .specs-table th {
            background: #2c3e50;
            color: white;
            padding: 15px;
            text-align: left;
        }
        
        .specs-table td {
            padding: 15px;
            border-bottom: 1px solid #ddd;
        }
        
        .signature-premium {
            border-top: 3px double #c9302c;
            margin-top: 50px;
            padding-top: 30px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="luxury-header">
            <div class="gold-seal">EXCELÊNCIA EM IMPLANTODONTIA</div>
            <h1>CONTRATO DE IMPLANTE DENTÁRIO PREMIUM</h1>
            <p style="font-style: italic; color: #666;">
                "Recupere seu sorriso com a mais alta tecnologia e garantia estendida"
            </p>
        </div>
        
        <div class="premium-box">
            <h2>DADOS DO PACIENTE VIP</h2>
            <table style="width: 100%;">
                <tr>
                    <td><strong>Nome:</strong></td>
                    <td>{paciente_nome}</td>
                </tr>
                <tr>
                    <td><strong>CPF:</strong></td>
                    <td>{paciente_cpf}</td>
                </tr>
                <tr>
                    <td><strong>E-mail:</strong></td>
                    <td>{paciente_email}</td>
                </tr>
                <tr>
                    <td><strong>Telefone:</strong></td>
                    <td>{paciente_telefone1}</td>
                </tr>
            </table>
        </div>
        
        <div class="warranty-section">
            <h2>⭐ GARANTIA PREMIUM DE 10 ANOS ⭐</h2>
            <p>Seu implante está protegido pela mais completa garantia do mercado</p>
            <ul style="text-align: left; max-width: 600px; margin: 20px auto;">
                <li>✓ Implante de titânio grau 5 (máxima qualidade)</li>
                <li>✓ Coroa em porcelana Premium ou Zircônia</li>
                <li>✓ Acompanhamento vitalício</li>
                <li>✓ Manutenções preventivas inclusas por 2 anos</li>
                <li>✓ Atendimento prioritário VIP</li>
            </ul>
        </div>
        
        <h2 style="color: #2c3e50;">ESPECIFICAÇÕES TÉCNICAS DO TRATAMENTO</h2>
        <table class="specs-table">
            <tr>
                <th>Componente</th>
                <th>Especificação</th>
                <th>Garantia</th>
            </tr>
            <tr>
                <td>Implante</td>
                <td>Titânio Grau 5 - Importado</td>
                <td>10 anos</td>
            </tr>
            <tr>
                <td>Pilar Protético</td>
                <td>Personalizado CAD/CAM</td>
                <td>10 anos</td>
            </tr>
            <tr>
                <td>Coroa</td>
                <td>Porcelana Premium / Zircônia</td>
                <td>5 anos</td>
            </tr>
            <tr>
                <td>Osseointegração</td>
                <td>Acompanhamento trimestral</td>
                <td>1 ano</td>
            </tr>
        </table>
        
        <div class="premium-box">
            <h2>INVESTIMENTO</h2>
            <p style="font-size: 24px; color: #c9302c;">
                Valor Total: <strong>R$ {valor_total:,.2f}</strong>
            </p>
            <p>Condições Especiais de Pagamento:</p>
            <ul>
                <li>{qtd_parcelas}x de R$ {valor_parcela:,.2f} no cartão</li>
                <li>Desconto de 10% para pagamento à vista</li>
                <li>Financiamento em até 48x (sujeito a análise)</li>
            </ul>
        </div>
        
        <div class="warranty-section" style="background: #27ae60;">
            <h3>BENEFÍCIOS EXCLUSIVOS VIP</h3>
            <p>✦ Sala de espera VIP ✦ Estacionamento gratuito ✦</p>
            <p>✦ Agendamento prioritário ✦ Check-up semestral cortesia ✦</p>
        </div>
        
        <div class="signature-premium">
            <p style="text-align: center; margin-bottom: 30px;">
                <strong>{cidade_contrato}, {data_contrato}</strong>
            </p>
            
            <div style="display: flex; justify-content: space-between;">
                <div style="text-align: center; width: 45%;">
                    {signature_html}
                    <div style="border-top: 2px solid #000; margin-top: 50px;"></div>
                    <p><strong>{paciente_nome}</strong><br>Contratante</p>
                </div>
                <div style="text-align: center; width: 45%;">
                    <div style="height: 80px;"></div>
                    <div style="border-top: 2px solid #000;"></div>
                    <p><strong>{empresa_razao_social}</strong><br>Contratada</p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# 3. Template para Emergência 24h
TEMPLATE_EMERGENCIA_24H = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Contrato de Atendimento Emergencial 24h</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        
        .emergency-header {
            background: #d32f2f;
            color: white;
            padding: 30px;
            text-align: center;
            margin: -20px -20px 30px -20px;
        }
        
        .emergency-header h1 {
            margin: 0;
            font-size: 32px;
        }
        
        .emergency-box {
            background: #ffebee;
            border: 3px solid #d32f2f;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            font-size: 18px;
            text-align: center;
        }
        
        .phone-24h {
            font-size: 36px;
            color: #d32f2f;
            font-weight: bold;
        }
        
        .coverage-list {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .coverage-list h3 {
            color: #d32f2f;
            border-bottom: 2px solid #d32f2f;
            padding-bottom: 10px;
        }
        
        .urgent-icon {
            color: #d32f2f;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="emergency-header">
            <h1>🚨 CONTRATO DE ATENDIMENTO EMERGENCIAL 24 HORAS 🚨</h1>
            <p>Proteção completa para urgências odontológicas</p>
        </div>
        
        <div class="emergency-box">
            <p>LINHA DIRETA DE EMERGÊNCIA</p>
            <p class="phone-24h">📞 0800-EMERGÊNCIA</p>
            <p>Atendimento 24 horas, 7 dias por semana</p>
        </div>
        
        <!-- Resto do template... -->
    </div>
</body>
</html>
"""

# Função para inserir todos os templates de exemplo
def inserir_templates_biblioteca():
    """
    Insere todos os templates da biblioteca no banco de dados
    """
    from app.database.db import DatabaseConnection
    import json
    
    templates = [
        {
            'name': 'Contrato Odontopediátrico - Cuidado Infantil',
            'slug': 'contrato-pediatrico-infantil',
            'description': 'Template lúdico e amigável para tratamentos infantis',
            'template_html': TEMPLATE_PEDIATRICO,
            'template_config': {
                'theme': 'kids',
                'show_parent_section': True,
                'mascot_enabled': True,
                'colors': ['#667eea', '#764ba2']
            }
        },
        {
            'name': 'Contrato Implante Premium - VIP',
            'slug': 'contrato-implante-premium-vip',
            'description': 'Template luxuoso para implantes com garantia estendida',
            'template_html': TEMPLATE_IMPLANTE_PREMIUM,
            'template_config': {
                'theme': 'luxury',
                'warranty_years': 10,
                'vip_benefits': True,
                'premium_design': True
            }
        },
        {
            'name': 'Contrato Emergência 24h',
            'slug': 'contrato-emergencia-24h',
            'description': 'Template para serviço de emergência odontológica',
            'template_html': TEMPLATE_EMERGENCIA_24H,
            'template_config': {
                'theme': 'emergency',
                'phone_highlight': True,
                'urgency_level': 'high'
            }
        }
    ]
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        for template in templates:
            cursor.execute("""
                INSERT INTO contract_templates (
                    name, slug, description, template_html, 
                    template_config, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    template_html = EXCLUDED.template_html,
                    template_config = EXCLUDED.template_config,
                    version = contract_templates.version + 1,
                    updated_at = NOW()
            """, (
                template['name'],
                template['slug'],
                template['description'],
                template['template_html'],
                json.dumps(template['template_config']),
                'system'
            ))
        
        conn.commit()
        print(f"✅ {len(templates)} templates da biblioteca inseridos!")

if __name__ == "__main__":
    inserir_templates_biblioteca()