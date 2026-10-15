ALTER TABLE vendas
ADD COLUMN IF NOT EXISTS tem_akimais_saude BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE vendas
ADD COLUMN IF NOT EXISTS akimais_seller_id TEXT;

CREATE INDEX IF NOT EXISTS idx_vendas_tem_akimais_saude
    ON vendas(tem_akimais_saude);

COMMENT ON COLUMN vendas.tem_akimais_saude IS
    'Indica se a venda possui split para o Aki Mais Saúde';

COMMENT ON COLUMN vendas.akimais_seller_id IS
    'sellerId do Aki Mais Saúde efetivamente usado na venda';

WITH akimais_por_venda AS (
    SELECT
        v.id AS venda_id,
        COALESCE(
            (
                SELECT pvs.seller_id::text
                FROM pre_venda_splits pvs
                WHERE pvs.pre_venda_id = v.pre_venda_id
                  AND (
                    pvs.empresa_id = 2
                    OR pvs.seller_id::text IN ('8', '17', '21')
                  )
                LIMIT 1
            ),
            (
                SELECT cs.seller_id::text
                FROM carne_splits cs
                WHERE cs.carne_id = v.carne_id
                  AND (
                    cs.empresa_id = 2
                    OR cs.seller_id::text IN ('8', '17', '21')
                  )
                LIMIT 1
            ),
            (
                SELECT frs.seller_id::text
                FROM fatura_recorrente_splits frs
                JOIN fatura_recorrente fr ON fr.subscription_id = frs.subscription_id
                WHERE fr.venda_id = v.id
                  AND (
                    frs.empresa_id = 2
                    OR frs.seller_id::text IN ('8', '17', '21')
                  )
                LIMIT 1
            )
        ) AS seller_id
    FROM vendas v
)
UPDATE vendas v
SET tem_akimais_saude = av.seller_id IS NOT NULL,
    akimais_seller_id = av.seller_id
FROM akimais_por_venda av
WHERE v.id = av.venda_id;
