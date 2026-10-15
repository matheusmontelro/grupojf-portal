import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import SignatureModal from './SignatureModal.tsx';
import ContratoDigitalPage from '../../pages/ContratoDigitalPage.tsx';
import {
  getContractForClient,
  signContract,
  uploadSelfie,
} from '../../api/digitalContracts.ts';


jest.mock('react-signature-canvas', () => {
  const React = require('react');

  return {
    __esModule: true,
    default: React.forwardRef(
      ({ onEnd }: { onEnd: () => void }, ref: React.ForwardedRef<unknown>) => {
        React.useImperativeHandle(ref, () => ({
          clear: () => undefined,
          isEmpty: () => false,
          toDataURL: () => 'data:image/png;base64,assinatura-atual',
        }));

        return (
          <button type="button" onClick={onEnd}>
            Desenhar assinatura
          </button>
        );
      }
    ),
  };
});

jest.mock('react-router-dom', () => ({
  useParams: () => ({ token: 'token-publico' }),
}), { virtual: true });

jest.mock('../../api/digitalContracts.ts', () => ({
  getContractForClient: jest.fn(),
  signContract: jest.fn(),
  uploadSelfie: jest.fn(),
}));

const mediaTrackStop = jest.fn();
const originalImage = globalThis.Image;
const originalCreateObjectURLDescriptor = Object.getOwnPropertyDescriptor(
  URL,
  'createObjectURL'
);
const originalInnerWidth = window.innerWidth;

const mockedGetContractForClient = getContractForClient as jest.MockedFunction<
  typeof getContractForClient
>;
const mockedSignContract = signContract as jest.MockedFunction<
  typeof signContract
>;
const mockedUploadSelfie = uploadSelfie as jest.MockedFunction<
  typeof uploadSelfie
>;

const markVideoAsReady = () => {
  const video = screen.getByTestId('signature-camera-video');

  Object.defineProperties(video, {
    videoWidth: { configurable: true, value: 640 },
    videoHeight: { configurable: true, value: 480 },
  });
  fireEvent.loadedMetadata(video);
};

const advanceToSignature = async () => {
  fireEvent.click(screen.getByRole('button', { name: 'Próximo' }));

  const preparingButton = await screen.findByRole('button', {
    name: 'Preparando câmera...',
  });
  expect(preparingButton).toBeDisabled();

  markVideoAsReady();
  const captureButton = screen.getByRole('button', {
    name: 'Capturar Foto',
  });
  fireEvent.click(captureButton);
  fireEvent.click(screen.getByRole('button', { name: 'Próximo' }));
  fireEvent.click(screen.getByRole('button', { name: 'Desenhar assinatura' }));
};

