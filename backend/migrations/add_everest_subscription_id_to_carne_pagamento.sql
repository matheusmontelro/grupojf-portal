ALTER TABLE carne_pagamento
ADD COLUMN IF NOT EXISTS everest_subscription_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_carne_pagamento_everest_subscription_id
    ON carne_pagamento(everest_subscription_id);

COMMENT ON COLUMN carne_pagamento.everest_subscription_id IS
    'ID da assinatura retornado pelo endpoint Everest (/everest/v1/subscriptions), separado do recurring_invoice_id salvo no carnê';
