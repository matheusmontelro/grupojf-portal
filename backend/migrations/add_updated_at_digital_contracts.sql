-- Migration atomica e idempotente. Executar o arquivo completo com
-- ON_ERROR_STOP; nao envolver em uma transacao externa.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';
SET LOCAL search_path = pg_catalog, public;
SET LOCAL TIME ZONE 'UTC';

ALTER TABLE public.digital_contracts
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;

-- Atualizar a funcao antes do backfill protege tambem uma reaplicacao sobre
-- uma versao anterior do trigger. Na primeira execucao, o trigger ainda nao
-- existe e a funcao so passa a ser usada depois da reconciliacao.
CREATE OR REPLACE FUNCTION public.set_digital_contract_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $function$
BEGIN
    -- Respeitar timestamps explicitos da migration e de correcoes
    -- operacionais; updates comuns, que mantem o valor anterior, recebem UTC.
    IF NEW.updated_at IS NOT DISTINCT FROM OLD.updated_at THEN
        NEW.updated_at := CURRENT_TIMESTAMP AT TIME ZONE 'UTC';
    END IF;
    RETURN NEW;
END
$function$;

-- Preencher antes de configurar o default impede que linhas historicas recebam
-- automaticamente o horario da migration. CURRENT_TIMESTAMP e apenas o
-- fallback para linhas legadas sem qualquer timestamp de ciclo de vida.
UPDATE public.digital_contracts
SET updated_at = COALESCE(
    GREATEST(signed_at, selfie_at, sent_at, created_at),
    CURRENT_TIMESTAMP
)
WHERE updated_at IS NULL;

-- Definir o default depois do backfill preserva o historico e tambem corrige
-- uma eventual execucao parcial anterior que tenha criado a coluna sem ele.
ALTER TABLE public.digital_contracts
    ALTER COLUMN updated_at
    SET DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC');

-- Os ALTER TABLE acima mantem digital_contracts bloqueada ate o COMMIT. SHARE
-- conflita com INSERT/UPDATE/DELETE na auditoria e estabiliza o outro lado do
-- predicado. O lock_timeout faz a migration falhar de forma segura em vez de
-- aguardar indefinidamente.
LOCK TABLE public.whatsapp_document_deliveries IN SHARE MODE;

-- Esta correcao operacional foi aprovada para no maximo um contrato. Contar
-- contratos (e nao linhas de auditoria) evita que reenvios do mesmo documento
-- sejam interpretados como candidatos distintos.
DO $migration$
DECLARE
    reconciliation_candidate_count BIGINT;
BEGIN
    SELECT COUNT(*)
    INTO reconciliation_candidate_count
    FROM public.digital_contracts AS contract
    WHERE contract.status = 'draft'
      AND EXISTS (
          SELECT 1
          FROM public.whatsapp_document_deliveries AS delivery
          WHERE delivery.document_id = contract.id
            AND delivery.document_type = 'contrato'
            AND delivery.status = 'enviado'
            AND delivery.sent_at IS NOT NULL
      );

    IF reconciliation_candidate_count > 1 THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE =
                'digital_contract_reconciliation_candidate_limit_exceeded';
    END IF;
END
$migration$;

-- Se a Meta aceitou o envio, a auditoria e a fonte de verdade para recuperar
-- contratos cujo status nao avancou por falha posterior no UPDATE. O primeiro
-- envio bem-sucedido representa o momento em que o contrato saiu de draft.
-- A conversao explicita para UTC evita depender do timezone da sessao ao
-- gravar colunas TIMESTAMP WITHOUT TIME ZONE.
WITH first_successful_delivery AS (
    SELECT DISTINCT ON (delivery.document_id)
        delivery.document_id,
        delivery.sent_at
    FROM public.whatsapp_document_deliveries AS delivery
    WHERE delivery.document_type = 'contrato'
      AND delivery.status = 'enviado'
      AND delivery.sent_at IS NOT NULL
    ORDER BY
        delivery.document_id,
        delivery.sent_at ASC,
        delivery.id ASC
)
UPDATE public.digital_contracts AS contract
SET status = 'sent',
    sent_at = delivery.sent_at AT TIME ZONE 'UTC',
    updated_at = delivery.sent_at AT TIME ZONE 'UTC'
FROM first_successful_delivery AS delivery
WHERE contract.id = delivery.document_id
  AND contract.status = 'draft';

CREATE OR REPLACE TRIGGER set_digital_contract_updated_at
BEFORE UPDATE ON public.digital_contracts
FOR EACH ROW
EXECUTE FUNCTION public.set_digital_contract_updated_at();

COMMENT ON COLUMN public.digital_contracts.updated_at IS
    'Ultima atualizacao do contrato digital em timestamp UTC sem fuso.';

COMMIT;
