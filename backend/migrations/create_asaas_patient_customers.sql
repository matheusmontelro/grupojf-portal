BEGIN;

CREATE TABLE IF NOT EXISTS asaas_patient_customers (
    id BIGSERIAL PRIMARY KEY,
    paciente_id INTEGER NOT NULL
        REFERENCES pacientes(paciente_id) ON DELETE CASCADE,
    unidade VARCHAR(100) NOT NULL
        CHECK (BTRIM(unidade) <> ''),
    environment VARCHAR(16) NOT NULL
        CHECK (environment IN ('sandbox', 'production')),
    account_wallet_id VARCHAR(100) NOT NULL
        CHECK (BTRIM(account_wallet_id) <> ''),
    asaas_customer_id VARCHAR(100)
        CHECK (asaas_customer_id IS NULL OR BTRIM(asaas_customer_id) <> ''),
    remote_creation_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    external_reference VARCHAR(120) NOT NULL
        CHECK (BTRIM(external_reference) <> ''),
    status VARCHAR(20) NOT NULL DEFAULT 'pendente'
        CHECK (status IN ('pendente', 'processando', 'integrado', 'erro', 'conflito')),
    attempt_count INTEGER NOT NULL DEFAULT 0
        CHECK (attempt_count >= 0),
    last_http_status SMALLINT
        CHECK (last_http_status IS NULL OR last_http_status BETWEEN 100 AND 599),
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
    last_sync_at TIMESTAMPTZ,
    last_synced_patient_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_asaas_patient_customer_integrated_id
        CHECK (status <> 'integrado' OR asaas_customer_id IS NOT NULL)
);

ALTER TABLE asaas_patient_customers
    ADD COLUMN IF NOT EXISTS remote_creation_allowed BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_patient_customer_account
    ON asaas_patient_customers (paciente_id, environment, account_wallet_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_customer_remote_account
    ON asaas_patient_customers (environment, account_wallet_id, asaas_customer_id)
    WHERE asaas_customer_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_customer_external_reference
    ON asaas_patient_customers (environment, account_wallet_id, external_reference);

CREATE INDEX IF NOT EXISTS idx_asaas_patient_customer_unit_status
    ON asaas_patient_customers (unidade, status);

CREATE INDEX IF NOT EXISTS idx_asaas_patient_customer_retry
    ON asaas_patient_customers (status, next_retry_at)
    WHERE status IN ('pendente', 'erro');

COMMENT ON TABLE asaas_patient_customers IS
    'Vincula pacientes locais aos customers do Asaas por ambiente e conta-mae.';

COMMENT ON COLUMN asaas_patient_customers.account_wallet_id IS
    'Wallet da conta-mae Asaas que detem o customer; nao e wallet de split.';

COMMENT ON COLUMN asaas_patient_customers.external_reference IS
    'Referencia deterministica sem dados pessoais enviada ao Asaas.';

COMMENT ON COLUMN asaas_patient_customers.remote_creation_allowed IS
    'Autoriza POST somente para paciente local novo ou ausencia remota confirmada.';

COMMIT;
