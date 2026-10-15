-- Migração para criar tabela de pagamentos de faturas avulsas e recorrentes
-- Esta tabela registra cada pagamento individual recebido via webhook
-- Considerando todos os 6 tipos de odontograma e suas diferenças

CREATE TABLE IF NOT EXISTS pagamentos_fatura (
    id SERIAL PRIMARY KEY,
    
    -- Identificação do pagamento
    venda_id INTEGER NOT NULL REFERENCES vendas(id),
    tipo_fatura VARCHAR(20) NOT NULL CHECK (tipo_fatura IN ('avulsa', 'recorrente')),
    tipo_odontograma_id INTEGER REFERENCES tipos_odontograma(id),
    
    -- Para faturas avulsas
    fatura_avulsa_id INTEGER REFERENCES fatura_avulsa(id),
    
    -- Para faturas recorrentes  
    fatura_recorrente_id INTEGER REFERENCES fatura_recorrente(id),
    numero_parcela INTEGER, -- Qual parcela foi paga (1, 2, 3...)
    
    -- Classificação do pagamento baseado no tipo de odontograma
    tipo_pagamento VARCHAR(30) NOT NULL CHECK (tipo_pagamento IN (
        'entrada',           -- Entrada obrigatória (Particular, Ortodontia, Contrato Ortodôntico)
        'taxa_adesao',       -- Taxa de adesão (ODC+Akimais, Combo, Taxa Adesão)
        'parcela_normal',    -- Parcela regular de carnê/recorrente
        'pagamento_avista',  -- Pagamento à vista completo
        'parcela_restante'   -- Parcela das sobras após entrada/taxa
    )),
    
    -- Dados do pagamento
    valor_pago DECIMAL(10,2) NOT NULL,
    valor_original_fatura DECIMAL(10,2) NOT NULL, -- Valor original da fatura que foi paga
    forma_pagamento VARCHAR(100),
    
    -- Dados específicos por tipo de odontograma
    eh_entrada_automatica BOOLEAN DEFAULT FALSE, -- Se foi entrada calculada automaticamente
    eh_taxa_adicional BOOLEAN DEFAULT FALSE,     -- Se é taxa que NÃO reduz valor total (ODC+Akimais, Combo)
    eh_entrada_redutora BOOLEAN DEFAULT FALSE,   -- Se é entrada que reduz parcelas restantes
    
    -- Dados do gateway
    gateway_id VARCHAR(255), -- ID na Delta/Bempaggo (invoice_id ou subscription charge)
    token_webhook VARCHAR(255), -- Token usado no webhook
    
    -- Metadados do webhook
    webhook_data JSONB, -- Dados completos do webhook para auditoria
    order_status VARCHAR(50),
    charge_status VARCHAR(50),
    
    -- Controle de conciliação
    conciliado BOOLEAN DEFAULT FALSE, -- Se foi conciliado com sistema financeiro
    data_conciliacao TIMESTAMP,
    
    -- Controle temporal
    data_pagamento TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT check_fatura_tipo CHECK (
        (tipo_fatura = 'avulsa' AND fatura_avulsa_id IS NOT NULL AND fatura_recorrente_id IS NULL) OR
        (tipo_fatura = 'recorrente' AND fatura_recorrente_id IS NOT NULL AND fatura_avulsa_id IS NULL)
    )
);

-- Índices para performance
CREATE INDEX idx_pagamentos_fatura_venda_id ON pagamentos_fatura(venda_id);
CREATE INDEX idx_pagamentos_fatura_tipo ON pagamentos_fatura(tipo_fatura);
CREATE INDEX idx_pagamentos_fatura_tipo_pagamento ON pagamentos_fatura(tipo_pagamento);
CREATE INDEX idx_pagamentos_fatura_tipo_odontograma ON pagamentos_fatura(tipo_odontograma_id);
CREATE INDEX idx_pagamentos_fatura_avulsa_id ON pagamentos_fatura(fatura_avulsa_id);
CREATE INDEX idx_pagamentos_fatura_recorrente_id ON pagamentos_fatura(fatura_recorrente_id);
CREATE INDEX idx_pagamentos_fatura_token ON pagamentos_fatura(token_webhook);
CREATE INDEX idx_pagamentos_fatura_data ON pagamentos_fatura(data_pagamento);
CREATE INDEX idx_pagamentos_fatura_conciliado ON pagamentos_fatura(conciliado);

