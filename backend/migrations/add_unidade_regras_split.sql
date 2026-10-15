-- Migration: Adicionar campo unidade nas regras de split
-- Data: 2025-01-30
-- Descrição: Permite criar regras específicas por unidade J&F

-- 1. Adicionar coluna unidade na tabela regras_split (cargos)
ALTER TABLE regras_split 
ADD COLUMN unidade VARCHAR(100) DEFAULT NULL;

-- 2. Adicionar coluna unidade na tabela empresa_regras_split
ALTER TABLE empresa_regras_split 
ADD COLUMN unidade VARCHAR(100) DEFAULT NULL;

-- 3. Criar índices para melhor performance
CREATE INDEX idx_regras_split_unidade ON regras_split(unidade);
CREATE INDEX idx_empresa_regras_split_unidade ON empresa_regras_split(unidade);

-- 4. Adicionar comentários
COMMENT ON COLUMN regras_split.unidade IS 'Unidade específica onde a regra se aplica. NULL significa todas as unidades';
COMMENT ON COLUMN empresa_regras_split.unidade IS 'Unidade específica onde a regra se aplica. NULL significa todas as unidades';

-- 5. Remover constraints únicas antigas
ALTER TABLE regras_split DROP CONSTRAINT IF EXISTS regras_split_tipo_odontograma_id_cargo_id_key;
ALTER TABLE empresa_regras_split DROP CONSTRAINT IF EXISTS unique_empresa_regra_split;

-- 6. Criar novas constraints únicas incluindo unidade
ALTER TABLE regras_split 
ADD CONSTRAINT unique_regra_split_unidade 
UNIQUE (tipo_odontograma_id, cargo_id, unidade);

ALTER TABLE empresa_regras_split 
ADD CONSTRAINT unique_empresa_regra_split_unidade 
UNIQUE (empresa_id, tipo_odontograma_id, unidade);

-- 7. Criar view para visualizar regras com prioridade (unidade específica > geral)
CREATE OR REPLACE VIEW v_regras_split_priorizadas AS
SELECT 
    rs.*,
    CASE 
        WHEN rs.unidade IS NOT NULL THEN 1  -- Prioridade alta para regras específicas
        ELSE 2                               -- Prioridade baixa para regras gerais
    END as prioridade
FROM regras_split rs
WHERE rs.ativo = true
ORDER BY prioridade, rs.id;

-- 8. Criar view similar para empresas
CREATE OR REPLACE VIEW v_empresa_regras_split_priorizadas AS
SELECT 
    ers.*,
    CASE 
        WHEN ers.unidade IS NOT NULL THEN 1
        ELSE 2
    END as prioridade
FROM empresa_regras_split ers
WHERE ers.ativo = true
ORDER BY prioridade, ers.id;

-- Rollback (caso necessário):
-- DROP VIEW IF EXISTS v_regras_split_priorizadas;
-- DROP VIEW IF EXISTS v_empresa_regras_split_priorizadas;
-- ALTER TABLE regras_split DROP CONSTRAINT IF EXISTS unique_regra_split_unidade;
-- ALTER TABLE empresa_regras_split DROP CONSTRAINT IF EXISTS unique_empresa_regra_split_unidade;
-- DROP INDEX IF EXISTS idx_regras_split_unidade;
-- DROP INDEX IF EXISTS idx_empresa_regras_split_unidade;
-- ALTER TABLE regras_split DROP COLUMN unidade;
-- ALTER TABLE empresa_regras_split DROP COLUMN unidade;