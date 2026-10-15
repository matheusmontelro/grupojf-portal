-- Migration: Adicionar suporte para valor fixo em BRL nos splits de cargos
-- Data: 2025-01-29

-- 1. Adicionar colunas para tipo de cálculo e valor fixo
ALTER TABLE regras_split 
ADD COLUMN tipo_calculo VARCHAR(20) DEFAULT 'percentual' CHECK (tipo_calculo IN ('percentual', 'valor_fixo')),
ADD COLUMN valor_fixo_brl NUMERIC(10, 2) DEFAULT NULL;

-- 2. Criar índice para performance
CREATE INDEX idx_regras_split_tipo_calculo ON regras_split(tipo_calculo);

-- 3. Adicionar comentários para documentação
COMMENT ON COLUMN regras_split.tipo_calculo IS 'Define se o cálculo é por percentual ou valor fixo em BRL';
COMMENT ON COLUMN regras_split.valor_fixo_brl IS 'Valor fixo em reais quando tipo_calculo = valor_fixo';

-- 4. Adicionar constraint para garantir integridade dos dados
ALTER TABLE regras_split ADD CONSTRAINT check_tipo_calculo_valores 
CHECK (
    (tipo_calculo = 'percentual' AND percentual IS NOT NULL AND percentual >= 0 AND percentual <= 100 AND valor_fixo_brl IS NULL) 
    OR 
    (tipo_calculo = 'valor_fixo' AND valor_fixo_brl IS NOT NULL AND valor_fixo_brl >= 0)
);

-- 5. Atualizar registros existentes para garantir consistência
UPDATE regras_split 
SET tipo_calculo = 'percentual', valor_fixo_brl = NULL 
WHERE tipo_calculo IS NULL;

-- Rollback (caso necessário):
-- ALTER TABLE regras_split DROP CONSTRAINT check_tipo_calculo_valores;
-- DROP INDEX idx_regras_split_tipo_calculo;
-- ALTER TABLE regras_split DROP COLUMN tipo_calculo, DROP COLUMN valor_fixo_brl;