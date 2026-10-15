-- Criar tabela para armazenar splits de faturas avulsas
CREATE TABLE IF NOT EXISTS fatura_avulsa_splits (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL,
    seller_id INTEGER NOT NULL,
    cargo_id INTEGER,
    user_id INTEGER,
    empresa_id INTEGER,
    percentage DECIMAL(5,2) NOT NULL,
    cycles_to_participate INTEGER DEFAULT 1,
    absorb_balance BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Criar índices separadamente
CREATE INDEX IF NOT EXISTS idx_fatura_avulsa_splits_invoice_id ON fatura_avulsa_splits (invoice_id);
CREATE INDEX IF NOT EXISTS idx_fatura_avulsa_splits_seller_id ON fatura_avulsa_splits (seller_id);
CREATE INDEX IF NOT EXISTS idx_fatura_avulsa_splits_cargo_id ON fatura_avulsa_splits (cargo_id);
CREATE INDEX IF NOT EXISTS idx_fatura_avulsa_splits_user_id ON fatura_avulsa_splits (user_id);
CREATE INDEX IF NOT EXISTS idx_fatura_avulsa_splits_empresa_id ON fatura_avulsa_splits (empresa_id);

-- Comentários nas colunas
COMMENT ON TABLE fatura_avulsa_splits IS 'Armazena a configuração de split de pagamento para faturas avulsas';
COMMENT ON COLUMN fatura_avulsa_splits.invoice_id IS 'ID da fatura avulsa na API Delta';
COMMENT ON COLUMN fatura_avulsa_splits.seller_id IS 'ID do recebedor na API Delta';
COMMENT ON COLUMN fatura_avulsa_splits.cargo_id IS 'ID do cargo associado ao split (opcional)';
COMMENT ON COLUMN fatura_avulsa_splits.user_id IS 'ID do usuário associado ao split (opcional)';
COMMENT ON COLUMN fatura_avulsa_splits.empresa_id IS 'ID da empresa associada ao split (opcional)';
COMMENT ON COLUMN fatura_avulsa_splits.percentage IS 'Percentual do split';
COMMENT ON COLUMN fatura_avulsa_splits.cycles_to_participate IS 'Número de ciclos de participação (sempre 1 para avulsa)';
COMMENT ON COLUMN fatura_avulsa_splits.absorb_balance IS 'Se absorve diferenças de arredondamento';