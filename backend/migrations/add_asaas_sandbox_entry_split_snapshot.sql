-- Congela a intenção financeira da entrada Sandbox e expõe ao runtime somente
-- metadados de recebedor. Aplicação operacional requer janela aprovada.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '10min';
SET LOCAL search_path = pg_catalog, public;

CREATE TABLE IF NOT EXISTS public.asaas_entry_financial_snapshots (
    entry_integration_id BIGINT PRIMARY KEY
        REFERENCES public.asaas_entry_integrations(id) ON DELETE RESTRICT,
    intent_version INTEGER NOT NULL CHECK (intent_version > 0),
    intent_sha256 CHAR(64) NOT NULL CHECK (intent_sha256 ~ '^[a-f0-9]{64}$'),
    snapshot_json JSONB NOT NULL,
    entry_plan_json JSONB NOT NULL,
    entry_split_json JSONB NOT NULL,
    carne_plan_json JSONB NOT NULL,
    carne_split_json JSONB NOT NULL,
    consumed_venda_id BIGINT NULL
        REFERENCES public.vendas(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_asaas_entry_snapshot_split_array
        CHECK (jsonb_typeof(entry_split_json) = 'array'),
    CONSTRAINT ck_asaas_entry_snapshot_entry_plan_object
        CHECK (jsonb_typeof(entry_plan_json) = 'object'),
    CONSTRAINT ck_asaas_entry_snapshot_carne_object
        CHECK (jsonb_typeof(carne_plan_json) = 'object'),
    CONSTRAINT ck_asaas_entry_snapshot_carne_split_array
        CHECK (jsonb_typeof(carne_split_json) = 'array'),
    CONSTRAINT ck_asaas_entry_snapshot_payload_object
        CHECK (jsonb_typeof(snapshot_json) = 'object')
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_entry_snapshot_consumed_venda
    ON public.asaas_entry_financial_snapshots (consumed_venda_id)
    WHERE consumed_venda_id IS NOT NULL;

-- O runtime não recebe UPDATE direto no marcador. A troca de NULL para a
-- venda informada é o único caminho e só pode acontecer uma vez.
CREATE OR REPLACE FUNCTION public.asaas_consume_entry_snapshot(
    p_entry_integration_id BIGINT,
    p_venda_id BIGINT
) RETURNS BIGINT
LANGUAGE sql
SECURITY DEFINER
VOLATILE
STRICT
SET search_path = pg_catalog, pg_temp
AS $function$
    UPDATE public.asaas_entry_financial_snapshots AS snapshot
       SET consumed_venda_id = p_venda_id
     WHERE p_entry_integration_id > 0
       AND p_venda_id > 0
       AND snapshot.entry_integration_id = p_entry_integration_id
       AND snapshot.consumed_venda_id IS NULL
     RETURNING snapshot.consumed_venda_id
$function$;

REVOKE ALL ON FUNCTION public.asaas_consume_entry_snapshot(BIGINT, BIGINT)
    FROM PUBLIC;

CREATE OR REPLACE VIEW public.asaas_sandbox_receiver_link_metadata
WITH (security_barrier = true) AS
SELECT id, user_id, unidade, environment, account_id, wallet_id, credential_state
FROM public.asaas_receiver_environment_links
WHERE environment = 'sandbox';

REVOKE ALL ON TABLE public.asaas_sandbox_receiver_link_metadata FROM PUBLIC;

-- A cifra só pode sair para a tupla já congelada. A view acima deliberadamente
-- não contém credential_ciphertext.
CREATE OR REPLACE FUNCTION public.asaas_get_verified_sandbox_receiver_cipher(
    p_link_id BIGINT,
    p_user_id INTEGER,
    p_unidade VARCHAR,
    p_account_id VARCHAR,
    p_wallet_id VARCHAR
) RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
    SELECT link.credential_ciphertext
    FROM public.asaas_receiver_environment_links AS link
    WHERE link.id = p_link_id
      AND link.user_id = p_user_id
      AND link.unidade = p_unidade
      AND link.environment = 'sandbox'
      AND link.account_id = p_account_id
      AND link.wallet_id = p_wallet_id
      AND link.credential_state = 'verified'
      AND link.credential_ciphertext IS NOT NULL
      AND BTRIM(link.credential_ciphertext) <> ''
    LIMIT 1
$function$;

REVOKE ALL ON FUNCTION public.asaas_get_verified_sandbox_receiver_cipher(
    BIGINT, INTEGER, VARCHAR, VARCHAR, VARCHAR
) FROM PUBLIC;

COMMENT ON TABLE public.asaas_entry_financial_snapshots IS
    'Plano financeiro imutável da entrada Pix e do carnê restante; sem cifra de credencial.';
COMMENT ON VIEW public.asaas_sandbox_receiver_link_metadata IS
    'Metadados Sandbox de recebedor para runtime; não expõe credential_ciphertext.';
COMMENT ON FUNCTION public.asaas_get_verified_sandbox_receiver_cipher(
    BIGINT, INTEGER, VARCHAR, VARCHAR, VARCHAR
) IS 'Leitura SECURITY DEFINER restrita à tupla Sandbox verificada e já congelada.';
COMMENT ON FUNCTION public.asaas_consume_entry_snapshot(BIGINT, BIGINT)
IS 'Consome uma única vez o snapshot pago, sem UPDATE direto pelo runtime.';

COMMIT;
