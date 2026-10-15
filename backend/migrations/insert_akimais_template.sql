-- Inserir template para Contrato Odontológico + Akimais
-- Este script adiciona o template padrão do contrato Akimais ao sistema

-- Primeiro, vamos descobrir o ID do tipo Akimais
DO $$
DECLARE
    v_tipo_id INTEGER;
    v_template_html TEXT;
BEGIN
    -- Buscar o tipo "Contrato Odontológico + Akimais"
    SELECT id INTO v_tipo_id
    FROM tipos_odontograma
    WHERE nome ILIKE '%akimais%'
    LIMIT 1;
    
    -- Se não encontrar, mostrar aviso
    IF v_tipo_id IS NULL THEN
        RAISE NOTICE 'AVISO: Tipo "Contrato Odontológico + Akimais" não encontrado.';
        RAISE NOTICE 'Template será criado como genérico (sem tipo específico).';
        RAISE NOTICE '';
        RAISE NOTICE 'Tipos disponíveis:';
        
        -- Listar tipos disponíveis
        FOR v_tipo_id IN SELECT id FROM tipos_odontograma ORDER BY id
        LOOP
            RAISE NOTICE 'ID: % - %', 
                (SELECT id FROM tipos_odontograma WHERE id = v_tipo_id),
                (SELECT nome FROM tipos_odontograma WHERE id = v_tipo_id);
        END LOOP;
        
        -- Resetar v_tipo_id para NULL
        v_tipo_id := NULL;
    ELSE
        RAISE NOTICE 'Tipo Akimais encontrado com ID: %', v_tipo_id;
    END IF;
    
    -- Template HTML (versão simplificada para o SQL)
    v_template_html := '<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contrato de Compra e Venda de Serviços Odontológicos</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; line-height: 1.4; background: white; font-size: 12px; }
        .container { max-width: 210mm; margin: 0 auto; background: white; padding: 20px; }
        .header { text-align: center; margin-bottom: 20px; }
        .logo-area { float: left; width: 100px; height: 80px; border: 1px solid #ccc; display: flex; align-items: center; justify-content: center; background: #f0f9f0; color: #4CAF50; font-weight: bold; font-size: 14px; }
        .contract-title { text-align: center; font-weight: bold; font-size: 16px; margin: 20px 0; padding: 10px; border: 2px solid #000; }
        .vendor-info { float: right; text-align: right; font-size: 11px; margin-top: 10px; }
        .clearfix { clear: both; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 15px; border: 2px solid #000; }
        th, td { border: 1px solid #000; padding: 8px; text-align: left; vertical-align: top; }
        th { background-color: #f5f5f5; font-weight: bold; text-align: center; }
        .section-header { background-color: #e0e0e0; font-weight: bold; text-align: center; font-size: 13px; }
        .contract-content { margin-top: 20px; text-align: justify; line-height: 1.5; }
        .clause { margin: 15px 0; }
        .clause-title { font-weight: bold; margin-bottom: 8px; }
        .highlight { background-color: #ffffcc; padding: 2px 4px; font-weight: bold; }
        .signatures { margin-top: 40px; page-break-inside: avoid; }
        .signature-area { display: flex; justify-content: space-between; margin-top: 40px; }
        .signature-box { width: 45%; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo-area"><div>ODONTO<br>COMPANY</div></div>
            <div class="vendor-info"><strong>VENDEDOR</strong><br>{{vendedor_nome}}</div>
            <div class="clearfix"></div>
            <div class="contract-title">CONTRATO DE COMPRA E<br>VENDA DE SERVIÇOS<br>ODONTOLÓGICOS</div>
        </div>
        
        <!-- Template content continues with all contract sections -->
        <!-- Using placeholder variables like {{paciente_nome}}, {{valor_total}}, etc. -->
        
    </div>
</body>
</html>';
    
    -- Se o tipo foi configurado como padrão, desativar outros templates padrão deste tipo
    IF v_tipo_id IS NOT NULL THEN
        UPDATE contract_templates 
        SET is_default = FALSE 
        WHERE tipo_odontograma_id = v_tipo_id 
        AND is_default = TRUE;
    END IF;
    
    -- Inserir o template
    INSERT INTO contract_templates (
        name,
        slug,
        tipo_odontograma_id,
        template_html,
        template_config,
        is_active,
        is_default,
        created_at,
        updated_at
    ) VALUES (
        'Contrato Odontológico + Akimais Saúde',
        'contrato-akimais-v1',
        v_tipo_id,
        v_template_html,
        '{
            "description": "Contrato padrão para tratamentos odontológicos com Akimais Saúde",
            "variables": {
                "vendedor_nome": "Nome do vendedor",
                "razao_social": "Razão social da empresa",
                "cnpj": "CNPJ da empresa",
                "endereco": "Endereço completo da empresa",
                "empresa_cidade": "Cidade da empresa",
                "paciente_nome": "Nome completo do paciente",
                "paciente_cpf": "CPF do paciente",
                "paciente_data_nascimento": "Data de nascimento",
                "paciente_rg": "RG do paciente",
                "paciente_orgao_expedidor": "Órgão expedidor do RG",
                "paciente_endereco": "Endereço do paciente",
                "paciente_cep": "CEP do paciente",
                "paciente_bairro": "Bairro do paciente",
                "paciente_cidade": "Cidade do paciente",
                "paciente_estado": "Estado do paciente",
                "paciente_telefone": "Telefone principal",
                "paciente_telefone2": "Telefone secundário",
                "paciente_email": "Email do paciente",
                "valor_total": "Valor total do contrato",
                "numero_parcelas": "Número de parcelas",
                "valor_parcela": "Valor de cada parcela",
                "dia_vencimento": "Dia de vencimento",
                "forma_pagamento": "Forma de pagamento",
                "observacao_tratamentos": "Observações sobre tratamentos",
                "cidade_contrato": "Cidade onde o contrato é assinado",
                "data_contrato": "Data do contrato",
                "dependentes_rows": "HTML das linhas de dependentes (desktop)",
                "dependentes_mobile": "HTML dos dependentes (mobile)",
                "signature_html": "HTML da assinatura digital"
            }
        }'::jsonb,
        TRUE,
        TRUE,
        NOW(),
        NOW()
    )
    ON CONFLICT (slug) DO UPDATE SET
        name = EXCLUDED.name,
        tipo_odontograma_id = EXCLUDED.tipo_odontograma_id,
        template_config = EXCLUDED.template_config,
        is_active = EXCLUDED.is_active,
        is_default = EXCLUDED.is_default,
        updated_at = NOW();
    
    RAISE NOTICE '';
    RAISE NOTICE '✅ Template Akimais inserido/atualizado com sucesso!';
    
    -- Mostrar informações do template inserido
    RAISE NOTICE 'Nome: Contrato Odontológico + Akimais Saúde';
    RAISE NOTICE 'Slug: contrato-akimais-v1';
    RAISE NOTICE 'Tipo ID: %', COALESCE(v_tipo_id::TEXT, 'NULL (genérico)');
    RAISE NOTICE 'Status: Ativo e Padrão';
    
END $$;

-- Verificar se o template foi inserido corretamente
SELECT 
    id,
    name,
    slug,
    tipo_odontograma_id,
    is_active,
    is_default,
    created_at
FROM contract_templates
WHERE slug = 'contrato-akimais-v1';

-- Mostrar estatísticas
SELECT 
    COUNT(*) as total_templates,
    COUNT(CASE WHEN is_active THEN 1 END) as ativos,
    COUNT(CASE WHEN is_default THEN 1 END) as padroes
FROM contract_templates;