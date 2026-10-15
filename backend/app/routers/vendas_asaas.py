"""API privada e independente do novo fluxo de vendas Asaas."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.asaas_sdk.exceptions import (
    AsaasConfigurationError,
    AsaasIntegrationError,
)
from app.asaas_sales_sdk import AsaasSalesSDK
from app.services.asaas_account_approval_service import (
    AsaasApprovalTarget,
    require_approved_targets,
)
from app.services.asaas_receiver_identity_provider import receiver_identity_provider_for_environment
from app.services.asaas_split_service import (
    _load_asaas_domain_rules,
    build_asaas_split_for_sale,
    to_asaas_payload,
)
from app.models.vendas_asaas import (
    AsaasCarneSaleCreate,
    AsaasCarneSaleCreated,
    AsaasCheckoutLink,
    AsaasCreditCardRecurringSaleCreate,
    AsaasCustomerReadiness,
    AsaasCustomerReadinessRequest,
    AsaasEntryCreate,
    AsaasEntryCreated,
    AsaasEntryStatus,
    AsaasPixAutomaticSaleCreate,
    AsaasPixQrCode,
    AsaasRecurringSaleCreateBase,
    AsaasSaleCapabilities,
    AsaasSaleIntegrationStatus,
    AsaasSalePaymentMethodCapability,
    AsaasSubaccountCreateRequest,
    AsaasSubaccountListItem,
    AsaasSubaccountListResponse,
    AsaasSubaccountProvisionResult,
)
from app.services.asaas_entry_service import (
    AsaasEntryConflictError,
    AsaasEntryError,
    AsaasEntryNotFoundError,
    create_asaas_entry,
    get_asaas_entry_checkout_url,
    get_asaas_entry_status,
)
from app.services.asaas_customer_readiness_service import (
    AsaasCustomerReadinessConflictError,
    AsaasCustomerReadinessError,
    AsaasCustomerReadinessNotFoundError,
    prepare_asaas_customer_readiness,
)
from app.services.asaas_sale_creation_service import (
    AsaasSaleCreationConflictError,
    AsaasSaleCreationError,
    AsaasSaleCreationNotFoundError,
    CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
    PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
    PAYMENT_METHOD_CODE,
    create_asaas_carne_sale,
    get_asaas_sale_status,
    get_payment_book_target,
    get_remote_action_target,
)
from app.services.asaas_account_provisioning_service import (
    provision_asaas_account_for_user,
)
from app.services.asaas_sale_database import (
    AsaasSaleDatabaseConfigError,
    DatabaseConnection,
)
from app.services.asaas_sale_integration_service import (
    AsaasSaleConflictError,
    AsaasSaleDataError,
    AsaasSaleIdentityPendingError,
)
from app.security.auth_dependencies import get_current_user
from app.services.asaas_sales_config import (
    ASAAS_SALES_PAYMENT_METHODS,
    AsaasSalesConfigError,
    is_asaas_sales_enabled,
    is_asaas_sales_carne_enabled,
    is_asaas_sales_credit_card_recurring_enabled,
    is_asaas_sales_entry_enabled,
    is_asaas_sales_entry_split_policy_approved,
    is_asaas_sales_payment_method_enabled,
    is_asaas_sales_payment_method_environment_enabled,
    is_asaas_sales_pix_automatic_enabled,
    is_asaas_sales_pix_automatic_split_policy_approved,
    is_asaas_sales_subaccount_provisioning_enabled,
    resolve_asaas_sales_unit,
    validate_enabled_asaas_sales_account_isolation,
)
from app.services.asaas_sales_preflight import (
    AsaasSalesPreflightError,
    is_asaas_sales_pf_user_excluded,
)
from app.workers.asaas_sale_celery_app import ASAAS_SALE_QUEUE
from app.workers.asaas_sale_integration_tasks import dispatch_asaas_sale_jobs


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vendas-asaas", tags=["vendas-asaas"])

IMMEDIATE_DISPATCH_EXPIRES_SECONDS = 12

_ALLOWED_ROLES = frozenset(
    {
        "master",
        "administrador",
        "comercial",
        "financeiro",
        "dentista",
        "gerente",
        "supervisor",
        "crc",
    }
)

# Roles autorizadas a provisionar/consultar subcontas Asaas (PF). Subset
# restrito do _ALLOWED_ROLES: so administracao/financeiro podem criar contas.
_SUBACCOUNT_ROLES = frozenset({"master", "administrador", "financeiro"})

# cargo_id dos usuarios elegiveis a subconta PF no rollout inicial (3 e 4).
_SUBACCOUNT_ELEGIBLE_CARGO_IDS = (3, 4)
_SUBACCOUNT_LIST_LIMIT_MAX = 100


@router.get("/capabilities", response_model=AsaasSaleCapabilities)
def get_asaas_sale_capabilities(
    unidade: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> AsaasSaleCapabilities:
    """Informa rollout sem iniciar venda; a prova de conta é autenticada."""
    _require_sale_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"),
            unidade,
        )
        enabled = is_asaas_sales_enabled(resolved_unit)
        method_enabled = {
            code: is_asaas_sales_payment_method_enabled(resolved_unit, code)
            for code, _label in ASAAS_SALES_PAYMENT_METHODS
        }
        method_available = {
            code: bool(
                method_enabled[code]
                and code != PIX_AUTOMATIC_PAYMENT_METHOD_CODE
            )
            for code, _label in ASAAS_SALES_PAYMENT_METHODS
        }
    except AsaasSalesConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None

    configured = False
    if enabled:
        try:
            validate_enabled_asaas_sales_account_isolation()
            with AsaasSalesSDK.for_unit(resolved_unit) as sdk:
                account_ready = any(
                    is_asaas_sales_payment_method_environment_enabled(
                        resolved_unit,
                        sdk.account.environment,
                        code,
                    )
                    for code, _label in ASAAS_SALES_PAYMENT_METHODS
                    if code != PIX_AUTOMATIC_PAYMENT_METHOD_CODE
                )
                approval_ready = _has_approved_account_evidence(
                    unidade=resolved_unit,
                    environment=sdk.account.environment,
                    account_id=sdk.account.account_id,
                    wallet_id=sdk.account.account_wallet_id,
                    evidence_reader=sdk.approval_evidence_reader,
                )
            configured = account_ready and approval_ready
            if configured:
                configured = _is_carne_database_ready()
        except (
            AsaasConfigurationError,
            AsaasSaleDatabaseConfigError,
            AsaasSalesConfigError,
        ):
            logger.error(
                "Configuracao da conta de vendas Asaas incompleta. unidade=%s",
                resolved_unit,
            )

    accepting_sales = bool(
        enabled and configured and any(method_available.values())
    )
    return AsaasSaleCapabilities(
        unidade=resolved_unit,
        enabled=enabled,
        configured=configured,
        accepting_sales=accepting_sales,
        payment_methods=[
            AsaasSalePaymentMethodCapability(
                code=code,
                label=label,
                available=bool(configured and method_available[code]),
            )
            for code, label in ASAAS_SALES_PAYMENT_METHODS
        ],
    )


def _has_approved_account_evidence(
    *,
    unidade: str,
    environment: str,
    account_id: str,
    wallet_id: str,
    evidence_reader: Callable,
) -> bool:
    """Só libera cobrança quando o leitor autenticado provar a identidade."""
    target = AsaasApprovalTarget(
        unidade=unidade,
        environment=environment,
        account_id=account_id,
        wallet_id=wallet_id,
    )
    return require_approved_targets((target,), evidence_reader)


@router.post(
    "/clientes/prontidao",
    response_model=AsaasCustomerReadiness,
)
def prepare_asaas_customer(
    request: AsaasCustomerReadinessRequest,
    current_user: dict = Depends(get_current_user),
) -> AsaasCustomerReadiness:
    """Solicita a identidade Sandbox sem chamar o Asaas no request."""
    _require_sale_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"),
            request.unidade,
        )
        if not is_asaas_sales_enabled(resolved_unit):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Vendas Asaas indisponíveis para esta unidade.",
            )
        validate_enabled_asaas_sales_account_isolation()
        with AsaasSalesSDK.for_unit(resolved_unit) as sdk:
            account = sdk.account
        if account.environment != "sandbox":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Prontidão de cliente disponível somente no Sandbox.",
            )
        with DatabaseConnection() as conn:
            readiness = prepare_asaas_customer_readiness(
                conn.cursor(),
                paciente_id=request.paciente_id,
                unidade=resolved_unit,
                environment=account.environment,
                account_wallet_id=account.account_wallet_id,
            )
    except HTTPException:
        raise
    except AsaasCustomerReadinessNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.code) from None
    except AsaasCustomerReadinessConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from None
    except AsaasCustomerReadinessError as exc:
        raise HTTPException(status_code=422, detail=exc.code) from None
    except (
        AsaasConfigurationError,
        AsaasSaleDatabaseConfigError,
        AsaasSalesConfigError,
    ) as exc:
        logger.error(
            "Infraestrutura de prontidao Asaas indisponivel. "
            "unidade=%s error_type=%s",
            locals().get("resolved_unit", "indefinida"),
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Infraestrutura de prontidão Asaas indisponível.",
        ) from None

    return AsaasCustomerReadiness(status=readiness.status)


@router.post(
    "/entradas",
    response_model=AsaasEntryCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_asaas_carne_entry(
    request: AsaasEntryCreate,
    response: Response,
    current_user: dict = Depends(get_current_user),
) -> AsaasEntryCreated:
    """Cria somente a outbox local; a cobrança nasce no worker dedicado."""
    _require_sale_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"), request.unidade
        )
        if not is_asaas_sales_entry_enabled(resolved_unit):
            raise HTTPException(
                status_code=503,
                detail="Entrada Asaas indisponível para esta unidade.",
            )
        if not is_asaas_sales_entry_split_policy_approved():
            raise HTTPException(
                status_code=503,
                detail="Entrada Asaas indisponível enquanto a política de split não for aprovada.",
            )
        if request.intent_version != 1 or request.data_vencimento_primeira_parcela is None:
            raise HTTPException(status_code=422, detail="asaas_entry_intent_version_invalid")
        if request.payment_method != "ASAAS_ENTRY_PIX":
            raise HTTPException(status_code=422, detail="asaas_entry_method_invalid")
        validate_enabled_asaas_sales_account_isolation()
        with AsaasSalesSDK.for_unit(resolved_unit) as sdk, DatabaseConnection() as conn:
            account = sdk.account
            if account.environment != "sandbox":
                raise HTTPException(
                    status_code=503,
                    detail="Entrada Asaas disponível somente no Sandbox nesta fase.",
                )
            # The issuer proof is deliberately evaluated by the service while
            # this authenticated SDK is still open, before its first INSERT.
            issuer_guard = lambda: _has_approved_account_evidence(
                unidade=account.unidade,
                environment=account.environment,
                account_id=account.account_id,
                wallet_id=account.account_wallet_id,
                evidence_reader=sdk.approval_evidence_reader,
            )
            cached_rules: list[Any] | None = None
            frozen_identities: dict[tuple[str, int], Any] | None = None

            def preview_entry_split(context: Mapping[str, Any]):
                nonlocal cached_rules, frozen_identities
                cursor = context["cursor"]
                cursor.execute(
                    "SELECT t.id FROM odontogramas o JOIN tipos_odontograma t ON LOWER(t.nome) = LOWER(o.tipo) WHERE o.id = %s AND t.ativo = TRUE LIMIT 1",
                    (context["odontograma_id"],),
                )
                type_row = cursor.fetchone()
                if type_row is None:
                    raise ValueError("tipo_odontograma_split_ausente")
                type_id = type_row["id"] if isinstance(type_row, Mapping) else type_row[0]
                if cached_rules is None:
                    cached_rules = _load_asaas_domain_rules(
                        cursor, venda_id=None, unidade=context["unidade"],
                        environment=context["environment"], tipo_odontograma_id=int(type_id),
                        dentista_id=request.dentista_id,
                        usuario_venda_id=context["usuario_venda_id"],
                    )
                provider = receiver_identity_provider_for_environment(context["environment"])
                if frozen_identities is None:
                    frozen_identities = {}
                    for rule in cached_rules:
                        kind = "pf" if rule.user_id is not None and rule.empresa_id is None else "empresa"
                        local_id = rule.user_id if kind == "pf" else rule.empresa_id
                        if type(local_id) is not int:
                            raise ValueError("identidade_recebedor_asaas_invalida")
                        identity = provider.resolve_for_new_sale(
                            kind=kind, local_id=local_id,
                            unidade=context["unidade"], environment=context["environment"],
                        )
                        frozen_identities[(kind, local_id)] = identity
                        with provider.approval_reader(identity) as reader:
                            if not _has_approved_account_evidence(
                                unidade=identity.unidade, environment=identity.environment,
                                account_id=identity.account_id, wallet_id=identity.wallet_id,
                                evidence_reader=reader,
                            ):
                                raise ValueError("asaas_account_approval_unverified")
                plan = build_asaas_split_for_sale(
                    cursor, venda_id=None, unidade=context["unidade"], environment=context["environment"],
                    tipo_odontograma_id=int(type_id), dentista_id=request.dentista_id,
                    usuario_venda_id=context["usuario_venda_id"], valor_liquido_total=context["valor_liquido_total"],
                    tem_entrada=True, contexto=context["contexto"], account_wallet_id=context["account_wallet_id"],
                    remaining_installments=context["remaining_installments"], domain_rules=cached_rules,
                    frozen_receiver_identities=frozen_identities,
                )
                return plan, to_asaas_payload(plan, context["contexto"])
            record = create_asaas_entry(
                conn.cursor(),
                client_request_id=request.client_request_id,
                intent_version=request.intent_version,
                first_due_date=request.data_vencimento_primeira_parcela,
                user_id=_current_user_id(current_user),
                paciente_id=request.paciente_id,
                dentista_id=request.dentista_id,
                odontograma_id=request.odontograma_id,
                dependente_id=request.dependente_id,
                unidade=resolved_unit,
                total_installments=request.qtd_parcelas_total,
                payment_method=request.payment_method,
                card_installments=request.card_installments,
                environment=account.environment,
                account_wallet_id=account.account_wallet_id,
                issuer_account_id=account.account_id,
                approval_guard=issuer_guard,
                split_preview=preview_entry_split,
            )
    except HTTPException:
        raise
    except AsaasEntryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.code) from None
    except AsaasEntryConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from None
    except AsaasEntryError as exc:
        raise HTTPException(status_code=422, detail=exc.code) from None
    except (
        AsaasConfigurationError,
        AsaasSaleDatabaseConfigError,
        AsaasSalesConfigError,
    ) as exc:
        logger.error(
            "Infraestrutura de entrada Asaas indisponivel. unidade=%s error_type=%s",
            locals().get("resolved_unit", "indefinida"),
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Infraestrutura de entrada Asaas indisponível.",
        ) from None
    response.headers["Cache-Control"] = "no-store"
    return AsaasEntryCreated(**record.__dict__)


@router.get("/entradas/{entry_id}", response_model=AsaasEntryStatus)
def read_asaas_entry(
    entry_id: int,
    response: Response,
    unidade: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> AsaasEntryStatus:
    _require_sale_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(current_user.get("unidade"), unidade)
        with DatabaseConnection(read_only=True) as conn:
            record = get_asaas_entry_status(
                conn.cursor(), entry_id=entry_id, unidade=resolved_unit
            )
    except (AsaasEntryError, AsaasSalesConfigError):
        raise HTTPException(status_code=404, detail="Entrada não encontrada.") from None
    except AsaasSaleDatabaseConfigError:
        raise HTTPException(status_code=503, detail="Entrada Asaas indisponível.") from None
    if record is None:
        raise HTTPException(status_code=404, detail="Entrada não encontrada.")
    response.headers["Cache-Control"] = "no-store"
    return AsaasEntryStatus(**record.__dict__)


@router.get("/entradas/{entry_id}/checkout", response_model=AsaasCheckoutLink)
def read_asaas_entry_checkout(
    entry_id: int,
    response: Response,
    unidade: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> AsaasCheckoutLink:
    _require_sale_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(current_user.get("unidade"), unidade)
        with DatabaseConnection(read_only=True) as conn:
            checkout_url = get_asaas_entry_checkout_url(
                conn.cursor(), entry_id=entry_id, unidade=resolved_unit
            )
    except (AsaasEntryError, AsaasSalesConfigError):
        raise HTTPException(status_code=404, detail="Checkout não encontrado.") from None
    except AsaasSaleDatabaseConfigError:
        raise HTTPException(status_code=503, detail="Checkout Asaas indisponível.") from None
    if not checkout_url:
        raise HTTPException(status_code=409, detail="Checkout ainda não disponível.")
    response.headers["Cache-Control"] = "no-store"
    return AsaasCheckoutLink(url=checkout_url)


@router.post(
    "/carnes",
    response_model=AsaasCarneSaleCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_asaas_carne(
    sale: AsaasCarneSaleCreate,
    current_user: dict = Depends(get_current_user),
) -> AsaasCarneSaleCreated:
    return _create_asaas_product(
        sale,
        current_user=current_user,
        payment_method=PAYMENT_METHOD_CODE,
        enabled_checker=is_asaas_sales_carne_enabled,
        label="Carnê",
    )


@router.post(
    "/pix-automatico",
    response_model=AsaasCarneSaleCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_asaas_pix_automatic(
    sale: AsaasPixAutomaticSaleCreate,
    current_user: dict = Depends(get_current_user),
) -> AsaasCarneSaleCreated:
    return _create_asaas_product(
        sale,
        current_user=current_user,
        payment_method=PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
        enabled_checker=is_asaas_sales_pix_automatic_enabled,
        label="Pix Recorrente",
    )


@router.post(
    "/cartao-recorrente",
    response_model=AsaasCarneSaleCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_asaas_credit_card_recurring(
    sale: AsaasCreditCardRecurringSaleCreate,
    current_user: dict = Depends(get_current_user),
) -> AsaasCarneSaleCreated:
    return _create_asaas_product(
        sale,
        current_user=current_user,
        payment_method=CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
        enabled_checker=is_asaas_sales_credit_card_recurring_enabled,
        label="Cartão recorrente",
    )


def _create_asaas_product(
    sale: AsaasRecurringSaleCreateBase,
    *,
    current_user: dict,
    payment_method: str,
    enabled_checker: Callable[[str], bool],
    label: str,
) -> AsaasCarneSaleCreated:
    """Cria venda e outbox sem transportar PII ao worker de vendas."""
    _require_sale_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"),
            sale.unidade,
        )
        if (
            payment_method == PIX_AUTOMATIC_PAYMENT_METHOD_CODE
            and not is_asaas_sales_pix_automatic_split_policy_approved()
        ):
            # A autorizacao inicial do Pix Automatico nao transporta o split
            # obrigatorio. Eventuais cobrancas futuras sao outro contrato e
            # ainda nao integram este fluxo.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="asaas_pix_split_nao_suportado",
            )
        user_id = _current_user_id(current_user)
        validate_enabled_asaas_sales_account_isolation()
        with AsaasSalesSDK.for_unit(resolved_unit) as sdk:
            account = sdk.account
            with DatabaseConnection() as conn:
                def preview_split(context: Mapping[str, Any]):
                    cursor = context["cursor"]
                    cursor.execute(
                        "SELECT t.id FROM odontogramas o JOIN tipos_odontograma t ON LOWER(t.nome) = LOWER(o.tipo) WHERE o.id = %s AND t.ativo = TRUE LIMIT 1",
                        (context["odontograma_id"],),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise ValueError("tipo_odontograma_split_ausente")
                    tipo_id = row["id"] if isinstance(row, Mapping) else row[0]
                    provider = receiver_identity_provider_for_environment(context["environment"])
                    plan = build_asaas_split_for_sale(
                        cursor, venda_id=None, unidade=context["unidade"], environment=context["environment"],
                        tipo_odontograma_id=int(tipo_id), dentista_id=sale.dentista_orcamentista_id,
                        usuario_venda_id=context["usuario_venda_id"], valor_liquido_total=context["valor_liquido_total"],
                        tem_entrada=context["tem_entrada"], contexto=context["contexto"],
                        account_wallet_id=context["account_wallet_id"], remaining_installments=context["remaining_installments"],
                        receiver_identity_resolver=lambda kind, local_id, unidade, environment, wallet: provider.resolve(kind=kind, local_id=local_id, unidade=unidade, environment=environment, wallet_id=wallet),
                        receiver_identity_for_new_sale_resolver=lambda kind, local_id, unidade, environment: provider.resolve_for_new_sale(kind=kind, local_id=local_id, unidade=unidade, environment=environment),
                    )
                    for item in plan.items:
                        identity = item.receiver_identity
                        if identity is None:
                            raise ValueError("identidade_recebedor_asaas_ausente")
                        with provider.approval_reader(identity) as reader:
                            if not _has_approved_account_evidence(
                                unidade=identity.unidade,
                                environment=identity.environment,
                                account_id=identity.account_id,
                                wallet_id=identity.wallet_id,
                                evidence_reader=reader,
                            ):
                                raise ValueError("asaas_account_approval_unverified")
                    return plan, to_asaas_payload(plan, context["contexto"])
                record = create_asaas_carne_sale(
                    conn.cursor(),
                    sale=sale,
                    unidade=resolved_unit,
                    user_id=user_id,
                    environment=account.environment,
                    account_wallet_id=account.account_wallet_id,
                    payment_method=payment_method,
                    approval_guard=lambda: _has_approved_account_evidence(
                        unidade=account.unidade,
                        environment=account.environment,
                        account_id=account.account_id,
                        wallet_id=account.account_wallet_id,
                        evidence_reader=sdk.approval_evidence_reader,
                    ),
                    split_preview=preview_split,
                )
    except HTTPException:
        raise
    except AsaasSaleCreationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.code) from None
    except (AsaasSaleCreationConflictError, AsaasSaleConflictError) as exc:
        code = getattr(exc, "code", str(exc))
        raise HTTPException(status_code=409, detail=code) from None
    except AsaasSaleIdentityPendingError:
        raise HTTPException(
            status_code=409,
            detail="asaas_customer_not_ready",
        ) from None
    except (AsaasSaleCreationError, AsaasSaleDataError) as exc:
        code = getattr(exc, "code", str(exc))
        raise HTTPException(status_code=422, detail=code) from None
    except (
        AsaasConfigurationError,
        AsaasSaleDatabaseConfigError,
        AsaasSalesConfigError,
    ) as exc:
        logger.error(
            "Infraestrutura de venda Asaas indisponível. unidade=%s "
            "method=%s error_type=%s",
            locals().get("resolved_unit", "indefinida"),
            payment_method,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Infraestrutura de {label} Asaas indisponível.",
        ) from None

    _request_immediate_sale_dispatch()
    return AsaasCarneSaleCreated(
        venda_id=record.venda_id,
        documento_venda=record.documento_venda,
        integration_id=record.integration_id,
        status=record.status,
        valor_liquido_total=record.valor_liquido_total,
        qtd_parcelas=record.qtd_parcelas,
        created_at=record.created_at,
    )


def _request_immediate_sale_dispatch() -> None:
    """Acelera o outbox; o beat continua como contingencia duravel."""
    try:
        dispatch_asaas_sale_jobs.apply_async(
            queue=ASAAS_SALE_QUEUE,
            expires=IMMEDIATE_DISPATCH_EXPIRES_SECONDS,
        )
    except Exception as exc:
        logger.warning(
            "Despacho imediato da venda Asaas indisponível; "
            "o agendador assumirá. error_type=%s",
            type(exc).__name__,
        )


@router.get(
    "/integracoes/{integration_id}",
    response_model=AsaasSaleIntegrationStatus,
)
def read_asaas_sale_integration(
    integration_id: int,
    unidade: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> AsaasSaleIntegrationStatus:
    _require_sale_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"),
            unidade,
        )
        with DatabaseConnection() as conn:
            record = get_asaas_sale_status(
                conn.cursor(),
                integration_id=integration_id,
                unidade=resolved_unit,
            )
    except (AsaasSalesConfigError, AsaasSaleCreationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except AsaasSaleDatabaseConfigError:
        raise HTTPException(
            status_code=503,
            detail="Infraestrutura de vendas Asaas indisponível.",
        ) from None
    if record is None:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    return AsaasSaleIntegrationStatus(**record.__dict__)


@router.get("/integracoes/{integration_id}/payment-book")
def read_asaas_sale_payment_book(
    integration_id: int,
    unidade: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> Response:
    _require_sale_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"),
            unidade,
        )
        if not is_asaas_sales_carne_enabled(resolved_unit):
            raise HTTPException(status_code=404, detail="Carnê não encontrado.")
        with DatabaseConnection() as conn:
            target = get_payment_book_target(
                conn.cursor(),
                integration_id=integration_id,
                unidade=resolved_unit,
            )
        if target is None:
            raise HTTPException(status_code=404, detail="Carnê não encontrado.")
        with AsaasSalesSDK.for_unit(target.unidade) as sdk:
            if (
                sdk.account.environment != target.environment
                or sdk.account.account_wallet_id != target.account_wallet_id
            ):
                raise HTTPException(status_code=404, detail="Carnê não encontrado.")
            pdf = sdk.installments.get_payment_book(
                target.installment_id,
                accept="application/pdf",
            )
    except HTTPException:
        raise
    except AsaasIntegrationError as exc:
        logger.error(
            "Falha ao consultar payment book Asaas. integration_id=%s error_type=%s",
            integration_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Não foi possível consultar o Carnê no Asaas.",
        ) from None
    except (
        AsaasSaleCreationError,
        AsaasSaleDatabaseConfigError,
        AsaasSalesConfigError,
    ):
        raise HTTPException(status_code=404, detail="Carnê não encontrado.") from None
    if not isinstance(pdf, bytes):
        raise HTTPException(status_code=502, detail="Resposta de Carnê inválida.")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="carne-{integration_id}.pdf"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/integracoes/{integration_id}/pix-qr",
    response_model=AsaasPixQrCode,
)
def read_asaas_pix_qr_code(
    integration_id: int,
    response: Response,
    unidade: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> AsaasPixQrCode:
    _require_sale_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"),
            unidade,
        )
        if not is_asaas_sales_pix_automatic_enabled(resolved_unit):
            raise HTTPException(status_code=404, detail="QR Pix não encontrado.")
        with DatabaseConnection() as conn:
            target = get_remote_action_target(
                conn.cursor(),
                integration_id=integration_id,
                unidade=resolved_unit,
                payment_method=PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                resource_type="pix_authorization",
            )
        if target is None:
            raise HTTPException(status_code=404, detail="QR Pix não encontrado.")
        with AsaasSalesSDK.for_unit(target.unidade) as sdk:
            if (
                target.environment != "sandbox"
                or sdk.account.environment != target.environment
                or sdk.account.account_wallet_id != target.account_wallet_id
            ):
                raise HTTPException(status_code=404, detail="QR Pix não encontrado.")
            authorization = sdk.recurring.get_pix_authorization(
                target.resource_id
            )
    except HTTPException:
        raise
    except AsaasIntegrationError as exc:
        logger.error(
            "Falha ao consultar QR Pix Asaas. integration_id=%s error_type=%s",
            integration_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Não foi possível consultar o QR Pix no Asaas.",
        ) from None
    except (
        AsaasSaleCreationError,
        AsaasSaleDatabaseConfigError,
        AsaasSalesConfigError,
    ):
        raise HTTPException(status_code=404, detail="QR Pix não encontrado.") from None
    if not authorization["qr_payload"]:
        raise HTTPException(status_code=409, detail="QR Pix ainda não disponível.")
    response.headers["Cache-Control"] = "no-store"
    return AsaasPixQrCode(
        payload=authorization["qr_payload"],
        expires_at=authorization["expires_at"],
    )


@router.get(
    "/integracoes/{integration_id}/checkout",
    response_model=AsaasCheckoutLink,
)
def read_asaas_recurring_checkout(
    integration_id: int,
    response: Response,
    unidade: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> AsaasCheckoutLink:
    _require_sale_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"),
            unidade,
        )
        if not is_asaas_sales_credit_card_recurring_enabled(resolved_unit):
            raise HTTPException(status_code=404, detail="Checkout não encontrado.")
        with DatabaseConnection() as conn:
            target = get_remote_action_target(
                conn.cursor(),
                integration_id=integration_id,
                unidade=resolved_unit,
                payment_method=CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
                resource_type="checkout",
            )
        if target is None:
            raise HTTPException(status_code=404, detail="Checkout não encontrado.")
        with AsaasSalesSDK.for_unit(target.unidade) as sdk:
            if (
                sdk.account.environment != target.environment
                or sdk.account.account_wallet_id != target.account_wallet_id
            ):
                raise HTTPException(status_code=404, detail="Checkout não encontrado.")
            checkout = sdk.recurring.get_checkout(target.resource_id)
    except HTTPException:
        raise
    except AsaasIntegrationError as exc:
        logger.error(
            "Falha ao consultar Checkout Asaas. integration_id=%s error_type=%s",
            integration_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Não foi possível consultar o Checkout no Asaas.",
        ) from None
    except (
        AsaasSaleCreationError,
        AsaasSaleDatabaseConfigError,
        AsaasSalesConfigError,
    ):
        raise HTTPException(status_code=404, detail="Checkout não encontrado.") from None
    response.headers["Cache-Control"] = "no-store"
    return AsaasCheckoutLink(url=checkout["link"])


@router.post(
    "/subcontas",
    response_model=AsaasSubaccountProvisionResult,
    status_code=status.HTTP_201_CREATED,
)
def create_asaas_subaccount(
    request: AsaasSubaccountCreateRequest,
    unidade: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> AsaasSubaccountProvisionResult:
    """Provisiona (idempotente) uma subconta Asaas PF para um usuario."""
    _require_subaccount_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"),
            unidade,
        )
    except AsaasSalesConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None

    try:
        if not is_asaas_sales_subaccount_provisioning_enabled(resolved_unit):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Subcontas Asaas indisponíveis para esta unidade.",
            )
        if is_asaas_sales_pf_user_excluded(
            request.user_id,
            resolved_unit,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Usuário temporariamente excluído do provisionamento "
                    "de subconta Asaas."
                ),
            )
        validate_enabled_asaas_sales_account_isolation()
        result = provision_asaas_account_for_user(
            request.user_id,
            expected_unit=resolved_unit,
        )
    except HTTPException:
        raise
    except (AsaasSalesConfigError, AsaasSalesPreflightError) as exc:
        logger.error(
            "Configuracao de subconta Asaas indisponivel. error_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Infraestrutura de subcontas Asaas indisponível.",
        ) from None
    except AsaasSaleDatabaseConfigError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Infraestrutura de subcontas Asaas indisponível.",
        ) from None

    http_status = _provision_status_to_http(result.status)
    if http_status == status.HTTP_422_UNPROCESSABLE_ENTITY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.mensagem or "validacao rejeitada pelo Asaas",
        )
    if http_status == status.HTTP_503_SERVICE_UNAVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.mensagem or "infraestrutura de subcontas Asaas indisponivel",
        )
    if http_status == status.HTTP_502_BAD_GATEWAY:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.mensagem or "falha de integracao com o Asaas",
        )
    return AsaasSubaccountProvisionResult(
        status=result.status,
        wallet_id=result.wallet_id,
        account_id=result.account_id,
        integration_status=result.integration_status,
        mensagem=result.mensagem,
        tem_wallet=bool(result.wallet_id),
    )


@router.get("/subcontas", response_model=AsaasSubaccountListResponse)
def list_asaas_subaccounts(
    response: Response,
    limit: int = Query(default=20, ge=1, le=_SUBACCOUNT_LIST_LIMIT_MAX),
    offset: int = Query(default=0, ge=0),
    unidade: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> AsaasSubaccountListResponse:
    """Lista usuarios elegiveis (cargo_id IN 3,4) com flags de integracao."""
    _require_subaccount_role(current_user)
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"),
            unidade,
        )
        with DatabaseConnection(read_only=True) as conn:
            rows = _list_eligible_subaccounts(
                conn.cursor(),
                unidade=resolved_unit,
                limit=limit,
                offset=offset,
            )
    except AsaasSalesConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except AsaasSaleDatabaseConfigError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Infraestrutura de subcontas Asaas indisponível.",
        ) from None
    response.headers["Cache-Control"] = "no-store"
    return AsaasSubaccountListResponse(
        data=[
            AsaasSubaccountListItem(
                user_id=row["user_id"],
                nome=row["nome"],
                cargo_id=row["cargo_id"],
                unidade=row["unidade"],
                tem_wallet=row["tem_wallet"],
                integration_status=row["integration_status"],
            )
            for row in rows
        ],
        total=len(rows),
    )


@router.get(
    "/subcontas/{user_id}",
    response_model=AsaasSubaccountProvisionResult,
)
def read_asaas_subaccount(
    user_id: int,
    response: Response,
    unidade: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> AsaasSubaccountProvisionResult:
    """Retorna o status de integracao de subconta de um usuario (somente leitura)."""
    _require_subaccount_role(current_user)
    if user_id <= 0:
        raise HTTPException(status_code=404, detail="Subconta não encontrada.")
    try:
        resolved_unit = resolve_asaas_sales_unit(
            current_user.get("unidade"),
            unidade,
        )
        with DatabaseConnection(read_only=True) as conn:
            row = _load_subaccount_status(
                conn.cursor(),
                user_id=user_id,
                unidade=resolved_unit,
            )
    except AsaasSalesConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except AsaasSaleDatabaseConfigError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Infraestrutura de subcontas Asaas indisponível.",
        ) from None
    if row is None:
        raise HTTPException(status_code=404, detail="Subconta não encontrada.")
    response.headers["Cache-Control"] = "no-store"
    integration_status = row["asaas_integration_status"]
    response_status = (
        integration_status
        if integration_status
        in {"erro_kyc", "erro_validacao", "erro_integracao"}
        else ("existente" if row["tem_wallet"] else "erro_validacao")
    )
    return AsaasSubaccountProvisionResult(
        status=response_status,
        wallet_id=row["asaas_wallet_id"],
        account_id=row["asaas_account_id"],
        integration_status=row["asaas_integration_status"],
        mensagem=None,
        tem_wallet=row["tem_wallet"],
    )


def _provision_status_to_http(
    provision_status: str,
) -> int:
    """Mapeia o ProvisionResult.status para um codigo HTTP de saida."""
    if provision_status in {"sucesso", "existente"}:
        return status.HTTP_201_CREATED
    if provision_status in {"erro_kyc", "erro_validacao"}:
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    if provision_status == "erro_integracao":
        return status.HTTP_502_BAD_GATEWAY
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _list_eligible_subaccounts(
    cursor: Any,
    *,
    unidade: str,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT
            id AS user_id,
            nome,
            cargo_id,
            unidade,
            asaas_wallet_id,
            asaas_integration_status
        FROM users
        WHERE cargo_id IN %s
          AND unidade = %s
          AND status_aprovacao = 'aprovado'
          AND LENGTH(
                REGEXP_REPLACE(
                    COALESCE(cpf, ''),
                    '[^0-9]',
                    '',
                    'g'
                )
              ) = 11
        ORDER BY id
        LIMIT %s
        OFFSET %s
        """,
        (
            tuple(_SUBACCOUNT_ELEGIBLE_CARGO_IDS),
            unidade,
            limit,
            offset,
        ),
    )
    rows = cursor.fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            user_id = row.get("user_id")
            nome = row.get("nome")
            cargo_id = row.get("cargo_id")
            unit_value = row.get("unidade")
            wallet_id = row.get("asaas_wallet_id")
            integration_status = row.get("asaas_integration_status")
        else:
            user_id, nome, cargo_id, unit_value, wallet_id, integration_status = row
        result.append(
            {
                "user_id": user_id,
                "nome": str(nome or ""),
                "cargo_id": cargo_id,
                "unidade": str(unit_value or unidade),
                "tem_wallet": bool(
                    isinstance(wallet_id, str) and wallet_id.strip()
                ),
                "integration_status": (
                    str(integration_status).strip()
                    if isinstance(integration_status, str)
                    and integration_status.strip()
                    else None
                ),
            }
        )
    return result


