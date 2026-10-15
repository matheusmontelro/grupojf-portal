import { createSecureUuidV4 } from './secureUuid.ts';

describe('createSecureUuidV4', () => {
  it('usa randomUUID quando o navegador disponibiliza a API', () => {
    const randomUUID = jest.fn(() => '11111111-1111-4111-8111-111111111111');

    expect(createSecureUuidV4({ randomUUID })).toBe(
      '11111111-1111-4111-8111-111111111111',
    );
    expect(randomUUID).toHaveBeenCalledTimes(1);
  });

  it('gera UUID v4 com getRandomValues em contexto HTTP sem randomUUID', () => {
    const getRandomValues = jest.fn((bytes: Uint8Array) => {
      bytes.fill(0);
      return bytes;
    });

    const uuid = createSecureUuidV4({ getRandomValues });

    expect(uuid).toBe('00000000-0000-4000-8000-000000000000');
    expect(uuid).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });

  it('falha explicitamente se nenhuma fonte criptográfica estiver disponível', () => {
    expect(() => createSecureUuidV4(null)).toThrow(
      'secure_random_unavailable',
    );
  });
});
