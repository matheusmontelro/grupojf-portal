-- Cadastro administrativo isolado de vínculos de recebedores Asaas por ambiente.
-- Não altera users.asaas_* nem concede acesso de runtime a credenciais.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL search_path = pg_catalog, public;

CREATE TABLE public.asaas_receiver_environment_links (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    unidade VARCHAR(100) NOT NULL CHECK (BTRIM(unidade) <> ''),
    environment VARCHAR(16) NOT NULL CHECK (environment IN ('sandbox', 'production')),
    account_id VARCHAR(128) NOT NULL CHECK (BTRIM(account_id) <> ''),
    wallet_id VARCHAR(128) NOT NULL CHECK (BTRIM(wallet_id) <> ''),
    credential_ciphertext TEXT,
    credential_state VARCHAR(16) NOT NULL CHECK (credential_state IN ('verified', 'pending')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_asaas_receiver_environment_link_credential
        CHECK ((credential_state = 'verified' AND credential_ciphertext IS NOT NULL AND BTRIM(credential_ciphertext) <> '')
            OR (credential_state = 'pending' AND credential_ciphertext IS NULL)),
    CONSTRAINT uq_asaas_receiver_environment_link_user_unit_environment
        UNIQUE (user_id, unidade, environment),
    CONSTRAINT uq_asaas_receiver_environment_link_wallet_environment
        UNIQUE (wallet_id, environment)
);

COMMENT ON TABLE public.asaas_receiver_environment_links IS
    'Vínculo administrativo Asaas por usuário, unidade e ambiente; não habilita runtime de vendas.';
COMMENT ON COLUMN public.asaas_receiver_environment_links.credential_ciphertext IS
    'apiKey cifrada por Fernet. Sem grants de runtime nesta entrega; nunca expor em logs ou APIs.';

COMMIT;
