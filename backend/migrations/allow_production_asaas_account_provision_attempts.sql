-- Separa tentativas de subconta por ambiente sem alterar o histórico Sandbox.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '10min';
SET LOCAL search_path = pg_catalog, public;

ALTER TABLE public.asaas_account_provision_attempts
    DROP CONSTRAINT IF EXISTS chk_asaas_account_provision_attempt_environment;
ALTER TABLE public.asaas_account_provision_attempts
    ADD CONSTRAINT chk_asaas_account_provision_attempt_environment
    CHECK (environment IN ('sandbox', 'production'));

DROP INDEX IF EXISTS public.uq_asaas_account_provision_attempt_active_user;
CREATE UNIQUE INDEX uq_asaas_account_provision_attempt_active_user
    ON public.asaas_account_provision_attempts (user_id, environment)
    WHERE lifecycle_state <> 'rejected';
COMMIT;
