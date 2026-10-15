-- Adicionar campo dependente_id na tabela digital_contracts
ALTER TABLE digital_contracts 
ADD COLUMN IF NOT EXISTS dependente_id INTEGER REFERENCES dependentes(dependente_id);

-- Criar índice para melhor performance
CREATE INDEX IF NOT EXISTS idx_digital_contracts_dependente 
ON digital_contracts(dependente_id);

-- Comentário explicativo
COMMENT ON COLUMN digital_contracts.dependente_id IS 'ID do dependente quando o contrato é para tratamento de um dependente';