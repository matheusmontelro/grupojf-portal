BEGIN;

ALTER TABLE pacientes
    ADD COLUMN IF NOT EXISTS line_two TEXT;

COMMENT ON COLUMN pacientes.line_two IS 'Complemento do endereço do paciente';

COMMIT;
