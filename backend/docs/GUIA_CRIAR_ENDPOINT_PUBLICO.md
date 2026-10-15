# 📘 Guia: Como Criar um Endpoint Público no FastAPI

Este guia mostra como criar endpoints públicos (sem autenticação) e documentá-los no Swagger.

---

## 🎯 Objetivo

Criar endpoints de API que:
- ✅ **Não requerem autenticação** (público)
- ✅ **Aparecem documentados no Swagger** (`/docs`)
- ✅ **São seguros** (não expõem dados sensíveis)
- ✅ **Seguem as melhores práticas** de REST API

---

## 📋 Passo a Passo

### **Passo 1: Criar o arquivo do router**

Crie um novo arquivo em `backend/app/routers/`:

```python
# app/routers/seu_router_publico.py

from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional, List
from pydantic import BaseModel, Field
import logging

from ..database.db import DatabaseConnection

logger = logging.getLogger(__name__)

# Criar router com prefixo /api/public/
# IMPORTANTE: Use /api/public/ para que o middleware ignore a autenticação
router = APIRouter(
    prefix="/api/public/seu-recurso",
    tags=["Public API - Seu Recurso"]  # Agrupa no Swagger
)

# ==================== SCHEMAS ====================

class SeuSchema(BaseModel):
    """Documentação do schema"""
    id: int = Field(..., description="ID do recurso")
    nome: str = Field(..., description="Nome do recurso")

    class Config:
        # Exemplo que aparece no Swagger
        schema_extra = {
            "example": {
                "id": 1,
                "nome": "Exemplo"
            }
        }

# ==================== ENDPOINTS ====================

@router.get(
    "/",
    response_model=List[SeuSchema],
    summary="Listar recursos",
    description="""
    **Endpoint público** para listar recursos.

    Este endpoint não requer autenticação.

    ### Parâmetros:
    - **limite**: Quantidade máxima de resultados

    ### Exemplo:
    ```
    GET /api/public/seu-recurso/?limite=10
    ```
    """,
    responses={
        200: {"description": "Lista de recursos"},
        400: {"description": "Parâmetros inválidos"},
        500: {"description": "Erro interno"}
    }
)
async def listar_recursos(
    limite: int = Query(10, ge=1, le=100, description="Máximo de resultados")
):
    """
    Lista recursos públicos (sem autenticação)
    """
    try:
        db = DatabaseConnection()

        query = "SELECT * FROM sua_tabela LIMIT %s"
        resultados = db.execute_query(query, (limite,))

        return [SeuSchema(**r) for r in resultados]

    except Exception as e:
        logger.error(f"Erro: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
```

---

### **Passo 2: Importar no main.py**

Adicione o import do seu router:

```python
# app/main.py

from .routers import (
    # ... outros routers ...
    seu_router_publico  # ← Adicione aqui
)
```

---

### **Passo 3: Registrar o router**

Adicione o router à aplicação FastAPI:

```python
# app/main.py

# Depois dos outros routers...
app.include_router(seu_router_publico.router)
```

**⚠️ IMPORTANTE:** Não adicione o `prefix="/api"`, pois o router já tem o prefixo completo!

---

### **Passo 4: Verificar middleware de autenticação**

O middleware em `backend/app/middleware/auth_middleware.py` já está configurado para **ignorar rotas que começam com `/api/public/`**.

Confira a linha 85:

```python
public_prefixes = [
    "/webhook/",
    "/api/webhooks/",
    "/static/",
    "/public/",
    "/api/public/",  # ← Rotas públicas da API
    # ...
]
```

Se o seu prefixo for diferente, adicione-o aqui.

---

### **Passo 5: Documentação Swagger**

A documentação aparece automaticamente no Swagger em:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

#### **Elementos importantes para boa documentação:**

1. **`summary`**: Título curto do endpoint
2. **`description`**: Descrição detalhada (suporta Markdown)
3. **`response_model`**: Schema de resposta
4. **`responses`**: Códigos HTTP e descrições
5. **`tags`**: Agrupamento no Swagger
6. **`Field(..., description="")`**: Descrição de cada campo
7. **`Query(..., description="")`**: Descrição de parâmetros

---

## 🔐 Segurança em Endpoints Públicos

### **1. Mascarar dados sensíveis**

Sempre oculte informações pessoais:

```python
def mascararCPF(cpf: str) -> str:
    """Mascara um CPF mostrando apenas os últimos dígitos"""
    if not cpf or len(cpf) < 11:
        return "***.***.***-**"

    cpf_numeros = ''.join(filter(str.isdigit, cpf))
    return f"***.***{cpf_numeros[-6:-2]}-{cpf_numeros[-2:]}"
```

### **2. Limitar quantidade de dados**

```python
limite: int = Query(
    10,
    ge=1,
    le=100,  # ← Máximo permitido
    description="Quantidade de resultados"
)
```

### **3. Filtrar dados sensíveis na query**

