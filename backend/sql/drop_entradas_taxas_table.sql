-- Remover tabela entradas_taxas e seus índices
DROP TABLE IF EXISTS entradas_taxas CASCADE;

-- Remover função de trigger se existir
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;