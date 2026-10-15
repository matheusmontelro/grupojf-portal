-- Migration: Criar tabela para armazenar entradas pagas antes da criação da venda

-- Tabela para rastrear pagamentos de entrada antes da venda ser criada
CREATE TABLE IF NOT EXISTS pre_vendas_entradas (
    id SERIAL PRIMARY KEY,
    pre_venda_id VARCHAR(100) UNIQUE NOT NULL,
    tipo_odontograma VARCHAR(50) NOT NULL,
    paciente_id INTEGER NOT NULL,
    dependente_id INTEGER,
    dentista_id INTEGER NOT NULL,
    unidade VARCHAR(50) NOT NULL,
    
    -- Valores
    valor_solicitado NUMERIC(12,2) NOT NULL,
    valor_pago NUMERIC(12,2),
    
    -- Dados do checkout Delta
    checkout_id VARCHAR(100),
    checkout_url TEXT,
    forma_pagamento_id INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pendente' CHECK (status IN ('pendente', 'pago', 'cancelado', 'expirado')),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '24 hours',
    
    -- Dados adicionais para criar a venda posteriormente
    metadata_json JSONB DEFAULT '{}'::jsonb
);

-- Índices para performance
CREATE INDEX idx_pre_vendas_entradas_status ON pre_vendas_entradas(status);
CREATE INDEX idx_pre_vendas_entradas_expires ON pre_vendas_entradas(expires_at);
CREATE INDEX idx_pre_vendas_entradas_paciente ON pre_vendas_entradas(paciente_id);
CREATE INDEX idx_pre_vendas_entradas_checkout ON pre_vendas_entradas(checkout_id);

-- Trigger para atualizar updated_at
CREATE OR REPLACE FUNCTION update_pre_vendas_entradas_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER pre_vendas_entradas_updated_at_trigger
BEFORE UPDATE ON pre_vendas_entradas
FOR EACH ROW
EXECUTE FUNCTION update_pre_vendas_entradas_updated_at();

-- Comentários para documentação
COMMENT ON TABLE pre_vendas_entradas IS 'Armazena temporariamente dados de entradas pagas antes da criação da venda final';
COMMENT ON COLUMN pre_vendas_entradas.pre_venda_id IS 'ID único temporário para rastrear a entrada até a criação da venda';
COMMENT ON COLUMN pre_vendas_entradas.metadata_json IS 'Dados adicionais em JSON para flexibilidade futura';