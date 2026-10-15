BEGIN;

ALTER TABLE asaas_patient_customers
    ADD COLUMN IF NOT EXISTS requested_patient_updated_at TIMESTAMPTZ;

ALTER TABLE asaas_patient_customers
    ADD COLUMN IF NOT EXISTS remote_creation_allowed BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    FOR constraint_record IN
        SELECT conname
        FROM pg_constraint
        WHERE contype = 'f'
          AND conrelid = 'asaas_patient_customers'::regclass
          AND confrelid = 'pacientes'::regclass
          AND confdeltype = 'c'
    LOOP
        EXECUTE format(
            'ALTER TABLE asaas_patient_customers DROP CONSTRAINT %I',
            constraint_record.conname
        );
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_asaas_patient_customer_patient_restrict'
          AND conrelid = 'asaas_patient_customers'::regclass
    ) THEN
        ALTER TABLE asaas_patient_customers
            ADD CONSTRAINT fk_asaas_patient_customer_patient_restrict
            FOREIGN KEY (paciente_id)
            REFERENCES pacientes(paciente_id)
            ON DELETE RESTRICT;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS patient_delta_customers (
    id BIGSERIAL PRIMARY KEY,
    paciente_id INTEGER NOT NULL
        REFERENCES pacientes(paciente_id) ON DELETE RESTRICT,
    environment VARCHAR(16) NOT NULL
        CHECK (environment IN ('sandbox', 'production')),
    target_key VARCHAR(160) NOT NULL
        CHECK (BTRIM(target_key) <> ''),
    delta_customer_id VARCHAR(100)
        CHECK (
            delta_customer_id IS NULL
            OR BTRIM(delta_customer_id) <> ''
        ),
    remote_creation_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE patient_delta_customers
    ADD COLUMN IF NOT EXISTS remote_creation_allowed BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_delta_customer_target
    ON patient_delta_customers (paciente_id, environment, target_key);

CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_delta_customer_remote
    ON patient_delta_customers (environment, target_key, delta_customer_id)
    WHERE delta_customer_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS patient_integration_jobs (
    id BIGSERIAL PRIMARY KEY,
    paciente_id INTEGER NOT NULL
        REFERENCES pacientes(paciente_id) ON DELETE RESTRICT,
    provider VARCHAR(16) NOT NULL
        CHECK (provider IN ('delta', 'asaas')),
    target_key VARCHAR(160) NOT NULL
        CHECK (BTRIM(target_key) <> ''),
    environment VARCHAR(16) NOT NULL
        CHECK (environment IN ('sandbox', 'production')),
    patient_version TIMESTAMPTZ NOT NULL,
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
    last_dispatched_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    integrated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_patient_integration_processing_attempt
        CHECK (
            status <> 'processando'
            OR (attempt_count > 0 AND last_attempt_at IS NOT NULL)
        ),
    CONSTRAINT chk_patient_integration_retry_schedule
        CHECK (status <> 'retry' OR next_retry_at IS NOT NULL),
    CONSTRAINT chk_patient_integration_failure_code
        CHECK (
            status NOT IN ('retry', 'conflito', 'erro_terminal')
            OR last_error_code IS NOT NULL
        ),
    CONSTRAINT chk_patient_integration_integrated_at
        CHECK (status <> 'integrado' OR integrated_at IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_integration_job_version
    ON patient_integration_jobs (
        paciente_id,
        provider,
        target_key,
        environment,
        patient_version
    );

CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_integration_job_active
    ON patient_integration_jobs (
        paciente_id,
        provider,
        target_key,
        environment
    )
    WHERE status = 'processando';

CREATE INDEX IF NOT EXISTS idx_patient_integration_dispatch
    ON patient_integration_jobs (
        provider,
        environment,
        status,
        next_retry_at,
        last_dispatched_at,
        id
    )
    WHERE status IN ('pendente', 'retry');

CREATE INDEX IF NOT EXISTS idx_patient_integration_stale_claim
    ON patient_integration_jobs (
        provider,
        last_attempt_at,
        last_dispatched_at,
        id
    )
    WHERE status = 'processando';

CREATE INDEX IF NOT EXISTS idx_patient_integration_patient_history
    ON patient_integration_jobs (
        paciente_id,
        provider,
        target_key,
        environment,
        patient_version DESC
    );

COMMENT ON TABLE patient_integration_jobs IS
    'Outbox sem dados pessoais para sincronizar versoes de pacientes por provedor.';

COMMENT ON TABLE patient_delta_customers IS
    'Vinculo tecnico entre paciente local e customer Delta, sem dados pessoais.';

COMMENT ON COLUMN patient_delta_customers.target_key IS
    'Destino tecnico Delta usado para separar unidade e ambiente.';

COMMENT ON COLUMN patient_delta_customers.delta_customer_id IS
    'Identificador tecnico retornado pela Delta; nao armazena documento.';

COMMENT ON COLUMN patient_delta_customers.remote_creation_allowed IS
    'Autoriza POST somente para paciente local novo ou ausencia remota confirmada.';

COMMENT ON COLUMN patient_integration_jobs.target_key IS
    'Identificador tecnico e nao pessoal do destino remoto configurado.';

COMMENT ON COLUMN patient_integration_jobs.patient_version IS
    'Versao local imutavel, derivada de pacientes.updated_at.';

COMMENT ON COLUMN asaas_patient_customers.requested_patient_updated_at IS
    'Versao mais recente solicitada para sincronizacao do customer.';

COMMIT;
