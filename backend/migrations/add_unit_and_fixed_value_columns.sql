-- Migration: Add unit-specific rules and fixed value support
-- Date: 2025-01-30
-- Description: Adds columns for unit-specific rules and fixed BRL values

-- 1. Add tipo_calculo and valor_fixo_brl columns to regras_split
ALTER TABLE regras_split 
ADD COLUMN IF NOT EXISTS tipo_calculo VARCHAR(20) DEFAULT 'percentual',
ADD COLUMN IF NOT EXISTS valor_fixo_brl NUMERIC(10, 2);

-- 2. Add unidade column to regras_split
ALTER TABLE regras_split 
ADD COLUMN IF NOT EXISTS unidade VARCHAR(100) DEFAULT NULL;

-- 3. Add unidade column to empresa_regras_split
ALTER TABLE empresa_regras_split 
ADD COLUMN IF NOT EXISTS unidade VARCHAR(100) DEFAULT NULL;

-- 4. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_regras_split_unidade ON regras_split(unidade);
CREATE INDEX IF NOT EXISTS idx_empresa_regras_split_unidade ON empresa_regras_split(unidade);

-- 5. Add check constraint for tipo_calculo
ALTER TABLE regras_split DROP CONSTRAINT IF EXISTS check_tipo_calculo_valores;
ALTER TABLE regras_split ADD CONSTRAINT check_tipo_calculo_valores CHECK (
    (tipo_calculo = 'percentual' AND percentual IS NOT NULL AND valor_fixo_brl IS NULL) OR 
    (tipo_calculo = 'valor_fixo' AND valor_fixo_brl IS NOT NULL)
);

-- 6. Make percentual nullable for regras_split (since valor_fixo doesn't use it)
ALTER TABLE regras_split ALTER COLUMN percentual DROP NOT NULL;

-- 7. Add comments
COMMENT ON COLUMN regras_split.tipo_calculo IS 'Tipo de cálculo: percentual ou valor_fixo';
COMMENT ON COLUMN regras_split.valor_fixo_brl IS 'Valor fixo em BRL quando tipo_calculo = valor_fixo';
COMMENT ON COLUMN regras_split.unidade IS 'Unidade específica onde a regra se aplica. NULL significa todas as unidades';
COMMENT ON COLUMN empresa_regras_split.unidade IS 'Unidade específica onde a regra se aplica. NULL significa todas as unidades';

-- 8. Remove old unique constraints if they exist
ALTER TABLE regras_split DROP CONSTRAINT IF EXISTS regras_split_tipo_odontograma_id_cargo_id_key;
ALTER TABLE empresa_regras_split DROP CONSTRAINT IF EXISTS unique_empresa_regra_split;

-- 9. Create new unique constraints including unidade
ALTER TABLE regras_split DROP CONSTRAINT IF EXISTS unique_regra_split_unidade;
ALTER TABLE regras_split 
ADD CONSTRAINT unique_regra_split_unidade 
UNIQUE (tipo_odontograma_id, cargo_id, unidade);

ALTER TABLE empresa_regras_split DROP CONSTRAINT IF EXISTS unique_empresa_regra_split_unidade;
ALTER TABLE empresa_regras_split 
ADD CONSTRAINT unique_empresa_regra_split_unidade 
UNIQUE (empresa_id, tipo_odontograma_id, unidade);

-- 10. Create views for prioritized rules
CREATE OR REPLACE VIEW v_regras_split_priorizadas AS
SELECT 
    rs.*,
    CASE 
        WHEN rs.unidade IS NOT NULL THEN 1  -- High priority for specific rules
        ELSE 2                               -- Low priority for general rules
    END as prioridade
FROM regras_split rs
WHERE rs.ativo = true
ORDER BY prioridade, rs.id;

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

-- 11. Update existing rules to have tipo_calculo = 'percentual' where NULL
UPDATE regras_split 
SET tipo_calculo = 'percentual' 
WHERE tipo_calculo IS NULL;

-- Display completion message
DO $$
BEGIN
    RAISE NOTICE 'Migration completed successfully!';
    RAISE NOTICE 'Added columns: tipo_calculo, valor_fixo_brl, unidade';
    RAISE NOTICE 'Created indexes and constraints';
    RAISE NOTICE 'Created prioritization views';
END $$;