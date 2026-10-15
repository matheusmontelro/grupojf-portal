export const canEnablePatientEditing = (
  isEditMode: boolean,
  isEditingEnabled: boolean
): boolean => isEditMode && !isEditingEnabled;
