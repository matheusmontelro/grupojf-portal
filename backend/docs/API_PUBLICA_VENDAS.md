# API Pública de Vendas - Documentação

Esta documentação descreve como utilizar a API pública de vendas do Grupo JF.

## 🌐 Características

- ✅ **Sem autenticação**: Endpoints públicos não requerem token JWT
- ✅ **Dados mascarados**: CPFs e informações sensíveis são parcialmente ocultados
- ✅ **Paginação**: Suporte para consultas paginadas
- ✅ **Filtros**: Múltiplos filtros para consultas personalizadas
- ✅ **Documentação Swagger**: Totalmente documentado em `/docs`

## 📋 Endpoints Disponíveis

### 1. Consultar Resumo de Vendas

**GET** `/api/public/vendas/resumo`

Retorna um resumo agregado das vendas com filtros opcionais.

#### Parâmetros Query (opcionais):

| Parâmetro | Tipo | Descrição | Exemplo |
|-----------|------|-----------|---------|
| `data_inicio` | string | Data inicial (YYYY-MM-DD) | `2025-10-01` |
| `data_fim` | string | Data final (YYYY-MM-DD) | `2025-10-31` |
| `unidade` | string | Filtrar por unidade | `Unidade Centro` |
| `limite` | integer | Máximo de vendas (1-100) | `50` |

#### Exemplo de Requisição:

```bash
curl -X GET "https://api.exemplo.com/api/public/vendas/resumo?data_inicio=2025-10-01&data_fim=2025-10-31&unidade=Centro&limite=20"
```

#### Exemplo de Resposta:

```json
{
  "total_vendas": 10,
  "valor_total": 15000.00,
  "vendas": [
    {
      "id": 123,
      "documento_venda": "VND-2025-00123",
      "data_venda": "2025-10-28",
      "valor_total": 1500.00,
      "status_venda": "ativa",
      "unidade": "Unidade Centro"
    }
  ]
}
```

---

### 2. Consultar Venda por Documento

**GET** `/api/public/vendas/{documento_venda}`

Retorna detalhes de uma venda específica pelo número do documento.

#### Parâmetros Path:

| Parâmetro | Tipo | Descrição | Exemplo |
|-----------|------|-----------|---------|
| `documento_venda` | string | Número do documento | `VND-2025-00123` |

#### Exemplo de Requisição:

```bash
curl -X GET "https://api.exemplo.com/api/public/vendas/VND-2025-00123"
```

#### Exemplo de Resposta:

```json
{
  "id": 123,
  "documento_venda": "VND-2025-00123",
  "data_venda": "2025-10-28",
  "cpf_paciente": "***.***.123-45",
  "nome_paciente": "João Silva",
  "valor_total": 1500.00,
  "status_venda": "ativa",
  "status_pagamento": "pago",
  "unidade": "Unidade Centro",
  "tipo_odontograma": "Contrato Ortodôntico"
}
```

**Nota:** O CPF é parcialmente mascarado para privacidade (`***.***.123-45`)

---

### 3. Listar Vendas Públicas

**GET** `/api/public/vendas/`

Lista vendas com paginação e filtros opcionais.

#### Parâmetros Query:

| Parâmetro | Tipo | Descrição | Padrão | Exemplo |
|-----------|------|-----------|--------|---------|
| `skip` | integer | Registros a pular (offset) | `0` | `20` |
| `limit` | integer | Máximo de registros (1-100) | `20` | `50` |
| `unidade` | string | Filtrar por unidade | - | `Centro` |
| `data_inicio` | string | Data inicial (YYYY-MM-DD) | - | `2025-10-01` |
| `data_fim` | string | Data final (YYYY-MM-DD) | - | `2025-10-31` |

#### Exemplo de Requisição:

```bash
curl -X GET "https://api.exemplo.com/api/public/vendas/?skip=0&limit=20&unidade=Centro"
```

#### Exemplo de Resposta:

