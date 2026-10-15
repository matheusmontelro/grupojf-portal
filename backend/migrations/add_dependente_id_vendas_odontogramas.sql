-- Migration: Adicionar suporte para vendas e odontogramas de dependentes
-- Data: 2025-01-30

-- Adicionar coluna dependente_id na tabela vendas
ALTER TABLE vendas 
ADD COLUMN dependente_id INTEGER DEFAULT NULL;

-- Adicionar foreign key para dependentes
ALTER TABLE vendas 
ADD CONSTRAINT fk_venda_dependente 
FOREIGN KEY (dependente_id) REFERENCES dependentes(dependente_id)
ON DELETE SET NULL;

-- Adicionar índice para melhorar performance de consultas
CREATE INDEX idx_vendas_dependente_id ON vendas(dependente_id);

-- Adicionar coluna dependente_id na tabela odontogramas
ALTER TABLE odontogramas
ADD COLUMN dependente_id INTEGER DEFAULT NULL;

-- Adicionar foreign key para dependentes
ALTER TABLE odontogramas
ADD CONSTRAINT fk_odontograma_dependente
FOREIGN KEY (dependente_id) REFERENCES dependentes(dependente_id)
ON DELETE SET NULL;

-- Adicionar índice para melhorar performance de consultas
CREATE INDEX idx_odontogramas_dependente_id ON odontogramas(dependente_id);

-- Comentários explicativos
COMMENT ON COLUMN vendas.dependente_id IS 'ID do dependente quando a venda é para um dependente do titular. NULL quando a venda é para o próprio titular.';
COMMENT ON COLUMN odontogramas.dependente_id IS 'ID do dependente quando o odontograma é para um dependente. NULL quando é para o próprio paciente.';