describe('SignatureModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: jest.fn().mockResolvedValue({
          getTracks: () => [{ stop: mediaTrackStop }],
        }),
      },
    });
    jest
      .spyOn(HTMLCanvasElement.prototype, 'getContext')
      .mockReturnValue({
        beginPath: jest.fn(),
        clearRect: jest.fn(),
        drawImage: jest.fn(),
        fillRect: jest.fn(),
        lineTo: jest.fn(),
        moveTo: jest.fn(),
        stroke: jest.fn(),
      } as unknown as CanvasRenderingContext2D);
    jest
      .spyOn(HTMLCanvasElement.prototype, 'toDataURL')
      .mockReturnValue('data:image/jpeg;base64,selfie');
    jest
      .spyOn(HTMLCanvasElement.prototype, 'getBoundingClientRect')
      .mockReturnValue({
        bottom: 200,
        height: 200,
        left: 0,
        right: 300,
        top: 0,
        width: 300,
        x: 0,
        y: 0,
        toJSON: () => undefined,
      });
  });

  afterEach(() => {
    jest.restoreAllMocks();
    Object.defineProperty(globalThis, 'Image', {
      configurable: true,
      writable: true,
      value: originalImage,
    });
    if (originalCreateObjectURLDescriptor) {
      Object.defineProperty(
        URL,
        'createObjectURL',
        originalCreateObjectURLDescriptor
      );
    } else {
      delete (URL as typeof URL & { createObjectURL?: unknown }).createObjectURL;
    }
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: originalInnerWidth,
    });
  });

  test('bloqueia envio duplicado e permite tentar novamente após erro', async () => {
    let rejectSave: (reason?: unknown) => void = () => undefined;
    const pendingSave = new Promise<void>((_resolve, reject) => {
      rejectSave = reject;
    });
    const onSave = jest.fn(() => pendingSave);
    const onClose = jest.fn();

    render(
      <SignatureModal
        isOpen
        onClose={onClose}
        onSave={onSave}
        patientName="Paciente Teste"
        patientCPF="00000000000"
        documentType="anamnese"
      />
    );

    await advanceToSignature();

    const submitButton = screen.getByRole('button', {
      name: 'Assinar e Finalizar',
    });
    fireEvent.click(submitButton);
    fireEvent.click(submitButton);

    expect(onSave).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole('button', { name: 'Assinando...' })
    ).toBeDisabled();
    expect(
      screen.getByRole('button', { name: 'Fechar assinatura digital' })
    ).toBeDisabled();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).not.toHaveBeenCalled();

    await act(async () => {
      rejectSave(new Error('Falha temporária ao assinar'));
      await pendingSave.catch(() => undefined);
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Falha temporária ao assinar'
    );

    const retryButton = screen.getByRole('button', {
      name: 'Assinar e Finalizar',
    });
    expect(retryButton).toBeEnabled();
    fireEvent.click(retryButton);

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(2));
  });

  test('encerra uma câmera que resolve depois do fechamento do modal', async () => {
    let resolveCamera: (stream: MediaStream) => void = () => undefined;
    const lateTrackStop = jest.fn();
    const pendingCamera = new Promise<MediaStream>((resolve) => {
      resolveCamera = resolve;
    });
    const getUserMedia = jest.fn(() => pendingCamera);
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });

    const { unmount } = render(
      <SignatureModal
        isOpen
        onClose={jest.fn()}
        onSave={jest.fn()}
        patientName="Paciente Teste"
        patientCPF="00000000000"
        documentType="anamnese"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Próximo' }));
    await waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(1));
    unmount();

    await act(async () => {
      resolveCamera({
        getTracks: () => [{ stop: lateTrackStop }],
      } as unknown as MediaStream);
      await pendingCamera;
    });

    expect(lateTrackStop).toHaveBeenCalledTimes(1);
  });

  test('encerra a câmera ativa quando o modal é ocultado', async () => {
    const activeTrackStop = jest.fn();
    const stream = {
      getTracks: () => [{ stop: activeTrackStop }],
    } as unknown as MediaStream;
    const getUserMedia = jest.fn().mockResolvedValue(stream);
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });

    const modalProps = {
      onClose: jest.fn(),
      onSave: jest.fn(),
      patientName: 'Paciente Teste',
      patientCPF: '00000000000',
      documentType: 'anamnese' as const,
    };
    const { rerender } = render(
      <SignatureModal isOpen {...modalProps} />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Próximo' }));
    await waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(1));
    await waitFor(() => {
      expect(
        (screen.getByTestId('signature-camera-video') as HTMLVideoElement)
          .srcObject
      ).toBe(stream);
    });

    rerender(<SignatureModal isOpen={false} {...modalProps} />);

    expect(activeTrackStop).toHaveBeenCalledTimes(1);
  });

  test('mantém captura bloqueada até a câmera ficar pronta e permite retry', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => undefined);
    const getUserMedia = jest
      .fn()
      .mockRejectedValueOnce(new Error('Permissão negada'))
      .mockResolvedValueOnce({
        getTracks: () => [{ stop: mediaTrackStop }],
      });
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });

    render(
      <SignatureModal
        isOpen
        onClose={jest.fn()}
        onSave={jest.fn()}
        patientName="Paciente Teste"
        patientCPF="00000000000"
        documentType="anamnese"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Próximo' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Verifique a permissão e tente novamente'
    );
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Tentar acessar câmera novamente',
      })
    );

    const preparingButton = await screen.findByRole('button', {
      name: 'Preparando câmera...',
    });
    expect(preparingButton).toBeDisabled();

    markVideoAsReady();
    expect(
      screen.getByRole('button', { name: 'Capturar Foto' })
    ).toBeEnabled();
  });
});

const installLoadedImageMock = () => {
  class LoadedImage {
    width = 640;
    height = 480;
    onload: ((event: Event) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;

    set src(_value: string) {
      this.onload?.(new Event('load'));
    }
  }

  Object.defineProperty(globalThis, 'Image', {
    configurable: true,
    writable: true,
    value: LoadedImage,
  });
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    value: jest.fn(() => 'blob:selfie'),
  });
};

const renderContractAtSignatureStep = async () => {
  installLoadedImageMock();
  mockedGetContractForClient.mockResolvedValue({
    contract_id: 123,
    paciente_nome: 'Paciente Teste',
    paciente_cpf: '00000000000',
    endereco: 'Rua Teste',
    valor_total: 100,
    status: 'sent',
    contract_html: '<p>Contrato de teste</p>',
  });
  mockedUploadSelfie.mockResolvedValue({});

  const view = render(<ContratoDigitalPage />);

  fireEvent.click(
    await screen.findByRole('button', {
      name: /Li e Aceito\. Avançar para Selfie/i,
    })
  );

  const fileInput = screen.getByLabelText('Selecionar selfie');
  fireEvent.change(fileInput, {
    target: {
      files: [new File(['selfie'], 'selfie.jpg', { type: 'image/jpeg' })],
    },
  });

  await screen.findByAltText('Selfie Preview');
  fireEvent.click(
    screen.getByRole('button', {
      name: /Usar esta Selfie e Avançar/i,
    })
  );
  await screen.findByRole('heading', { name: 'Sua Assinatura Digital' });

  return view;
};

