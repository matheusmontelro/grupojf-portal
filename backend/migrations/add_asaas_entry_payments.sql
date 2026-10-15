-- Entrada avulsa do Carnê Asaas. Esta migration é somente aditiva e deve ser
-- executada separadamente, após validação manual e aprovação operacional.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '10min';
SET LOCAL search_path = pg_catalog, public;

CREATE TABLE IF NOT EXISTS public.asaas_entry_integrations (
    id BIGSERIAL PRIMARY KEY,
    pre_venda_id VARCHAR(100) NOT NULL UNIQUE
        REFERENCES public.pre_vendas_entradas(pre_venda_id) ON DELETE RESTRICT,
    asaas_patient_customer_id BIGINT NOT NULL,
    odontograma_id INTEGER NOT NULL
        REFERENCES public.odontogramas(id) ON DELETE RESTRICT,
    unidade VARCHAR(100) NOT NULL CHECK (BTRIM(unidade) <> ''),
    environment VARCHAR(16) NOT NULL CHECK (environment = 'sandbox'),
    account_wallet_id VARCHAR(100) NOT NULL CHECK (BTRIM(account_wallet_id) <> ''),
    payment_method VARCHAR(40) NOT NULL CHECK (
        payment_method IN (
            'ASAAS_ENTRY_PIX',
            'ASAAS_ENTRY_BOLETO',
            'ASAAS_ENTRY_CREDIT_CARD'
        )
    ),
    card_installments INTEGER NOT NULL DEFAULT 1
        CHECK (card_installments BETWEEN 1 AND 12),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    idempotency_key UUID NOT NULL,
    request_fingerprint CHAR(64) NOT NULL
        CHECK (request_fingerprint ~ '^[a-f0-9]{64}$'),
    external_reference VARCHAR(120) NOT NULL CHECK (BTRIM(external_reference) <> ''),
    status VARCHAR(28) NOT NULL DEFAULT 'pendente' CHECK (
        status IN (
            'pendente', 'processando', 'aguardando_pagamento', 'pago',
            'retry', 'conflito', 'cancelado', 'expirado',
            'erro_terminal', 'resultado_incerto'
        )
    ),
    remote_creation_state VARCHAR(24) NOT NULL DEFAULT 'nao_iniciado' CHECK (
        remote_creation_state IN (
            'nao_iniciado', 'requisicao_iniciada', 'resultado_incerto',
            'confirmado', 'falha_terminal'
        )
    ),
    remote_payment_id VARCHAR(120),
    remote_status VARCHAR(80),
    checkout_url TEXT,
    remote_attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (remote_attempt_count >= 0),
    last_error_code VARCHAR(100),
    last_attempt_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_asaas_entry_customer_scope FOREIGN KEY (
        asaas_patient_customer_id, unidade, environment, account_wallet_id
    ) REFERENCES public.asaas_patient_customers (
        id, unidade, environment, account_wallet_id
    ) ON DELETE RESTRICT,
    CONSTRAINT uq_asaas_entry_id_scope UNIQUE (
        id, unidade, environment, account_wallet_id
    ),
    CONSTRAINT chk_asaas_entry_card_installments CHECK (
        (payment_method = 'ASAAS_ENTRY_CREDIT_CARD')
        OR card_installments = 1
    ),
    CONSTRAINT chk_asaas_entry_remote_identity CHECK (
        (remote_payment_id IS NULL AND checkout_url IS NULL)
        OR (remote_payment_id IS NOT NULL AND checkout_url IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_entry_idempotency
    ON public.asaas_entry_integrations (
        environment, account_wallet_id, idempotency_key
    );

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_entry_external_reference
    ON public.asaas_entry_integrations (
        environment, account_wallet_id, external_reference
    );

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_entry_remote_payment
    ON public.asaas_entry_integrations (
        environment, account_wallet_id, remote_payment_id
    ) WHERE remote_payment_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_asaas_entry_dispatch
    ON public.asaas_entry_integrations (unidade, status, updated_at);

CREATE TABLE IF NOT EXISTS public.asaas_entry_jobs (
    id BIGSERIAL PRIMARY KEY,
    entry_integration_id BIGINT NOT NULL
        REFERENCES public.asaas_entry_integrations(id) ON DELETE RESTRICT,
    operation VARCHAR(48) NOT NULL CHECK (
        operation IN ('provisionar_entrada', 'reconciliar_entrada')
    ),
    status VARCHAR(24) NOT NULL DEFAULT 'pendente' CHECK (
        status IN (
            'pendente', 'processando', 'retry', 'integrado',
            'conflito', 'erro_terminal'
        )
    ),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error_code VARCHAR(100),
    last_attempt_at TIMESTAMPTZ,
    last_dispatched_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_asaas_entry_job_retry CHECK (
        (status = 'retry') = (next_retry_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_entry_active_job
    ON public.asaas_entry_jobs (entry_integration_id, operation)
    WHERE status IN ('pendente', 'processando', 'retry');

CREATE INDEX IF NOT EXISTS idx_asaas_entry_job_dispatch
    ON public.asaas_entry_jobs (
        status, next_retry_at, last_dispatched_at, created_at
    ) WHERE status IN ('pendente', 'retry', 'processando');

-- Uma entrada Asaas não pode ser consumida por mais de uma venda final.
CREATE UNIQUE INDEX IF NOT EXISTS uq_vendas_asaas_pre_venda
    ON public.vendas (pre_venda_id)
    WHERE pre_venda_id LIKE 'PV-AS-%';

COMMENT ON TABLE public.asaas_entry_integrations IS
    'Cobranças de entrada Sandbox isoladas do carnê e sem dados de cartão.';
COMMENT ON TABLE public.asaas_entry_jobs IS
    'Outbox da entrada Asaas; o broker recebe somente o ID numérico.';

COMMIT;
