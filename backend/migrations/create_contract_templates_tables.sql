-- migrations/create_contract_templates_tables.sql
-- Criar tabelas para gerenciar templates de contratos

-- Tabela principal de templates
CREATE TABLE IF NOT EXISTS contract_templates (
    id SERIAL PRIMARY KEY,
    
    -- Identificação
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    
    -- Associação com tipo de odontograma
    tipo_odontograma_id INTEGER REFERENCES tipos_odontograma(id) ON DELETE SET NULL,
    
    -- Conteúdo
    template_html TEXT NOT NULL,
    template_config JSONB DEFAULT '{}',
    
    -- Metadados
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,
    
    -- Estatísticas
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- Índices
CREATE INDEX idx_contract_templates_slug ON contract_templates(slug);
CREATE INDEX idx_contract_templates_tipo ON contract_templates(tipo_odontograma_id);
CREATE INDEX idx_contract_templates_active ON contract_templates(is_active);
CREATE INDEX idx_contract_templates_default ON contract_templates(is_default);

-- Tabela de variáveis customizáveis
CREATE TABLE IF NOT EXISTS contract_template_variables (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES contract_templates(id) ON DELETE CASCADE,
    
    -- Identificação
    variable_name VARCHAR(100) NOT NULL,
    variable_label VARCHAR(200) NOT NULL,
    variable_type VARCHAR(50) NOT NULL, -- text, number, date, boolean
    
    -- Configuração
    default_value TEXT,
    is_required BOOLEAN DEFAULT true,
    validation_rules JSONB,
    display_order INTEGER DEFAULT 0,
    
    -- Unique constraint
    CONSTRAINT unique_template_variable UNIQUE (template_id, variable_name)
);

-- Índice
CREATE INDEX idx_template_variables_template ON contract_template_variables(template_id);

-- Tabela para histórico de versões (auditoria)
CREATE TABLE IF NOT EXISTS contract_template_history (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES contract_templates(id),
    version INTEGER NOT NULL,
    template_html TEXT NOT NULL,
    template_config JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    change_description TEXT
);

-- Índice
CREATE INDEX idx_template_history_template ON contract_template_history(template_id);

-- Trigger para criar histórico quando template é atualizado
CREATE OR REPLACE FUNCTION save_template_history()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.template_html IS DISTINCT FROM NEW.template_html THEN
        INSERT INTO contract_template_history (
            template_id, version, template_html, template_config,
            changed_by, change_description
        ) VALUES (
            NEW.id, OLD.version, OLD.template_html, OLD.template_config,
            NEW.updated_by, 'Template HTML atualizado'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER template_history_trigger
BEFORE UPDATE ON contract_templates
FOR EACH ROW
EXECUTE FUNCTION save_template_history();

-- Adicionar coluna na tabela de contratos digitais para rastrear qual template foi usado
ALTER TABLE digital_contracts 
ADD COLUMN IF NOT EXISTS template_id INTEGER REFERENCES contract_templates(id),
ADD COLUMN IF NOT EXISTS template_version INTEGER;

-- Inserir template padrão baseado no atual
INSERT INTO contract_templates (
    name, 
    slug, 
    description,
    is_default,
    template_html,
    template_config,
    created_by
) VALUES (
    'Contrato Padrão - Odontologia Geral',
    'contrato-padrao-odontologia',
    'Template padrão para contratos de serviços odontológicos gerais',
    true,
    '<!-- Template será inserido via script de migração -->',
    '{
        "show_dependents": true,
        "show_witnesses": true,
        "show_payment_details": true,
        "clauses": {
            "clause_1": {
                "title": "Cláusula 1",
                "content": "A VENDEDORA se obriga a prestar serviços odontológicos..."
            }
        }
    }',
    'system'
) ON CONFLICT (slug) DO NOTHING;

-- Inserir template específico para Contrato Odontológico + Akimais
INSERT INTO contract_templates (
    name,
    slug,
    description,
    tipo_odontograma_id,
    template_html,
    template_config,
    created_by
) VALUES (
    'Contrato Odontológico + Akimais',
    'contrato-odontologico-akimais',
    'Template específico para Contrato Odontológico + Akimais com condições especiais',
    (SELECT id FROM tipos_odontograma WHERE nome = 'Contrato Odontológico + Akimais' LIMIT 1),
    '<!-- Template específico Akimais será inserido via script -->',
    '{
        "show_dependents": true,
        "show_witnesses": true,
        "show_payment_details": true,
        "highlight_akimais": true,
        "custom_clauses": [
            {
                "position": "after_clause_3",
                "title": "Benefícios Akimais",
                "content": "O contratante terá direito aos benefícios exclusivos do programa Akimais..."
            }
        ]
    }',
    'system'
) ON CONFLICT (slug) DO NOTHING;

-- Comentários
COMMENT ON TABLE contract_templates IS 'Tabela para armazenar templates de contratos digitais';
COMMENT ON COLUMN contract_templates.slug IS 'Identificador único do template para URLs e referências';
COMMENT ON COLUMN contract_templates.tipo_odontograma_id IS 'Associação opcional com tipo de odontograma';
COMMENT ON COLUMN contract_templates.template_config IS 'Configurações JSON do template (flags, customizações, etc)';
COMMENT ON COLUMN contract_templates.is_default IS 'Indica se é o template padrão quando não há específico';

-- Função para buscar template apropriado
CREATE OR REPLACE FUNCTION get_contract_template_for_odontograma(p_odontograma_id INTEGER)
RETURNS TABLE (
    template_id INTEGER,
    template_html TEXT,
    template_config JSONB,
    template_version INTEGER
) AS $$
DECLARE
    v_tipo_id INTEGER;
BEGIN
    -- Buscar tipo do odontograma
    SELECT tipo_id INTO v_tipo_id
    FROM odontogramas
    WHERE id = p_odontograma_id;
    
    -- Primeiro tentar buscar template específico para o tipo
    IF v_tipo_id IS NOT NULL THEN
        RETURN QUERY
        SELECT ct.id, ct.template_html, ct.template_config, ct.version
        FROM contract_templates ct
        WHERE ct.tipo_odontograma_id = v_tipo_id
        AND ct.is_active = true
        ORDER BY ct.version DESC
        LIMIT 1;
        
        IF FOUND THEN
            RETURN;
        END IF;
    END IF;
    
    -- Se não encontrou específico, buscar o padrão
    RETURN QUERY
    SELECT ct.id, ct.template_html, ct.template_config, ct.version
    FROM contract_templates ct
    WHERE ct.is_default = true
    AND ct.is_active = true
    ORDER BY ct.version DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Permissões
GRANT SELECT ON contract_templates TO PUBLIC;
GRANT ALL ON contract_templates TO postgres;
GRANT ALL ON contract_template_variables TO postgres;
GRANT ALL ON contract_template_history TO postgres;