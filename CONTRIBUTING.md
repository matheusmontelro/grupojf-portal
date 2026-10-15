# Contribuindo

## Fluxo

1. Crie uma branch a partir de `main`.
2. Faca commits pequenos e descritivos.
3. Abra pull request com contexto, prints quando houver UI e notas de validacao.
4. Aguarde o CI passar antes de fazer merge.

## Validacao local

Backend:

```bash
cd backend
python -m compileall app
```

Frontend:

```bash
cd frontend
npm ci
npm run build
```
