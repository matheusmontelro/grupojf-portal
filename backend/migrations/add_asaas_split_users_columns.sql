-- Migration: Add Asaas split/provisioning columns to users
-- Date: 2026-07-25
-- Description: Adds columns to support Asaas wallet/account integration per user
--   (PF subaccounts and PJ wallet references) for the sale split flow.
--
-- Security notes:
--   * asaas_account_api_key_enc holds the apiKey of an Asaas subaccount. It MUST
--     be encrypted in app via Fernet using the ASAAS_ACCOUNT_API_KEY_SECRET
--     environment variable (see app/security/asaas_account_secret.py).
--   * The plaintext apiKey MUST NEVER be logged, returned in read payloads, or
--     committed. UserRead intentionally excludes this column.
--   * Grant only SELECT/UPDATE on these columns to the Asaas runtime role;
--     there is no INSERT path because users already exist.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS asaas_wallet_id VARCHAR(64),
ADD COLUMN IF NOT EXISTS asaas_account_id VARCHAR(64),
ADD COLUMN IF NOT EXISTS asaas_integration_status VARCHAR(50),
ADD COLUMN IF NOT EXISTS asaas_account_api_key_enc TEXT,
ADD COLUMN IF NOT EXISTS asaas_account_updated_at TIMESTAMPTZ;

COMMENT ON COLUMN users.asaas_wallet_id IS
    'Wallet id da subconta Asaas (PF) ou wallet de referencia PJ associada ao usuario.';
COMMENT ON COLUMN users.asaas_account_id IS
    'Account id da subconta Asaas do usuario, quando aplicavel.';
COMMENT ON COLUMN users.asaas_integration_status IS
    'Estado da integracao da conta Asaas do usuario (ex.: pendente, integrado, falha).';
COMMENT ON COLUMN users.asaas_account_api_key_enc IS
    'apiKey da subconta Asaas CIFRADA via Fernet (ASAAS_ACCOUNT_API_KEY_SECRET). Nunca logar nem expor em leituras.';
COMMENT ON COLUMN users.asaas_account_updated_at IS
    'Timestamp da ultima atualizacao dos dados de conta Asaas do usuario.';
