# 🔐 Guia de Uso da API Key

## 📋 Informações da API Key

**API Key atual:**
```
SUA_API_KEY_PUBLIC
```

**Header obrigatório:**
```
X-API-Key: SUA_API_KEY_PUBLIC
```

---

## 🚀 Como Usar

### 1. cURL

```bash
curl -X GET "https://api.exemplo.com/api/public/vendas/resumo?limite=10" \
  -H "X-API-Key: SUA_API_KEY_PUBLIC" \
  -H "Accept: application/json"
```

### 2. Python

```python
import requests

url = "https://api.exemplo.com/api/public/vendas/resumo"
headers = {
    "X-API-Key": "SUA_API_KEY_PUBLIC",
    "Accept": "application/json"
}
params = {"limite": 10}

response = requests.get(url, headers=headers, params=params)
print(response.json())
```

### 3. JavaScript/Node.js

```javascript
const axios = require('axios');

const url = 'https://api.exemplo.com/api/public/vendas/resumo';
const headers = {
    'X-API-Key': 'SUA_API_KEY_PUBLIC',
    'Accept': 'application/json'
};
const params = { limite: 10 };

axios.get(url, { headers, params })
    .then(response => console.log(response.data))
    .catch(error => console.error(error));
```

### 4. Postman

A collection já está configurada com a API Key:

2. A API Key está em **Collection → Variables → api_key**
3. Todos os requests herdam automaticamente
4. Clique em **Send** - funciona!

Para alterar a API Key:
1. Clique nos **3 pontinhos** (...) na collection
2. **Edit** → **Variables**
3. Altere o valor de `api_key`
4. **Save**

---

## ⚠️ Segurança

### ✅ Boas Práticas

1. **Não commite a API Key** no código
   - Use variáveis de ambiente
   - `.env` está no `.gitignore`

2. **Não compartilhe publicamente**
   - Envie por canais seguros (email criptografado, Slack privado)
   - Não poste em issues públicas do GitHub

3. **Use HTTPS em produção**
   - ✅ Desenvolvimento: `http://localhost:8000` (OK)
   - ✅ Produção: use o domínio HTTPS da sua instância
   - ❌ NUNCA: use HTTP para transmitir a chave

4. **Monitore o uso**
   - Use a observabilidade configurada no seu ambiente, sem registrar a chave.

### 🔄 Renovar API Key

Para gerar uma nova chave:

```bash
cd backend
python3 -c "import secrets; print('API_KEY_PUBLIC=' + secrets.token_urlsafe(32))"
```

Depois:
1. Atualizar no `.env`
2. Aplicar a configuração no ambiente da aplicação
3. Distribuir nova chave para os clientes

---

## ❌ Erros Comuns

### Erro: "API Key obrigatória"

**Causa:** Header `X-API-Key` não foi enviado

**Solução:**
```bash
# ❌ Errado
curl "https://api.exemplo.com/api/public/vendas/resumo"

# ✅ Correto
curl "https://api.exemplo.com/api/public/vendas/resumo" \
  -H "X-API-Key: SUA_API_KEY_PUBLIC"
```

### Erro: "API Key inválida"

**Causa:** API Key incorreta ou expirada

**Solução:**
1. Verificar se copiou corretamente (sem espaços extras)
2. Confirmar que é a chave atual
3. Contactar administrador para renovação

---

## 📊 Endpoints Protegidos

Todos os endpoints em `/api/public/vendas/` requerem API Key:

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/public/vendas/resumo` | GET | Resumo agregado |
| `/api/public/vendas/` | GET | Listagem com paginação |
| `/api/public/vendas/{documento}` | GET | Consulta específica |

---

## 🔍 Testando a API Key

### Teste 1: Sem API Key (deve falhar)
```bash
curl "http://localhost:8000/api/public/vendas/resumo?limite=5"
```

**Resposta esperada:**
```json
{
    "detail": "API Key obrigatória. Envie no header: X-API-Key"
}
```

### Teste 2: Com API Key (deve funcionar)
```bash
curl "http://localhost:8000/api/public/vendas/resumo?limite=5" \
  -H "X-API-Key: SUA_API_KEY_PUBLIC"
```

**Resposta esperada:**
```json
{
    "total_vendas": 5,
    "valor_total": 12345.00,
    "vendas": [...]
}
```

---

## 📞 Suporte

Consulte a documentação pública da instância da aplicação.

---

## 📝 Changelog

**v1.1.0** - 2025-10-28
- ✅ Adicionada proteção com API Key
- ✅ Middleware de validação implementado
- ✅ Logs de acesso habilitados

**v1.0.0** - 2025-10-28
- ✅ Endpoints públicos criados (sem proteção)

---

**Última atualização:** 2025-10-28
**Status:** ✅ Ativo
