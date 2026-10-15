-- Índices do Dashboard de Vendas.
-- IMPORTANTE: CREATE INDEX CONCURRENTLY deve ser executado fora de transação.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dashboard_vendas_data_ativa
    ON vendas (data_venda)
    WHERE status_venda != 'Cancelada';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dashboard_vendas_unidade_data_ativa
    ON vendas (unidade, data_venda)
    WHERE status_venda != 'Cancelada';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dashboard_venda_parcelas_pagamento_pago
    ON venda_parcelas (data_pagamento, venda_id)
    WHERE status_parcela IN ('Pago', 'Paga', 'PAID');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dashboard_venda_parcelas_vencimento
    ON venda_parcelas (data_vencimento, venda_id)
    WHERE status_parcela NOT IN ('Cancelada', 'CANCELED');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dashboard_carne_parcelas_pagamento_pago
    ON carne_parcelas (data_pagamento, carne_id)
    WHERE status IN ('PAID', 'Pago', 'pago');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dashboard_carne_parcelas_vencimento
    ON carne_parcelas (data_vencimento, carne_id)
    WHERE status NOT IN ('Cancelada', 'CANCELED');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dashboard_pre_vendas_pagamento
    ON pre_vendas_entradas (updated_at, pre_venda_id)
    WHERE status = 'pago';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dashboard_pre_vendas_unidade_pagamento
    ON pre_vendas_entradas (unidade, updated_at)
    WHERE status = 'pago';