-- Índice composto para queries frequentes
CREATE INDEX idx_pagamentos_fatura_venda_tipo ON pagamentos_fatura(venda_id, tipo_pagamento);
CREATE INDEX idx_pagamentos_fatura_gateway ON pagamentos_fatura(gateway_id, tipo_fatura);

-- Comentários detalhados
COMMENT ON TABLE pagamentos_fatura IS 'Registra pagamentos individuais recebidos via webhook de faturas avulsas e recorrentes, considerando todos os tipos de odontograma';

COMMENT ON COLUMN pagamentos_fatura.venda_id IS 'ID da venda associada ao pagamento';
COMMENT ON COLUMN pagamentos_fatura.tipo_fatura IS 'Tipo da fatura: avulsa ou recorrente';
COMMENT ON COLUMN pagamentos_fatura.tipo_odontograma_id IS 'Tipo de odontograma que determina as regras de cálculo';
COMMENT ON COLUMN pagamentos_fatura.tipo_pagamento IS 'Classificação: entrada, taxa_adesao, parcela_normal, pagamento_avista, parcela_restante';

COMMENT ON COLUMN pagamentos_fatura.valor_pago IS 'Valor efetivamente pago (pode diferir do valor original por taxas/ajustes do gateway)';
COMMENT ON COLUMN pagamentos_fatura.valor_original_fatura IS 'Valor original da fatura antes de taxas/ajustes do gateway';
COMMENT ON COLUMN pagamentos_fatura.numero_parcela IS 'Número da parcela paga (usado em faturas recorrentes)';

COMMENT ON COLUMN pagamentos_fatura.eh_entrada_automatica IS 'TRUE se foi entrada calculada automaticamente (Contrato Ortodôntico)';
COMMENT ON COLUMN pagamentos_fatura.eh_taxa_adicional IS 'TRUE se é taxa que NÃO reduz valor total - ODC+Akimais(R$150), Combo(R$200)';
COMMENT ON COLUMN pagamentos_fatura.eh_entrada_redutora IS 'TRUE se é entrada que reduz parcelas restantes - Particular, Ortodontia, Contrato Ortodôntico';

COMMENT ON COLUMN pagamentos_fatura.gateway_id IS 'ID da fatura/cobrança no gateway de pagamento (Delta/Bempaggo)';
COMMENT ON COLUMN pagamentos_fatura.token_webhook IS 'Token UUID usado no webhook para identificar a fatura';
COMMENT ON COLUMN pagamentos_fatura.webhook_data IS 'Dados completos do webhook em formato JSON para auditoria';

COMMENT ON COLUMN pagamentos_fatura.conciliado IS 'TRUE se o pagamento foi conciliado com sistema financeiro/contábil';
COMMENT ON COLUMN pagamentos_fatura.data_conciliacao IS 'Data/hora da conciliação financeira';

-- Trigger para atualizar atualizado_em
CREATE OR REPLACE FUNCTION update_pagamentos_fatura_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_pagamentos_fatura_updated_at
    BEFORE UPDATE ON pagamentos_fatura
    FOR EACH ROW
    EXECUTE FUNCTION update_pagamentos_fatura_updated_at();

-- View para facilitar consultas por tipo de odontograma
CREATE OR REPLACE VIEW vw_pagamentos_por_tipo AS
SELECT 
    pf.*,
    to_nome.nome as tipo_odontograma_nome,
    v.documento_venda,
    v.valor_total as valor_total_venda,
    v.valor_entrada,
    v.valor_taxa_adesao,
    CASE 
        WHEN pf.eh_taxa_adicional THEN 'Taxa Adicional'
        WHEN pf.eh_entrada_redutora THEN 'Entrada Redutora' 
        ELSE 'Parcela Normal'
    END as categoria_pagamento
FROM pagamentos_fatura pf
JOIN vendas v ON pf.venda_id = v.id
LEFT JOIN tipos_odontograma to_nome ON pf.tipo_odontograma_id = to_nome.id;

COMMENT ON VIEW vw_pagamentos_por_tipo IS 'View que facilita consultas de pagamentos com informações dos tipos de odontograma e regras aplicadas';