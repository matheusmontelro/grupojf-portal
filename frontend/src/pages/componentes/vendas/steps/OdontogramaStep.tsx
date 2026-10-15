import React from 'react';
import OdontogramaSelector from './OdontogramaSelector.tsx';
import type { OdontogramaRead } from '../../../../api/odontogramas.ts';
import type { User } from '../../../../App.tsx';

interface OdontogramaStepProps {
  pacienteId: number;
  dentistaId: number;
  dependenteId?: number;
  usuarioLogado?: User | null;
  onOdontogramaSelect: (odontograma: OdontogramaRead, tipoNome: string | null) => void;
  onBack: () => void;
}

const OdontogramaStep: React.FC<OdontogramaStepProps> = ({
  pacienteId,
  dentistaId,
  dependenteId,
  usuarioLogado,
  onOdontogramaSelect,
  onBack,
}) => (
  <div className="sales-step-layout mx-auto max-w-5xl">
    <OdontogramaSelector
      pacienteId={pacienteId}
      dentistaId={dentistaId}
      dependenteId={dependenteId}
      usuarioLogado={usuarioLogado}
      onOdontogramaSelect={onOdontogramaSelect}
      onBack={onBack}
    />
  </div>
);

export default OdontogramaStep;