```json
[
  {
    "id": 123,
    "documento_venda": "VND-2025-00123",
    "data_venda": "2025-10-28",
    "valor_total": 1500.00,
    "status_venda": "ativa",
    "unidade": "Unidade Centro"
  },
  {
    "id": 124,
    "documento_venda": "VND-2025-00124",
    "data_venda": "2025-10-27",
    "valor_total": 2000.00,
    "status_venda": "ativa",
    "unidade": "Unidade Centro"
  }
]
```

---

## 🔐 Segurança e Privacidade

### Dados Mascarados

Para proteger a privacidade dos pacientes, alguns dados são mascarados:

- **CPF**: Apenas os 5 últimos dígitos são visíveis
  - Original: `123.456.789-01`
  - Mascarado: `***.***789-01`

### Rate Limiting

Recomenda-se implementar rate limiting na camada de entrada da API para evitar abuso.

---

## 📊 Códigos de Status HTTP

| Código | Descrição |
|--------|-----------|
| `200` | Sucesso - Dados retornados |
| `400` | Bad Request - Parâmetros inválidos |
| `404` | Not Found - Recurso não encontrado |
| `500` | Internal Server Error - Erro no servidor |

---

## 💡 Exemplos de Uso

### Python

```python
import requests

# Consultar resumo de vendas
response = requests.get(
    "https://api.exemplo.com/api/public/vendas/resumo",
    params={
        "data_inicio": "2025-10-01",
        "data_fim": "2025-10-31",
        "unidade": "Centro",
        "limite": 50
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Total de vendas: {data['total_vendas']}")
    print(f"Valor total: R$ {data['valor_total']:.2f}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

async function getVendasResumo() {
  try {
    const response = await axios.get('https://api.exemplo.com/api/public/vendas/resumo', {
      params: {
        data_inicio: '2025-10-01',
        data_fim: '2025-10-31',
        unidade: 'Centro',
        limite: 50
      }
    });

    console.log(`Total de vendas: ${response.data.total_vendas}`);
    console.log(`Valor total: R$ ${response.data.valor_total.toFixed(2)}`);
  } catch (error) {
    console.error('Erro:', error.response?.data || error.message);
  }
}

getVendasResumo();
```

### cURL

```bash
# Consultar resumo
curl -X GET \
  "https://api.exemplo.com/api/public/vendas/resumo?data_inicio=2025-10-01&data_fim=2025-10-31" \
  -H "Accept: application/json"

# Consultar venda específica
curl -X GET \
  "https://api.exemplo.com/api/public/vendas/VND-2025-00123" \
  -H "Accept: application/json"

# Listar com paginação
curl -X GET \
  "https://api.exemplo.com/api/public/vendas/?skip=0&limit=20&unidade=Centro" \
  -H "Accept: application/json"
```

---

## 🎯 Boas Práticas

1. **Cache**: Implemente cache local para reduzir requisições desnecessárias
2. **Tratamento de Erros**: Sempre trate os códigos de status HTTP adequadamente
3. **Validação**: Valide os parâmetros antes de enviar a requisição
4. **Timeout**: Configure timeouts apropriados para suas requisições
5. **Logs**: Registre requisições para auditoria e debugging

---

## 📝 Notas Importantes

- ⚠️ Esta API é **somente leitura** - não é possível criar ou modificar vendas
- ⚠️ Os dados retornados são **públicos mas mascarados** para privacidade
- ⚠️ Vendas **canceladas** são **excluídas** dos resultados por padrão
- ⚠️ O limite máximo de resultados por requisição é **100 registros**

---

## 🔗 Links Úteis

- **Swagger UI**: `https://api.exemplo.com/docs`
- **ReDoc**: `https://api.exemplo.com/redoc`
- **OpenAPI Spec**: `https://api.exemplo.com/openapi.json`

---

## 📞 Suporte

Para questões ou problemas relacionados à API, consulte a documentação pública
da instância da aplicação.

---

**Última atualização:** 2025-10-28
**Versão da API:** 1.0.0
