-- Adicionar colunas para rastrear carnê e pré-venda nas vendas
ALTER TABLE vendas
ADD COLUMN IF NOT EXISTS carne_id INTEGER REFERENCES carne_pagamento(id),
ADD COLUMN IF NOT EXISTS pre_venda_id VARCHAR(100);

-- Adicionar índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_vendas_carne_id ON vendas(carne_id);
CREATE INDEX IF NOT EXISTS idx_vendas_pre_venda_id ON vendas(pre_venda_id);

-- Adicionar coluna venda_id no carne_pagamento para referência bidirecional
ALTER TABLE carne_pagamento
ADD COLUMN IF NOT EXISTS venda_id INTEGER REFERENCES vendas(id);

CREATE INDEX IF NOT EXISTS idx_carne_pagamento_venda_id ON carne_pagamento(venda_id);

-- Comentários para documentação
COMMENT ON COLUMN vendas.carne_id IS 'ID do carnê associado a esta venda';
COMMENT ON COLUMN vendas.pre_venda_id IS 'ID da pré-venda (entrada) associada a esta venda';
COMMENT ON COLUMN carne_pagamento.venda_id IS 'ID da venda associada a este carnê';