-- Migration: Criar tabela para armazenar splits de pré-vendas (entradas)
-- Data: 2025-01-08
-- Descrição: Armazena os splits calculados para entradas de vendas

-- Criar tabela pre_venda_splits
CREATE TABLE IF NOT EXISTS pre_venda_splits (
    id SERIAL PRIMARY KEY,
    pre_venda_id VARCHAR(100) NOT NULL,
    seller_id VARCHAR(50) NOT NULL,
    percentage DECIMAL(5,2) NOT NULL CHECK (percentage >= 0 AND percentage <= 100),
    absorb_balance BOOLEAN NOT NULL DEFAULT FALSE,
    valor_calculado DECIMAL(12,2) DEFAULT NULL, -- Valor em R$ que o seller receberá
    
    -- Metadados para rastreabilidade
    empresa_id INTEGER REFERENCES empresas(id),
    cargo_id INTEGER REFERENCES cargos(id),
    user_id INTEGER REFERENCES users(id),
    
    -- Controle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Chave estrangeira e índices
    CONSTRAINT fk_pre_venda_splits_pre_venda 
        FOREIGN KEY (pre_venda_id) 
        REFERENCES pre_vendas_entradas(pre_venda_id)
        ON DELETE CASCADE,
    
    -- Evitar duplicação de seller na mesma pré-venda
    CONSTRAINT unique_pre_venda_seller 
        UNIQUE (pre_venda_id, seller_id)
);

-- Criar índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_pre_venda_splits_pre_venda_id ON pre_venda_splits(pre_venda_id);
CREATE INDEX IF NOT EXISTS idx_pre_venda_splits_seller_id ON pre_venda_splits(seller_id);
CREATE INDEX IF NOT EXISTS idx_pre_venda_splits_empresa_id ON pre_venda_splits(empresa_id);
CREATE INDEX IF NOT EXISTS idx_pre_venda_splits_cargo_id ON pre_venda_splits(cargo_id);
CREATE INDEX IF NOT EXISTS idx_pre_venda_splits_user_id ON pre_venda_splits(user_id);
CREATE INDEX IF NOT EXISTS idx_pre_venda_splits_absorb_balance ON pre_venda_splits(absorb_balance);

-- Adicionar comentários para documentação
COMMENT ON TABLE pre_venda_splits IS 'Armazena a configuração de split de pagamento para pré-vendas (entradas)';
COMMENT ON COLUMN pre_venda_splits.pre_venda_id IS 'ID da pré-venda relacionada';
COMMENT ON COLUMN pre_venda_splits.seller_id IS 'ID do recebedor na API Delta';
COMMENT ON COLUMN pre_venda_splits.percentage IS 'Percentual do split';
COMMENT ON COLUMN pre_venda_splits.absorb_balance IS 'Se este seller absorve diferenças de arredondamento';
COMMENT ON COLUMN pre_venda_splits.valor_calculado IS 'Valor em reais que será recebido (percentage * valor_entrada / 100)';
COMMENT ON COLUMN pre_venda_splits.empresa_id IS 'Referência à empresa participante (opcional)';
COMMENT ON COLUMN pre_venda_splits.cargo_id IS 'Referência ao cargo do participante (opcional)';
COMMENT ON COLUMN pre_venda_splits.user_id IS 'Referência ao usuário específico (opcional)';

-- Criar trigger para atualizar updated_at
CREATE OR REPLACE FUNCTION update_pre_venda_splits_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_pre_venda_splits_updated_at
    BEFORE UPDATE ON pre_venda_splits
    FOR EACH ROW
    EXECUTE FUNCTION update_pre_venda_splits_updated_at();