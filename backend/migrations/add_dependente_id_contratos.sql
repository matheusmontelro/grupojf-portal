-- Migration: Adicionar suporte para contratos de dependentes
-- Data: 2025-01-06
-- Descrição: Permite que contratos sejam vinculados a dependentes, mantendo o titular como responsável financeiro

-- Adicionar coluna dependente_id na tabela contratos
ALTER TABLE contratos 
ADD COLUMN dependente_id INTEGER DEFAULT NULL;

-- Adicionar foreign key para dependentes
ALTER TABLE contratos 
ADD CONSTRAINT fk_contrato_dependente 
FOREIGN KEY (dependente_id) REFERENCES dependentes(dependente_id)
ON DELETE SET NULL;

-- Adicionar índice para melhorar performance de consultas
CREATE INDEX idx_contratos_dependente_id ON contratos(dependente_id);

-- Comentário explicativo
COMMENT ON COLUMN contratos.dependente_id IS 'ID do dependente quando o contrato é para tratamento de um dependente. NULL quando o tratamento é para o próprio titular.';

-- Adicionar coluna para rastrear também nas parcelas_contrato (para relatórios futuros)
ALTER TABLE parcelas_contrato
ADD COLUMN dependente_id INTEGER DEFAULT NULL;

-- Adicionar foreign key nas parcelas
ALTER TABLE parcelas_contrato
ADD CONSTRAINT fk_parcela_dependente 
FOREIGN KEY (dependente_id) REFERENCES dependentes(dependente_id)
ON DELETE SET NULL;

-- Índice para parcelas
CREATE INDEX idx_parcelas_contrato_dependente_id ON parcelas_contrato(dependente_id);

COMMENT ON COLUMN parcelas_contrato.dependente_id IS 'Referência ao dependente beneficiário do tratamento. Copiado do contrato para facilitar relatórios.';