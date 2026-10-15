-- Criar tabela para armazenar splits de fatura recorrente
CREATE TABLE IF NOT EXISTS fatura_recorrente_splits (
    id SERIAL PRIMARY KEY,
    subscription_id INTEGER NOT NULL, -- ID da assinatura/fatura recorrente no Delta
    seller_id VARCHAR(50) NOT NULL,   -- ID do seller/receiver no Delta
    percentage DECIMAL(5, 2) NOT NULL CHECK (percentage >= 0 AND percentage <= 100),
    cycles_to_participate INTEGER NOT NULL DEFAULT 1,
    absorb_balance BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Metadados adicionais do nosso sistema
    cargo_id INTEGER REFERENCES cargos(id),
    user_id INTEGER REFERENCES users(id),
    empresa_id INTEGER REFERENCES empresas(id),
    
    -- Controle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Índices
    CONSTRAINT unique_subscription_seller UNIQUE (subscription_id, seller_id)
);

-- Criar índices para melhor performance
CREATE INDEX idx_fatura_recorrente_splits_subscription ON fatura_recorrente_splits(subscription_id);
CREATE INDEX idx_fatura_recorrente_splits_seller ON fatura_recorrente_splits(seller_id);
CREATE INDEX idx_fatura_recorrente_splits_cargo ON fatura_recorrente_splits(cargo_id);
CREATE INDEX idx_fatura_recorrente_splits_user ON fatura_recorrente_splits(user_id);
CREATE INDEX idx_fatura_recorrente_splits_empresa ON fatura_recorrente_splits(empresa_id);

-- Adicionar comentários para documentação
COMMENT ON TABLE fatura_recorrente_splits IS 'Armazena configurações de split (divisão de receita) para faturas recorrentes';
COMMENT ON COLUMN fatura_recorrente_splits.subscription_id IS 'ID da assinatura/fatura recorrente no sistema Delta';
COMMENT ON COLUMN fatura_recorrente_splits.seller_id IS 'ID do seller/receiver no sistema Delta';
COMMENT ON COLUMN fatura_recorrente_splits.percentage IS 'Percentual de participação no split';
COMMENT ON COLUMN fatura_recorrente_splits.cycles_to_participate IS 'Número de ciclos que o seller participa';
COMMENT ON COLUMN fatura_recorrente_splits.absorb_balance IS 'Se este seller absorve diferenças de arredondamento';
COMMENT ON COLUMN fatura_recorrente_splits.cargo_id IS 'Referência ao cargo do participante (opcional)';
COMMENT ON COLUMN fatura_recorrente_splits.user_id IS 'Referência ao usuário específico (opcional)';
COMMENT ON COLUMN fatura_recorrente_splits.empresa_id IS 'Referência à empresa participante (opcional)';