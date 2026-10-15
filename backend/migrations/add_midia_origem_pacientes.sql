-- Adicionar campo midia_origem na tabela pacientes
-- Este campo armazena a fonte/origem do paciente (como ele conheceu a clínica)

ALTER TABLE pacientes 
ADD COLUMN IF NOT EXISTS midia_origem VARCHAR(50);

-- Adicionar comentário explicativo
COMMENT ON COLUMN pacientes.midia_origem IS 'Fonte de origem do paciente: Meta Ads, Indicação, Google, Fachada, etc.';

-- Criar índice para facilitar relatórios por mídia
CREATE INDEX IF NOT EXISTS idx_pacientes_midia_origem ON pacientes(midia_origem);

-- Atualizar pacientes existentes com valor padrão (opcional)
-- UPDATE pacientes SET midia_origem = 'Não informado' WHERE midia_origem IS NULL;