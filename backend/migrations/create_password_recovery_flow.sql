BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS phone_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS unidade_recuperacao VARCHAR(100),
    ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS password_recovery_requests (
    id UUID PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    purpose VARCHAR(32) NOT NULL CHECK (purpose IN ('password_reset', 'phone_verification')),
    account_digest VARCHAR(64) NOT NULL,
    requester_digest VARCHAR(64) NOT NULL,
    code_digest VARCHAR(64) NOT NULL,
    recipient_digest VARCHAR(64),
    reset_token_digest VARCHAR(64),
    sender_unit VARCHAR(100),
    attempts SMALLINT NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
    expires_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    reset_token_expires_at TIMESTAMPTZ,
    consumed_at TIMESTAMPTZ,
    delivery_status VARCHAR(24) NOT NULL DEFAULT 'not_sent',
    meta_message_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_password_recovery_account_created
    ON password_recovery_requests (account_digest, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_password_recovery_requester_created
    ON password_recovery_requests (requester_digest, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_password_recovery_user_purpose
    ON password_recovery_requests (user_id, purpose, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_password_recovery_reset_token
    ON password_recovery_requests (reset_token_digest)
    WHERE reset_token_digest IS NOT NULL;

COMMIT;
