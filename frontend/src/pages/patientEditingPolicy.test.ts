import { canEnablePatientEditing } from './patientEditingPolicy';

describe('patientEditingPolicy', () => {
  it('permite habilitar a edição independentemente do perfil', () => {
    expect(canEnablePatientEditing(true, false)).toBe(true);
  });

  it('não exibe a ação fora do modo de edição ou após habilitá-la', () => {
    expect(canEnablePatientEditing(false, false)).toBe(false);
    expect(canEnablePatientEditing(true, true)).toBe(false);
  });
});
