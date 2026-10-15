# Application entry point.
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
import logging
from dotenv import load_dotenv

# Load environment variables
from pathlib import Path
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Configurar logging para ver os logs do middleware
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# O entrypoint principal preserva o registro eager dos mappers legados. O
# entrypoint isolado de vendas Asaas nao chama este carregador.
from .models import load_legacy_models

load_legacy_models()

# Importar middlewares
from .middleware.auth_middleware import AuthMiddleware
from .middleware.api_key_middleware import APIKeyMiddleware
from .digital_contracts.router import router as digital_contracts_router
from .digital_contracts.public_router import router as digital_contracts_public_router
from .digital_contracts.selfie_test_router import router as selfie_test_router

# Importar routers existentes
from .routers import users, boletos, bempaggo_webhooks, pacientes, contratos, auth, transacoes
from .routers import venda_parcela, tipos_odontograma, parcelas_contrato
# Importar os NOVOS routers que criamos/planejamos
from .routers import (
    produto,
    dentista,
    forma_pagamento,
    regra_desconto,
    odontograma,
    venda,
    venda_parcela,
    solicitacao_desconto,
    cargos,
    regras_split,
    carne,
    empresas,
    empresa_regras_split,
    configuracao_split,
    carne_webhook,
    pacientes_integrados,  # Novo router para integração com Delta
    fatura_avulsa,
    fatura_recorrente,
    fatura_avulsa_webhook,
    fatura_recorrente_webhook,
    pre_venda,  # Novo router para pré-vendas com entrada
    webhook_entrada,  # Novo router para webhook de entrada
    relatorio_caixa,  # Novo router para relatório de caixa
    relatorio_vendas,  # Novo router para relatório de vendas completo
    vendas_list,  # Novo router para listagem de vendas com filtros
    relatorio_splits_seller,  # Novo router para relatório de splits por seller
    relatorio_splits_seller_v2,  # Novo router para relatório de splits versão 2
    relatorio_splits_seller_v3,  # Novo router para relatório de splits versão 3 com mapeamento correto
    relatorio_splits_seller_v5,  # Novo router para relatório de splits versão 5 com filtro por unidade
    relatorio_splits_seller_v6,  # Novo router para relatório de splits versão 6 com contexto de venda
    relatorio_vendas_publico,  # Novo router para relatório público de vendas Excel
    caixa_diario,  # Novo router para caixa diário
    parcelas_router,  # Novo router para parcelas unificadas
    dashboard_vendas,  # Novo router para dashboard de vendas
    financeiro_pagamentos,  # Router de gestão financeira de pagamentos
    caixa_firebird,
)

# Importar novos routers
from app.routers import dependentes
from app.routers import public_registration
from app.routers import funcoes_dentista

# Importar routers da anamnese digital
from app.anamnese_digital import anamnese_router, anamnese_public_router

# Criar aplicação FastAPI com documentação explicitamente habilitada
app = FastAPI(
    title="Grupo JF API",
    description="API para gestão financeira e administrativa do Grupo JF.",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)

# Middleware para logging de requests em fatura-avulsa
@app.middleware("http")
async def log_requests(request, call_next):
    if request.url.path.startswith("/api/fatura-avulsa"):
        logger.info(f"[REQUEST] {request.method} {request.url.path}")
        if request.method == "POST":
            try:
                # Read the body
                body = await request.body()
                logger.info(f"[REQUEST BODY] {body.decode()}")
                # Recreate the request to pass the body along
                import json
                from starlette.datastructures import Headers
                from starlette.requests import Request
                
                async def receive():
                    return {"type": "http.request", "body": body}
                
                request = Request(request.scope, receive=receive)
            except Exception as e:
                logger.error(f"[REQUEST] Error reading body: {e}")
    
    response = await call_next(request)
    
    if request.url.path.startswith("/api/fatura-avulsa"):
        logger.info(f"[RESPONSE] {request.method} {request.url.path} - Status: {response.status_code}")
    
    return response

# 2. Middleware de API Key (para endpoints públicos)
app.add_middleware(APIKeyMiddleware)
logger.info("🔑 Middleware de API Key adicionado à aplicação")

# 3. Middleware de autenticação (para endpoints privados)
app.add_middleware(AuthMiddleware)
logger.info("🔐 Middleware de autenticação adicionado à aplicação")

