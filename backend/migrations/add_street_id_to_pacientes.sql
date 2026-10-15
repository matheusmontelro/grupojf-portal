-- Migration: Adicionar coluna street_id na tabela pacientes
-- Data: 2025-07-17
-- Descrição: Adiciona referência ao vendedor street selecionado como origem do paciente

-- Adicionar coluna street_id
ALTER TABLE pacientes 
ADD COLUMN street_id INTEGER DEFAULT NULL;

-- Adicionar chave estrangeira para a tabela users
ALTER TABLE pacientes
ADD CONSTRAINT fk_pacientes_street_id 
FOREIGN KEY (street_id) 
REFERENCES users(id) 
ON DELETE SET NULL;

-- Criar índice para melhor performance
CREATE INDEX idx_pacientes_street_id ON pacientes(street_id);

-- Comentário na coluna
COMMENT ON COLUMN pacientes.street_id IS 'ID do vendedor street que originou o cadastro do paciente';