def _load_subaccount_status(
    cursor: Any,
    *,
    user_id: int,
    unidade: str,
) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT
            asaas_wallet_id,
            asaas_account_id,
            asaas_integration_status
        FROM users
        WHERE id = %s
          AND unidade = %s
          AND cargo_id IN %s
          AND status_aprovacao = 'aprovado'
          AND LENGTH(
                REGEXP_REPLACE(
                    COALESCE(cpf, ''),
                    '[^0-9]',
                    '',
                    'g'
                )
              ) = 11
        LIMIT 1
        """,
        (user_id, unidade, tuple(_SUBACCOUNT_ELEGIBLE_CARGO_IDS)),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, Mapping):
        wallet_id = row.get("asaas_wallet_id")
        account_id = row.get("asaas_account_id")
        integration_status = row.get("asaas_integration_status")
    else:
        wallet_id, account_id, integration_status = row
    has_wallet = isinstance(wallet_id, str) and bool(wallet_id.strip())
    return {
        "asaas_wallet_id": wallet_id.strip() if has_wallet else None,
        "asaas_account_id": (
            str(account_id).strip()
            if isinstance(account_id, str) and account_id.strip()
            else None
        ),
        "asaas_integration_status": (
            str(integration_status).strip()
            if isinstance(integration_status, str)
            and integration_status.strip()
            else None
        ),
        "tem_wallet": has_wallet,
    }


def _require_sale_role(current_user: dict) -> None:
    role = str(current_user.get("role") or "").strip().casefold()
    if role not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem permissão para vendas Asaas.",
        )


def _require_subaccount_role(current_user: dict) -> None:
    role = str(current_user.get("role") or "").strip().casefold()
    if role not in _SUBACCOUNT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem permissão para gerenciar subcontas Asaas.",
        )


def _current_user_id(current_user: dict) -> int:
    value = current_user.get("user_id")
    if isinstance(value, bool):
        value = None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = 0
    if normalized <= 0:
        raise HTTPException(status_code=401, detail="Usuário autenticado inválido.")
    return normalized


def _is_carne_database_ready() -> bool:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                to_regclass('asaas_sale_payment_links') IS NOT NULL
                AND to_regclass('asaas_sale_items') IS NOT NULL
                AND to_regclass('asaas_sale_discount_rules') IS NOT NULL
                AND to_regclass('asaas_entry_integrations') IS NOT NULL
                AND to_regclass('asaas_entry_jobs') IS NOT NULL
            """
        )
        row = cursor.fetchone()
        return bool(row and row[0])