const drawContractSignature = (canvas: HTMLCanvasElement) => {
  fireEvent.mouseDown(canvas, { clientX: 20, clientY: 20 });
  fireEvent.mouseMove(canvas, { clientX: 80, clientY: 60 });
  fireEvent.mouseUp(canvas, { clientX: 80, clientY: 60 });
};

describe('ContratoDigitalPage - assinatura', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest
      .spyOn(HTMLCanvasElement.prototype, 'getContext')
      .mockReturnValue({
        beginPath: jest.fn(),
        clearRect: jest.fn(),
        drawImage: jest.fn(),
        fillRect: jest.fn(),
        lineTo: jest.fn(),
        moveTo: jest.fn(),
        stroke: jest.fn(),
      } as unknown as CanvasRenderingContext2D);
    jest
      .spyOn(HTMLCanvasElement.prototype, 'toDataURL')
      .mockReturnValue('data:image/jpeg;base64,dados');
    jest
      .spyOn(HTMLCanvasElement.prototype, 'getBoundingClientRect')
      .mockReturnValue({
        bottom: 200,
        height: 200,
        left: 0,
        right: 300,
        top: 0,
        width: 300,
        x: 0,
        y: 0,
        toJSON: () => undefined,
      });
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 390,
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
    Object.defineProperty(globalThis, 'Image', {
      configurable: true,
      writable: true,
      value: originalImage,
    });
    if (originalCreateObjectURLDescriptor) {
      Object.defineProperty(
        URL,
        'createObjectURL',
        originalCreateObjectURLDescriptor
      );
    } else {
      delete (URL as typeof URL & { createObjectURL?: unknown }).createObjectURL;
    }
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: originalInnerWidth,
    });
  });

  test('preserva o canvas após erro, bloqueia duplicidade e permite retry', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => undefined);
    let rejectSignature: (reason?: unknown) => void = () => undefined;
    const pendingSignature = new Promise<void>((_resolve, reject) => {
      rejectSignature = reject;
    });
    mockedSignContract
      .mockReturnValueOnce(pendingSignature)
      .mockResolvedValueOnce({});

    await renderContractAtSignatureStep();
    const canvas = screen.getByTestId(
      'contract-signature-canvas'
    ) as HTMLCanvasElement;
    drawContractSignature(canvas);

    const submitButton = screen.getByRole('button', {
      name: 'Salvar e Enviar Assinatura',
    });
    expect(submitButton).toBeEnabled();
    fireEvent.click(submitButton);
    fireEvent.click(submitButton);
    expect(mockedSignContract).toHaveBeenCalledTimes(1);

    await act(async () => {
      rejectSignature(new Error('Falha temporária ao enviar'));
      await pendingSignature.catch(() => undefined);
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Falha temporária ao enviar'
    );
    expect(screen.getByTestId('contract-signature-canvas')).toBe(canvas);

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Salvar e Enviar Assinatura',
      })
    );

    await waitFor(() => expect(mockedSignContract).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByRole('heading', {
        name: 'Contrato Assinado com Sucesso!',
      })
    ).toBeInTheDocument();
  });

  test('invalida a assinatura quando o canvas muda de tamanho', async () => {
    await renderContractAtSignatureStep();
    const canvas = screen.getByTestId(
      'contract-signature-canvas'
    ) as HTMLCanvasElement;
    drawContractSignature(canvas);

    expect(
      screen.getByRole('button', {
        name: 'Salvar e Enviar Assinatura',
      })
    ).toBeEnabled();

    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 900,
    });
    fireEvent(window, new Event('resize'));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'A área de assinatura foi redimensionada'
    );
    expect(
      screen.getByRole('button', {
        name: 'Salvar e Enviar Assinatura',
      })
    ).toBeDisabled();
  });

  test('escala as coordenadas CSS para o bitmap da assinatura', async () => {
    await renderContractAtSignatureStep();
    const canvas = screen.getByTestId(
      'contract-signature-canvas'
    ) as HTMLCanvasElement;
    jest.spyOn(canvas, 'getBoundingClientRect').mockReturnValue({
      bottom: 400,
      height: 400,
      left: 0,
      right: 600,
      top: 0,
      width: 600,
      x: 0,
      y: 0,
      toJSON: () => undefined,
    });
    const context = canvas.getContext('2d') as CanvasRenderingContext2D;

    fireEvent.mouseDown(canvas, { clientX: 500, clientY: 200 });
    fireEvent.mouseMove(canvas, { clientX: 550, clientY: 300 });
    fireEvent.mouseUp(canvas, { clientX: 550, clientY: 300 });

    expect(context.moveTo).toHaveBeenCalledWith(250, 100);
    expect(context.lineTo).toHaveBeenCalledWith(275, 150);
    expect(
      screen.getByRole('button', {
        name: 'Salvar e Enviar Assinatura',
      })
    ).toBeEnabled();
  });
});
