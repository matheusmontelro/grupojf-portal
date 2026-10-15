ALTER TABLE fatura_recorrente
ADD COLUMN IF NOT EXISTS everest_subscription_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_fatura_recorrente_everest_subscription_id
    ON fatura_recorrente(everest_subscription_id);

COMMENT ON COLUMN fatura_recorrente.everest_subscription_id IS
    'ID da assinatura retornado pelo endpoint Everest (/everest/v1/subscriptions), separado do ID local salvo em subscription_id';
