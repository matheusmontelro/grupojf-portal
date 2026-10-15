-- Plano imutavel usado antes de qualquer criacao remota de venda no Asaas.
-- Esta migration e somente aditiva e deve ser aplicada pelo fluxo operacional
-- aprovado; este arquivo nao executa nenhuma alteracao por conta propria.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '10min';
SET LOCAL search_path = pg_catalog, public;

CREATE TABLE IF NOT EXISTS public.asaas_sale_split_plans (
    id BIGSERIAL PRIMARY KEY,
    integration_id BIGINT NOT NULL,
    venda_id BIGINT NOT NULL,
    payment_method VARCHAR(32) NOT NULL,
    contexto VARCHAR(16) NOT NULL,
    unidade VARCHAR(100) NOT NULL,
    environment VARCHAR(20) NOT NULL,
    account_wallet_id VARCHAR(64) NOT NULL,
    charge_value NUMERIC(12,2) NOT NULL,
    plan_json JSONB NOT NULL,
    payload_json JSONB NOT NULL,
    plan_sha256 CHAR(64) NOT NULL,
    payload_sha256 CHAR(64) NOT NULL,
    lifecycle_state VARCHAR(16) NOT NULL DEFAULT 'sealed',
    remote_attempt_count INTEGER NOT NULL DEFAULT 0,
    remote_started_at TIMESTAMPTZ,
    remote_confirmed_at TIMESTAMPTZ,
    remote_uncertain_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_asaas_sale_split_plan_integration_scope
        FOREIGN KEY (
            integration_id,
            venda_id,
            unidade,
            environment,
            account_wallet_id
        )
        REFERENCES public.asaas_sale_integrations (
            id,
            venda_id,
            unidade,
            environment,
            account_wallet_id
        )
        ON DELETE RESTRICT,
    CONSTRAINT uq_asaas_sale_split_plans_integration
        UNIQUE (integration_id),
    CONSTRAINT chk_asaas_sale_split_plans_context
        CHECK (contexto IN ('carne', 'pix', 'cartao', 'entrada')),
    CONSTRAINT chk_asaas_sale_split_plans_state
        CHECK (
            lifecycle_state IN (
                'sealed', 'started', 'confirmed', 'uncertain',
                'blocked', 'rejected'
            )
        ),
    CONSTRAINT chk_asaas_sale_split_plans_charge
        CHECK (charge_value > 0),
    CONSTRAINT chk_asaas_sale_split_plans_attempt
        CHECK (remote_attempt_count IN (0, 1)),
    CONSTRAINT chk_asaas_sale_split_plans_timeline
        CHECK (
            (
                lifecycle_state IN ('sealed', 'blocked')
                AND remote_attempt_count = 0
                AND remote_started_at IS NULL
                AND remote_confirmed_at IS NULL
                AND remote_uncertain_at IS NULL
            )
            OR
            (
                lifecycle_state IN ('started', 'rejected')
                AND remote_attempt_count = 1
                AND remote_started_at IS NOT NULL
                AND remote_confirmed_at IS NULL
                AND remote_uncertain_at IS NULL
            )
            OR
            (
                lifecycle_state = 'confirmed'
                AND remote_attempt_count = 1
                AND remote_started_at IS NOT NULL
                AND remote_confirmed_at IS NOT NULL
                AND remote_confirmed_at >= remote_started_at
                AND remote_uncertain_at IS NULL
            )
            OR
            (
                lifecycle_state = 'uncertain'
                AND remote_attempt_count = 1
                AND remote_started_at IS NOT NULL
                AND remote_confirmed_at IS NULL
                AND remote_uncertain_at IS NOT NULL
                AND remote_uncertain_at >= remote_started_at
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_asaas_sale_split_plans_sale
    ON public.asaas_sale_split_plans (venda_id);

COMMENT ON TABLE public.asaas_sale_split_plans IS
    'Snapshot imutavel do plano e payload de split selado antes do POST Asaas.';

COMMIT;
