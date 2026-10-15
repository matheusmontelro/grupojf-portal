# digital_contracts/templates.py
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Template Akimais para uso no sistema
CONTRATO_AKIMAIS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contrato de Prestação de Serviços Odontológicos e Telemedicina</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0;
            padding: 20px;
            line-height: 1.4;
            background: white;
            font-size: 12px;
        }}
        
        .container {{
            max-width: 210mm;
            margin: 0 auto;
            background: white;
            padding: 20px;
        }}
        
        /* Header */
        .header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        
        .logo-area {{
            float: left;
            width: 100px;
            height: 80px;
            border: 1px solid #ccc;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f0f9f0;
            color: #4CAF50;
            font-weight: bold;
            font-size: 14px;
        }}
        
        .contract-title {{
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0;
            padding: 10px;
            border: 2px solid #000;
        }}
        
        .vendor-info {{
            float: right;
            text-align: right;
            font-size: 11px;
            margin-top: 10px;
        }}
        
        .clearfix {{ clear: both; }}
        
        /* Tables - Desktop */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
            border: 2px solid #000;
        }}
        
        th, td {{
            border: 1px solid #000;
            padding: 8px;
            text-align: left;
            vertical-align: top;
        }}
        
        th {{
            background-color: #f5f5f5;
            font-weight: bold;
            text-align: center;
        }}
        
        .section-header {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
        }}
        
        .number-cell {{
            width: 30px;
            text-align: center;
            font-weight: bold;
        }}
        
        /* Services Table Styles - Simplified to match other sections */
        .services-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
            border: 2px solid #000;
        }}
        
        .services-table th {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
            padding: 8px;
            border: 1px solid #000;
        }}
        
        .services-table td {{
            border: 1px solid #000;
            padding: 8px;
            text-align: left;
            vertical-align: top;
        }}
        
        .services-table .price-cell {{
            text-align: center;
            font-weight: bold;
        }}
        
        /* Mobile-friendly card layout */
        .mobile-card {{
            display: none;
            border: 2px solid #000;
            margin-bottom: 15px;
            background: white;
        }}
        
        .mobile-card-header {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
            padding: 10px;
            border-bottom: 1px solid #000;
        }}
        
        .mobile-card-content {{
            padding: 15px;
        }}
        
        .mobile-field {{
            margin-bottom: 12px;
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
        }}
        
        .mobile-field:last-child {{
            border-bottom: none;
            margin-bottom: 0;
        }}
        
        .mobile-field-label {{
            font-weight: bold;
            color: #333;
            font-size: 11px;
            margin-bottom: 4px;
        }}
        
        .mobile-field-value {{
            font-size: 12px;
            color: #000;
        }}
        
        .mobile-dependente {{
            border: 1px solid #ccc;
            margin-bottom: 10px;
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .mobile-dependente-header {{
            background-color: #f5f5f5;
            padding: 8px;
            font-weight: bold;
            font-size: 11px;
            border-bottom: 1px solid #ccc;
        }}
        
        .mobile-dependente-content {{
            padding: 10px;
        }}
        
        /* Mobile Services Table */
        .mobile-services {{
            display: none;
        }}
        
        .mobile-service-item {{
            border: 1px solid #333;
            margin-bottom: 10px;
            border-radius: 5px;
            overflow: hidden;
        }}
        
        .mobile-service-header {{
            background: #4CAF50;
            color: white;
            padding: 10px;
            font-weight: bold;
        }}
        
        .mobile-service-content {{
            padding: 10px;
            background: white;
        }}
        
        .mobile-service-price {{
            font-weight: bold;
            color: #2c3e50;
            font-size: 16px;
            margin-bottom: 5px;
        }}
        
        /* Contract Content */
        .contract-content {{
            margin-top: 20px;
            text-align: justify;
            line-height: 1.6;
        }}
        
        .clause {{
            margin: 20px 0;
        }}
        
        .clause-title {{
            font-weight: bold;
            margin-bottom: 10px;
            font-size: 14px;
            color: #2c3e50;
        }}
        
        .clause-content {{
            margin: 10px 0;
            text-indent: 20px;
        }}
        
        .sub-clause {{
            margin: 8px 0 8px 20px;
        }}
        
        .highlight {{
            background-color: #ffffcc;
            padding: 2px 4px;
            font-weight: bold;
        }}
        
        /* Signatures */
        .signatures {{
            margin-top: 40px;
            page-break-inside: avoid;
        }}
        
        .signature-line {{
            border-bottom: 1px solid #000;
            margin: 30px 20px 5px 20px;
            text-align: center;
            font-weight: bold;
        }}
        
        .signature-area {{
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
        }}
        
        .signature-box {{
            width: 45%;
            text-align: center;
        }}
        
        .signature-image {{
            max-width: 100%;
            max-height: 80px;
            margin: 0 auto 10px auto;
            display: block;
        }}
        
        .witness-area {{
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
        }}
        
        .witness-box {{
            width: 45%;
        }}
        
        .witness-line {{
            border-bottom: 1px solid #000;
            margin: 20px 0 5px 0;
        }}
        
        /* Print styles */
        @media print {{
            body {{ margin: 0; padding: 10px; }}
            .container {{ padding: 10px; }}
            .no-print {{ display: none; }}
            .mobile-card {{ display: none !important; }}
            .mobile-services {{ display: none !important; }}
            table {{ display: table !important; }}
            .services-table {{ display: table !important; }}
        }}
        
        /* Mobile responsiveness */
        @media (max-width: 768px) {{
            body {{ 
                padding: 10px; 
                font-size: 11px;
            }}
            
            .container {{ 
                padding: 10px; 
            }}
            
            .logo-area {{ 
                float: none; 
                margin: 0 auto 10px; 
                width: 80px;
                height: 60px;
                font-size: 12px;
            }}
            
            .vendor-info {{ 
                float: none; 
                text-align: center; 
                margin-top: 10px;
            }}
            
            .contract-title {{
                font-size: 14px;
                padding: 8px;
            }}
            
            /* Hide desktop tables on mobile */
            table {{
                display: none;
            }}
            
            .services-table {{
                display: none;
            }}
            
            /* Show mobile cards */
            .mobile-card {{
                display: block;
            }}
            
            .mobile-services {{
                display: block;
            }}
            
            .signature-area, .witness-area {{ 
                flex-direction: column; 
            }}
            
            .signature-box, .witness-box {{ 
                width: 100%; 
                margin-bottom: 20px; 
            }}
            
            .contract-content {{
                font-size: 11px;
                line-height: 1.4;
            }}
            
            .clause-title {{
                font-size: 12px;
            }}
            
            .highlight {{
                display: inline-block;
                margin: 2px 0;
            }}
        }}
        
        @media (max-width: 480px) {{
            body {{ 
                padding: 8px; 
                font-size: 10px;
            }}
            
            .container {{ 
                padding: 8px; 
            }}
            
            .mobile-card-content {{
                padding: 10px;
            }}
            
            .mobile-field {{
                margin-bottom: 8px;
            }}
            
            .logo-area {{
                width: 70px;
                height: 50px;
                font-size: 10px;
            }}
            
            .contract-title {{
                font-size: 12px;
                padding: 6px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            </div>
            
            <div class="vendor-info">
                <strong>VENDEDOR</strong><br>
                {vendedor_nome}
            </div>
            
            <div class="clearfix"></div>
            
            <div class="contract-title">
                CONTRATO DE PRESTAÇÃO DE<br>
                SERVIÇOS ODONTOLÓGICOS<br>
                E BENEFÍCIO DE TELEMEDICINA "AKI MAIS SAÚDE"
            </div>
        </div>

        {dependent_header}

        <!-- Seção A - CONTRATADA (Desktop) -->
        <table>
            <tr>
                <th class="section-header">A - CONTRATADA</th>
            </tr>
            <tr>
                <td>
                    Pelo presente Instrumento Particular, de um lado <strong>{empresa_razao_social}</strong>, inscrita no CNPJ/MF nº <strong>{empresa_cnpj}</strong>, com sede na cidade de {empresa_cidade} na {empresa_endereco_completo} a seguir denominada <strong>CONTRATADA</strong> e por outro lado, como <strong>CONTRATANTE</strong>, abaixo discriminado.
                </td>
            </tr>
        </table>

        <!-- Seção A - CONTRATADA (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">A - CONTRATADA</div>
            <div class="mobile-card-content">
                Pelo presente Instrumento Particular, de um lado <strong>{empresa_razao_social}</strong>, inscrita no CNPJ/MF nº <strong>{empresa_cnpj}</strong>, com sede na cidade de {empresa_cidade} na {empresa_endereco_completo} a seguir denominada <strong>CONTRATADA</strong> e por outro lado, como <strong>CONTRATANTE</strong>, abaixo discriminado.
            </div>
        </div>

        <!-- Seção B - CONTRATANTE (Desktop) -->
        <table>
            <tr>
                <th colspan="4" class="section-header">B - CONTRATANTE</th>
            </tr>
            <tr>
                <td colspan="2" style="width: 60%; font-weight: bold;">NOME</td>
                <td colspan="2" style="width: 40%; font-weight: bold;">DATA DE NASCIMENTO</td>
            </tr>
            <tr>
                <td colspan="2">{paciente_nome}</td>
                <td colspan="2">{paciente_data_nascimento}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">CPF</td>
                <td style="font-weight: bold;">RG</td>
                <td style="font-weight: bold;">ORGÃO EXPED</td>
                <td style="font-weight: bold;">CONTRATANTE INCLUSO</td>
            </tr>
            <tr>
                <td>{paciente_cpf}</td>
                <td>{paciente_rg}</td>
                <td>{paciente_orgao_expedidor}</td>
                <td>SIM</td>
            </tr>
        </table>

        <!-- Seção B - CONTRATANTE (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">B - CONTRATANTE</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">NOME</div>
                    <div class="mobile-field-value">{paciente_nome}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">DATA DE NASCIMENTO</div>
                    <div class="mobile-field-value">{paciente_data_nascimento}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CPF</div>
                    <div class="mobile-field-value">{paciente_cpf}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">RG</div>
                    <div class="mobile-field-value">{paciente_rg}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">ÓRGÃO EXPEDIDOR</div>
                    <div class="mobile-field-value">{paciente_orgao_expedidor}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CONTRATANTE INCLUSO</div>
                    <div class="mobile-field-value">SIM</div>
                </div>
            </div>
        </div>

        <!-- Seção C - CONTRATANTEes Vinculados (Desktop) -->
        <table>
            <tr>
                <th colspan="4" class="section-header">C - CONTRATANTEES VINCULADOS</th>
            </tr>
            {dependentes_rows}
        </table>

        <!-- Seção C - CONTRATANTEes Vinculados (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">C - CONTRATANTEES VINCULADOS</div>
            <div class="mobile-card-content">
                {dependentes_mobile}
            </div>
        </div>

        <!-- Seção D - Endereço (Desktop) -->
        <table>
            <tr>
                <th colspan="3" class="section-header">D - ENDEREÇO</th>
            </tr>
            <tr>
                <td colspan="2" style="font-weight: bold; width: 60%;">RESIDENCIAL</td>
                <td style="font-weight: bold; width: 40%;">CEP</td>
            </tr>
            <tr>
                <td colspan="2">{paciente_endereco}</td>
                <td>{paciente_cep}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">BAIRRO</td>
                <td style="font-weight: bold;">CIDADE</td>
                <td style="font-weight: bold;">ESTADO</td>
            </tr>
            <tr>
                <td>{paciente_bairro}</td>
                <td>{paciente_cidade}</td>
                <td>{paciente_estado}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">TEL 1</td>
                <td style="font-weight: bold;">TEL 2</td>
                <td style="font-weight: bold;">EMAIL</td>
            </tr>
            <tr>
                <td>{paciente_telefone1}</td>
                <td>{paciente_telefone2}</td>
                <td>{paciente_email}</td>
            </tr>
        </table>

        <!-- Seção D - Endereço (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">D - ENDEREÇO</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">RESIDENCIAL</div>
                    <div class="mobile-field-value">{paciente_endereco}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CEP</div>
                    <div class="mobile-field-value">{paciente_cep}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">BAIRRO</div>
                    <div class="mobile-field-value">{paciente_bairro}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CIDADE</div>
                    <div class="mobile-field-value">{paciente_cidade}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">ESTADO</div>
                    <div class="mobile-field-value">{paciente_estado}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">TELEFONE 1</div>
                    <div class="mobile-field-value">{paciente_telefone1}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">TELEFONE 2</div>
                    <div class="mobile-field-value">{paciente_telefone2}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">EMAIL</div>
                    <div class="mobile-field-value">{paciente_email}</div>
                </div>
            </div>
        </div>

        <!-- Observação sobre tratamentos -->
        <div style="text-align: center; padding: 10px; border: 1px solid #000; margin-bottom: 20px;">
            {observacao_tratamentos}
        </div>

        <!-- Conteúdo do Contrato de Prestação de Serviços -->
        <div class="contract-content">
            <div class="clause">
                <div class="clause-title">1. PARTES</div>
                <div class="sub-clause">
                    <strong>1.1 Contratante (Paciente/Titular do Cartão):</strong> {paciente_nome}, CPF nº {paciente_cpf}, residente em {paciente_endereco}, {paciente_cidade}/{paciente_estado}.
                </div>
                <div class="sub-clause">
                    <strong>1.2 Contratada (Clínica/Provedora):</strong> {empresa_razao_social}, CNPJ nº {empresa_cnpj}, com sede à {empresa_endereco_completo}.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">2. OBJETO</div>
                <div class="clause-content">
                    <strong>2.1</strong> O presente contrato tem por objeto (i) a compra e venda pré-paga ou pós-paga de serviços odontológicos prestados nas unidades da Contratada e (ii) a disponibilização do benefício de telemedicina "Aki Mais Saúde" ao Contratante.
                </div>
                <div class="clause-content">
                    <strong>2.2</strong> Este instrumento não se caracteriza como plano ou seguro de saúde/odontológico e a Contratada não está vinculada à ANS – Agência Nacional de Saúde Suplementar.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">3. SERVIÇOS ODONTOLÓGICOS</div>
                <div class="clause-content">
                    <strong>3.1</strong> A Contratada prestará atendimentos clínicos e cirúrgicos, exames de diagnóstico e demais procedimentos listados a seguir, exclusivamente em suas unidades e por profissionais de seu corpo clínico:
                </div>

                <!-- Tabela de Serviços - Desktop -->
                <table class="services-table">
                    <tr>
                        <th colspan="3" class="section-header">TABELA DE SERVIÇOS ODONTOLÓGICOS</th>
                    </tr>
                    <tr>
                        <th style="width: 50%;">Procedimento</th>
                        <th style="width: 25%;">Valor de Referência (R$)</th>
                        <th style="width: 25%;">Observações</th>
                    </tr>
                        <tr>
                            <td>Avaliação inicial, raio-x e documentação</td>
                            <td class="price-cell">180,00</td>
                            <td>Inclui exame clínico completo</td>
                        </tr>
                        <tr>
                            <td>Profilaxia</td>
                            <td class="price-cell">180,00</td>
                            <td>—</td>
                        </tr>
                        <tr>
                            <td>Instalação de aparelho ortodôntico</td>
                            <td class="price-cell">60,00</td>
                            <td>Manutenções não incluídas</td>
                        </tr>
                        <tr>
                            <td>Restauração em resina (por dente)</td>
                            <td class="price-cell">35,00</td>
                            <td>—</td>
                        </tr>
                        <tr>
                            <td>Extração simples (por dente)</td>
                            <td class="price-cell">35,00</td>
                            <td>Terceiro molar excluído</td>
                        </tr>
                        <tr>
                            <td>Raspagem periodontal (por dente)</td>
                            <td class="price-cell">35,00</td>
                            <td>—</td>
                        </tr>
                </table>

                <!-- Tabela de Serviços - Mobile -->
                <div class="mobile-services">
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Avaliação inicial, raio-x e documentação</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 180,00</div>
                            <div>Inclui exame clínico completo</div>
                        </div>
                    </div>
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Profilaxia</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 180,00</div>
                        </div>
                    </div>
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Instalação de aparelho ortodôntico</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 60,00</div>
                            <div>Manutenções não incluídas</div>
                        </div>
                    </div>
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Restauração em resina (por dente)</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 35,00</div>
                        </div>
                    </div>
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Extração simples (por dente)</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 35,00</div>
                            <div>Terceiro molar excluído</div>
                        </div>
                    </div>
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Raspagem periodontal (por dente)</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 35,00</div>
                        </div>
                    </div>
                </div>

                <div class="clause-content">
                    <strong>3.2</strong> Procedimentos não listados na tabela acima terão desconto de até 50% sobre a tabela vigente da clínica odontológica.
                </div>
                <div class="clause-content">
                    <strong>3.3</strong> Procedimentos hospitalares, extrações de terceiros molares (siso) e tratamento endodôntico (canal) não estão cobertos e deverão ser contratados em instrumento específico, se houver interesse.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">4. BENEFÍCIO DE TELEMEDICINA "AKI MAIS SAÚDE"</div>
                <div class="clause-content">
                    <strong>4.1</strong> O Contratante terá acesso exclusivamente a consultas médicas por telemedicina, ilimitadas, mediante agendamento prévio na plataforma "Aki Mais Saúde".
                </div>
                <div class="clause-content">
                    <strong>4.2</strong> A utilização do benefício está condicionada à observância dos protocolos de agendamento e disponibilidade da rede de telemedicina.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">5. PAGAMENTO</div>
                <div class="clause-content">
                    <strong>5.1</strong> Planos Odontológicos – O Contratante pagará o valor total de <span class="highlight">R$ {valor_total_formatado}</span>, conforme as seguintes condições:
                    {clausula_pagamento_detalhada}
                </div>
                <div class="clause-content">
                    <strong>5.2</strong> O benefício de telemedicina "Aki Mais Saúde" é concedido gratuitamente, não acarretando cobrança de mensalidade ou taxa adicional ao Contratante.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">6. OBRIGAÇÕES DAS PARTES</div>
                <div class="sub-clause">
                    <strong>6.1 Da Contratada:</strong>
                    <ul>
                        <li>Prestar os serviços contratados com qualidade técnica e ética;</li>
                        <li>Garantir acesso ao benefício de telemedicina conforme este contrato;</li>
                        <li>Manter confidenciais os dados pessoais do Contratante, cumprindo integralmente a Lei 13.709/2018 (LGPD);</li>
                        <li>Fornecer suporte e informações sobre uso do benefício.</li>
                    </ul>
                </div>
                <div class="sub-clause">
                    <strong>6.2 Do Contratante:</strong>
                    <ul>
                        <li>Pagar pontualmente os valores devidos;</li>
                        <li>Cumprir orientações clínicas e utilizar os serviços de boa-fé;</li>
                        <li>Manter seus dados cadastrais atualizados;</li>
                        <li>Não ceder o cartão ou o acesso ao benefício a terceiros não autorizados.</li>
                    </ul>
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">7. VIGÊNCIA E CANCELAMENTO</div>
                <div class="clause-content">
                    <strong>7.1</strong> Este contrato entra em vigor na data de assinatura e permanecerá válido por 22 (vinte e dois) meses, renovando-se automaticamente por períodos iguais, salvo manifestação contrária de qualquer Parte com 30 (trinta) dias de antecedência.
                </div>
                <div class="clause-content">
                    <strong>7.2</strong> O Contratante poderá rescindir antecipadamente mediante solicitação escrita; será feito acerto de contas:
                    <ul>
                        <li>Se houver saldo a favor do Contratante, a Contratada restituirá a diferença;</li>
                        <li>Se houver saldo devedor, o Contratante deverá quitá-lo no ato da rescisão.</li>
                    </ul>
                </div>
                <div class="clause-content">
                    <strong>7.3</strong> O não pagamento por mais de 30 dias ensejará cancelamento automático deste instrumento e do benefício de telemedicina.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">8. RESPONSABILIDADES E LIMITAÇÕES</div>
                <div class="clause-content">
                    <strong>8.1</strong> A Contratada responde apenas por atendimentos realizados em suas unidades e por profissionais credenciados; procedimentos externos eximem-na de qualquer ônus.
                </div>
                <div class="clause-content">
                    <strong>8.2</strong> Este contrato não cria vínculo empregatício, societário ou associativo entre as Partes.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">9. CONFIDENCIALIDADE E PROTEÇÃO DE DADOS</div>
                <div class="clause-content">
                    <strong>9.1</strong> As Partes comprometem-se a guardar sigilo sobre quaisquer informações trocadas em razão deste contrato.
                </div>
                <div class="clause-content">
                    <strong>9.2</strong> A Contratada observa as disposições da LGPD, adotando medidas técnicas e administrativas aptas a proteger os dados pessoais aqui tratados.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">10. DISPOSIÇÕES GERAIS</div>
                <div class="clause-content">
                    <strong>10.1</strong> Alterações somente terão validade se formalizadas por aditivo escrito.
                </div>
                <div class="clause-content">
                    <strong>10.2</strong> A eventual tolerância de uma Parte à transgressão da outra não constituirá renúncia de direito ou novação.
                </div>
                <div class="clause-content">
                    <strong>10.3</strong> Se qualquer cláusula for considerada nula, as demais permanecerão em pleno vigor.
                </div>
            </div>

            {dependent_clause}

            <div class="clause">
                <div class="clause-title">11. FORO</div>
                <div class="clause-content">
                    Fica eleito o foro da Comarca de {cidade_contrato}, renunciando-se a qualquer outro, por mais privilegiado que seja, para dirimir controvérsias decorrentes deste contrato.
                </div>
            </div>
        </div>

        <!-- Data e Local -->
        <div style="text-align: center; margin: 30px 0;">
            <strong>{cidade_contrato}, {data_contrato}</strong>
        </div>

        <!-- Assinaturas -->
        <div class="signatures">
            <div class="signature-area">
                <div class="signature-box">
                    {signature_html}
                    <div class="signature-line"></div>
                    <div style="margin-top: 10px;"><strong>{paciente_nome}</strong><br>Contratante / Titular</div>
                </div>
                <div class="signature-box">
                    <div style="height: 80px;"></div>
                    <div class="signature-line"></div>
                    <div style="margin-top: 10px;"><strong>{empresa_razao_social}</strong><br>Representante Legal</div>
                </div>
            </div>

            <!-- Testemunhas -->
            <div style="margin-top: 40px;">
                <strong>TESTEMUNHAS:</strong>
                <div class="witness-area">
                    <div class="witness-box">
                        <div class="witness-line"></div>
                        <div>Testemunha 1 – Nome / CPF</div>
                    </div>
                    <div class="witness-box">
                        <div class="witness-line"></div>
                        <div>Testemunha 2 – Nome / CPF</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

def _prepare_dependent_header(dados: dict) -> str:
    """
    Prepara o cabeçalho de informações do dependente quando aplicável
    """
    if not dados.get('is_dependente_contract'):
        return ''
    
    return f"""
    <!-- Informações do Dependente -->
    <div style="background: #fff3cd; border: 2px solid #ffeaa7; padding: 15px; margin-bottom: 20px; border-radius: 8px;">
        <h3 style="color: #856404; margin-bottom: 10px;">⚠️ TRATAMENTO PARA DEPENDENTE</h3>
        <table style="width: 100%; border: none;">
            <tr>
                <td style="border: none; padding: 5px;"><strong>Paciente do Tratamento:</strong></td>
                <td style="border: none; padding: 5px; font-size: 14px; font-weight: bold;">{dados.get('dependente_nome', '')}</td>
                <td style="border: none; padding: 5px;"><strong>Data de Nascimento:</strong></td>
                <td style="border: none; padding: 5px;">{dados.get('dependente_data_nascimento', '')}</td>
            </tr>
            <tr>
                <td style="border: none; padding: 5px;"><strong>Parentesco:</strong></td>
                <td style="border: none; padding: 5px;">{dados.get('dependente_parentesco', '')}</td>
                <td style="border: none; padding: 5px;"><strong>CPF:</strong></td>
                <td style="border: none; padding: 5px;">{dados.get('dependente_cpf', 'Não informado')}</td>
            </tr>
            <tr>
                <td style="border: none; padding: 5px;"><strong>Responsável Financeiro:</strong></td>
                <td style="border: none; padding: 5px; font-weight: bold;">{dados.get('responsavel_nome', '')}</td>
                <td style="border: none; padding: 5px;"><strong>CPF Responsável:</strong></td>
                <td style="border: none; padding: 5px;">{dados.get('responsavel_cpf', '')}</td>
            </tr>
        </table>
        <p style="margin-top: 10px; color: #856404; font-size: 11px;">
            <strong>Importante:</strong> O contratante abaixo identificado é o responsável financeiro e legal pelo tratamento do dependente acima.
        </p>
    </div>
    """

def _prepare_dependent_clause(dados: dict) -> str:
    """
    Prepara cláusula específica para tratamento de dependentes
    """
    if not dados.get('is_dependente_contract'):
        return ''
    
    return """
    <div class="clause">
        <div class="clause-title">CLÁUSULA ESPECIAL - TRATAMENTO DE DEPENDENTE</div>
        <div class="clause-content">
            <p><strong>1.</strong> O CONTRATANTE/RESPONSÁVEL declara-se responsável legal pelo dependente acima identificado, autorizando a realização dos procedimentos odontológicos descritos neste contrato.</p>
            <p><strong>2.</strong> O CONTRATANTE assume todas as obrigações financeiras decorrentes do tratamento do dependente.</p>
            <p><strong>3.</strong> Em caso de menor de idade, o CONTRATANTE declara possuir autorização do outro genitor/responsável legal, quando aplicável.</p>
            <p><strong>4.</strong> O CONTRATANTE compromete-se a acompanhar o dependente nas consultas quando solicitado pela equipe odontológica.</p>
        </div>
    </div>
    """

def _generate_payment_clause(dados, defaults):
    """Gera cláusula de pagamento detalhada baseada nas condições da venda"""
    
    # Verificar se tem entrada
    valor_entrada = dados.get('valor_entrada', 0)
    valor_taxa_adesao = dados.get('valor_taxa_adesao', 0)
    tipo_cobranca_inicial = dados.get('tipo_cobranca_inicial', '')
    entrada_automatica = dados.get('entrada_automatica', False)
    percentual_desconto = dados.get('percentual_desconto_avista', 0)
    
    # Valores básicos
    valor_total = float(defaults.get('valor_total', 0))
    qtd_parcelas = int(defaults.get('qtd_parcelas', 1))
    valor_parcela = float(defaults.get('valor_parcela', 0))
    forma_pagamento = defaults.get('forma_pagamento', '')
    dia_vencimento = defaults.get('dia_vencimento', '10')
    
    clausula = []
    
    # Se tem desconto à vista
    if percentual_desconto > 0 and 'AVULSO' in forma_pagamento.upper():
        valor_com_desconto = valor_total * (1 - percentual_desconto / 100)
        valor_desconto = valor_total - valor_com_desconto
        valor_com_desconto_fmt = f"{valor_com_desconto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        valor_desconto_fmt = f"{valor_desconto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        clausula.append(f"""
            <ul>
                <li>Valor original: R$ {defaults['valor_total_formatado']}</li>
                <li>Desconto concedido ({percentual_desconto}%): R$ {valor_desconto_fmt}</li>
                <li><strong>Valor final à vista: R$ {valor_com_desconto_fmt}</strong></li>
                <li>Forma de pagamento: <span class="highlight">{forma_pagamento}</span></li>
            </ul>
        """)
    
    # Se tem taxa de adesão
    elif valor_taxa_adesao > 0:
        taxa_fmt = f"{valor_taxa_adesao:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        # Calcular valor restante e parcelas do carnê
        valor_restante = valor_total - valor_taxa_adesao
        valor_restante_fmt = f"{valor_restante:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        clausula.append(f"""
            <ul>
                <li><strong>Taxa de adesão (paga no ato):</strong> R$ {taxa_fmt}</li>
                <li><strong>Valor restante:</strong> R$ {valor_restante_fmt}</li>
                <li><strong>Parcelamento:</strong> {qtd_parcelas} parcelas mensais de R$ {defaults['valor_parcela_formatado']}</li>
                <li><strong>Vencimento:</strong> Todo dia {dia_vencimento} de cada mês</li>
                <li><strong>Forma de pagamento do carnê:</strong> {forma_pagamento}</li>
            </ul>
            <div style="margin-top: 10px; padding: 10px; background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px;">
                <strong>Observação:</strong> A taxa de adesão deve ser paga no ato da contratação. O carnê com as parcelas mensais iniciará no mês seguinte.
            </div>
        """)
    
    # Se tem entrada
    elif valor_entrada > 0:
        entrada_fmt = f"{valor_entrada:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        # Calcular valor restante e parcelas
        valor_restante = valor_total - valor_entrada
        qtd_parcelas_restantes = qtd_parcelas - 1 if qtd_parcelas > 1 else 1
        valor_parcela_recalc = valor_restante / qtd_parcelas_restantes if qtd_parcelas_restantes > 0 else valor_restante
        
        valor_restante_fmt = f"{valor_restante:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        valor_parcela_recalc_fmt = f"{valor_parcela_recalc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        tipo_entrada = "Entrada automática" if entrada_automatica else "Entrada"
        
        clausula.append(f"""
            <ul>
                <li><strong>{tipo_entrada}:</strong> R$ {entrada_fmt}</li>
                <li><strong>Valor restante:</strong> R$ {valor_restante_fmt}</li>
                <li><strong>Parcelamento:</strong> {qtd_parcelas_restantes} parcelas mensais de R$ {valor_parcela_recalc_fmt}</li>
                <li><strong>Vencimento:</strong> Todo dia {dia_vencimento} de cada mês</li>
                <li><strong>Forma de pagamento:</strong> {forma_pagamento}</li>
            </ul>
        """)
        
        if entrada_automatica:
            clausula.append("""
                <div style="margin-top: 10px; padding: 10px; background-color: #e3f2fd; border: 1px solid #90caf9; border-radius: 4px;">
                    <strong>Nota:</strong> A entrada foi calculada automaticamente com valor igual ao da parcela mensal.
                </div>
            """)
    
    # Pagamento padrão sem entrada/taxa
    else:
        clausula.append(f"""
            <ul>
                <li><strong>Número de parcelas:</strong> {qtd_parcelas} parcelas mensais</li>
                <li><strong>Valor da parcela:</strong> R$ {defaults['valor_parcela_formatado']}</li>
                <li><strong>Vencimento:</strong> Todo dia {dia_vencimento} de cada mês</li>
                <li><strong>Forma de pagamento:</strong> {forma_pagamento}</li>
            </ul>
        """)
    
    return ''.join(clausula)

def render_contract(dados: dict) -> str:
    """
    Renderiza o template do contrato com os dados fornecidos
    """
    # Preparar dependentes (até 5) - só adicionar se tiver dados
    dependentes_rows = ""
    dependentes_count = 0
    for i in range(1, 6):
        dependente_nome = dados.get(f'dependente_{i}_nome', '')
        dependente_cpf = dados.get(f'dependente_{i}_cpf', '')
        dependente_nascimento = dados.get(f'dependente_{i}_nascimento', '')
        
        # Só adicionar linha se tiver pelo menos o nome do dependente
        if dependente_nome and dependente_nome.strip():
            dependentes_count += 1
            dependentes_rows += f"""
            <tr>
                <td class="number-cell">{dependentes_count}</td>
                <td style="font-weight: bold;">NOME</td>
                <td style="font-weight: bold;">CPF</td>
                <td style="font-weight: bold;">DATA DE NASCIMENTO</td>
            </tr>
            <tr>
                <td></td>
                <td>{dependente_nome}</td>
                <td>{dependente_cpf}</td>
                <td>{dependente_nascimento}</td>
            </tr>
            """
    
    # Se não houver dependentes, adicionar uma linha indicando isso
    if not dependentes_rows:
        dependentes_rows = """
        <tr>
            <td colspan="4" style="text-align: center; font-style: italic; color: #666;">
                Nenhum dependente vinculado
            </td>
        </tr>
        """
    
    # Preparar dependentes para mobile
    dependentes_mobile = ""
    dependentes_mobile_count = 0
    for i in range(1, 6):
        dependente_nome = dados.get(f'dependente_{i}_nome', '')
        dependente_cpf = dados.get(f'dependente_{i}_cpf', '')
        dependente_nascimento = dados.get(f'dependente_{i}_nascimento', '')
        
        # Só adicionar se tiver pelo menos o nome
        if dependente_nome and dependente_nome.strip():
            dependentes_mobile_count += 1
            dependentes_mobile += f"""
            <div class="mobile-dependente">
                <div class="mobile-dependente-header">DEPENDENTE {dependentes_mobile_count}</div>
                <div class="mobile-dependente-content">
                    <div class="mobile-field">
                        <div class="mobile-field-label">NOME</div>
                        <div class="mobile-field-value">{dependente_nome}</div>
                    </div>
                    <div class="mobile-field">
                        <div class="mobile-field-label">CPF</div>
                        <div class="mobile-field-value">{dependente_cpf}</div>
                    </div>
                    <div class="mobile-field">
                        <div class="mobile-field-label">DATA DE NASCIMENTO</div>
                        <div class="mobile-field-value">{dependente_nascimento}</div>
                    </div>
                </div>
            </div>
            """
    
    # Se não houver dependentes mobile
    if not dependentes_mobile:
        dependentes_mobile = """
        <div style="text-align: center; font-style: italic; color: #666; padding: 20px;">
            Nenhum dependente vinculado
        </div>
        """
    
    # Processar produtos do odontograma
    produtos_table_desktop = ""
    produtos_table_mobile = ""
    
    produtos_odontograma = dados.get('produtos_odontograma', [])
    if produtos_odontograma:
        # Cabeçalho da tabela desktop
        produtos_table_desktop = """
        <table class="services-table">
            <tr>
                <th colspan="4" class="section-header">PROCEDIMENTOS DO ODONTOGRAMA</th>
            </tr>
            <tr>
                <th style="width: 50%;">Procedimento</th>
                <th style="width: 15%;">Dente/Face</th>
                <th style="width: 15%;">Qtd</th>
                <th style="width: 20%;">Valor (R$)</th>
            </tr>
        """
        
        # Cabeçalho mobile
        produtos_table_mobile = """
        <div class="mobile-card">
            <div class="mobile-card-header">PROCEDIMENTOS DO ODONTOGRAMA</div>
            <div class="mobile-card-content">
        """
        
        valor_total_produtos = 0.0
        
        for produto in produtos_odontograma:
            # Localização (dente/face)
            localizacao = ""
            if produto.get('dente'):
                localizacao = f"Dente {produto['dente']}"
                if produto.get('face'):
                    localizacao += f" - {produto['face']}"
            
            # Valor formatado
            valor_produto = float(produto.get('valor', 0))
            valor_total_produtos += valor_produto
            valor_formatado = f"{valor_produto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            # Desktop
            produtos_table_desktop += f"""
            <tr>
                <td>{produto.get('nome', '')}</td>
                <td>{localizacao}</td>
                <td style="text-align: center;">{produto.get('quantidade', 1)}</td>
                <td style="text-align: right;">R$ {valor_formatado}</td>
            </tr>
            """
            
            # Mobile
            produtos_table_mobile += f"""
            <div class="mobile-field" style="border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 10px;">
                <div class="mobile-field-label">PROCEDIMENTO</div>
                <div class="mobile-field-value" style="font-weight: bold;">{produto.get('nome', '')}</div>
                {f'<div class="mobile-field-label" style="margin-top: 5px;">LOCAL</div><div class="mobile-field-value">{localizacao}</div>' if localizacao else ''}
                <div style="display: flex; justify-content: space-between; margin-top: 5px;">
                    <div>
                        <div class="mobile-field-label">QUANTIDADE</div>
                        <div class="mobile-field-value">{produto.get('quantidade', 1)}</div>
                    </div>
                    <div style="text-align: right;">
                        <div class="mobile-field-label">VALOR</div>
                        <div class="mobile-field-value" style="font-weight: bold; color: #2c3e50;">R$ {valor_formatado}</div>
                    </div>
                </div>
            </div>
            """
        
        # Total geral
        valor_total_formatado_produtos = f"{valor_total_produtos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        # Adicionar linha de total na tabela desktop
        produtos_table_desktop += f"""
            <tr style="font-weight: bold; background-color: #f5f5f5;">
                <td colspan="3">VALOR TOTAL DOS PROCEDIMENTOS</td>
                <td style="text-align: right; font-size: 14px;">R$ {valor_total_formatado_produtos}</td>
            </tr>
        </table>
        """
        
        # Adicionar total no mobile
        produtos_table_mobile += f"""
                <div style="margin-top: 15px; padding-top: 15px; border-top: 2px solid #000;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: bold; font-size: 14px;">TOTAL DOS PROCEDIMENTOS:</span>
                        <span style="font-weight: bold; font-size: 16px; color: #2c3e50;">R$ {valor_total_formatado_produtos}</span>
                    </div>
                </div>
            </div>
        </div>
        """
    
    # Calcular valor por parcela
    valor_total = float(dados.get('valor_total', 0)) # Este é o valor total do contrato (ex: 1320)
    qtd_parcelas_frontend = int(dados.get('qtd_parcelas', 1)) # Parcelas enviadas pelo frontend (ex: 22)
    
    valor_base_contrato_frontend = dados.get('valor_base_contrato') # Valor da parcela/mensalidade enviado pelo frontend (ex: 60)
    
    # Verificar se é PIX ou Boleto avulso para forçar 1 parcela
    forma_pagamento = dados.get('forma_pagamento', '')
    if 'PIX AVULSO' in forma_pagamento or 'BOLETO AVULSO' in forma_pagamento:
        logger.info(f"📍 Pagamento avulso detectado ({forma_pagamento}) - forçando 1 parcela")
        qtd_parcelas_frontend = 1

    final_qtd_parcelas = qtd_parcelas_frontend
    final_valor_parcela = 0

    if valor_base_contrato_frontend is not None:
        # Se o frontend enviou 'valor_base_contrato', ele representa o valor da parcela/mensalidade.
        final_valor_parcela = float(valor_base_contrato_frontend)
        # O valor_total já deve ter sido calculado no frontend como valor_base_contrato * qtd_parcelas.
        # A qtd_parcelas do frontend é a correta.
        # Não é necessário recalcular valor_total aqui, assumimos que o frontend já fez isso.
        # Apenas garantimos que final_qtd_parcelas use o valor do frontend.
    else:
        # Lógica fallback se 'valor_base_contrato' não for enviado (comportamento antigo)
        # Isso pode acontecer para tipos de venda que não são contratos Akimais.
        if qtd_parcelas_frontend > 0:
            final_valor_parcela = valor_total / qtd_parcelas_frontend
        else:
            final_valor_parcela = valor_total
            final_qtd_parcelas = 1 # Garante que qtd_parcelas seja ao menos 1 se for 0 e não houver valor_base_contrato
    
    # Preparar HTML da assinatura se existir
    signature_html = ""
    if dados.get('assinatura_base64'):
        signature_html = f'<img src="{dados["assinatura_base64"]}" class="signature-image" alt="Assinatura do paciente" />'
    
    # Formatar valores monetários
    valor_total_formatado = f"{valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valor_parcela_formatado = f"{final_valor_parcela:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Preparar seções específicas para dependentes
    dependent_header = _prepare_dependent_header(dados)
    dependent_clause = _prepare_dependent_clause(dados)
    
    # Se for contrato de dependente, ajustar os dados do contratante
    if dados.get('is_dependente_contract'):
        # Para contratos de dependente, o CONTRATANTE na seção B deve ser o responsável (titular)
        # mas vamos manter o nome do dependente visível no cabeçalho amarelo
        contratante_nome = dados.get('paciente_nome', '')  # Responsável/Titular
        contratante_cpf = dados.get('paciente_cpf', '')
        contratante_data_nascimento = dados.get('paciente_data_nascimento', '')
        contratante_rg = dados.get('paciente_rg', '')
        
        # Adicionar indicação de que o tratamento é para o dependente
        observacao_tratamentos = f"TRATAMENTO PARA DEPENDENTE: {dados.get('dependente_nome', '')} - " + dados.get('observacao_tratamentos', 'CONFORME ORÇAMENTO APRESENTADO')
    else:
        # Contrato normal - usar dados do paciente
        contratante_nome = dados.get('paciente_nome', '')
        contratante_cpf = dados.get('paciente_cpf', '')
        contratante_data_nascimento = dados.get('paciente_data_nascimento', '')
        contratante_rg = dados.get('paciente_rg', '')
        observacao_tratamentos = dados.get('observacao_tratamentos', 'PACIENTE NÃO INFORMOU INTERESSE EM TRATAMENTOS')
    
    # Dados padrão se não fornecidos
    defaults = {
        'vendedor_nome': dados.get('vendedor_nome', 'VENDEDOR RESPONSÁVEL'),
        'empresa_razao_social': 'J&F ODONTOLOGIA 2016 LTDA',
        'empresa_cnpj': '24.476.639/0001-06',
        'empresa_cidade': 'Nova Iguaçu',
        'empresa_estado': 'RJ',
        'empresa_endereco_completo': 'Rua Otávio Tarquino Nº 173 - Centro - CEP: 26215-342',
        'numero_contrato': dados.get('numero_contrato', f"{datetime.now().strftime('%Y%m%d')}{dados.get('paciente_id', '00')}"),
        'paciente_nome': contratante_nome,
        'paciente_cpf': contratante_cpf,
        'paciente_data_nascimento': contratante_data_nascimento,
        'paciente_rg': contratante_rg,
        'paciente_orgao_expedidor': dados.get('paciente_orgao_expedidor', 'DETRAN'),
        'paciente_endereco': dados.get('endereco', '') or dados.get('paciente_endereco', ''),
        'paciente_cep': dados.get('paciente_cep', ''),
        'paciente_bairro': dados.get('paciente_bairro', ''),
        'paciente_cidade': dados.get('paciente_cidade', ''),
        'paciente_estado': dados.get('paciente_estado', ''),
        'paciente_telefone1': dados.get('paciente_telefone1', ''),
        'paciente_telefone2': dados.get('paciente_telefone2', ''),
        'paciente_email': dados.get('paciente_email', ''),
        'observacao_tratamentos': observacao_tratamentos,
        'valor_total': valor_total,
        'valor_total_formatado': valor_total_formatado, # ADICIONADO
        'qtd_parcelas': final_qtd_parcelas,
        'valor_parcela': final_valor_parcela,
        'valor_parcela_formatado': valor_parcela_formatado, # ADICIONADO
        'dia_vencimento': dados.get('dia_vencimento', '10'),
        'forma_pagamento': dados.get('forma_pagamento', 'BOLETO'),
        'cidade_contrato': dados.get('cidade_contrato', 'Rio de Janeiro'),
        'data_contrato': datetime.now().strftime("%d de %B de %Y").replace(
            'January', 'janeiro').replace('February', 'fevereiro').replace('March', 'março').replace(
            'April', 'abril').replace('May', 'maio').replace('June', 'junho').replace(
            'July', 'julho').replace('August', 'agosto').replace('September', 'setembro').replace(
            'October', 'outubro').replace('November', 'novembro').replace('December', 'dezembro'),
        'data_atual': datetime.now().strftime("%d de %B de %Y").replace(
            'January', 'janeiro').replace('February', 'fevereiro').replace('March', 'março').replace(
            'April', 'abril').replace('May', 'maio').replace('June', 'junho').replace(
            'July', 'julho').replace('August', 'agosto').replace('September', 'setembro').replace(
            'October', 'outubro').replace('November', 'novembro').replace('December', 'dezembro'),
        'dependentes_rows': dependentes_rows,
        'dependentes_mobile': dependentes_mobile,
        'signature_html': signature_html,
        'produtos_table_desktop': produtos_table_desktop,
        'produtos_table_mobile': produtos_table_mobile,
        'dependent_header': dependent_header,
        'dependent_clause': dependent_clause,
    }
    
    # Gerar cláusula de pagamento detalhada baseada nas condições
    clausula_pagamento_detalhada = _generate_payment_clause(dados, defaults)
    defaults['clausula_pagamento_detalhada'] = clausula_pagamento_detalhada
    
    return CONTRATO_AKIMAIS_TEMPLATE.format(**defaults)

# Manter o template antigo como backup
CONTRACT_TEMPLATE = CONTRATO_AKIMAIS_TEMPLATE

# =============================================================================
# TEMPLATES ESPECÍFICOS POR TIPO DE ODONTOGRAMA
# =============================================================================

# 1. Template para "Particular" (ID: 1)
TEMPLATE_PARTICULAR = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contrato de Prestação de Serviços Odontológicos</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0;
            padding: 20px;
            line-height: 1.4;
            background: white;
            font-size: 12px;
        }}
        
        .container {{
            max-width: 210mm;
            margin: 0 auto;
            background: white;
            padding: 20px;
        }}
        
        /* Header */
        .header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        
        .logo-area {{
            float: left;
            width: 100px;
            height: 80px;
            border: 1px solid #ccc;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f0f9f0;
            color: #4CAF50;
            font-weight: bold;
            font-size: 14px;
        }}
        
        .contract-title {{
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0;
            padding: 10px;
            border: 2px solid #000;
        }}
        
        .vendor-info {{
            float: right;
            text-align: right;
            font-size: 11px;
            margin-top: 10px;
        }}
        
        .clearfix {{ clear: both; }}
        
        /* Tables - Desktop */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
            border: 2px solid #000;
        }}
        
        th, td {{
            border: 1px solid #000;
            padding: 8px;
            text-align: left;
            vertical-align: top;
        }}
        
        th {{
            background-color: #f5f5f5;
            font-weight: bold;
            text-align: center;
        }}
        
        .section-header {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
        }}
        
        .number-cell {{
            width: 30px;
            text-align: center;
            font-weight: bold;
        }}
        
        /* Services table styles */
        .services-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            border: 2px solid #000;
        }}
        
        .services-table th {{
            background-color: #f5f5f5;
            font-weight: bold;
            text-align: center;
            padding: 10px;
            border: 1px solid #000;
        }}
        
        .services-table td {{
            padding: 8px;
            border: 1px solid #000;
        }}
        
        .price-cell {{
            text-align: right;
        }}
        
        /* Mobile-friendly card layout */
        .mobile-card {{
            display: none;
            border: 2px solid #000;
            margin-bottom: 15px;
            background: white;
        }}
        
        .mobile-card-header {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
            padding: 10px;
            border-bottom: 1px solid #000;
        }}
        
        .mobile-card-content {{
            padding: 15px;
        }}
        
        .mobile-field {{
            margin-bottom: 12px;
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
        }}
        
        .mobile-field:last-child {{
            border-bottom: none;
            margin-bottom: 0;
        }}
        
        .mobile-field-label {{
            font-weight: bold;
            color: #333;
            font-size: 11px;
            margin-bottom: 4px;
        }}
        
        .mobile-field-value {{
            font-size: 12px;
            color: #000;
        }}
        
        .mobile-dependente {{
            border: 1px solid #ccc;
            margin-bottom: 10px;
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .mobile-dependente-header {{
            background-color: #f5f5f5;
            padding: 8px;
            font-weight: bold;
            font-size: 11px;
            border-bottom: 1px solid #ccc;
        }}
        
        .mobile-dependente-content {{
            padding: 10px;
        }}
        
        /* Contract Content */
        .contract-content {{
            margin-top: 20px;
            text-align: justify;
            line-height: 1.6;
        }}
        
        .clause {{
            margin: 20px 0;
        }}
        
        .clause-title {{
            font-weight: bold;
            margin-bottom: 10px;
            font-size: 14px;
            color: #2c3e50;
        }}
        
        .clause-content {{
            margin: 10px 0;
            text-indent: 20px;
        }}
        
        .sub-clause {{
            margin: 8px 0 8px 20px;
        }}
        
        .highlight {{
            background-color: #ffffcc;
            padding: 2px 4px;
            font-weight: bold;
        }}
        
        /* Signatures */
        .signatures {{
            margin-top: 40px;
            page-break-inside: avoid;
        }}
        
        .signature-line {{
            border-bottom: 1px solid #000;
            margin: 30px 20px 5px 20px;
            text-align: center;
            font-weight: bold;
        }}
        
        .signature-area {{
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
        }}
        
        .signature-box {{
            width: 45%;
            text-align: center;
        }}
        
        .signature-image {{
            max-width: 100%;
            max-height: 80px;
            margin: 0 auto 10px auto;
            display: block;
        }}
        
        /* Print styles */
        @media print {{
            body {{ margin: 0; padding: 10px; }}
            .container {{ padding: 10px; }}
            .no-print {{ display: none; }}
            .mobile-card {{ display: none !important; }}
            table {{ display: table !important; }}
        }}
        
        /* Mobile responsiveness */
        @media (max-width: 768px) {{
            body {{ 
                padding: 10px; 
                font-size: 11px;
            }}
            
            .container {{ 
                padding: 10px; 
            }}
            
            .logo-area {{ 
                float: none; 
                margin: 0 auto 10px; 
                width: 80px;
                height: 60px;
                font-size: 12px;
            }}
            
            .vendor-info {{ 
                float: none; 
                text-align: center; 
                margin-top: 10px;
            }}
            
            .contract-title {{
                font-size: 14px;
                padding: 8px;
            }}
            
            /* Hide desktop tables on mobile */
            table {{
                display: none;
            }}
            
            /* Show mobile cards */
            .mobile-card {{
                display: block;
            }}
            
            .signature-area {{ 
                flex-direction: column; 
            }}
            
            .signature-box {{ 
                width: 100%; 
                margin-bottom: 20px; 
            }}
            
            .contract-content {{
                font-size: 11px;
                line-height: 1.4;
            }}
            
            .clause-title {{
                font-size: 12px;
            }}
            
            .highlight {{
                display: inline-block;
                margin: 2px 0;
            }}
        }}
        
        @media (max-width: 480px) {{
            body {{ 
                padding: 8px; 
                font-size: 10px;
            }}
            
            .container {{ 
                padding: 8px; 
            }}
            
            .mobile-card-content {{
                padding: 10px;
            }}
            
            .mobile-field {{
                margin-bottom: 8px;
            }}
            
            .logo-area {{
                width: 70px;
                height: 50px;
                font-size: 10px;
            }}
            
            .contract-title {{
                font-size: 12px;
                padding: 6px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            
            <div class="vendor-info">
                <strong>VENDEDOR:</strong><br>
                {vendedor_nome}<br>
                <strong>DATA:</strong> {data_contrato}
            </div>
            
            <div class="clearfix"></div>
            
            <div class="contract-title">
                CONTRATO DE PRESTAÇÃO DE<br>
                SERVIÇOS ODONTOLÓGICOS - PARTICULAR
            </div>
        </div>

        <!-- Informações do Dependente (se aplicável) -->
        {dependent_header}

        <!-- Seção A - CONTRATADA (Desktop) -->
        <table>
            <tr>
                <th class="section-header">A - CONTRATADA</th>
            </tr>
            <tr>
                <td>
                    Pelo presente Instrumento Particular, de um lado <strong>{empresa_razao_social}</strong>, inscrita no CNPJ/MF nº <strong>{empresa_cnpj}</strong>, com sede na cidade de {empresa_cidade} na {empresa_endereco_completo} a seguir denominada <strong>CONTRATADA</strong> e por outro lado, como <strong>CONTRATANTE</strong>, abaixo discriminado.
                </td>
            </tr>
        </table>

        <!-- Seção A - CONTRATADA (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">A - CONTRATADA</div>
            <div class="mobile-card-content">
                Pelo presente Instrumento Particular, de um lado <strong>{empresa_razao_social}</strong>, inscrita no CNPJ/MF nº <strong>{empresa_cnpj}</strong>, com sede na cidade de {empresa_cidade} na {empresa_endereco_completo} a seguir denominada <strong>CONTRATADA</strong> e por outro lado, como <strong>CONTRATANTE</strong>, abaixo discriminado.
            </div>
        </div>

        <!-- Seção B - CONTRATANTE (Desktop) -->
        <table>
            <tr>
                <th colspan="4" class="section-header">B - CONTRATANTE</th>
            </tr>
            <tr>
                <td colspan="2" style="width: 60%; font-weight: bold;">NOME</td>
                <td colspan="2" style="width: 40%; font-weight: bold;">DATA DE NASCIMENTO</td>
            </tr>
            <tr>
                <td colspan="2">{paciente_nome}</td>
                <td colspan="2">{paciente_data_nascimento}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">CPF</td>
                <td style="font-weight: bold;">RG</td>
                <td style="font-weight: bold;">ORGÃO EXPED</td>
                <td style="font-weight: bold;">CONTRATANTE INCLUSO</td>
            </tr>
            <tr>
                <td>{paciente_cpf}</td>
                <td>{paciente_rg}</td>
                <td>{paciente_orgao_expedidor}</td>
                <td>SIM</td>
            </tr>
        </table>

        <!-- Seção B - CONTRATANTE (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">B - CONTRATANTE</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">NOME</div>
                    <div class="mobile-field-value">{paciente_nome}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">DATA DE NASCIMENTO</div>
                    <div class="mobile-field-value">{paciente_data_nascimento}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CPF</div>
                    <div class="mobile-field-value">{paciente_cpf}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">RG</div>
                    <div class="mobile-field-value">{paciente_rg}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">ÓRGÃO EXPEDIDOR</div>
                    <div class="mobile-field-value">{paciente_orgao_expedidor}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CONTRATANTE INCLUSO</div>
                    <div class="mobile-field-value">SIM</div>
                </div>
            </div>
        </div>

        <!-- Seção C - CONTRATANTES Vinculados (Desktop) -->
        <table>
            <tr>
                <th colspan="4" class="section-header">C - CONTRATANTES VINCULADOS</th>
            </tr>
            {dependentes_rows}
        </table>

        <!-- Seção C - CONTRATANTES Vinculados (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">C - CONTRATANTES VINCULADOS</div>
            <div class="mobile-card-content">
                {dependentes_mobile}
            </div>
        </div>

        <!-- Seção D - Endereço (Desktop) -->
        <table>
            <tr>
                <th colspan="3" class="section-header">D - ENDEREÇO</th>
            </tr>
            <tr>
                <td colspan="2" style="font-weight: bold; width: 60%;">RESIDENCIAL</td>
                <td style="font-weight: bold; width: 40%;">CEP</td>
            </tr>
            <tr>
                <td colspan="2">{paciente_endereco}</td>
                <td>{paciente_cep}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">BAIRRO</td>
                <td style="font-weight: bold;">CIDADE</td>
                <td style="font-weight: bold;">ESTADO</td>
            </tr>
            <tr>
                <td>{paciente_bairro}</td>
                <td>{paciente_cidade}</td>
                <td>{paciente_estado}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">TEL 1</td>
                <td style="font-weight: bold;">TEL 2</td>
                <td style="font-weight: bold;">EMAIL</td>
            </tr>
            <tr>
                <td>{paciente_telefone1}</td>
                <td>{paciente_telefone2}</td>
                <td>{paciente_email}</td>
            </tr>
        </table>

        <!-- Seção D - Endereço (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">D - ENDEREÇO</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">RESIDENCIAL</div>
                    <div class="mobile-field-value">{paciente_endereco}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CEP</div>
                    <div class="mobile-field-value">{paciente_cep}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">BAIRRO</div>
                    <div class="mobile-field-value">{paciente_bairro}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CIDADE</div>
                    <div class="mobile-field-value">{paciente_cidade}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">ESTADO</div>
                    <div class="mobile-field-value">{paciente_estado}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">TELEFONE 1</div>
                    <div class="mobile-field-value">{paciente_telefone1}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">TELEFONE 2</div>
                    <div class="mobile-field-value">{paciente_telefone2}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">EMAIL</div>
                    <div class="mobile-field-value">{paciente_email}</div>
                </div>
            </div>
        </div>

        <!-- Observação sobre tratamentos -->
        <div style="text-align: center; padding: 10px; border: 1px solid #000; margin-bottom: 20px;">
            {observacao_tratamentos}
        </div>

        <!-- Tabela de Procedimentos do Odontograma -->
        {produtos_table_desktop}
        {produtos_table_mobile}

        <!-- Conteúdo do Contrato de Prestação de Serviços -->
        <div class="contract-content">
            <div class="clause">
                <div class="clause-title">CLÁUSULA PRIMEIRA – DAS PARTES</div>
                <div class="clause-content">
                    <strong>Contratante:</strong> {paciente_nome}, CPF nº {paciente_cpf}, responsável pelos pagamentos integrante deste contrato.
                </div>
                <div class="clause-content">
                    <strong>Contratada:</strong> {empresa_razao_social}, CNPJ nº {empresa_cnpj}, com sede à {empresa_endereco_completo}.
                </div>
                <div class="clause-content">
                    <strong>Paciente:</strong> {paciente_nome}, que recebeu avaliação de um profissional qualificado e que fará uso dos serviços apresentados no odontograma e descritos no presente contrato.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA SEGUNDA – OBJETO</div>
                <div class="clause-content">
                    Através deste contrato, a contratada prestará serviços odontológicos ao contratante.
                </div>
                <div class="clause-content">
                    <strong>Parágrafo único:</strong> Para fins de esclarecimento, fica expresso que o presente contrato de prestação de serviços não é plano de saúde, e nem de seguro saúde. Declara a contratada, neste ato, que não possui vínculo com a assistência de saúde e não está vinculada a ANS (Agência Nacional de Saúde Suplementar). Assim, o presente contrato trata somente da prestação de serviços odontológicos e forma de pagamento para o tratamento odontológico.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA TERCEIRA – DOS BENEFICIÁRIOS</div>
                <div class="clause-content">
                    O contratante será o responsável pelos pagamentos dos beneficiários que farão jus aos benefícios do tratamento estabelecidos.
                </div>
                <div class="clause-content">
                    <strong>Parágrafo único:</strong> Quando o contratante não for o paciente avaliado no odontograma, esse não fará jus aos benefícios do tratamento contratado.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA QUARTA – DO PAGAMENTO E PREÇO</div>
                <div class="clause-content">
                    O contratante pagará o valor total de <span class="highlight">R$ {valor_total_formatado}</span>, nas seguintes condições:
                    {clausula_pagamento_detalhada}
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO PRIMEIRO:</strong> O contratante se obriga a pagar a contratada pela compra expressa neste contrato nos valores e prazos determinados na venda.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO SEGUNDO:</strong> É opcional ao contratante o pagamento de entrada para reduzir o valor total a ser pago.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO TERCEIRO:</strong> A entrada pode ser paga em qualquer forma de pagamento aceita pela clínica.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO QUARTO:</strong> O contratante se responsabiliza pela informação de pagamentos não presenciais na clínica (depósitos, PIX, TED, DOC, e outros).
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO QUINTO:</strong> O vencimento de cada parcela será no intervalo sequencial de 30 (trinta) dias. Em caso de atrasos ou não pagamento, o paciente pode ter o atendimento suspenso até a regularização dos pagamentos.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA QUINTA – DAS CONDICIONAIS</div>
                <div class="clause-content">
                    O paciente só iniciará tratamento após pagar no mínimo 40% (quarenta por cento) do total dos serviços contratados.
                </div>
                <div class="clause-content">
                    Caso haja pagamento de entrada, no ato da contratação, o valor somará para cálculo do percentual.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA SEXTA – DA RESCISÃO CONTRATUAL</div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO PRIMEIRO:</strong> A rescisão contratual está condicionada a uma prévia avaliação do setor de atendimento ao cliente da unidade.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO SEGUNDO:</strong> A rescisão deve ser solicitada em condição formal e presencial na unidade, onde o contratante preencherá um termo de solicitação que será avaliado num prazo de 30 (trinta) dias após a solicitação.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO TERCEIRO:</strong> Em caso de estorno/devolução de valores, será feito atendimento que tem o prazo de 30 (trinta) dias para avaliação, resposta e estorno/devolução (caso seja aprovado).
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO QUARTO:</strong> O estorno/devolução de valores está condicionado aos serviços/materiais utilizados até o momento do requerimento assinado.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA SÉTIMA – DAS CONDIÇÕES GERAIS</div>
                <div class="clause-content">
                    O presente contrato resulta de consenso entre os pactuantes com relação ao seu conteúdo e forma.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA OITAVA – DO FORO</div>
                <div class="clause-content">
                    Este contrato é de natureza civil elegendo livremente as partes o foro da comarca de {cidade_contrato} para dirimir quaisquer dúvidas oriundas do presente instrumento com renúncia expressa de qualquer outro foro por mais privilégio que seja.
                </div>
            </div>
        </div>

        <!-- Data e Local -->
        <div style="text-align: center; margin: 30px 0;">
            <strong>{cidade_contrato}, {data_contrato}</strong>
        </div>

        <!-- Assinaturas -->
        <div class="signatures">
            <div class="signature-area">
                <div class="signature-box">
                    {signature_html}
                    <div class="signature-line"></div>
                    <div style="margin-top: 10px;"><strong>{paciente_nome}</strong><br>Contratante</div>
                </div>
                <div class="signature-box">
                    <div style="height: 80px;"></div>
                    <div class="signature-line"></div>
                    <div style="margin-top: 10px;"><strong>{empresa_razao_social}</strong><br>Contratada</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# 2. Template para "Ortodontia" (ID: 2)
TEMPLATE_ORTODONTIA = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contrato de Prestação de Serviços Ortodônticos</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0;
            padding: 20px;
            line-height: 1.4;
            background: white;
            font-size: 12px;
        }}
        
        .container {{
            max-width: 210mm;
            margin: 0 auto;
            background: white;
            padding: 20px;
        }}
        
        /* Header */
        .header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        
        .logo-area {{
            float: left;
            width: 100px;
            height: 80px;
            border: 1px solid #ccc;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f0f9f0;
            color: #4CAF50;
            font-weight: bold;
            font-size: 14px;
        }}
        
        .contract-title {{
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0;
            padding: 10px;
            border: 2px solid #000;
        }}
        
        .vendor-info {{
            float: right;
            text-align: right;
            font-size: 11px;
            margin-top: 10px;
        }}
        
        .clearfix {{ clear: both; }}
        
        /* Tables - Desktop */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
            border: 2px solid #000;
        }}
        
        th, td {{
            border: 1px solid #000;
            padding: 8px;
            text-align: left;
            vertical-align: top;
        }}
        
        th {{
            background-color: #f5f5f5;
            font-weight: bold;
            text-align: center;
        }}
        
        .section-header {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
        }}
        
        .number-cell {{
            width: 30px;
            text-align: center;
            font-weight: bold;
        }}
        
        /* Services table styles */
        .services-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            border: 2px solid #000;
        }}
        
        .services-table th {{
            background-color: #f5f5f5;
            font-weight: bold;
            text-align: center;
            padding: 10px;
            border: 1px solid #000;
        }}
        
        .services-table td {{
            padding: 8px;
            border: 1px solid #000;
        }}
        
        .price-cell {{
            text-align: right;
        }}
        
        /* Mobile-friendly card layout */
        .mobile-card {{
            display: none;
            border: 2px solid #000;
            margin-bottom: 15px;
            background: white;
        }}
        
        .mobile-card-header {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
            padding: 10px;
            border-bottom: 1px solid #000;
        }}
        
        .mobile-card-content {{
            padding: 15px;
        }}
        
        .mobile-field {{
            margin-bottom: 12px;
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
        }}
        
        .mobile-field:last-child {{
            border-bottom: none;
            margin-bottom: 0;
        }}
        
        .mobile-field-label {{
            font-weight: bold;
            color: #333;
            font-size: 11px;
            margin-bottom: 4px;
        }}
        
        .mobile-field-value {{
            font-size: 12px;
            color: #000;
        }}
        
        .mobile-dependente {{
            border: 1px solid #ccc;
            margin-bottom: 10px;
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .mobile-dependente-header {{
            background-color: #f5f5f5;
            padding: 8px;
            font-weight: bold;
            font-size: 11px;
            border-bottom: 1px solid #ccc;
        }}
        
        .mobile-dependente-content {{
            padding: 10px;
        }}
        
        /* Contract Content */
        .contract-content {{
            margin-top: 20px;
            text-align: justify;
            line-height: 1.6;
        }}
        
        .clause {{
            margin: 20px 0;
        }}
        
        .clause-title {{
            font-weight: bold;
            margin-bottom: 10px;
            font-size: 14px;
            color: #2c3e50;
        }}
        
        .clause-content {{
            margin: 10px 0;
            text-indent: 20px;
        }}
        
        .sub-clause {{
            margin: 8px 0 8px 20px;
        }}
        
        .highlight {{
            background-color: #ffffcc;
            padding: 2px 4px;
            font-weight: bold;
        }}
        
        /* Signatures */
        .signatures {{
            margin-top: 40px;
            page-break-inside: avoid;
        }}
        
        .signature-line {{
            border-bottom: 1px solid #000;
            margin: 30px 20px 5px 20px;
            text-align: center;
            font-weight: bold;
        }}
        
        .signature-area {{
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
        }}
        
        .signature-box {{
            width: 45%;
            text-align: center;
        }}
        
        .signature-image {{
            max-width: 100%;
            max-height: 80px;
            margin: 0 auto 10px auto;
            display: block;
        }}
        
        /* Print styles */
        @media print {{
            body {{ margin: 0; padding: 10px; }}
            .container {{ padding: 10px; }}
            .no-print {{ display: none; }}
            .mobile-card {{ display: none !important; }}
            table {{ display: table !important; }}
        }}
        
        /* Mobile responsiveness */
        @media (max-width: 768px) {{
            body {{ 
                padding: 10px; 
                font-size: 11px;
            }}
            
            .container {{ 
                padding: 10px; 
            }}
            
            .logo-area {{ 
                float: none; 
                margin: 0 auto 10px; 
                width: 80px;
                height: 60px;
                font-size: 12px;
            }}
            
            .vendor-info {{ 
                float: none; 
                text-align: center; 
                margin-top: 10px;
            }}
            
            .contract-title {{
                font-size: 14px;
                padding: 8px;
            }}
            
            /* Hide desktop tables on mobile */
            table {{
                display: none;
            }}
            
            /* Show mobile cards */
            .mobile-card {{
                display: block;
            }}
            
            .signature-area {{ 
                flex-direction: column; 
            }}
            
            .signature-box {{ 
                width: 100%; 
                margin-bottom: 20px; 
            }}
            
            .contract-content {{
                font-size: 11px;
                line-height: 1.4;
            }}
            
            .clause-title {{
                font-size: 12px;
            }}
            
            .highlight {{
                display: inline-block;
                margin: 2px 0;
            }}
        }}
        
        @media (max-width: 480px) {{
            body {{ 
                padding: 8px; 
                font-size: 10px;
            }}
            
            .container {{ 
                padding: 8px; 
            }}
            
            .mobile-card-content {{
                padding: 10px;
            }}
            
            .mobile-field {{
                margin-bottom: 8px;
            }}
            
            .logo-area {{
                width: 70px;
                height: 50px;
                font-size: 10px;
            }}
            
            .contract-title {{
                font-size: 12px;
                padding: 6px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            
            <div class="vendor-info">
                <strong>VENDEDOR:</strong><br>
                {vendedor_nome}<br>
                <strong>DATA:</strong> {data_atual}
            </div>
            
            <div class="clearfix"></div>
            
            <div class="contract-title">
                CONTRATO DE PRESTAÇÃO DE SERVIÇOS ORTODÔNTICOS<br>
                <span style="font-size: 14px;">Nº {numero_contrato}</span>
            </div>
        </div>

        <!-- Informações do Dependente (se aplicável) -->
        {dependent_header}

        <!-- Seção A - CONTRATADA (Desktop) -->
        <table>
            <tr>
                <th class="section-header">A - CONTRATADA</th>
            </tr>
            <tr>
                <td>
                    Pelo presente Instrumento Particular, de um lado <strong>{empresa_razao_social}</strong>, inscrita no CNPJ/MF nº <strong>{empresa_cnpj}</strong>, com sede na cidade de {empresa_cidade} na {empresa_endereco_completo} a seguir denominada <strong>CONTRATADA</strong> e por outro lado, como <strong>CONTRATANTE</strong>, abaixo discriminado.
                </td>
            </tr>
        </table>

        <!-- Seção A - CONTRATADA (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">A - CONTRATADA</div>
            <div class="mobile-card-content">
                Pelo presente Instrumento Particular, de um lado <strong>{empresa_razao_social}</strong>, inscrita no CNPJ/MF nº <strong>{empresa_cnpj}</strong>, com sede na cidade de {empresa_cidade} na {empresa_endereco_completo} a seguir denominada <strong>CONTRATADA</strong> e por outro lado, como <strong>CONTRATANTE</strong>, abaixo discriminado.
            </div>
        </div>

        <!-- Seção B - CONTRATANTE (Desktop) -->
        <table>
            <tr>
                <th colspan="4" class="section-header">B - CONTRATANTE</th>
            </tr>
            <tr>
                <td colspan="2" style="width: 60%; font-weight: bold;">NOME</td>
                <td colspan="2" style="width: 40%; font-weight: bold;">DATA DE NASCIMENTO</td>
            </tr>
            <tr>
                <td colspan="2">{paciente_nome}</td>
                <td colspan="2">{paciente_data_nascimento}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">CPF</td>
                <td style="font-weight: bold;">RG</td>
                <td style="font-weight: bold;">ORGÃO EXPED</td>
                <td style="font-weight: bold;">CONTRATANTE INCLUSO</td>
            </tr>
            <tr>
                <td>{paciente_cpf}</td>
                <td>{paciente_rg}</td>
                <td>{paciente_orgao_expedidor}</td>
                <td>SIM</td>
            </tr>
        </table>

        <!-- Seção B - CONTRATANTE (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">B - CONTRATANTE</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">NOME</div>
                    <div class="mobile-field-value">{paciente_nome}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">DATA DE NASCIMENTO</div>
                    <div class="mobile-field-value">{paciente_data_nascimento}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CPF</div>
                    <div class="mobile-field-value">{paciente_cpf}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">RG</div>
                    <div class="mobile-field-value">{paciente_rg}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">ÓRGÃO EXPEDIDOR</div>
                    <div class="mobile-field-value">{paciente_orgao_expedidor}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CONTRATANTE INCLUSO</div>
                    <div class="mobile-field-value">SIM</div>
                </div>
            </div>
        </div>

        <!-- Seção C - CONTRATANTES Vinculados (Desktop) -->
        <table>
            <tr>
                <th colspan="4" class="section-header">C - CONTRATANTES VINCULADOS</th>
            </tr>
            {dependentes_rows}
        </table>

        <!-- Seção C - CONTRATANTES Vinculados (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">C - CONTRATANTES VINCULADOS</div>
            <div class="mobile-card-content">
                {dependentes_mobile}
            </div>
        </div>

        <!-- Seção D - Endereço (Desktop) -->
        <table>
            <tr>
                <th colspan="3" class="section-header">D - ENDEREÇO</th>
            </tr>
            <tr>
                <td colspan="2" style="font-weight: bold; width: 60%;">RESIDENCIAL</td>
                <td style="font-weight: bold; width: 40%;">CEP</td>
            </tr>
            <tr>
                <td colspan="2">{paciente_endereco}</td>
                <td>{paciente_cep}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">BAIRRO</td>
                <td style="font-weight: bold;">CIDADE</td>
                <td style="font-weight: bold;">ESTADO</td>
            </tr>
            <tr>
                <td>{paciente_bairro}</td>
                <td>{paciente_cidade}</td>
                <td>{paciente_estado}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">TEL 1</td>
                <td style="font-weight: bold;">TEL 2</td>
                <td style="font-weight: bold;">EMAIL</td>
            </tr>
            <tr>
                <td>{paciente_telefone1}</td>
                <td>{paciente_telefone2}</td>
                <td>{paciente_email}</td>
            </tr>
        </table>

        <!-- Seção D - Endereço (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">D - ENDEREÇO</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">RESIDENCIAL</div>
                    <div class="mobile-field-value">{paciente_endereco}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CEP</div>
                    <div class="mobile-field-value">{paciente_cep}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">BAIRRO</div>
                    <div class="mobile-field-value">{paciente_bairro}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CIDADE</div>
                    <div class="mobile-field-value">{paciente_cidade}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">ESTADO</div>
                    <div class="mobile-field-value">{paciente_estado}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">TELEFONE 1</div>
                    <div class="mobile-field-value">{paciente_telefone1}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">TELEFONE 2</div>
                    <div class="mobile-field-value">{paciente_telefone2}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">EMAIL</div>
                    <div class="mobile-field-value">{paciente_email}</div>
                </div>
            </div>
        </div>

        <!-- Observação sobre tratamentos -->
        <div style="text-align: center; padding: 10px; border: 1px solid #000; margin-bottom: 20px;">
            {observacao_tratamentos}
        </div>

        <!-- Tabela de Procedimentos do Odontograma -->
        {produtos_table_desktop}
        {produtos_table_mobile}

        <!-- Conteúdo do Contrato de Prestação de Serviços Ortodônticos -->
        <div class="contract-content">
            <div class="clause">
                <div class="clause-title">CLÁUSULA PRIMEIRA – DAS PARTES</div>
                <div class="clause-content">
                    <strong>Contratante:</strong> {paciente_nome}, CPF nº {paciente_cpf}, responsável pelos pagamentos integrante deste contrato.
                </div>
                <div class="clause-content">
                    <strong>Contratada:</strong> {empresa_razao_social}, CNPJ nº {empresa_cnpj}, com sede à {empresa_endereco_completo}.
                </div>
                <div class="clause-content">
                    <strong>Paciente:</strong> {paciente_nome}, que recebeu avaliação ortodôntica de um profissional qualificado e que fará uso dos serviços ortodônticos descritos no presente contrato.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA SEGUNDA – OBJETO</div>
                <div class="clause-content">
                    Através deste contrato, a contratada prestará serviços ortodônticos ao contratante, incluindo:
                </div>
                <div class="sub-clause">
                    a) Diagnóstico e planejamento ortodôntico;<br>
                    b) Instalação de aparelho ortodôntico fixo;<br>
                    c) Manutenções mensais durante todo o período de tratamento;<br>
                    d) Remoção do aparelho ao final do tratamento;<br>
                    e) Confecção e instalação de contenção.
                </div>
                <div class="clause-content">
                    <strong>Parágrafo único:</strong> Para fins de esclarecimento, fica expresso que o presente contrato de prestação de serviços não é plano de saúde, e nem de seguro saúde. A contratada não possui vínculo com a assistência de saúde e não está vinculada a ANS (Agência Nacional de Saúde Suplementar).
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA TERCEIRA – DOS ESCLARECIMENTOS ORTODÔNTICOS</div>
                <div class="clause-content">
                    O paciente tem ciência que a ortodontia depende de fatores biológicos pertinentes a cada paciente, e não sendo uma ciência exata, <strong>não lhe é assegurada nenhuma garantia de sucesso</strong>. O resultado depende muito de um paciente cooperativo e que compareça a todas as manutenções mensais.
                </div>
                <div class="clause-content">
                    Um plano de tratamento será fornecido, porém está sujeito a alterações, uma vez que a resposta do organismo e padrão de crescimento são observados. Essas mudanças podem envolver extrações de dentes permanentes, cirurgia ortognática, instalação de mini-implante para tracionamento dentário, etc.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA QUARTA – DO PAGAMENTO E PREÇO</div>
                <div class="clause-content">
                    O contratante pagará o valor total de <span class="highlight">R$ {valor_total_formatado}</span>, dividido em <span class="highlight">{qtd_parcelas} parcelas</span> de <span class="highlight">R$ {valor_parcela_formatado}</span>, por <span class="highlight">{forma_pagamento}</span>.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO PRIMEIRO:</strong> O contratante se obriga a pagar a contratada pela compra expressa neste contrato nos valores e prazos determinados.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO SEGUNDO:</strong> As mensalidades deverão ser pagas independentemente da frequência do paciente no consultório. A primeira mensalidade deverá ser paga no início do tratamento.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO TERCEIRO:</strong> O aparelho ortodôntico convencional na forma de braquetes metálicos será instalado uma vez, em sua totalidade, sem custo adicional.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO QUARTO:</strong> Caso ocorra quebra de alguma peça ou seu descolamento, a mesma será reposta mediante cobrança conforme tabela vigente.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO QUINTO:</strong> O vencimento de cada parcela será no intervalo sequencial de 30 (trinta) dias. Em caso de atrasos ou não pagamento, o paciente pode ter o atendimento suspenso até a regularização dos pagamentos.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA QUINTA – DO ATENDIMENTO ORTODÔNTICO</div>
                <div class="clause-content">
                    O paciente será sempre atendido uma vez ao mês para realização da manutenção do aparelho. Quando houver algum problema com o aparelho ou dúvidas, o paciente poderá alterar o horário de sua consulta comunicando de preferência com 24 horas de antecedência.
                </div>
                <div class="clause-content">
                    O paciente que não comparecer à consulta ficará responsável por telefonar para remarcar nova consulta e receberá o atendimento o mais breve possível.
                </div>
                <div class="clause-content">
                    O paciente ou representante legal deverá comunicar a clínica por escrito, toda e qualquer alteração que ocorra em seu endereço, inclusive telefone.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA SEXTA – DA RESCISÃO CONTRATUAL</div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO PRIMEIRO:</strong> O paciente ou responsável pode a qualquer momento desistir do tratamento, devendo assinar Termo de Revogação. Será cobrada uma multa contratual no valor de <strong>R$ 200,00 (duzentos reais)</strong> referente ao aparelho ortodôntico instalado, materiais e honorários.
                </sub-clause>
                <div class="sub-clause">
                    <strong>PARÁGRAFO SEGUNDO:</strong> A rescisão deve ser solicitada em condição formal e presencial na unidade, onde o contratante preencherá um termo de solicitação que será avaliado num prazo de 30 (trinta) dias.
                </div>
                <div class="sub-clause">
                    <strong>PARÁGRAFO TERCEIRO:</strong> O paciente que se ausentar por 6 (seis) meses e não comunicar por escrito o motivo se responsabiliza por qualquer problema que venha ocorrer em decorrência da falta de manutenção.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA SÉTIMA – DAS CONTENÇÕES</div>
                <div class="clause-content">
                    A contenção é utilizada no final do tratamento ortodôntico, a fim de manter os dentes em suas novas posições. Os aparelhos de contenção superior e inferior terão custo conforme tabela vigente à época.
                </div>
                <div class="clause-content">
                    Após a colocação do aparelho de contenção, o paciente se obriga a retornar ao consultório no mínimo 6 (seis) vezes, sendo o intervalo entre as consultas pré determinado pelo cirurgião dentista.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">CLÁUSULA OITAVA – DO FORO</div>
                <div class="clause-content">
                    Este contrato é de natureza civil elegendo livremente as partes o foro da comarca de {cidade_contrato} para dirimir quaisquer dúvidas oriundas do presente instrumento com renúncia expressa de qualquer outro foro por mais privilégio que seja.
                </div>
            </div>
        </div>

        <!-- Data e Local -->
        <div style="text-align: center; margin: 30px 0;">
            <strong>{cidade_contrato}, {data_contrato}</strong>
        </div>

        <!-- Assinaturas -->
        <div class="signatures">
            <div class="signature-area">
                <div class="signature-box">
                    {signature_html}
                    <div class="signature-line"></div>
                    <div style="margin-top: 10px;"><strong>{paciente_nome}</strong><br>Contratante</div>
                </div>
                <div class="signature-box">
                    <div style="height: 80px;"></div>
                    <div class="signature-line"></div>
                    <div style="margin-top: 10px;"><strong>{empresa_razao_social}</strong><br>Contratada</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# 3. Template para "Contrato Odontológico + Akimais" (ID: 3) - Já existe como CONTRATO_AKIMAIS_TEMPLATE

# 4. Template para "Contrato Ortodôntico" (ID: 4)
TEMPLATE_CONTRATO_ORTODONTICO = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contrato de Prestação de Serviços Ortodônticos</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0;
            padding: 20px;
            line-height: 1.4;
            background: white;
            font-size: 12px;
        }}
        
        .container {{
            max-width: 210mm;
            margin: 0 auto;
            background: white;
            padding: 20px;
        }}
        
        /* Header */
        .header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        
        .logo-area {{
            float: left;
            width: 100px;
            height: 80px;
            border: 1px solid #ccc;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f0f9f0;
            color: #4CAF50;
            font-weight: bold;
            font-size: 14px;
        }}
        
        .contract-title {{
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0;
            padding: 10px;
            border: 2px solid #000;
        }}
        
        .vendor-info {{
            float: right;
            text-align: right;
            font-size: 11px;
            margin-top: 10px;
        }}
        
        .clearfix {{ clear: both; }}
        
        /* Tables - Desktop */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
            border: 2px solid #000;
        }}
        
        th, td {{
            border: 1px solid #000;
            padding: 8px;
            text-align: left;
            vertical-align: top;
        }}
        
        th {{
            background-color: #f5f5f5;
            font-weight: bold;
            text-align: center;
        }}
        
        .section-header {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
        }}
        
        .number-cell {{
            width: 30px;
            text-align: center;
            font-weight: bold;
        }}
        
        /* Services table styles */
        .services-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            border: 2px solid #000;
        }}
        
        .services-table th {{
            background-color: #f5f5f5;
            font-weight: bold;
            text-align: center;
            padding: 10px;
            border: 1px solid #000;
        }}
        
        .services-table td {{
            padding: 8px;
            border: 1px solid #000;
        }}
        
        .price-cell {{
            text-align: right;
        }}
        
        /* Mobile-friendly card layout */
        .mobile-card {{
            display: none;
            border: 2px solid #000;
            margin-bottom: 15px;
            background: white;
        }}
        
        .mobile-card-header {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
            padding: 10px;
            border-bottom: 1px solid #000;
        }}
        
        .mobile-card-content {{
            padding: 15px;
        }}
        
        .mobile-field {{
            margin-bottom: 12px;
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
        }}
        
        .mobile-field:last-child {{
            border-bottom: none;
            margin-bottom: 0;
        }}
        
        .mobile-field-label {{
            font-weight: bold;
            color: #333;
            font-size: 11px;
            margin-bottom: 4px;
        }}
        
        .mobile-field-value {{
            font-size: 12px;
            color: #000;
        }}
        
        /* Contract Content */
        .contract-content {{
            margin-top: 20px;
            text-align: justify;
            line-height: 1.6;
        }}
        
        .clause {{
            margin: 20px 0;
        }}
        
        .clause-title {{
            font-weight: bold;
            margin-bottom: 10px;
            font-size: 14px;
            color: #2c3e50;
        }}
        
        .clause-content {{
            margin: 10px 0;
            text-indent: 20px;
        }}
        
        .sub-clause {{
            margin: 8px 0 8px 20px;
        }}
        
        .highlight {{
            background-color: #ffffcc;
            padding: 2px 4px;
            font-weight: bold;
        }}
        
        /* Value Box */
        .value-box {{
            border: 2px solid #000;
            background: #f0f9f0;
            padding: 20px;
            margin: 20px 0;
            text-align: center;
        }}
        
        .value-box-title {{
            font-size: 14px;
            font-weight: bold;
            color: #4CAF50;
            margin-bottom: 10px;
        }}
        
        .value-box-amount {{
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
            margin: 10px 0;
        }}
        
        .value-box-details {{
            font-size: 13px;
            color: #333;
            margin: 5px 0;
        }}
        
        /* Signatures */
        .signatures {{
            margin-top: 40px;
            page-break-inside: avoid;
        }}
        
        .signature-line {{
            border-bottom: 1px solid #000;
            margin: 30px 20px 5px 20px;
            text-align: center;
            font-weight: bold;
        }}
        
        .signature-area {{
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
        }}
        
        .signature-box {{
            width: 45%;
            text-align: center;
        }}
        
        .signature-image {{
            max-width: 100%;
            max-height: 80px;
            margin: 0 auto 10px auto;
            display: block;
        }}
        
        /* Witness Area */
        .witness-area {{
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
        }}
        
        .witness-box {{
            width: 45%;
            text-align: center;
        }}
        
        .witness-line {{
            border-bottom: 1px solid #000;
            margin: 30px 0 5px 0;
        }}
        
        /* Print styles */
        @media print {{
            body {{ margin: 0; padding: 10px; }}
            .container {{ padding: 10px; }}
            .no-print {{ display: none; }}
            .mobile-card {{ display: none !important; }}
            table {{ display: table !important; }}
        }}
        
        /* Mobile responsiveness */
        @media (max-width: 768px) {{
            body {{ 
                padding: 10px; 
                font-size: 11px;
            }}
            
            .container {{ 
                padding: 10px; 
            }}
            
            .logo-area {{ 
                float: none; 
                margin: 0 auto 10px; 
                width: 80px;
                height: 60px;
                font-size: 12px;
            }}
            
            .vendor-info {{ 
                float: none; 
                text-align: center; 
                margin-top: 10px;
            }}
            
            .contract-title {{
                font-size: 14px;
                padding: 8px;
            }}
            
            /* Hide desktop tables on mobile */
            table {{
                display: none;
            }}
            
            /* Show mobile cards on mobile */
            .mobile-card {{
                display: block;
            }}
            
            .signature-area, .witness-area {{
                flex-direction: column;
            }}
            
            .signature-box, .witness-box {{
                width: 100%;
                margin-bottom: 30px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
    
        <!-- Header -->
        <div class="header">

            <div class="vendor-info">
                <strong>VENDEDOR:</strong><br>
                {vendedor_nome}<br>
                <strong>DATA:</strong> {data_contrato}
            </div>
            <div class="clearfix"></div>
        </div>

        <!-- Título do Contrato -->
        <div class="contract-title">
            CONTRATO DE PRESTAÇÃO DE SERVIÇOS ORTODÔNTICOS<br>
            <span style="font-size: 14px;">Nº {numero_contrato}</span>
        </div>

        <!-- Informações do Dependente (se aplicável) -->
        {dependent_header}

        <!-- Seção A - Dados Pessoais (Desktop) -->
        <table>
            <tr>
                <th colspan="4" class="section-header">A - DADOS PESSOAIS</th>
            </tr>
            <tr>
                <td style="font-weight: bold; width: 25%;">NOME COMPLETO</td>
                <td colspan="3">{paciente_nome}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">CPF</td>
                <td>{paciente_cpf}</td>
                <td style="font-weight: bold;">RG</td>
                <td>{paciente_rg} - {paciente_orgao_expedidor}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">DATA DE NASCIMENTO</td>
                <td>{paciente_data_nascimento}</td>
                <td style="font-weight: bold;">TELEFONE</td>
                <td>{paciente_telefone1}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">EMAIL</td>
                <td colspan="3">{paciente_email}</td>
            </tr>
        </table>

        <!-- Seção A - Dados Pessoais (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">A - DADOS PESSOAIS</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">NOME COMPLETO</div>
                    <div class="mobile-field-value">{paciente_nome}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CPF</div>
                    <div class="mobile-field-value">{paciente_cpf}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">RG</div>
                    <div class="mobile-field-value">{paciente_rg} - {paciente_orgao_expedidor}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">DATA DE NASCIMENTO</div>
                    <div class="mobile-field-value">{paciente_data_nascimento}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">TELEFONE</div>
                    <div class="mobile-field-value">{paciente_telefone1}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">EMAIL</div>
                    <div class="mobile-field-value">{paciente_email}</div>
                </div>
            </div>
        </div>

        <!-- Seção B - Endereço (Desktop) -->
        <table>
            <tr>
                <th colspan="3" class="section-header">B - ENDEREÇO</th>
            </tr>
            <tr>
                <td colspan="2" style="font-weight: bold; width: 60%;">RESIDENCIAL</td>
                <td style="font-weight: bold; width: 40%;">CEP</td>
            </tr>
            <tr>
                <td colspan="2">{paciente_endereco}</td>
                <td>{paciente_cep}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">BAIRRO</td>
                <td style="font-weight: bold;">CIDADE</td>
                <td style="font-weight: bold;">ESTADO</td>
            </tr>
            <tr>
                <td>{paciente_bairro}</td>
                <td>{paciente_cidade}</td>
                <td>{paciente_estado}</td>
            </tr>
        </table>

        <!-- Seção B - Endereço (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">B - ENDEREÇO</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">RESIDENCIAL</div>
                    <div class="mobile-field-value">{paciente_endereco}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CEP</div>
                    <div class="mobile-field-value">{paciente_cep}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">BAIRRO</div>
                    <div class="mobile-field-value">{paciente_bairro}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CIDADE</div>
                    <div class="mobile-field-value">{paciente_cidade}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">ESTADO</div>
                    <div class="mobile-field-value">{paciente_estado}</div>
                </div>
            </div>
        </div>

        <!-- Seção C - Contratada -->
        <table>
            <tr>
                <th colspan="2" class="section-header">C - CONTRATADA</th>
            </tr>
            <tr>
                <td style="font-weight: bold; width: 30%;">RAZÃO SOCIAL</td>
                <td>{empresa_razao_social}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">CNPJ</td>
                <td>{empresa_cnpj}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">ENDEREÇO</td>
                <td>{empresa_endereco_completo}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">CIDADE/ESTADO</td>
                <td>{empresa_cidade}/{empresa_estado}</td>
            </tr>
        </table>

        <!-- Seção C - Contratada (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">C - CONTRATADA</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">RAZÃO SOCIAL</div>
                    <div class="mobile-field-value">{empresa_razao_social}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CNPJ</div>
                    <div class="mobile-field-value">{empresa_cnpj}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">ENDEREÇO</div>
                    <div class="mobile-field-value">{empresa_endereco_completo}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CIDADE/ESTADO</div>
                    <div class="mobile-field-value">{empresa_cidade}/{empresa_estado}</div>
                </div>
            </div>
        </div>

    <div class="clause">
        <div class="clause-title">CLÁUSULA PRIMEIRA - DOS ESCLARECIMENTOS GERAIS</div>
        <p>O paciente tem ciência que a odontologia depende de fatores biológicos pertinentes a cada paciente, e não sendo uma ciência exata, <strong>não lhe é assegurada nenhuma garantia de sucesso</strong>, e que o resultado depende muito de um paciente cooperativo e que compareça a todas as manutenções mensais.</p>
        <p>Um plano de tratamento será fornecido, porém está sujeito a alterações, uma vez que a resposta do organismo e padrão de crescimento são observados. Essas mudanças podem envolver extrações de dentes permanentes, cirurgia ortognática, instalação de mini-implante para tracionamento dentário, etc. Esses procedimentos deverão ser realizados pela clínica/cirurgião dentista de sua escolha sob solicitação por escrito.</p>
    </div>

    <div class="clause">
        <div class="clause-title">CLÁUSULA SEGUNDA - DO OBJETO E ATENDIMENTO</div>
        <p>O presente contrato tem por objeto a prestação de serviços ortodônticos, autorizando antecipadamente o paciente ou representante legal a clínica sob supervisão do cirurgião dentista a realizar seu tratamento ortodôntico, tendo em vista que este foi elaborado na avaliação do questionário de anamnese geral e odontológico, dos exames clínicos e radiográficos.</p>
        <div class="sub-clause">
            a) O paciente será sempre atendido uma vez ao mês para realização da manutenção do aparelho;<br>
            b) Quando houver algum problema com o aparelho ou dúvidas, o paciente poderá alterar o horário de sua consulta comunicando de preferência com 24 horas de antecedência;<br>
            c) O paciente que não comparecer à consulta ficará responsável por telefonar para remarcar nova consulta;<br>
            d) O paciente ou representante legal deverá comunicar a clínica por escrito, toda e qualquer alteração que ocorra em seu endereço, inclusive telefone.
        </div>
    </div>

    <div class="clause">
        <div class="clause-title">CLÁUSULA TERCEIRA - DOS EXAMES COMPLEMENTARES</div>
        <p>O paciente necessitará de exames complementares para um correto diagnóstico e plano de tratamento. O tratamento não será iniciado e nem continuado sem a realização dos mesmos. O paciente tem o direito de fazer o exame no seu local de escolha.</p>
        <p>Com a evolução do tratamento do paciente, caso o dentista veja a necessidade de novos exames como radiografia cefalométrica com traçado e moldes de gesso, ele os solicitará para que o paciente tenha um correto tratamento. Esses exames podem ser realizados na contratada, caso o paciente opte, e o valor será de acordo com a tarifa vigente.</p>
    </div>

    <div class="clause">
        <div class="clause-title">CLÁUSULA QUARTA - DO VALOR E FORMA DE PAGAMENTO</div>
        
        <p>O valor total do tratamento ortodôntico é de <span class="highlight">R$ {valor_total_formatado}</span>, nas seguintes condições:</p>
        
        {clausula_pagamento_detalhada}
        
        <!-- Seção de Valores (Desktop) -->
        <table style="margin: 20px 0;">
            <tr>
                <th colspan="2" class="section-header">RESUMO DO PAGAMENTO</th>
            </tr>
            <tr>
                <td style="font-weight: bold; width: 40%;">VALOR TOTAL DO TRATAMENTO</td>
                <td style="text-align: center; font-size: 18px; font-weight: bold; color: #2c3e50;">R$ {valor_total_formatado}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">FORMA DE PAGAMENTO</td>
                <td style="text-align: center;">{forma_pagamento}</td>
            </tr>
        </table>
        
        <!-- Seção de Valores (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">RESUMO DO PAGAMENTO</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">VALOR TOTAL DO TRATAMENTO</div>
                    <div class="mobile-field-value" style="font-size: 18px; font-weight: bold; color: #2c3e50;">R$ {valor_total_formatado}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">FORMA DE PAGAMENTO</div>
                    <div class="mobile-field-value">{forma_pagamento}</div>
                </div>
            </div>
        </div>
        <p>O valor do tratamento proposto será reajustado anualmente conforme o índice do IGP-M medido pela Fundação Getúlio Vargas ou outro índice que venha a substituí-lo.</p>
        <div class="sub-clause">
            1. As mensalidades deverão ser pagas independentemente da frequência do paciente no consultório. A primeira mensalidade deverá ser paga no início do tratamento;<br>
            2. O aparelho ortodôntico convencional na forma de braquetes metálicos será instalado uma vez, em sua totalidade, sem custo adicional;<br>
            3. Caso ocorra quebra de alguma peça ou seu descolamento, a mesma será reposta pela clínica no valor de acordo com a tabela vigente por peça (braquetes, bandas ou tubos);<br>
            4. Cirurgias e outros tratamentos clínicos <strong>NÃO</strong> estão incluídos no tratamento aqui proposto.
        </div>
    </div>

    <div class="clause">
        <div class="clause-title">CLÁUSULA QUINTA - DA INTERRUPÇÃO DO TRATAMENTO</div>
        <p>O paciente ou responsável pode a qualquer momento desistir do tratamento, devendo avisar com antecedência, bastando para tanto que comunique sua decisão ao seu dentista e assine o Termo de Revogação. Será cobrada uma multa contratual no valor de <strong>R$ 200,00 (duzentos reais)</strong> referente ao gasto com o aparelho ortodôntico que foi instalado sem custo, outros materiais e honorários.</p>
        <p>O paciente que não apresentar assiduidade às consultas, não mantiver uma higiene bucal correta, provocar quebras constantes em seu aparelho, terá seu tratamento replanejado junto ao responsável para uma continuidade ou não do mesmo.</p>
        <p>O paciente que se ausentar por 6 (seis) meses e não comunicar por escrito o motivo se responsabiliza por qualquer problema que venha ocorrer em decorrência da falta de manutenção, isentando automaticamente o cirurgião dentista de qualquer responsabilidade por problemas que venham a ocorrer.</p>
    </div>

    <div class="clause">
        <div class="clause-title">CLÁUSULA SEXTA - DO FINAL DE TRATAMENTO E CONTENÇÕES</div>
        <p>Em casos de término ou desistência do tratamento, o paciente não deverá em hipótese alguma continuar fazendo uso de qualquer aparato ortodôntico ou ortopédico instalado pela clínica, visto que estará sem o acompanhamento do cirurgião dentista que o planejou e instalou.</p>
        <p>A contenção é utilizada no final do tratamento ortodôntico, a fim de manter os dentes em suas novas posições até que se complete a formação do novo tecido ósseo em torno dos mesmos. Sem o uso apropriado da contenção, os dentes tenderão a se mover para suas posições originais.</p>
        <p>Os aparelhos de contenção superior e inferior terão o custo no valor da tabela vigente na época, cada um. Após a colocação do aparelho de contenção, o paciente se obriga a retornar ao consultório no mínimo 6 (seis) vezes, sendo o intervalo entre as consultas pré determinado pelo cirurgião dentista.</p>
    </div>

    <div class="clause">
        <div class="clause-title">CLÁUSULA SÉTIMA - DAS OBRIGAÇÕES DAS PARTES</div>
        <p><strong>São obrigações do CONTRATANTE:</strong></p>
        <div class="sub-clause">
            a) Comparecer pontualmente às consultas agendadas;<br>
            b) Seguir rigorosamente as orientações do profissional;<br>
            c) Manter adequada higiene bucal;<br>
            d) Efetuar os pagamentos nas datas acordadas;<br>
            e) Comunicar imediatamente quebras ou problemas com o aparelho.
        </div>
        <p><strong>São obrigações da CONTRATADA:</strong></p>
        <div class="sub-clause">
            a) Prestar os serviços com zelo e competência profissional;<br>
            b) Disponibilizar horários para atendimento mensal;<br>
            c) Fornecer todas as orientações necessárias;<br>
            d) Utilizar materiais de qualidade comprovada;<br>
            e) Manter o prontuário atualizado.
        </div>
    </div>

    <div class="clause">
        <div class="clause-title">CLÁUSULA OITAVA - DO FORO</div>
        <p>As partes elegem o foro da Comarca de {cidade_contrato} - {paciente_estado} para eliminar quaisquer dúvidas oriundas deste documento, renunciando, desde já, qualquer outro por mais privilegiado que seja.</p>
    </div>

        <!-- Data e Local -->
        <div style="text-align: center; margin: 30px 0;">
            <strong>{cidade_contrato}, {data_contrato}</strong>
        </div>

        <!-- Assinaturas -->
        <div class="signatures">
            <div class="signature-area">
                <div class="signature-box">
                    {signature_html}
                    <div class="signature-line"></div>
                    <div style="margin-top: 10px;"><strong>{paciente_nome}</strong><br>Contratante</div>
                </div>
                <div class="signature-box">
                    <div style="height: 80px;"></div>
                    <div class="signature-line"></div>
                    <div style="margin-top: 10px;"><strong>{empresa_razao_social}</strong><br>Contratada</div>
                </div>
            </div>

            <!-- Testemunhas -->
            <div style="margin-top: 40px;">
                <strong>TESTEMUNHAS:</strong>
                <div class="witness-area">
                    <div class="witness-box">
                        <div class="witness-line"></div>
                        <div>Testemunha 1 – Nome / CPF</div>
                    </div>
                    <div class="witness-box">
                        <div class="witness-line"></div>
                        <div>Testemunha 2 – Nome / CPF</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# 5. Template para "Combo Orto + ODC" (ID: 5)
TEMPLATE_COMBO_ORTO_ODC = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contrato Combo - Tratamentos Gerais + Ortodontia + Telemedicina</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 0;
            padding: 20px;
            line-height: 1.4;
            background: white;
            font-size: 12px;
        }}
        
        .container {{
            max-width: 210mm;
            margin: 0 auto;
            background: white;
            padding: 20px;
        }}
        
        /* Header */
        .header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        
        .logo-area {{
            float: left;
            width: 100px;
            height: 80px;
            border: 1px solid #ccc;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f0f9f0;
            color: #4CAF50;
            font-weight: bold;
            font-size: 14px;
        }}
        
        .contract-title {{
            text-align: center;
            font-weight: bold;
            font-size: 16px;
            margin: 20px 0;
            padding: 10px;
            border: 2px solid #000;
        }}
        
        .vendor-info {{
            float: right;
            text-align: right;
            font-size: 11px;
            margin-top: 10px;
        }}
        
        .clearfix {{ clear: both; }}
        
        /* Tables - Desktop */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
            border: 2px solid #000;
        }}
        
        th, td {{
            border: 1px solid #000;
            padding: 8px;
            text-align: left;
            vertical-align: top;
        }}
        
        th {{
            background-color: #f5f5f5;
            font-weight: bold;
            text-align: center;
        }}
        
        .section-header {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
        }}
        
        .number-cell {{
            width: 30px;
            text-align: center;
            font-weight: bold;
        }}
        
        /* Services Table Styles */
        .services-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
            border: 2px solid #000;
        }}
        
        .services-table th {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
            padding: 8px;
            border: 1px solid #000;
        }}
        
        .services-table td {{
            border: 1px solid #000;
            padding: 8px;
            text-align: left;
            vertical-align: top;
        }}
        
        .services-table .price-cell {{
            text-align: center;
            font-weight: bold;
        }}
        
        /* Mobile-friendly card layout */
        .mobile-card {{
            display: none;
            border: 2px solid #000;
            margin-bottom: 15px;
            background: white;
        }}
        
        .mobile-card-header {{
            background-color: #e0e0e0;
            font-weight: bold;
            text-align: center;
            font-size: 13px;
            padding: 10px;
            border-bottom: 1px solid #000;
        }}
        
        .mobile-card-content {{
            padding: 15px;
        }}
        
        .mobile-field {{
            margin-bottom: 12px;
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
        }}
        
        .mobile-field:last-child {{
            border-bottom: none;
            margin-bottom: 0;
        }}
        
        .mobile-field-label {{
            font-weight: bold;
            color: #333;
            font-size: 11px;
            margin-bottom: 4px;
        }}
        
        .mobile-field-value {{
            font-size: 12px;
            color: #000;
        }}
        
        .mobile-dependente {{
            border: 1px solid #ccc;
            margin-bottom: 10px;
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .mobile-dependente-header {{
            background-color: #f5f5f5;
            padding: 8px;
            font-weight: bold;
            font-size: 11px;
            border-bottom: 1px solid #ccc;
        }}
        
        .mobile-dependente-content {{
            padding: 10px;
        }}
        
        /* Mobile Services Table */
        .mobile-services {{
            display: none;
        }}
        
        .mobile-service-item {{
            border: 1px solid #333;
            margin-bottom: 10px;
            border-radius: 5px;
            overflow: hidden;
        }}
        
        .mobile-service-header {{
            background: #4CAF50;
            color: white;
            padding: 10px;
            font-weight: bold;
        }}
        
        .mobile-service-content {{
            padding: 10px;
            background: white;
        }}
        
        .mobile-service-price {{
            font-weight: bold;
            color: #2c3e50;
            font-size: 16px;
            margin-bottom: 5px;
        }}
        
        /* Contract Content */
        .contract-content {{
            margin-top: 20px;
            text-align: justify;
            line-height: 1.6;
        }}
        
        .clause {{
            margin: 20px 0;
        }}
        
        .clause-title {{
            font-weight: bold;
            margin-bottom: 10px;
            font-size: 14px;
            color: #2c3e50;
        }}
        
        .clause-content {{
            margin: 10px 0;
            text-indent: 20px;
        }}
        
        .sub-clause {{
            margin: 8px 0 8px 20px;
        }}
        
        .highlight {{
            background-color: #ffffcc;
            padding: 2px 4px;
            font-weight: bold;
        }}
        
        /* Signatures */
        .signatures {{
            margin-top: 40px;
            page-break-inside: avoid;
        }}
        
        .signature-line {{
            border-bottom: 1px solid #000;
            margin: 30px 20px 5px 20px;
            text-align: center;
            font-weight: bold;
        }}
        
        .signature-area {{
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
        }}
        
        .signature-box {{
            width: 45%;
            text-align: center;
        }}
        
        .signature-image {{
            max-width: 100%;
            max-height: 80px;
            margin: 0 auto 10px auto;
            display: block;
        }}
        
        .witness-area {{
            display: flex;
            justify-content: space-between;
            margin-top: 40px;
        }}
        
        .witness-box {{
            width: 45%;
        }}
        
        .witness-line {{
            border-bottom: 1px solid #000;
            margin: 20px 0 5px 0;
        }}
        
        /* Print styles */
        @media print {{
            body {{ margin: 0; padding: 10px; }}
            .container {{ padding: 10px; }}
            .no-print {{ display: none; }}
            .mobile-card {{ display: none !important; }}
            .mobile-services {{ display: none !important; }}
            table {{ display: table !important; }}
            .services-table {{ display: table !important; }}
        }}
        
        /* Mobile responsiveness */
        @media (max-width: 768px) {{
            body {{ 
                padding: 10px; 
                font-size: 11px;
            }}
            
            .container {{ 
                padding: 10px; 
            }}
            
            .logo-area {{ 
                float: none; 
                margin: 0 auto 10px; 
                width: 80px;
                height: 60px;
                font-size: 12px;
            }}
            
            .vendor-info {{ 
                float: none; 
                text-align: center; 
                margin-top: 10px;
            }}
            
            .contract-title {{
                font-size: 14px;
                padding: 8px;
            }}
            
            /* Hide desktop tables on mobile */
            table {{
                display: none;
            }}
            
            .services-table {{
                display: none;
            }}
            
            /* Show mobile cards */
            .mobile-card {{
                display: block;
            }}
            
            .mobile-services {{
                display: block;
            }}
            
            .signature-area, .witness-area {{ 
                flex-direction: column; 
            }}
            
            .signature-box, .witness-box {{ 
                width: 100%; 
                margin-bottom: 20px; 
            }}
            
            .contract-content {{
                font-size: 11px;
                line-height: 1.4;
            }}
            
            .clause-title {{
                font-size: 12px;
            }}
            
            .highlight {{
                display: inline-block;
                margin: 2px 0;
            }}
        }}
        
        @media (max-width: 480px) {{
            body {{ 
                padding: 8px; 
                font-size: 10px;
            }}
            
            .container {{ 
                padding: 8px; 
            }}
            
            .mobile-card-content {{
                padding: 10px;
            }}
            
            .mobile-field {{
                margin-bottom: 8px;
            }}
            
            .logo-area {{
                width: 70px;
                height: 50px;
                font-size: 10px;
            }}
            
            .contract-title {{
                font-size: 12px;
                padding: 6px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            
            <div class="vendor-info">
                <strong>VENDEDOR:</strong><br>
                {vendedor_nome}<br>
                <strong>DATA:</strong> {data_atual}
            </div>
            
            <div class="clearfix"></div>
            
            <div class="contract-title">
                CONTRATO COMBO - TRATAMENTOS GERAIS +<br>
                ORTODONTIA + TELEMEDICINA "AKI MAIS SAÚDE"<br>
                <span style="font-size: 14px;">Nº {numero_contrato}</span>
            </div>
        </div>

        <!-- Informações do Dependente (se aplicável) -->
        {dependent_header}

        <!-- Seção A - CONTRATADA (Desktop) -->
        <table>
            <tr>
                <th class="section-header">A - CONTRATADA</th>
            </tr>
            <tr>
                <td>
                    Pelo presente Instrumento Particular, de um lado <strong>{empresa_razao_social}</strong>, inscrita no CNPJ/MF nº <strong>{empresa_cnpj}</strong>, com sede na cidade de {empresa_cidade} na {empresa_endereco_completo} a seguir denominada <strong>CONTRATADA</strong> e por outro lado, como <strong>CONTRATANTE</strong>, abaixo discriminado.
                </td>
            </tr>
        </table>

        <!-- Seção A - CONTRATADA (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">A - CONTRATADA</div>
            <div class="mobile-card-content">
                Pelo presente Instrumento Particular, de um lado <strong>{empresa_razao_social}</strong>, inscrita no CNPJ/MF nº <strong>{empresa_cnpj}</strong>, com sede na cidade de {empresa_cidade} na {empresa_endereco_completo} a seguir denominada <strong>CONTRATADA</strong> e por outro lado, como <strong>CONTRATANTE</strong>, abaixo discriminado.
            </div>
        </div>

        <!-- Seção B - CONTRATANTE (Desktop) -->
        <table>
            <tr>
                <th colspan="4" class="section-header">B - CONTRATANTE</th>
            </tr>
            <tr>
                <td colspan="2" style="width: 60%; font-weight: bold;">NOME</td>
                <td colspan="2" style="width: 40%; font-weight: bold;">DATA DE NASCIMENTO</td>
            </tr>
            <tr>
                <td colspan="2">{paciente_nome}</td>
                <td colspan="2">{paciente_data_nascimento}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">CPF</td>
                <td style="font-weight: bold;">RG</td>
                <td style="font-weight: bold;">ORGÃO EXPED</td>
                <td style="font-weight: bold;">CONTRATANTE INCLUSO</td>
            </tr>
            <tr>
                <td>{paciente_cpf}</td>
                <td>{paciente_rg}</td>
                <td>{paciente_orgao_expedidor}</td>
                <td>SIM</td>
            </tr>
        </table>

        <!-- Seção B - CONTRATANTE (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">B - CONTRATANTE</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">NOME</div>
                    <div class="mobile-field-value">{paciente_nome}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">DATA DE NASCIMENTO</div>
                    <div class="mobile-field-value">{paciente_data_nascimento}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CPF</div>
                    <div class="mobile-field-value">{paciente_cpf}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">RG</div>
                    <div class="mobile-field-value">{paciente_rg}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">ÓRGÃO EXPEDIDOR</div>
                    <div class="mobile-field-value">{paciente_orgao_expedidor}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CONTRATANTE INCLUSO</div>
                    <div class="mobile-field-value">SIM</div>
                </div>
            </div>
        </div>

        <!-- Seção C - CONTRATANTES Vinculados (Desktop) -->
        <table>
            <tr>
                <th colspan="4" class="section-header">C - CONTRATANTES VINCULADOS</th>
            </tr>
            {dependentes_rows}
        </table>

        <!-- Seção C - CONTRATANTES Vinculados (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">C - CONTRATANTES VINCULADOS</div>
            <div class="mobile-card-content">
                {dependentes_mobile}
            </div>
        </div>

        <!-- Seção D - Endereço (Desktop) -->
        <table>
            <tr>
                <th colspan="3" class="section-header">D - ENDEREÇO</th>
            </tr>
            <tr>
                <td colspan="2" style="font-weight: bold; width: 60%;">RESIDENCIAL</td>
                <td style="font-weight: bold; width: 40%;">CEP</td>
            </tr>
            <tr>
                <td colspan="2">{paciente_endereco}</td>
                <td>{paciente_cep}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">BAIRRO</td>
                <td style="font-weight: bold;">CIDADE</td>
                <td style="font-weight: bold;">ESTADO</td>
            </tr>
            <tr>
                <td>{paciente_bairro}</td>
                <td>{paciente_cidade}</td>
                <td>{paciente_estado}</td>
            </tr>
            <tr>
                <td style="font-weight: bold;">TEL 1</td>
                <td style="font-weight: bold;">TEL 2</td>
                <td style="font-weight: bold;">EMAIL</td>
            </tr>
            <tr>
                <td>{paciente_telefone1}</td>
                <td>{paciente_telefone2}</td>
                <td>{paciente_email}</td>
            </tr>
        </table>

        <!-- Seção D - Endereço (Mobile) -->
        <div class="mobile-card">
            <div class="mobile-card-header">D - ENDEREÇO</div>
            <div class="mobile-card-content">
                <div class="mobile-field">
                    <div class="mobile-field-label">RESIDENCIAL</div>
                    <div class="mobile-field-value">{paciente_endereco}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CEP</div>
                    <div class="mobile-field-value">{paciente_cep}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">BAIRRO</div>
                    <div class="mobile-field-value">{paciente_bairro}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">CIDADE</div>
                    <div class="mobile-field-value">{paciente_cidade}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">ESTADO</div>
                    <div class="mobile-field-value">{paciente_estado}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">TELEFONE 1</div>
                    <div class="mobile-field-value">{paciente_telefone1}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">TELEFONE 2</div>
                    <div class="mobile-field-value">{paciente_telefone2}</div>
                </div>
                <div class="mobile-field">
                    <div class="mobile-field-label">EMAIL</div>
                    <div class="mobile-field-value">{paciente_email}</div>
                </div>
            </div>
        </div>

        <!-- Observação sobre tratamentos -->
        <div style="text-align: center; padding: 10px; border: 1px solid #000; margin-bottom: 20px;">
            {observacao_tratamentos}
        </div>

        <!-- Conteúdo do Contrato Combo -->
        <div class="contract-content">
            <div class="clause">
                <div class="clause-title">1. PARTES</div>
                <div class="sub-clause">
                    <strong>1.1 Contratante (Paciente/Titular do Cartão):</strong> {paciente_nome}, CPF nº {paciente_cpf}, residente em {paciente_endereco}, {paciente_cidade}/{paciente_estado}.
                </div>
                <div class="sub-clause">
                    <strong>1.2 Contratada (Clínica/Provedora):</strong> {empresa_razao_social}, CNPJ nº {empresa_cnpj}, com sede à {empresa_endereco_completo}.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">2. OBJETO</div>
                <div class="clause-content">
                    <strong>2.1</strong> O presente instrumento tem por objeto:
                </div>
                <div class="sub-clause">
                    a) A prestação de serviços odontológicos gerais nas dependências da Contratada;<br>
                    b) A prestação de serviços odontológicos de ortodontia (instalação, manutenção e finalização de tratamento com contenções);<br>
                    c) A concessão, a título gratuito, do benefício de telemedicina "Aki Mais Saúde", limitado a consultas médicas on-line.
                </div>
                <div class="clause-content">
                    <strong>2.2</strong> O presente contrato não caracteriza plano ou seguro de saúde/odontológico, pois contempla apenas pacote específico de procedimentos e não cobertura integral regulamentada pela ANS.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">3. SERVIÇOS ODONTOLÓGICOS GERAIS</div>
                <div class="clause-content">
                    <strong>3.1</strong> A Contratada disponibilizará os seguintes procedimentos em tabela reduzida (valores de referência):
                </div>

                <!-- Tabela de Serviços - Desktop -->
                <table class="services-table">
                    <tr>
                        <th colspan="3" class="section-header">TABELA DE SERVIÇOS ODONTOLÓGICOS GERAIS</th>
                    </tr>
                    <tr>
                        <th style="width: 50%;">Procedimento</th>
                        <th style="width: 25%;">Valor de Referência (R$)</th>
                        <th style="width: 25%;">Observações</th>
                    </tr>
                    <tr>
                        <td>Avaliação clínica inicial c/ documentação básica</td>
                        <td class="price-cell">180,00</td>
                        <td>Inclui radiografia panorâmica</td>
                    </tr>
                    <tr>
                        <td>Profilaxia</td>
                        <td class="price-cell">180,00</td>
                        <td>—</td>
                    </tr>
                    <tr>
                        <td>Restauração em resina (por dente)</td>
                        <td class="price-cell">35,00</td>
                        <td>—</td>
                    </tr>
                    <tr>
                        <td>Extração simples (por dente)</td>
                        <td class="price-cell">35,00</td>
                        <td>Sem terceiros molares</td>
                    </tr>
                    <tr>
                        <td>Raspagem periodontal (por dente)</td>
                        <td class="price-cell">35,00</td>
                        <td>—</td>
                    </tr>
                </table>

                <!-- Tabela de Serviços - Mobile -->
                <div class="mobile-services">
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Avaliação clínica inicial c/ documentação básica</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 180,00</div>
                            <div>Inclui radiografia panorâmica</div>
                        </div>
                    </div>
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Profilaxia</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 180,00</div>
                        </div>
                    </div>
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Restauração em resina (por dente)</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 35,00</div>
                        </div>
                    </div>
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Extração simples (por dente)</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 35,00</div>
                            <div>Sem terceiros molares</div>
                        </div>
                    </div>
                    <div class="mobile-service-item">
                        <div class="mobile-service-header">Raspagem periodontal (por dente)</div>
                        <div class="mobile-service-content">
                            <div class="mobile-service-price">R$ 35,00</div>
                        </div>
                    </div>
                </div>

                <div class="clause-content">
                    <strong>3.2</strong> Procedimentos não listados na tabela acima receberão desconto de até 50% sobre a tabela vigente da clínica odontológica.
                </div>
                <div class="clause-content">
                    <strong>3.3</strong> Procedimentos hospitalares, tratamento endodôntico em terceiros molares, cirurgias complexas e próteses não estão incluídos neste contrato e, se desejados, serão formalizados em instrumento próprio.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">4. MÓDULO ORTODONTIA — CLÁUSULAS ESPECÍFICAS</div>
                
                <div class="clause-content">
                    <strong>4.1 Esclarecimentos Gerais</strong>
                </div>
                <div class="sub-clause">
                    4.1.1 A ortodontia depende de fatores biológicos individuais; não há garantia de resultado específico. O êxito exige cooperação do paciente, comparecimento às manutenções e higiene adequada.
                </div>
                <div class="sub-clause">
                    4.1.2 O plano de tratamento poderá ser ajustado segundo a resposta orgânica ou padrão de crescimento do paciente, podendo envolver extrações dentárias, cirurgia ortognática, instalação de mini‑implantes, entre outros. Tais procedimentos extra serão orçados à parte.
                </div>

                <div class="clause-content">
                    <strong>4.2 Atendimento</strong>
                </div>
                <div class="sub-clause">
                    4.2.1 O paciente será atendido uma vez ao mês para manutenção do aparelho. Alterações de horário deverão ser comunicadas preferencialmente com 24h de antecedência.
                </div>
                <div class="sub-clause">
                    4.2.2 A ausência não justifica isenção de pagamento. O paciente deverá remarcar a consulta no prazo mais breve possível.
                </div>
                <div class="sub-clause">
                    4.2.3 Alterações de endereço ou telefone devem ser informadas à Contratada por escrito.
                </div>

                <div class="clause-content">
                    <strong>4.3 Interrupção do Tratamento</strong>
                </div>
                <div class="sub-clause">
                    4.3.1 O paciente poderá desistir do tratamento a qualquer momento, devendo assinar Termo de Revogação. Será cobrada multa contratual de <strong>R$ 400,00</strong> referente ao aparelho instalado, materiais e honorários iniciais.
                </div>
                <div class="sub-clause">
                    4.3.2 Ausência superior a seis meses sem justificativa escrita exime o cirurgião‑dentista de responsabilidade por intercorrências.
                </div>

                <div class="clause-content">
                    <strong>4.4 Contenções</strong>
                </div>
                <div class="sub-clause">
                    4.4.1 Serão confeccionadas contenções superior e inferior, com custo individual conforme tabela vigente à época.
                </div>
                <div class="sub-clause">
                    4.4.2 O paciente compromete‑se a retornar seis vezes após instalação das contenções, pagando cada consulta o valor de uma mensalidade vigente.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">5. BENEFÍCIO DE TELEMEDICINA "AKI MAIS SAÚDE"</div>
                <div class="clause-content">
                    <strong>5.1</strong> O Contratante terá direito à realização de consultas médicas exclusivamente por telemedicina, sem qualquer custo adicional.
                </div>
                <div class="clause-content">
                    <strong>5.2</strong> A utilização obedece às regras de agendamento da plataforma e disponibilidade da rede credenciada.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">6. PAGAMENTO</div>
                <div class="clause-content">
                    <strong>6.1</strong> O valor total do contrato Combo (Ortodontia + Odontologia Clínica) é de <span class="highlight">R$ {valor_total_formatado}</span>, que cobre todos os serviços descritos nas cláusulas 3, 4 e 5.
                </div>
                <div class="clause-content">
                    <strong>6.2</strong> Condições de pagamento:
                    {clausula_pagamento_detalhada}
                </div>
                <div class="clause-content">
                    <strong>6.3</strong> A primeira parcela ou taxa de adesão é devida na assinatura. Inadimplência superior a 30 dias suspende atendimentos e acesso ao benefício.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">7. OBRIGAÇÕES DAS PARTES</div>
                <div class="sub-clause">
                    <strong>7.1 Da Contratada:</strong>
                    <ul>
                        <li>Prestar serviços com qualidade técnica e ética;</li>
                        <li>Disponibilizar profissionais habilitados;</li>
                        <li>Assegurar dados pessoais conforme LGPD;</li>
                        <li>Fornecer suporte sobre o benefício de telemedicina.</li>
                    </ul>
                </div>
                <div class="sub-clause">
                    <strong>7.2 Do Contratante:</strong>
                    <ul>
                        <li>Pagar valores na forma e prazos ajustados;</li>
                        <li>Seguir orientações clínicas e manter higiene oral;</li>
                        <li>Comparecer às manutenções mensais;</li>
                        <li>Informar dados cadastrais atualizados.</li>
                    </ul>
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">8. VIGÊNCIA E CANCELAMENTO</div>
                <div class="clause-content">
                    <strong>8.1</strong> Vigência inicial de {qtd_parcelas} meses, renovável automaticamente.
                </div>
                <div class="clause-content">
                    <strong>8.2</strong> O Contratante pode rescindir mediante aviso escrito com 30 dias de antecedência, quitando eventuais valores em aberto. No módulo ortodontia aplica‑se a multa da Cláusula 4.3.1.
                </div>
                <div class="clause-content">
                    <strong>8.3</strong> Inadimplência superior a 30 dias autoriza cancelamento por parte da Contratada.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">9. RESPONSABILIDADES E LIMITAÇÕES</div>
                <div class="clause-content">
                    <strong>9.1</strong> A Contratada responde apenas por serviços executados em suas instalações ou por profissionais por ela designados.
                </div>
                <div class="clause-content">
                    <strong>9.2</strong> Complicações decorrentes de doenças sistêmicas (ex.: diabetes descontrolado, bruxismo severo) ou hábitos prejudiciais são de responsabilidade do Contratante.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">10. CONFIDENCIALIDADE E PROTEÇÃO DE DADOS</div>
                <div class="clause-content">
                    <strong>10.1</strong> As Partes comprometem‑se a manter sigilo sobre informações obtidas em razão deste contrato.
                </div>
                <div class="clause-content">
                    <strong>10.2</strong> A Contratada observa as disposições da LGPD, adotando medidas técnicas e administrativas aptas a proteger os dados pessoais aqui tratados.
                </div>
            </div>

            <div class="clause">
                <div class="clause-title">11. FORO</div>
                <div class="clause-content">
                    Fica eleito o foro da Comarca de {cidade_contrato}, renunciando-se a qualquer outro, por mais privilegiado que seja, para dirimir controvérsias decorrentes deste contrato.
                </div>
            </div>
        </div>

        <!-- Data e Local -->
        <div style="text-align: center; margin: 30px 0;">
            <strong>{cidade_contrato}, {data_contrato}</strong>
        </div>

        <!-- Assinaturas -->
        <div class="signatures">
            <div class="signature-area">
                <div class="signature-box">
                    {signature_html}
                    <div class="signature-line"></div>
                    <div style="margin-top: 10px;"><strong>{paciente_nome}</strong><br>Contratante / Titular</div>
                </div>
                <div class="signature-box">
                    <div style="height: 80px;"></div>
                    <div class="signature-line"></div>
                    <div style="margin-top: 10px;"><strong>{empresa_razao_social}</strong><br>Representante Legal</div>
                </div>
            </div>

            <!-- Testemunhas -->
            <div style="margin-top: 40px;">
                <strong>TESTEMUNHAS:</strong>
                <div class="witness-area">
                    <div class="witness-box">
                        <div class="witness-line"></div>
                        <div>Testemunha 1 – Nome / CPF</div>
                    </div>
                    <div class="witness-box">
                        <div class="witness-line"></div>
                        <div>Testemunha 2 – Nome / CPF</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# 6. Template para "Taxa de Adesão" (ID: 6)
TEMPLATE_TAXA_ADESAO = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Termo de Adesão - Programa de Benefícios Odontológicos</title>
    <style>
        body { font-family: 'Arial', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        .container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 3px solid #2ecc71; }
        .logo { font-size: 32px; font-weight: bold; color: #2ecc71; margin-bottom: 10px; }
        .badge { display: inline-block; background: #2ecc71; color: white; padding: 8px 20px; border-radius: 20px; font-size: 14px; margin-top: 10px; }
        .info-section { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #2ecc71; }
        .benefits { margin: 30px 0; }
        .benefit-card { background: white; border: 2px solid #e0e0e0; padding: 20px; margin: 15px 0; border-radius: 8px; transition: all 0.3s; }
        .benefit-card:hover { border-color: #2ecc71; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .benefit-icon { font-size: 24px; margin-right: 10px; }
        .price-info { background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%); color: white; padding: 30px; text-align: center; border-radius: 10px; margin: 30px 0; }
        .price { font-size: 48px; font-weight: bold; margin: 10px 0; }
        .price-period { font-size: 18px; opacity: 0.9; }
        .terms { font-size: 14px; line-height: 1.8; margin: 20px 0; }
        .terms-box { background: #fff5f5; border: 1px solid #ffcccc; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .signature-section { margin-top: 50px; text-align: center; }
        .signature-line { border-bottom: 2px solid #333; margin: 40px auto 10px; width: 300px; }
        .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 2px solid #e0e0e0; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">{empresa_razao_social}</div>
            <h1 style="color: #333; font-size: 24px;">TERMO DE ADESÃO</h1>
            <div class="badge">PROGRAMA DE BENEFÍCIOS ODONTOLÓGICOS</div>
        </div>

        <!-- Informações do Dependente (se aplicável) -->
        {dependent_header}

        <div class="info-section">
            <h3 style="color: #2ecc71; margin-bottom: 15px;">Dados do Associado</h3>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                <div><strong>Nome:</strong> {paciente_nome}</div>
                <div><strong>CPF:</strong> {paciente_cpf}</div>
                <div><strong>Telefone:</strong> {paciente_telefone1}</div>
                <div><strong>E-mail:</strong> {paciente_email}</div>
                <div><strong>Data de Adesão:</strong> {data_contrato}</div>
                <div><strong>Código do Associado:</strong> #{numero_contrato}</div>
            </div>
        </div>

        <div class="benefits">
            <h2 style="text-align: center; color: #333;">🎁 Seus Benefícios Exclusivos</h2>
            
            <div class="benefit-card">
                <span class="benefit-icon">🦷</span>
                <strong>Consultas e Avaliações</strong>
                <p>Consultas ilimitadas com nossos especialistas durante a vigência do programa.</p>
            </div>
            
            <div class="benefit-card">
                <span class="benefit-icon">💰</span>
                <strong>Descontos Especiais</strong>
                <p>Até 50% de desconto em todos os procedimentos odontológicos da clínica.</p>
            </div>
            
            <div class="benefit-card">
                <span class="benefit-icon">🚨</span>
                <strong>Atendimento de Urgência</strong>
                <p>Prioridade no atendimento em casos de urgência e emergência odontológica.</p>
            </div>
            
            <div class="benefit-card">
                <span class="benefit-icon">👨‍👩‍👧‍👦</span>
                <strong>Benefícios Familiares</strong>
                <p>Extensão dos benefícios para dependentes diretos com condições especiais.</p>
            </div>
        </div>

        <div class="price-info">
            <h3 style="margin-bottom: 20px;">Taxa de Adesão</h3>
            <div class="price">R$ {valor_total_formatado}</div>
            <div class="price-period">{forma_pagamento}</div>
            <p style="margin-top: 20px;">{qtd_parcelas} parcela(s) de R$ {valor_parcela_formatado}</p>
        </div>

        <div class="terms-box">
            <h3 style="color: #d73502;">⚠️ Informações Importantes</h3>
            <ul style="margin-left: 20px;">
                <li>Este NÃO é um plano de saúde, mas sim um programa de benefícios</li>
                <li>Não possui cobertura obrigatória pela ANS</li>
                <li>Os descontos são válidos apenas na rede credenciada</li>
                <li>Carência de 30 dias para utilização dos benefícios</li>
            </ul>
        </div>

        <div class="terms">
            <h3>Termos e Condições</h3>
            <p><strong>1. VIGÊNCIA:</strong> Este termo tem validade de 12 meses a partir da data de adesão, renovável automaticamente.</p>
            <p><strong>2. UTILIZAÇÃO:</strong> Os benefícios podem ser utilizados após 30 dias da confirmação do pagamento da taxa de adesão.</p>
            <p><strong>3. CANCELAMENTO:</strong> O associado pode cancelar a qualquer momento, sem direito a reembolso da taxa paga.</p>
            <p><strong>4. BENEFICIÁRIOS:</strong> O titular pode incluir até 3 dependentes diretos com 50% de desconto na taxa.</p>
            <p><strong>5. REDE CREDENCIADA:</strong> Os benefícios são válidos exclusivamente nas unidades da {empresa_razao_social}.</p>
            <p><strong>6. REAJUSTE:</strong> A taxa pode ser reajustada anualmente conforme variação do IPCA.</p>
        </div>

        <p style="text-align: center; margin: 30px 0; font-style: italic;">
            Ao assinar este termo, declaro ter lido e concordado com todas as condições do 
            Programa de Benefícios Odontológicos.
        </p>

        <div class="signature-section">
            {signature_html}
            <div class="signature-line"></div>
            <div>{paciente_nome}<br>Associado</div>
            
            <div style="margin-top: 50px;">
                <div style="height: 80px;"></div>
                <div class="signature-line"></div>
                <div>{empresa_razao_social}<br>{vendedor_nome} - CRO: {vendedor_nome}</div>
            </div>
        </div>

        <div class="footer">
            <p><strong>{empresa_razao_social}</strong></p>
            <p>CNPJ: {empresa_cnpj} | {empresa_endereco_completo}</p>
            <p>Tel: {paciente_telefone1} | contato@clinica.com.br</p>
            <p style="margin-top: 15px; font-size: 12px;">
                Documento assinado digitalmente em {data_contrato}<br>
                Este termo possui validade jurídica conforme MP 2.200-2/2001
            </p>
        </div>
    </div>
</body>
</html>
"""

# Função auxiliar para escolher template baseado no tipo
def get_template_by_tipo_id(tipo_id: int) -> str:
    """Retorna o template HTML específico baseado no ID do tipo de odontograma"""
    
    templates_map = {
        1: TEMPLATE_PARTICULAR,  # Particular
        2: TEMPLATE_ORTODONTIA,  # Ortodontia
        3: CONTRATO_AKIMAIS_TEMPLATE,  # Contrato Odontológico + Akimais
        4: TEMPLATE_CONTRATO_ORTODONTICO,  # Contrato Ortodôntico
        5: TEMPLATE_COMBO_ORTO_ODC,  # Combo Orto + ODC
        6: TEMPLATE_TAXA_ADESAO  # Taxa de Adesão
    }
    
    # Retorna o template específico ou o padrão se não encontrar
    return templates_map.get(tipo_id, CONTRACT_TEMPLATE)


# Função para renderizar contrato com template específico
def render_contract_by_tipo(dados: dict, tipo_id: int) -> str:
    """
    Renderiza o contrato usando o template específico do tipo
    
    Args:
        dados: Dicionário com os dados do contrato
        tipo_id: ID do tipo de odontograma
    
    Returns:
        HTML renderizado do contrato
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📍 DEBUG render_contract_by_tipo: tipo_id={tipo_id}")
    
    # Obter o template correto
    template = get_template_by_tipo_id(tipo_id)
    logger.info(f"📍 DEBUG: Template obtido tem {len(template)} caracteres")
    logger.info(f"📍 DEBUG: É template ortodôntico? {'ORTODÔNTICOS' in template}")
    
    # Usar a função render_contract existente, mas com o template específico
    # Temporariamente substituir o template global
    global CONTRATO_AKIMAIS_TEMPLATE
    original_template = CONTRATO_AKIMAIS_TEMPLATE
    CONTRATO_AKIMAIS_TEMPLATE = template
    
    try:
        html = render_contract(dados)
        logger.info(f"📍 DEBUG: HTML renderizado tem {len(html)} caracteres")
        logger.info(f"📍 DEBUG: HTML contém 'ORTODÔNTICOS'? {'ORTODÔNTICOS' in html}")
    finally:
        # Restaurar o template original
        CONTRATO_AKIMAIS_TEMPLATE = original_template
    
    return html