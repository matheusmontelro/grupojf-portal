-- Adicionar novas formas de pagamento para integração com Delta
-- Formas de pagamento para FATURA AVULSA (pagamento único)
INSERT INTO formas_pagamento (nome, categorias, ativo) VALUES
('CARTÃO CRÉDITO AVULSO DELTA', '["VENDA", "TAXA ADESAO", "CREDIT_CARD", "AVULSO"]', true),
('PIX AVULSO DELTA', '["VENDA", "TAXA ADESAO", "PIX", "AVULSO"]', true),
('BOLETO AVULSO DELTA', '["VENDA", "TAXA ADESAO", "BANK_SLIP", "AVULSO"]', true);

-- Forma de pagamento para FATURA RECORRENTE (apenas cartão de crédito)
INSERT INTO formas_pagamento (nome, categorias, ativo) VALUES
('CARTÃO CRÉDITO RECORRENTE DELTA', '["REC", "VENDA", "CREDIT_CARD", "RECORRENTE", "AUTOMATIC_CHARGE"]', true);

-- Adicionar campos na tabela vendas para suportar entrada + parcelamento
ALTER TABLE vendas ADD COLUMN IF NOT EXISTS tem_entrada BOOLEAN DEFAULT FALSE;
ALTER TABLE vendas ADD COLUMN IF NOT EXISTS valor_entrada DECIMAL(10,2);
ALTER TABLE vendas ADD COLUMN IF NOT EXISTS forma_pagamento_entrada_id INTEGER REFERENCES formas_pagamento(id);
ALTER TABLE vendas ADD COLUMN IF NOT EXISTS valor_parcelado DECIMAL(10,2);

-- Adicionar índices para performance
CREATE INDEX IF NOT EXISTS idx_vendas_tem_entrada ON vendas(tem_entrada);
CREATE INDEX IF NOT EXISTS idx_vendas_forma_pagamento_entrada ON vendas(forma_pagamento_entrada_id);