# Adicionado por último para envolver também respostas geradas diretamente
# pelos middlewares de autenticação e API Key (por exemplo, erros 401).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Certifique-se de que a seção components existe
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    
    # Preservar os esquemas existentes se houver 
    if "schemas" not in openapi_schema["components"]:
        openapi_schema["components"]["schemas"] = {}
    
    # Adicionar o esquema de segurança - não sobrescrever a seção components inteira
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}
    
    # Configuração de segurança para JWT
    openapi_schema["components"]["securitySchemes"]["bearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Insira seu token JWT com o prefixo 'Bearer'"
    }
    
    # Aplicar segurança globalmente - todos endpoints requerem autenticação
    openapi_schema["security"] = [{"bearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# --- Configuração de Arquivos Estáticos ---
# Montar diretório estático para servir arquivos públicos (logos, etc.)
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent.parent / "static"), name="static")

# --- Inclusão dos Routers ---

# Rotas existentes com prefixo /api
app.include_router(users.router, prefix="/api")
app.include_router(boletos.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(transacoes.router, prefix="/api")
app.include_router(pacientes.router, prefix="/api")
app.include_router(contratos.router, prefix="/api")

# Novas rotas com prefixo /api
app.include_router(produto.router, prefix="/api")
app.include_router(dentista.router, prefix="/api")
app.include_router(forma_pagamento.router, prefix="/api")
app.include_router(regra_desconto.router, prefix="/api")
app.include_router(odontograma.router, prefix="/api")
app.include_router(venda.router, prefix="/api")
app.include_router(venda_parcela.router, prefix="/api")
app.include_router(solicitacao_desconto.router, prefix="/api")
app.include_router(venda_parcela.router)
app.include_router(tipos_odontograma.router, prefix="/api")
app.include_router(parcelas_contrato.router, prefix="/api")
app.include_router(cargos.router, prefix="/api")
app.include_router(regras_split.router, prefix="/api")
app.include_router(carne.router, prefix="/api")  # Adicionar o router de carnês
app.include_router(empresas.router, prefix="/api")
app.include_router(empresa_regras_split.router)
app.include_router(configuracao_split.router)
app.include_router(pacientes_integrados.router, prefix="/api")  # Router de integração com Delta
app.include_router(digital_contracts_router, prefix="/api")
app.include_router(fatura_avulsa.router, prefix="/api")
app.include_router(fatura_recorrente.router, prefix="/api")

# Rota de webhook isolada em /webhook (mantida) 
app.include_router(bempaggo_webhooks.router)
app.include_router(carne_webhook.router)
app.include_router(fatura_avulsa_webhook.router)
app.include_router(fatura_recorrente_webhook.router)

# Incluir novos routers
app.include_router(dependentes.router, prefix="/api")
app.include_router(funcoes_dentista.router, prefix="/api")

# Incluir router público (sem prefixo /api para ser acessível publicamente)
app.include_router(public_registration.router)

# Incluir routers da anamnese digital
app.include_router(anamnese_router, prefix="/api")
app.include_router(anamnese_public_router, prefix="/api")  # Com prefixo /api para padronização

# Incluir routers de pré-venda e webhook de entrada
app.include_router(pre_venda.router, prefix="/api")
app.include_router(webhook_entrada.router, prefix="/api")

# Incluir router de relatório de caixa
app.include_router(relatorio_caixa.router, prefix="/api")

# Incluir router de relatório de vendas completo
app.include_router(relatorio_vendas.router, prefix="/api")

# Incluir router de listagem de vendas
app.include_router(vendas_list.router)
app.include_router(relatorio_splits_seller.router, prefix="/api")
app.include_router(relatorio_splits_seller_v2.router, prefix="/api")
app.include_router(relatorio_splits_seller_v3.router, prefix="/api")
app.include_router(relatorio_splits_seller_v5.router, prefix="/api")
app.include_router(relatorio_splits_seller_v6.router, prefix="/api")

# Incluir router público de relatório de vendas
app.include_router(relatorio_vendas_publico.router)

# Incluir router público de contratos digitais
app.include_router(digital_contracts_public_router)

# Incluir router de teste de selfie (público)
app.include_router(selfie_test_router)

# Incluir router do caixa diário
app.include_router(caixa_diario.router, prefix="/api")

# Incluir router de parcelas unificadas
app.include_router(parcelas_router.router)

# Incluir router do dashboard de vendas
app.include_router(dashboard_vendas.router)

# Incluir router de gestão financeira de pagamentos
app.include_router(financeiro_pagamentos.router, prefix="/api")
app.include_router(caixa_firebird.router, prefix="/api")

# Rota Raiz
@app.get("/", tags=["Root"])
def home():
    """ Rota raiz da API """
    return {
        "message": "Bem-vindo à API do Grupo JF!",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }
