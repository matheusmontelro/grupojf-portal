-- Migration atomica. Executar o arquivo completo com ON_ERROR_STOP em janela
-- de baixa atividade; nao envolver em uma transacao externa.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '10min';
SET LOCAL search_path = pg_catalog, public;

-- O id da integracao e dos recursos ja e unico isoladamente. Estes indices
-- compostos tornam o escopo completo referenciavel por FKs e impedem que um
-- recurso de outra venda, integracao ou conta seja associado por engano.
CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_integration_carne_scope
    ON public.asaas_sale_integrations (
        id,
        venda_id,
        unidade,
        environment,
        account_wallet_id
    );

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_integration_item_scope
    ON public.asaas_sale_integrations (id, venda_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_asaas_sale_resource_carne_scope
    ON public.asaas_sale_resources (
        id,
        integration_id,
        unidade,
        environment,
        account_wallet_id,
        resource_type
    );

ALTER TABLE public.asaas_sale_integrations
    ADD COLUMN IF NOT EXISTS request_fingerprint CHAR(64)
        CHECK (
            request_fingerprint IS NULL
            OR request_fingerprint ~ '^[a-f0-9]{64}$'
        ),
    ADD COLUMN IF NOT EXISTS remote_creation_state VARCHAR(24)
        NOT NULL DEFAULT 'nao_iniciado'
        CHECK (
            remote_creation_state IN (
                'nao_iniciado',
                'requisicao_iniciada',
                'resultado_incerto',
                'confirmado',
                'falha_terminal'
            )
        ),
    ADD COLUMN IF NOT EXISTS remote_attempt_count INTEGER
        NOT NULL DEFAULT 0
        CHECK (remote_attempt_count >= 0),
    ADD COLUMN IF NOT EXISTS last_remote_attempt_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS remote_result_unknown_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS remote_confirmed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reconciliation_required BOOLEAN
        NOT NULL DEFAULT FALSE;

-- As constraints sao recriadas com o contrato atual para que uma repeticao da
-- migration tambem corrija uma execucao parcial de uma versao anterior.
ALTER TABLE public.asaas_sale_integrations
    DROP CONSTRAINT IF EXISTS chk_asaas_sale_remote_attempt_metadata,
    DROP CONSTRAINT IF EXISTS chk_asaas_sale_remote_state_attempts,
    DROP CONSTRAINT IF EXISTS chk_asaas_sale_remote_uncertain_state,
    DROP CONSTRAINT IF EXISTS chk_asaas_sale_remote_reconciliation_state,
    DROP CONSTRAINT IF EXISTS chk_asaas_sale_remote_confirmation;

ALTER TABLE public.asaas_sale_integrations
    ADD CONSTRAINT chk_asaas_sale_remote_attempt_metadata
        CHECK (
            (
                remote_attempt_count = 0
                AND last_remote_attempt_at IS NULL
            )
            OR (
                remote_attempt_count > 0
                AND last_remote_attempt_at IS NOT NULL
            )
        ) NOT VALID,
    -- resultado_incerto e confirmado tambem podem nascer de uma descoberta
    -- remota anterior a qualquer POST local; somente requisicao_iniciada exige
    -- uma tentativa local persistida.
    ADD CONSTRAINT chk_asaas_sale_remote_state_attempts
        CHECK (
            (
                remote_creation_state = 'nao_iniciado'
                AND remote_attempt_count = 0
            )
            OR (
                remote_creation_state = 'requisicao_iniciada'
                AND remote_attempt_count > 0
            )
            OR remote_creation_state IN (
                'resultado_incerto',
                'confirmado',
                'falha_terminal'
            )
        ) NOT VALID,
    ADD CONSTRAINT chk_asaas_sale_remote_uncertain_state
        CHECK (
            remote_creation_state <> 'resultado_incerto'
            OR (
                remote_result_unknown_at IS NOT NULL
                AND reconciliation_required
            )
        ) NOT VALID,
    ADD CONSTRAINT chk_asaas_sale_remote_reconciliation_state
        CHECK (
            reconciliation_required = (
                remote_creation_state IN (
                    'requisicao_iniciada',
                    'resultado_incerto'
                )
            )
        ) NOT VALID,
    ADD CONSTRAINT chk_asaas_sale_remote_confirmation
        CHECK (
            (remote_creation_state = 'confirmado') =
                (remote_confirmed_at IS NOT NULL)
        ) NOT VALID;

ALTER TABLE public.asaas_sale_integrations
    VALIDATE CONSTRAINT chk_asaas_sale_remote_attempt_metadata;
ALTER TABLE public.asaas_sale_integrations
    VALIDATE CONSTRAINT chk_asaas_sale_remote_state_attempts;
ALTER TABLE public.asaas_sale_integrations
    VALIDATE CONSTRAINT chk_asaas_sale_remote_uncertain_state;
ALTER TABLE public.asaas_sale_integrations
    VALIDATE CONSTRAINT chk_asaas_sale_remote_reconciliation_state;
ALTER TABLE public.asaas_sale_integrations
    VALIDATE CONSTRAINT chk_asaas_sale_remote_confirmation;

-- A protecao por prefixo depende desta invariante. Se uma versao anterior tiver
-- gravado integracao incompatível, a migration para sem expor IDs ou PII.
DO $migration$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM public.asaas_sale_integrations AS integration
          JOIN public.vendas AS sale
            ON sale.id = integration.venda_id
         WHERE sale.documento_venda IS NULL
            OR sale.documento_venda NOT LIKE 'VA-%'
            OR sale.forma_pagamento_id IS NOT NULL
            OR NOT (
                (
                    sale.status_venda IS NOT DISTINCT FROM 'Pendente Asaas'
                    AND integration.remote_creation_state IN (
                        'nao_iniciado',
                        'requisicao_iniciada',
                        'resultado_incerto'
                    )
                )
                OR (
                    sale.status_venda IS NOT DISTINCT FROM 'Efetuada'
                    AND integration.remote_creation_state = 'confirmado'
                )
                OR (
                    sale.status_venda IS NOT DISTINCT FROM 'Cancelada'
                    AND integration.remote_creation_state = 'falha_terminal'
                )
            )
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'asaas_sale_existing_integration_incompatible';
    END IF;
END
$migration$;

CREATE TABLE IF NOT EXISTS public.asaas_sale_discount_rules (
    id BIGSERIAL PRIMARY KEY,
    unidade VARCHAR(100) NOT NULL
        CHECK (BTRIM(unidade) <> ''),
    payment_method VARCHAR(40) NOT NULL
        CHECK (
            payment_method IN (
                'ASAAS_BOLETO_INSTALLMENT',
                'ASAAS_PIX_AUTOMATIC',
                'ASAAS_CREDIT_CARD_RECURRENT'
            )
        ),
    installment_min INTEGER NOT NULL
        CHECK (installment_min > 0),
    installment_max INTEGER NOT NULL
        CHECK (installment_max >= installment_min),
    percentage NUMERIC(5, 2) NOT NULL
        CHECK (percentage >= 0 AND percentage < 100),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_asaas_sale_discount_rule_exact
        UNIQUE (
            unidade,
            payment_method,
            installment_min,
            installment_max,
            percentage
        )
);

CREATE INDEX IF NOT EXISTS idx_asaas_sale_discount_rule_lookup
    ON public.asaas_sale_discount_rules (
        unidade,
        payment_method,
        active,
        installment_min,
        installment_max
    );

CREATE TABLE IF NOT EXISTS public.asaas_sale_items (
    id BIGSERIAL PRIMARY KEY,
    integration_id BIGINT NOT NULL,
    venda_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    item_number INTEGER NOT NULL
        CHECK (item_number > 0),
    quantity INTEGER NOT NULL
        CHECK (quantity > 0),
    unit_value NUMERIC(12, 2) NOT NULL
        CHECK (unit_value > 0),
    total_value NUMERIC(12, 2) NOT NULL
        CHECK (total_value > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_asaas_sale_item_total
        CHECK (total_value = unit_value * quantity),
    CONSTRAINT fk_asaas_sale_item_integration_sale_scope
        FOREIGN KEY (integration_id, venda_id)
        REFERENCES public.asaas_sale_integrations (id, venda_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_asaas_sale_item_product
        FOREIGN KEY (product_id)
        REFERENCES public.produtos (id)
        ON DELETE RESTRICT,
    CONSTRAINT uq_asaas_sale_item_integration_number
        UNIQUE (integration_id, item_number),
    CONSTRAINT uq_asaas_sale_item_sale_number
        UNIQUE (venda_id, item_number)
);

CREATE INDEX IF NOT EXISTS idx_asaas_sale_item_product
    ON public.asaas_sale_items (product_id);

CREATE TABLE IF NOT EXISTS public.asaas_sale_payment_links (
    id BIGSERIAL PRIMARY KEY,
    integration_id BIGINT NOT NULL,
    venda_id INTEGER NOT NULL,
    resource_id BIGINT NOT NULL,
    numero_parcela INTEGER NOT NULL
        CHECK (numero_parcela > 0),
    unidade VARCHAR(100) NOT NULL
        CHECK (BTRIM(unidade) <> ''),
    environment VARCHAR(16) NOT NULL
        CHECK (environment IN ('sandbox', 'production')),
    account_wallet_id VARCHAR(100) NOT NULL
        CHECK (BTRIM(account_wallet_id) <> ''),
    resource_type VARCHAR(32) NOT NULL DEFAULT 'payment'
        CHECK (resource_type = 'payment'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_asaas_sale_payment_link_integration_scope
        FOREIGN KEY (
            integration_id,
            venda_id,
            unidade,
            environment,
            account_wallet_id
        )
        REFERENCES public.asaas_sale_integrations (
            id,
            venda_id,
            unidade,
            environment,
            account_wallet_id
        )
        ON DELETE RESTRICT,
    CONSTRAINT fk_asaas_sale_payment_link_resource_scope
        FOREIGN KEY (
            resource_id,
            integration_id,
            unidade,
            environment,
            account_wallet_id,
            resource_type
        )
        REFERENCES public.asaas_sale_resources (
            id,
            integration_id,
            unidade,
            environment,
            account_wallet_id,
            resource_type
        )
        ON DELETE RESTRICT,
    CONSTRAINT fk_asaas_sale_payment_link_parcela_scope
        FOREIGN KEY (venda_id, numero_parcela)
        REFERENCES public.venda_parcelas (venda_id, numero_parcela)
        ON DELETE RESTRICT,
    CONSTRAINT uq_asaas_sale_payment_link_resource
        UNIQUE (resource_id),
    CONSTRAINT uq_asaas_sale_payment_link_numero
        UNIQUE (integration_id, numero_parcela)
);

CREATE INDEX IF NOT EXISTS idx_asaas_sale_payment_link_venda
    ON public.asaas_sale_payment_links (venda_id, numero_parcela);

CREATE OR REPLACE FUNCTION public.asaas_validate_sale_integration_parent()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.venda_id IS DISTINCT FROM OLD.venda_id THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'asaas_sale_integration_sale_immutable';
        END IF;
        RETURN NEW;
    END IF;

    IF pg_catalog.current_setting(
        'app.asaas_sale_creation',
        TRUE
    ) IS DISTINCT FROM 'enabled' THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'asaas_sale_creation_context_required';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM public.vendas AS parent_sale
         WHERE parent_sale.id = NEW.venda_id
           AND parent_sale.documento_venda LIKE 'VA-%'
           AND parent_sale.forma_pagamento_id IS NULL
           AND parent_sale.status_venda = 'Pendente Asaas'
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'asaas_sale_integration_parent_invalid';
    END IF;

    RETURN NEW;
END
$function$;

-- Serializa somente a disputa envolvendo uma venda Asaas. Duplicatas legadas
-- entre vendas nao-Asaas continuam fora do escopo desta migration.
CREATE OR REPLACE FUNCTION public.asaas_guard_venda_odontograma()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
DECLARE
    creation_context_enabled BOOLEAN;
    document_is_asaas BOOLEAN;
    new_sale_is_asaas BOOLEAN;
BEGIN
    creation_context_enabled := (
        pg_catalog.current_setting(
            'app.asaas_sale_creation',
            TRUE
        ) IS NOT DISTINCT FROM 'enabled'
    );
    document_is_asaas := NEW.documento_venda LIKE 'VA-%';

    IF TG_OP = 'INSERT'
       AND document_is_asaas
       AND NOT creation_context_enabled THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'asaas_sale_creation_context_required';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF NEW.odontograma_id IS NOT DISTINCT FROM OLD.odontograma_id
           AND NEW.status_venda IS NOT DISTINCT FROM OLD.status_venda
           AND NEW.documento_venda IS NOT DISTINCT FROM OLD.documento_venda
        THEN
            RETURN NEW;
        END IF;
    END IF;

    IF TG_OP = 'INSERT' THEN
        new_sale_is_asaas := (
            document_is_asaas
            AND creation_context_enabled
        );
    ELSIF document_is_asaas THEN
        SELECT EXISTS (
            SELECT 1
              FROM public.asaas_sale_integrations AS integration
             WHERE integration.venda_id = NEW.id
        )
          INTO new_sale_is_asaas;
    ELSE
        new_sale_is_asaas := FALSE;
    END IF;

    IF NEW.odontograma_id IS NULL
       OR NEW.status_venda IS NOT DISTINCT FROM 'Cancelada' THEN
        RETURN NEW;
    END IF;

    -- Inclusive uma venda nao-Asaas precisa participar deste lock: sem isso,
    -- ela poderia correr em paralelo com a primeira venda Asaas do odontograma.
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(
            'asaas-sale-odontograma:' || NEW.odontograma_id::TEXT,
            0
        )
    );

    IF new_sale_is_asaas THEN
        IF EXISTS (
            SELECT 1
              FROM public.vendas AS other_sale
             WHERE other_sale.odontograma_id = NEW.odontograma_id
               AND other_sale.status_venda IS DISTINCT FROM 'Cancelada'
               AND other_sale.id IS DISTINCT FROM NEW.id
        ) THEN
            RAISE EXCEPTION USING
                ERRCODE = '23505',
                MESSAGE = 'asaas_sale_odontogram_active_conflict';
        END IF;
    ELSIF EXISTS (
        SELECT 1
          FROM public.vendas AS other_sale
         WHERE other_sale.odontograma_id = NEW.odontograma_id
           AND other_sale.status_venda IS DISTINCT FROM 'Cancelada'
           AND other_sale.id IS DISTINCT FROM NEW.id
           AND EXISTS (
               SELECT 1
                 FROM public.asaas_sale_integrations AS integration
                WHERE integration.venda_id = other_sale.id
           )
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23505',
            MESSAGE = 'asaas_sale_odontogram_active_conflict';
    END IF;

    RETURN NEW;
END
$function$;

CREATE OR REPLACE FUNCTION public.asaas_protect_integrated_venda()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
DECLARE
    integration_remote_state TEXT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.documento_venda NOT LIKE 'VA-%' THEN
            RETURN OLD;
        END IF;
    ELSIF OLD.documento_venda NOT LIKE 'VA-%'
          AND NEW.documento_venda NOT LIKE 'VA-%' THEN
        RETURN NEW;
    END IF;

    SELECT integration.remote_creation_state
      INTO integration_remote_state
      FROM public.asaas_sale_integrations AS integration
     WHERE integration.venda_id = OLD.id
     LIMIT 1;

    IF NOT FOUND THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'asaas_sale_integrated_sale_delete_forbidden';
    END IF;

    IF (
        pg_catalog.to_jsonb(NEW) - ARRAY['status_venda', 'updated_at']
    ) IS DISTINCT FROM (
        pg_catalog.to_jsonb(OLD) - ARRAY['status_venda', 'updated_at']
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'asaas_sale_integrated_sale_immutable';
    END IF;

    IF NEW.status_venda IS NOT DISTINCT FROM OLD.status_venda THEN
        RETURN NEW;
    END IF;

    IF OLD.status_venda = 'Pendente Asaas'
       AND NEW.status_venda = 'Efetuada'
       AND integration_remote_state = 'confirmado' THEN
        RETURN NEW;
    END IF;

    IF OLD.status_venda = 'Pendente Asaas'
       AND NEW.status_venda = 'Cancelada'
       AND integration_remote_state = 'falha_terminal' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION USING
        ERRCODE = '55000',
        MESSAGE = 'asaas_sale_integrated_sale_status_transition_forbidden';
END
$function$;

CREATE OR REPLACE FUNCTION public.asaas_protect_integrated_venda_parcela()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
DECLARE
    parent_sale_is_asaas BOOLEAN;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF EXISTS (
            SELECT 1
              FROM public.asaas_sale_integrations AS integration
             WHERE integration.venda_id = NEW.venda_id
        ) THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'asaas_sale_integrated_installment_immutable';
        END IF;

        SELECT EXISTS (
            SELECT 1
              FROM public.vendas AS parent_sale
             WHERE parent_sale.id = NEW.venda_id
               AND parent_sale.documento_venda LIKE 'VA-%'
        )
          INTO parent_sale_is_asaas;

        IF NOT parent_sale_is_asaas THEN
            RETURN NEW;
        END IF;

        IF COALESCE(NEW.documento_referencia, '') NOT LIKE 'VA-%' THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                MESSAGE = 'asaas_sale_installment_document_invalid';
        END IF;

        IF pg_catalog.current_setting(
            'app.asaas_sale_creation',
            TRUE
        ) IS DISTINCT FROM 'enabled' THEN
            RAISE EXCEPTION USING
                ERRCODE = '42501',
                MESSAGE = 'asaas_sale_creation_context_required';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        IF COALESCE(OLD.documento_referencia, '') NOT LIKE 'VA-%' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'asaas_sale_integrated_installment_immutable';
    END IF;

    IF COALESCE(OLD.documento_referencia, '') NOT LIKE 'VA-%'
       AND COALESCE(NEW.documento_referencia, '') NOT LIKE 'VA-%' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION USING
        ERRCODE = '55000',
        MESSAGE = 'asaas_sale_integrated_installment_immutable';
END
$function$;

REVOKE ALL ON FUNCTION public.asaas_validate_sale_integration_parent()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION public.asaas_guard_venda_odontograma()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION public.asaas_protect_integrated_venda()
    FROM PUBLIC;
REVOKE ALL ON FUNCTION public.asaas_protect_integrated_venda_parcela()
    FROM PUBLIC;

DROP TRIGGER IF EXISTS trg_asaas_validate_sale_integration_parent
    ON public.asaas_sale_integrations;
CREATE TRIGGER trg_asaas_validate_sale_integration_parent
BEFORE INSERT OR UPDATE OF venda_id
ON public.asaas_sale_integrations
FOR EACH ROW
EXECUTE FUNCTION public.asaas_validate_sale_integration_parent();

DROP TRIGGER IF EXISTS trg_asaas_guard_venda_odontograma
    ON public.vendas;
CREATE TRIGGER trg_asaas_guard_venda_odontograma
BEFORE INSERT OR UPDATE OF odontograma_id, status_venda, documento_venda
ON public.vendas
FOR EACH ROW
EXECUTE FUNCTION public.asaas_guard_venda_odontograma();

DROP TRIGGER IF EXISTS trg_asaas_protect_integrated_venda
    ON public.vendas;
CREATE TRIGGER trg_asaas_protect_integrated_venda
BEFORE UPDATE OR DELETE
ON public.vendas
FOR EACH ROW
EXECUTE FUNCTION public.asaas_protect_integrated_venda();

DROP TRIGGER IF EXISTS trg_asaas_protect_integrated_venda_parcela
    ON public.venda_parcelas;
CREATE TRIGGER trg_asaas_protect_integrated_venda_parcela
BEFORE INSERT OR UPDATE OR DELETE
ON public.venda_parcelas
FOR EACH ROW
EXECUTE FUNCTION public.asaas_protect_integrated_venda_parcela();

COMMENT ON TABLE public.asaas_sale_items IS
    'Snapshot tecnico e imutavel dos itens usados para calcular a venda Asaas.';

COMMENT ON TABLE public.asaas_sale_payment_links IS
    'Vinculo isolado e escopado entre payment Asaas e parcela da venda local.';

COMMENT ON COLUMN public.asaas_sale_integrations.remote_creation_state IS
    'Estado duravel da tentativa ou descoberta do parcelamento remoto.';

COMMENT ON COLUMN public.asaas_sale_integrations.request_fingerprint IS
    'SHA-256 do payload normalizado; nullable para integracoes anteriores.';

COMMENT ON COLUMN public.asaas_sale_integrations.remote_result_unknown_at IS
    'Marca resultado remoto incerto; nunca armazena resposta ou dados pessoais.';

COMMENT ON FUNCTION public.asaas_guard_venda_odontograma() IS
    'Serializa conflitos de odontograma quando pelo menos uma venda e Asaas.';

COMMENT ON FUNCTION public.asaas_validate_sale_integration_parent() IS
    'Garante que toda integracao nova pertença a venda VA pendente e isolada.';

COMMENT ON FUNCTION public.asaas_protect_integrated_venda() IS
    'Restringe mutacoes locais de vendas ja vinculadas ao Asaas.';

COMMENT ON FUNCTION public.asaas_protect_integrated_venda_parcela() IS
    'Impede update e delete de parcelas de vendas vinculadas ao Asaas.';

COMMIT;