```python
# ❌ NÃO faça isso (expõe dados sensíveis):
query = "SELECT * FROM usuarios"

# ✅ Faça isso (selecione apenas campos públicos):
query = "SELECT id, nome, email FROM usuarios"
```

### **4. Implementar rate limiting**

Implemente rate limiting na camada de entrada compatível com o ambiente em que a API será publicada.

---

## 📊 Exemplo Completo: Endpoint de Consulta Pública

```python
@router.get(
    "/{id}",
    response_model=RecursoPublico,
    summary="Consultar recurso por ID",
    description="""
    **Endpoint público** para consultar um recurso específico.

    ### Parâmetros:
    - **id**: ID do recurso a consultar

    ### Exemplo:
    ```bash
    curl -X GET "http://localhost:8000/api/public/recursos/123"
    ```

    ### Resposta:
    ```json
    {
      "id": 123,
      "nome": "Recurso Exemplo",
      "data_criacao": "2025-10-28"
    }
    ```
    """,
    responses={
        200: {
            "description": "Recurso encontrado",
            "content": {
                "application/json": {
                    "example": {
                        "id": 123,
                        "nome": "Recurso Exemplo",
                        "data_criacao": "2025-10-28"
                    }
                }
            }
        },
        404: {"description": "Recurso não encontrado"},
        500: {"description": "Erro interno"}
    }
)
async def consultar_recurso(
    id: int = Query(..., description="ID do recurso", example=123)
):
    """Consulta um recurso público por ID"""
    try:
        db = DatabaseConnection()

        query = "SELECT id, nome, data_criacao FROM recursos WHERE id = %s"
        resultado = db.execute_query(query, (id,))

        if not resultado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recurso {id} não encontrado"
            )

        return RecursoPublico(**resultado[0])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao consultar recurso {id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar consulta"
        )
```

---

## 🧪 Testando seus Endpoints

### **1. Testar no navegador**

Acesse diretamente:
```
http://localhost:8000/api/public/seu-recurso/
```

### **2. Testar com cURL**

```bash
# GET simples
curl -X GET "http://localhost:8000/api/public/seu-recurso/"

# GET com parâmetros
curl -X GET "http://localhost:8000/api/public/seu-recurso/?limite=20"

# Com formatação JSON
curl -X GET "http://localhost:8000/api/public/seu-recurso/" | jq
```

### **3. Testar no Swagger**

1. Acesse http://localhost:8000/docs
2. Encontre sua tag "Public API - Seu Recurso"
3. Clique em "Try it out"
4. Preencha os parâmetros
5. Clique em "Execute"

### **4. Testar com Python**

```python
import requests

response = requests.get("http://localhost:8000/api/public/seu-recurso/")
print(response.json())
```

---

## ✅ Checklist Final

Antes de colocar em produção, verifique:

- [ ] Router criado com prefixo `/api/public/`
- [ ] Tags configuradas no router
- [ ] Schemas Pydantic com `Field()` e descrições
- [ ] Docstrings completas nos endpoints
- [ ] Exemplos no `schema_extra` ou `responses`
- [ ] Tratamento de erros adequado
- [ ] Dados sensíveis mascarados
- [ ] Limites de paginação implementados
- [ ] Logging configurado
- [ ] Testado no Swagger
- [ ] Testado com cURL ou cliente HTTP
- [ ] Documentação criada

---

## 📁 Estrutura de Arquivos

```
backend/
├── app/
│   ├── main.py                           # ← Registrar router aqui
│   ├── middleware/
│   │   └── auth_middleware.py            # ← Verificar prefixos públicos
│   └── routers/
│       ├── seu_router_publico.py         # ← Criar router aqui
│       └── public_registration.py        # ← Outro exemplo
└── docs/
    ├── GUIA_CRIAR_ENDPOINT_PUBLICO.md    # ← Este guia
    └── API_PUBLICA_VENDAS.md             # ← Documentação de exemplo
```

---

## 📚 Referências

- [FastAPI - Path Operations](https://fastapi.tiangolo.com/tutorial/path-params/)
- [FastAPI - Query Parameters](https://fastapi.tiangolo.com/tutorial/query-params/)
- [FastAPI - Response Model](https://fastapi.tiangolo.com/tutorial/response-model/)
- [Pydantic - Field](https://docs.pydantic.dev/latest/usage/fields/)
- [OpenAPI Specification](https://swagger.io/specification/)

---

## 💡 Dicas Importantes

1. **Use prefixos descritivos**: `/api/public/vendas`, `/api/public/relatorios`
2. **Agrupe por tags**: Facilita navegação no Swagger
3. **Documente tudo**: Description, examples, responses
4. **Valide entradas**: Use Pydantic e Query validators
5. **Trate erros**: HTTPException com mensagens claras
6. **Log tudo**: Logger para debug e auditoria
7. **Teste sempre**: Swagger, cURL, Postman
8. **Segurança primeiro**: Mascare dados, limite queries

---

**Última atualização:** 2025-10-28
**Autor:** Equipe de Desenvolvimento Grupo JF
