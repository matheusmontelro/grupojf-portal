BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_patient_customer_id_scope
    ON asaas_patient_customers (
        id,
        unidade,
        environment,
        account_wallet_id
    );

CREATE TABLE IF NOT EXISTS asaas_sale_integrations (
    id BIGSERIAL PRIMARY KEY,
    venda_id INTEGER NOT NULL
        REFERENCES vendas(id) ON DELETE RESTRICT,
    asaas_patient_customer_id BIGINT NOT NULL,
    unidade VARCHAR(100) NOT NULL
        CHECK (BTRIM(unidade) <> ''),
    environment VARCHAR(16) NOT NULL
        CHECK (environment IN ('sandbox', 'production')),
    account_wallet_id VARCHAR(100) NOT NULL
        CHECK (BTRIM(account_wallet_id) <> ''),
    payment_method VARCHAR(40) NOT NULL
        CHECK (
            payment_method IN (
                'ASAAS_BOLETO_INSTALLMENT',
                'ASAAS_PIX_AUTOMATIC',
                'ASAAS_CREDIT_CARD_RECURRENT'
            )
        ),
    revision INTEGER NOT NULL DEFAULT 1
        CHECK (revision > 0),
    financial_fingerprint CHAR(64) NOT NULL
        CHECK (financial_fingerprint ~ '^[a-f0-9]{64}$'),
    idempotency_key VARCHAR(100) NOT NULL
        CHECK (BTRIM(idempotency_key) <> ''),
    external_reference VARCHAR(120) NOT NULL
        CHECK (BTRIM(external_reference) <> ''),
    status VARCHAR(24) NOT NULL DEFAULT 'pendente'
        CHECK (
            status IN (
                'pendente',
                'processando',
                'integrado',
                'retry',
                'conflito',
                'cancelado',
                'erro_terminal'
            )
        ),
    last_error_code VARCHAR(100)
        CHECK (
            last_error_code IS NULL
            OR (
                last_error_code ~ '^[A-Za-z][A-Za-z0-9_.:-]{0,99}$'
                AND last_error_code !~ '[0-9]{4,}'
                AND LENGTH(
                    REGEXP_REPLACE(last_error_code, '[^0-9]', '', 'g')
                ) <= 3
            )
        ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_asaas_sale_integration_customer_scope
        FOREIGN KEY (
            asaas_patient_customer_id,
            unidade,
            environment,
            account_wallet_id
        )
        REFERENCES asaas_patient_customers (
            id,
            unidade,
            environment,
            account_wallet_id
        )
        ON DELETE RESTRICT,
    CONSTRAINT uq_asaas_sale_integration_id_scope
        UNIQUE (id, unidade, environment, account_wallet_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_integration_sale_account
    ON asaas_sale_integrations (venda_id, environment, account_wallet_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_integration_sale
    ON asaas_sale_integrations (venda_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_integration_idempotency
    ON asaas_sale_integrations (
        environment,
        account_wallet_id,
        idempotency_key
    );

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_integration_external_reference
    ON asaas_sale_integrations (
        environment,
        account_wallet_id,
        external_reference
    );

CREATE INDEX IF NOT EXISTS idx_asaas_sale_integration_unit_status
    ON asaas_sale_integrations (unidade, status, updated_at);

CREATE TABLE IF NOT EXISTS asaas_sale_resources (
    id BIGSERIAL PRIMARY KEY,
    integration_id BIGINT NOT NULL,
    unidade VARCHAR(100) NOT NULL
        CHECK (BTRIM(unidade) <> ''),
    environment VARCHAR(16) NOT NULL
        CHECK (environment IN ('sandbox', 'production')),
    account_wallet_id VARCHAR(100) NOT NULL
        CHECK (BTRIM(account_wallet_id) <> ''),
    resource_type VARCHAR(32) NOT NULL
        CHECK (
            resource_type IN (
                'payment',
                'installment',
                'subscription',
                'checkout',
                'pix_authorization',
                'pix_instruction'
            )
        ),
    asaas_resource_id VARCHAR(120) NOT NULL
        CHECK (asaas_resource_id ~ '^[A-Za-z0-9_-]{1,120}$'),
    external_reference VARCHAR(120)
        CHECK (
            external_reference IS NULL
            OR BTRIM(external_reference) <> ''
        ),
    remote_status VARCHAR(80),
    last_event_type VARCHAR(100),
    last_event_at TIMESTAMPTZ,
    needs_reconciliation BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_asaas_sale_resource_integration_scope
        FOREIGN KEY (
            integration_id,
            unidade,
            environment,
            account_wallet_id
        )
        REFERENCES asaas_sale_integrations (
            id,
            unidade,
            environment,
            account_wallet_id
        )
        ON DELETE RESTRICT,
    CONSTRAINT uq_asaas_sale_resource_id_scope
        UNIQUE (id, unidade, environment, account_wallet_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_resource_remote
    ON asaas_sale_resources (
        environment,
        account_wallet_id,
        resource_type,
        asaas_resource_id
    );

CREATE INDEX IF NOT EXISTS idx_asaas_sale_resource_integration
    ON asaas_sale_resources (integration_id, resource_type);

CREATE INDEX IF NOT EXISTS idx_asaas_sale_resource_external_reference
    ON asaas_sale_resources (
        environment,
        account_wallet_id,
        external_reference
    )
    WHERE external_reference IS NOT NULL;

CREATE TABLE IF NOT EXISTS asaas_sale_webhook_events (
    id BIGSERIAL PRIMARY KEY,
    unidade VARCHAR(100) NOT NULL
        CHECK (BTRIM(unidade) <> ''),
    environment VARCHAR(16) NOT NULL
        CHECK (environment IN ('sandbox', 'production')),
    account_wallet_id VARCHAR(100) NOT NULL
        CHECK (BTRIM(account_wallet_id) <> ''),
    event_id VARCHAR(120) NOT NULL
        CHECK (event_id ~ '^evt_[A-Za-z0-9_&-]{1,116}$'),
    event_type VARCHAR(100) NOT NULL
        CHECK (event_type ~ '^[A-Z][A-Z0-9_]{1,99}$'),
    technical_data JSONB NOT NULL DEFAULT '{}'::JSONB,
    resource_id BIGINT,
    status VARCHAR(24) NOT NULL DEFAULT 'pendente'
        CHECK (
            status IN (
                'pendente',
                'processando',
                'retry',
                'processado',
                'ignorado',
                'erro_terminal'
            )
        ),
    attempt_count INTEGER NOT NULL DEFAULT 0
        CHECK (attempt_count >= 0),
    last_error_code VARCHAR(100)
        CHECK (
            last_error_code IS NULL
            OR (
                last_error_code ~ '^[A-Za-z][A-Za-z0-9_.:-]{0,99}$'
                AND last_error_code !~ '[0-9]{4,}'
                AND LENGTH(
                    REGEXP_REPLACE(last_error_code, '[^0-9]', '', 'g')
                ) <= 3
            )
        ),
    last_attempt_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_asaas_sale_webhook_retry_schedule
        CHECK ((status = 'retry') = (next_retry_at IS NOT NULL)),
    CONSTRAINT chk_asaas_sale_webhook_processing_claim
        CHECK (
            status <> 'processando'
            OR (attempt_count > 0 AND last_attempt_at IS NOT NULL)
        ),
    CONSTRAINT chk_asaas_sale_webhook_terminal_timestamp
        CHECK (
            (status IN ('processado', 'ignorado', 'erro_terminal')) =
            (processed_at IS NOT NULL)
        ),
    CONSTRAINT fk_asaas_sale_webhook_resource_scope
        FOREIGN KEY (
            resource_id,
            unidade,
            environment,
            account_wallet_id
        )
        REFERENCES asaas_sale_resources (
            id,
            unidade,
            environment,
            account_wallet_id
        )
        ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_webhook_event_account
    ON asaas_sale_webhook_events (
        environment,
        account_wallet_id,
        event_id
    );

CREATE INDEX IF NOT EXISTS idx_asaas_sale_webhook_dispatch
    ON asaas_sale_webhook_events (status, next_retry_at, received_at)
    WHERE status IN ('pendente', 'retry');

CREATE TABLE IF NOT EXISTS asaas_sale_integration_jobs (
    id BIGSERIAL PRIMARY KEY,
    integration_id BIGINT
        REFERENCES asaas_sale_integrations(id) ON DELETE RESTRICT,
    webhook_event_id BIGINT
        REFERENCES asaas_sale_webhook_events(id) ON DELETE RESTRICT,
    operation VARCHAR(48) NOT NULL
        CHECK (operation ~ '^[a-z][a-z0-9_]{1,47}$'),
    deduplication_key VARCHAR(160) NOT NULL
        CHECK (BTRIM(deduplication_key) <> ''),
    status VARCHAR(24) NOT NULL DEFAULT 'pendente'
        CHECK (
            status IN (
                'pendente',
                'processando',
                'retry',
                'integrado',
                'conflito',
                'erro_terminal',
                'superseded'
            )
        ),
    attempt_count INTEGER NOT NULL DEFAULT 0
        CHECK (attempt_count >= 0),
    last_error_code VARCHAR(100)
        CHECK (
            last_error_code IS NULL
            OR (
                last_error_code ~ '^[A-Za-z][A-Za-z0-9_.:-]{0,99}$'
                AND last_error_code !~ '[0-9]{4,}'
                AND LENGTH(
                    REGEXP_REPLACE(last_error_code, '[^0-9]', '', 'g')
                ) <= 3
            )
        ),
    last_attempt_at TIMESTAMPTZ,
    last_dispatched_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_asaas_sale_job_single_subject
        CHECK (NUM_NONNULLS(integration_id, webhook_event_id) = 1),
    CONSTRAINT chk_asaas_sale_job_retry_schedule
        CHECK ((status = 'retry') = (next_retry_at IS NOT NULL)),
    CONSTRAINT chk_asaas_sale_job_processing_claim
        CHECK (
            status <> 'processando'
            OR (attempt_count > 0 AND last_attempt_at IS NOT NULL)
        ),
    CONSTRAINT chk_asaas_sale_job_terminal_timestamp
        CHECK (
            (status IN ('integrado', 'conflito', 'erro_terminal', 'superseded')) =
            (completed_at IS NOT NULL)
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_job_deduplication
    ON asaas_sale_integration_jobs (operation, deduplication_key);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_job_active_subject
    ON asaas_sale_integration_jobs (
        COALESCE(integration_id, 0),
        COALESCE(webhook_event_id, 0),
        operation
    )
    WHERE status IN ('pendente', 'processando', 'retry');

CREATE INDEX IF NOT EXISTS idx_asaas_sale_job_dispatch
    ON asaas_sale_integration_jobs (
        status,
        next_retry_at,
        last_dispatched_at,
        created_at
    )
    WHERE status IN ('pendente', 'retry');

CREATE INDEX IF NOT EXISTS idx_asaas_sale_job_stale_claim
    ON asaas_sale_integration_jobs (status, last_attempt_at)
    WHERE status = 'processando';

COMMENT ON TABLE asaas_sale_integrations IS
    'Vinculo isolado entre a venda local e os recursos financeiros do Asaas.';

COMMENT ON COLUMN asaas_sale_integrations.account_wallet_id IS
    'Wallet da conta-mae da unidade; nao representa beneficiario de split.';

COMMENT ON TABLE asaas_sale_webhook_events IS
    'Inbox idempotente com somente identificadores tecnicos de eventos Asaas.';

COMMENT ON COLUMN asaas_sale_webhook_events.technical_data IS
    'Envelope allowlisted sem nome, documento, email, telefone, endereco ou segredo.';

COMMENT ON TABLE asaas_sale_integration_jobs IS
    'Outbox duravel; o broker recebe somente o ID numerico do job.';

COMMIT;
