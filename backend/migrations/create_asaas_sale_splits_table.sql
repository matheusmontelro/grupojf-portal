-- Migration: Create asaas_sale_splits table
-- Date: 2026-07-25
-- Description: Persists each wallet-level split applied to a sale when sending
--   the payment to Asaas. One row per (venda, wallet) pair, recording the
--   destination wallet, the kind of split value and the value itself.
--
-- Notes:
--   * split_kind discriminates whether the split sent to Asaas used
--     percentualValue ('percentual') or totalFixedValue ('total_fixed'); the
--     decision belongs to asaas_split_service. Only percentual_value OR
--     total_fixed_value is filled, accordingly.
--   * Guaranteeing that exactly one of percentual_value/total_fixed_value is
--     filled is the application's responsibility (validate before INSERT). The
--     simple CHECK constraints below encode the value ranges; a complex XOR
--     CHECK is intentionally omitted to keep migrations cheap to evolve.

CREATE TABLE IF NOT EXISTS asaas_sale_splits (
    id BIGSERIAL PRIMARY KEY,
    venda_id BIGINT NOT NULL,
    unidade VARCHAR(100) NOT NULL,
    environment VARCHAR(20) NOT NULL,
    cargo_id INTEGER REFERENCES cargos(id),
    user_id BIGINT REFERENCES users(id),
    empresa_id INTEGER REFERENCES empresas(id),
    wallet_id VARCHAR(64) NOT NULL,
    split_kind VARCHAR(20) NOT NULL,
    percentual_value NUMERIC(5,2),
    total_fixed_value NUMERIC(12,2),
    remote_account_wallet_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- CHECKs nomeadas com prefixo chk_ para casar com o contrato de privilegios
    -- do preflight (asaas_sales_preflight._REQUIRED_CONSTRAINTS).
    CONSTRAINT chk_asaas_sale_splits_split_kind
        CHECK (split_kind::text = ANY (ARRAY['percentual'::character varying,
            'total_fixed'::character varying]::text[])),
    CONSTRAINT chk_asaas_sale_splits_percentual_value
        CHECK (percentual_value >= 0::numeric AND percentual_value <= 100::numeric)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_splits_venda_wallet
    ON asaas_sale_splits (venda_id, wallet_id);
CREATE INDEX IF NOT EXISTS idx_asaas_sale_splits_venda
    ON asaas_sale_splits (venda_id);
CREATE INDEX IF NOT EXISTS idx_asaas_sale_splits_unidade_env
    ON asaas_sale_splits (unidade, environment);

COMMENT ON TABLE asaas_sale_splits IS
    'Splits por wallet aplicados a cada venda no envio ao Asaas (PF/empresas).';
COMMENT ON COLUMN asaas_sale_splits.split_kind IS
    'Define se o split usou percentualValue (percentual) ou totalFixedValue (total_fixed) no Asaas.';
COMMENT ON COLUMN asaas_sale_splits.percentual_value IS
    'Preenchido quando split_kind = percentual; caso contrario NULL.';
COMMENT ON COLUMN asaas_sale_splits.total_fixed_value IS
    'Preenchido quando split_kind = total_fixed; caso contrario NULL. A aplicacao garante exatamente um dos dois preenchido.';
