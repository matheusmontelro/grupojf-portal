-- Relatório de Splits com Absorve Saldo para bempaggo_receiver_id = 1
-- Este relatório mostra todas as vendas onde a empresa com receiver_id = 1 
-- recebeu splits com a flag absorve_saldo = TRUE

WITH splits_absorve_saldo AS (
    -- Splits de faturas avulsas
    SELECT 
        fa.venda_id,
        fas.seller_id,
        fas.percentage,
        'AVULSA' as tipo_faturamento,
        fa.valor_total as valor_faturamento,
        fa.criado_em as data_fatura
    FROM fatura_avulsa fa
    JOIN fatura_avulsa_splits fas ON fa.invoice_id = fas.invoice_id
    WHERE fas.absorb_balance = TRUE 
      AND fas.seller_id = '1'  -- bempaggo_receiver_id das empresas J&F
    
    UNION ALL
    
    -- Splits de faturas recorrentes
    SELECT 
        fr.venda_id,
        frs.seller_id,
        frs.percentage,
        'RECORRENTE' as tipo_faturamento,
        fr.valor_mensal as valor_faturamento,
        fr.criado_em as data_fatura
    FROM fatura_recorrente fr
    JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id
    WHERE frs.absorb_balance = TRUE 
      AND frs.seller_id = '1'
),
produtos_odontograma AS (
    SELECT 
        oi.odontograma_id,
        STRING_AGG(
            p.nome || ' (Dente: ' || oi.dente_numero || ', R$ ' || oi.valor_registrado || ')',
            '; ' 
            ORDER BY oi.dente_numero
        ) as produtos_detalhes,
        COUNT(oi.id) as qtd_produtos,
        SUM(oi.valor_registrado) as valor_total_produtos
    FROM odontograma_itens oi
    JOIN produtos p ON oi.produto_id = p.id
    GROUP BY oi.odontograma_id
)
SELECT 
    -- Dados da Venda
    v.id as venda_id,
    v.documento_venda,
    v.data_venda,
    v.valor_liquido_total,
    v.unidade,
    
    -- Dados do Paciente
    p.paciente_id,
    p.nome_paciente,
    p.cpf_cnpj,
    
    -- Dados do Odontograma
    v.odontograma_id,
    po.qtd_produtos,
    po.produtos_detalhes,
    po.valor_total_produtos,
    
    -- Dados do Split
    sas.tipo_faturamento,
    sas.percentage as percentual_split,
    sas.valor_faturamento,
    ROUND((sas.valor_faturamento * sas.percentage / 100)::numeric, 2) as valor_recebido_empresa,
    
    -- Informações Adicionais
    d.nome as dentista_orcamentista,
    u.nome as usuario_venda,
    sas.data_fatura

FROM splits_absorve_saldo sas
JOIN vendas v ON sas.venda_id = v.id
JOIN pacientes p ON v.paciente_id = p.paciente_id
LEFT JOIN produtos_odontograma po ON v.odontograma_id = po.odontograma_id
LEFT JOIN dentistas d ON v.dentista_orcamentista_id = d.id
LEFT JOIN users u ON v.usuario_venda_id = u.id

WHERE v.status_venda = 'Efetuada'
  AND v.status_pagamento != 'cancelado'
  -- Filtros adicionais podem ser adicionados aqui:
  -- AND v.data_venda >= :data_inicio AND v.data_venda <= :data_fim
  -- AND v.unidade = :unidade

ORDER BY 
    v.data_venda DESC,
    v.id DESC;

-- Query para resumo totalizador
/*
SELECT 
    COUNT(DISTINCT venda_id) as total_vendas,
    SUM(valor_recebido_empresa) as total_recebido,
    AVG(percentual_split) as percentual_medio,
    MIN(data_venda) as primeira_venda,
    MAX(data_venda) as ultima_venda
FROM (
    -- Usar a query principal aqui
) as vendas_com_splits;
*/