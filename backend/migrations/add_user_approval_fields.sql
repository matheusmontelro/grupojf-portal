-- Adicionar campos de aprovação na tabela users
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS status_aprovacao VARCHAR(20) DEFAULT 'aprovado',
ADD COLUMN IF NOT EXISTS data_solicitacao TIMESTAMP DEFAULT NULL,
ADD COLUMN IF NOT EXISTS usuario_aprovador_id INTEGER DEFAULT NULL,
ADD COLUMN IF NOT EXISTS data_aprovacao TIMESTAMP DEFAULT NULL,
ADD COLUMN IF NOT EXISTS motivo_rejeicao TEXT DEFAULT NULL;

-- Adicionar índice para facilitar busca por status
CREATE INDEX IF NOT EXISTS idx_users_status_aprovacao ON users(status_aprovacao);

-- Adicionar foreign key para o usuário aprovador
ALTER TABLE users 
ADD CONSTRAINT fk_usuario_aprovador 
FOREIGN KEY (usuario_aprovador_id) 
REFERENCES users(id) 
ON DELETE SET NULL;

-- Atualizar usuários existentes para status 'aprovado'
UPDATE users 
SET status_aprovacao = 'aprovado' 
WHERE status_aprovacao IS NULL;

-- Comentário nas colunas
COMMENT ON COLUMN users.status_aprovacao IS 'Status de aprovação: pendente_aprovacao, aprovado, rejeitado';
COMMENT ON COLUMN users.data_solicitacao IS 'Data/hora da solicitação de cadastro';
COMMENT ON COLUMN users.usuario_aprovador_id IS 'ID do usuário que aprovou/rejeitou';
COMMENT ON COLUMN users.data_aprovacao IS 'Data/hora da aprovação/rejeição';
COMMENT ON COLUMN users.motivo_rejeicao IS 'Motivo da rejeição (opcional)';