BEGIN;

CREATE TABLE IF NOT EXISTS whatsapp_document_deliveries (
    id BIGSERIAL PRIMARY KEY,
    document_type VARCHAR(20) NOT NULL
        CHECK (document_type IN ('anamnese', 'contrato')),
    document_id BIGINT NOT NULL,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(paciente_id),
    dependente_id INTEGER REFERENCES dependentes(dependente_id),
    template_name VARCHAR(100) NOT NULL,
    sender_unit VARCHAR(100) NOT NULL,
    recipient_masked VARCHAR(32) NOT NULL,
    origin VARCHAR(20) NOT NULL
        CHECK (origin IN ('automatico', 'manual')),
    status VARCHAR(20) NOT NULL DEFAULT 'processando'
        CHECK (status IN ('processando', 'enviado', 'erro')),
    meta_message_id TEXT,
    error_message TEXT,
    requested_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_document_auto_delivery
    ON whatsapp_document_deliveries (document_type, document_id)
    WHERE origin = 'automatico';

CREATE INDEX IF NOT EXISTS idx_whatsapp_document_reference
    ON whatsapp_document_deliveries (document_type, document_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_whatsapp_document_patient
    ON whatsapp_document_deliveries (paciente_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_whatsapp_document_status
    ON whatsapp_document_deliveries (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_whatsapp_document_meta_message
    ON whatsapp_document_deliveries (meta_message_id)
    WHERE meta_message_id IS NOT NULL;

COMMENT ON TABLE whatsapp_document_deliveries IS
    'Auditoria sanitizada das tentativas de envio de anamnese e contrato pelo WhatsApp oficial.';

COMMENT ON COLUMN whatsapp_document_deliveries.document_id IS
    'ID de anamnese_tokens para anamnese ou de digital_contracts para contrato.';

COMMENT ON COLUMN whatsapp_document_deliveries.recipient_masked IS
    'Telefone mascarado; o número completo não é armazenado nesta auditoria.';

COMMIT;
