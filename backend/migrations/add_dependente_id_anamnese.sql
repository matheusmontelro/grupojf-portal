-- Migration: Adicionar suporte para anamnese de dependentes
-- Data: 2025-01-30
-- Descrição: Permite que cada dependente tenha sua própria anamnese digital

-- 1. Adicionar campo dependente_id na tabela anamneses_digitais
ALTER TABLE anamneses_digitais 
ADD COLUMN dependente_id INTEGER DEFAULT NULL;

-- 2. Adicionar foreign key para dependentes
ALTER TABLE anamneses_digitais 
ADD CONSTRAINT fk_anamnese_dependente 
FOREIGN KEY (dependente_id) REFERENCES dependentes(dependente_id)
ON DELETE CASCADE;

-- 3. Criar índice para melhorar performance de consultas
CREATE INDEX idx_anamneses_dependente_id ON anamneses_digitais(dependente_id);

-- 4. Criar índice composto para buscar anamneses válidas por paciente/dependente
CREATE INDEX idx_anamnese_paciente_dependente_status 
ON anamneses_digitais(paciente_id, dependente_id, status, validade_ate);

-- 5. Adicionar constraint única para garantir apenas uma anamnese ativa por paciente/dependente
-- Nota: Esta constraint permite múltiplas anamneses com status diferente de 'aguardando_assinatura' e 'assinado'
CREATE UNIQUE INDEX idx_anamnese_paciente_dependente_ativa 
ON anamneses_digitais(paciente_id, COALESCE(dependente_id, -1))
WHERE status IN ('aguardando_assinatura', 'assinado') AND validade_ate > NOW();

-- 6. Adicionar comentário explicativo
COMMENT ON COLUMN anamneses_digitais.dependente_id IS 
'ID do dependente quando a anamnese é específica para um dependente. NULL quando é para o próprio titular.';

-- 7. Atualizar tabela anamnese_tokens para incluir dependente_id
ALTER TABLE anamnese_tokens
ADD COLUMN dependente_id INTEGER DEFAULT NULL;

-- 8. Adicionar foreign key na tabela de tokens
ALTER TABLE anamnese_tokens
ADD CONSTRAINT fk_token_dependente
FOREIGN KEY (dependente_id) REFERENCES dependentes(dependente_id)
ON DELETE CASCADE;

-- 9. Criar índice para tokens por dependente
CREATE INDEX idx_anamnese_tokens_dependente_id ON anamnese_tokens(dependente_id);

-- 10. Adicionar comentário na tabela de tokens
COMMENT ON COLUMN anamnese_tokens.dependente_id IS 
'ID do dependente quando o token é para anamnese de dependente. NULL para anamnese do titular.';

-- 11. Atualizar tabela anamnese_envios para rastrear envios por dependente
ALTER TABLE anamnese_envios
ADD COLUMN dependente_id INTEGER DEFAULT NULL;

ALTER TABLE anamnese_envios
ADD CONSTRAINT fk_envio_dependente
FOREIGN KEY (dependente_id) REFERENCES dependentes(dependente_id)
ON DELETE CASCADE;

-- 12. Adicionar índice para envios por dependente
CREATE INDEX idx_anamnese_envios_dependente_id ON anamnese_envios(dependente_id);

-- 13. Criar view para facilitar consultas de anamneses com dados do dependente
CREATE OR REPLACE VIEW v_anamneses_com_dependente AS
SELECT 
    a.id,
    a.paciente_id,
    a.dependente_id,
    a.status,
    a.signed_at,
    a.validade_ate,
    a.created_at,
    p.nome_paciente,
    d.nome_dependente,
    d.parentesco,
    CASE 
        WHEN a.dependente_id IS NULL THEN p.nome_paciente
        ELSE d.nome_dependente || ' (' || COALESCE(d.parentesco, 'Dependente') || ')'
    END AS nome_exibicao
FROM anamneses_digitais a
INNER JOIN pacientes p ON a.paciente_id = p.paciente_id
LEFT JOIN dependentes d ON a.dependente_id = d.dependente_id;

-- 14. Garantir integridade: dependente deve pertencer ao paciente
CREATE OR REPLACE FUNCTION verificar_dependente_pertence_paciente()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.dependente_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM dependentes 
            WHERE dependente_id = NEW.dependente_id 
            AND responsavel_paciente_id = NEW.paciente_id
        ) THEN
            RAISE EXCEPTION 'Dependente % não pertence ao paciente %', NEW.dependente_id, NEW.paciente_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_verificar_dependente_anamnese
BEFORE INSERT OR UPDATE ON anamneses_digitais
FOR EACH ROW
EXECUTE FUNCTION verificar_dependente_pertence_paciente();

-- 15. Atualizar função de busca de anamnese válida para considerar dependentes
CREATE OR REPLACE FUNCTION obter_anamnese_valida(
    p_paciente_id INTEGER,
    p_dependente_id INTEGER DEFAULT NULL
)
RETURNS TABLE (
    id INTEGER,
    status VARCHAR,
    signed_at TIMESTAMP,
    validade_ate TIMESTAMP,
    dados_anamnese JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id,
        a.status,
        a.signed_at,
        a.validade_ate,
        a.dados_anamnese
    FROM anamneses_digitais a
    WHERE a.paciente_id = p_paciente_id
    AND (
        (p_dependente_id IS NULL AND a.dependente_id IS NULL) OR
        (p_dependente_id IS NOT NULL AND a.dependente_id = p_dependente_id)
    )
    AND a.status = 'assinado'
    AND a.validade_ate > NOW()
    ORDER BY a.signed_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Fim da migration