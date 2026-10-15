-- Migrations para o sistema de Anamnese Digital
-- Criação das tabelas necessárias

-- Tabela principal de anamneses digitais
CREATE TABLE IF NOT EXISTS anamneses_digitais (
    id SERIAL PRIMARY KEY,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(paciente_id),
    status VARCHAR(50) DEFAULT 'rascunho' CHECK (status IN ('rascunho', 'aguardando_assinatura', 'assinado', 'expirado')),
    dados_anamnese JSONB NOT NULL,
    observacoes_profissional TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    signed_at TIMESTAMP,
    validade_ate TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    ip_address VARCHAR(45),
    user_agent TEXT
);

-- Tabela de assinaturas da anamnese
CREATE TABLE IF NOT EXISTS anamnese_assinaturas (
    id SERIAL PRIMARY KEY,
    anamnese_id INTEGER NOT NULL REFERENCES anamneses_digitais(id) ON DELETE CASCADE,
    tipo_assinatura VARCHAR(20) NOT NULL CHECK (tipo_assinatura IN ('paciente', 'responsavel')),
    nome_assinante VARCHAR(255) NOT NULL,
    cpf_assinante VARCHAR(14),
    foto_selfie TEXT, -- Base64 da foto
    assinatura_digital TEXT, -- Base64 da assinatura
    ip_address VARCHAR(45),
    user_agent TEXT,
    geolocalizacao JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tabela de tokens para links públicos
CREATE TABLE IF NOT EXISTS anamnese_tokens (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(paciente_id),
    anamnese_id INTEGER REFERENCES anamneses_digitais(id),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP,
    ip_usado VARCHAR(45),
    user_agent_usado TEXT
);

-- Tabela de envios de links
CREATE TABLE IF NOT EXISTS anamnese_envios (
    id SERIAL PRIMARY KEY,
    token_id INTEGER NOT NULL REFERENCES anamnese_tokens(id) ON DELETE CASCADE,
    meio_envio VARCHAR(50) NOT NULL CHECK (meio_envio IN ('whatsapp', 'sms', 'email', 'presencial')),
    destinatario VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'enviado',
    enviado_em TIMESTAMP DEFAULT NOW(),
    visualizado_em TIMESTAMP,
    preenchido_em TIMESTAMP,
    mensagem_erro TEXT
);

-- Índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_anamnese_paciente ON anamneses_digitais(paciente_id);
CREATE INDEX IF NOT EXISTS idx_anamnese_status ON anamneses_digitais(status);
CREATE INDEX IF NOT EXISTS idx_anamnese_validade ON anamneses_digitais(validade_ate);
CREATE INDEX IF NOT EXISTS idx_anamnese_created ON anamneses_digitais(created_at);

CREATE INDEX IF NOT EXISTS idx_anamnese_assinatura_anamnese ON anamnese_assinaturas(anamnese_id);
CREATE INDEX IF NOT EXISTS idx_anamnese_assinatura_created ON anamnese_assinaturas(created_at);

CREATE INDEX IF NOT EXISTS idx_anamnese_token ON anamnese_tokens(token);
CREATE INDEX IF NOT EXISTS idx_anamnese_token_paciente ON anamnese_tokens(paciente_id);
CREATE INDEX IF NOT EXISTS idx_anamnese_token_expires ON anamnese_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_anamnese_token_used ON anamnese_tokens(used);

CREATE INDEX IF NOT EXISTS idx_anamnese_envio_token ON anamnese_envios(token_id);
CREATE INDEX IF NOT EXISTS idx_anamnese_envio_status ON anamnese_envios(status);

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_anamnese_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para atualizar updated_at
CREATE TRIGGER update_anamneses_digitais_updated_at
    BEFORE UPDATE ON anamneses_digitais
    FOR EACH ROW
    EXECUTE FUNCTION update_anamnese_updated_at();

-- Comentários nas tabelas
COMMENT ON TABLE anamneses_digitais IS 'Armazena as fichas de anamnese digitais dos pacientes';
COMMENT ON TABLE anamnese_assinaturas IS 'Armazena as assinaturas digitais das anamneses';
COMMENT ON TABLE anamnese_tokens IS 'Tokens para acesso público às anamneses';
COMMENT ON TABLE anamnese_envios IS 'Registro de envios de links para preenchimento';

-- Adicionar permissões (ajustar conforme usuário do banco)
-- GRANT ALL ON anamneses_digitais TO seu_usuario;
-- GRANT ALL ON anamnese_assinaturas TO seu_usuario;
-- GRANT ALL ON anamnese_tokens TO seu_usuario;
-- GRANT ALL ON anamnese_envios TO seu_usuario;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO seu_usuario;