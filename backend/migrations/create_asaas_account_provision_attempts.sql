-- Lifecycle duravel para impedir duplicidade de subcontas quando o resultado
-- do POST remoto for incerto. Migration somente aditiva; a aplicacao depende
-- do fluxo operacional aprovado e nao e executada por este arquivo.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '10min';
SET LOCAL search_path = pg_catalog, public;

CREATE TABLE IF NOT EXISTS public.asaas_account_provision_attempts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    unidade VARCHAR(100) NOT NULL,
    environment VARCHAR(20) NOT NULL,
    attempt_token UUID NOT NULL,
    lifecycle_state VARCHAR(16) NOT NULL DEFAULT 'reserved',
    remote_attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error_code VARCHAR(64),
    remote_started_at TIMESTAMPTZ,
    remote_confirmed_at TIMESTAMPTZ,
    remote_uncertain_at TIMESTAMPTZ,
    remote_rejected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_asaas_account_provision_attempt_user
        FOREIGN KEY (user_id)
        REFERENCES public.users(id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_asaas_account_provision_attempt_token
        UNIQUE (attempt_token),
    CONSTRAINT chk_asaas_account_provision_attempt_environment
        CHECK (environment = 'sandbox'),
    CONSTRAINT chk_asaas_account_provision_attempt_state
        CHECK (
            lifecycle_state IN (
                'reserved', 'started', 'confirmed', 'rejected', 'uncertain'
            )
        ),
    CONSTRAINT chk_asaas_account_provision_attempt_count
        CHECK (remote_attempt_count IN (0, 1)),
    CONSTRAINT chk_asaas_account_provision_attempt_timeline
        CHECK (
            (
                lifecycle_state = 'reserved'
                AND remote_attempt_count = 0
                AND remote_started_at IS NULL
                AND remote_confirmed_at IS NULL
                AND remote_uncertain_at IS NULL
                AND remote_rejected_at IS NULL
            )
            OR
            (
                lifecycle_state = 'started'
                AND remote_attempt_count = 1
                AND remote_started_at IS NOT NULL
                AND remote_confirmed_at IS NULL
                AND remote_uncertain_at IS NULL
                AND remote_rejected_at IS NULL
            )
            OR
            (
                lifecycle_state = 'confirmed'
                AND remote_attempt_count = 1
                AND remote_started_at IS NOT NULL
                AND remote_confirmed_at IS NOT NULL
                AND remote_confirmed_at >= remote_started_at
                AND remote_uncertain_at IS NULL
                AND remote_rejected_at IS NULL
            )
            OR
            (
                lifecycle_state = 'rejected'
                AND remote_attempt_count = 1
                AND remote_started_at IS NOT NULL
                AND remote_confirmed_at IS NULL
                AND remote_uncertain_at IS NULL
                AND remote_rejected_at IS NOT NULL
                AND remote_rejected_at >= remote_started_at
            )
            OR
            (
                lifecycle_state = 'uncertain'
                AND remote_attempt_count = 1
                AND remote_started_at IS NOT NULL
                AND remote_confirmed_at IS NULL
                AND remote_uncertain_at IS NOT NULL
                AND remote_uncertain_at >= remote_started_at
                AND remote_rejected_at IS NULL
            )
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS
    uq_asaas_account_provision_attempt_active_user
    ON public.asaas_account_provision_attempts (user_id)
    WHERE lifecycle_state <> 'rejected';

CREATE INDEX IF NOT EXISTS idx_asaas_account_provision_attempts_unit_state
    ON public.asaas_account_provision_attempts (unidade, lifecycle_state);

COMMENT ON TABLE public.asaas_account_provision_attempts IS
    'Historico fail-closed de tentativas de criacao remota de subconta Asaas.';

COMMIT;
