"""Configuracao fail-closed do fluxo independente de vendas Asaas."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import unicodedata
from collections.abc import Iterable
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID


SUPPORTED_ASAAS_SALES_UNITS = (
    "Nova Iguaçu 1",
    "São João de Meriti",
    "Vilar dos Teles",
)

ASAAS_SALES_PAYMENT_METHODS = (
    ("ASAAS_BOLETO_INSTALLMENT", "Carnê"),
    ("ASAAS_PIX_AUTOMATIC", "Pix Recorrente"),
    ("ASAAS_CREDIT_CARD_RECURRENT", "Cartão de crédito recorrente"),
)

GLOBAL_UNIT_ALIASES = frozenset(
    {
        "todas unidades",
        "todas as unidades",
        "todas",
    }
)

_UNIT_ENV_ALIASES = {
    "Nova Iguaçu 1": ("NOVA_IGUACU_1",),
    "São João de Meriti": ("SAO_JOAO_DE_MERITI",),
    "Vilar dos Teles": ("VILAR", "VILAR_DOS_TELES"),
}

_PRODUCTION_ENVIRONMENTS = frozenset({"prod", "production"})
_NON_PRODUCTION_ENVIRONMENTS = frozenset(
    {"dev", "development", "sandbox", "staging", "test", "testing"}
)
_WEBHOOK_TOKEN_PLACEHOLDERS = frozenset(
    {
        "change-me",
        "changeme",
        "placeholder",
        "secret",
        "webhook-secret",
    }
)
_REPEATED_TOKEN_CHARACTER_PATTERN = re.compile(r"([A-Za-z0-9])\1{3}")
_SEQUENTIAL_DIGITS = (
    "01234",
    "12345",
    "23456",
    "34567",
    "45678",
    "56789",
    "98765",
    "87654",
    "76543",
    "65432",
    "54321",
    "43210",
    "09876",
)


class AsaasSalesConfigError(ValueError):
    """Configuracao ausente, ambigua ou fora do rollout de vendas Asaas."""


def unit_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.casefold()).strip("_")


_UNIT_BY_SLUG = {
    unit_slug(unit): unit for unit in SUPPORTED_ASAAS_SALES_UNITS
}
_UNIT_BY_SLUG.update(
    {
        "ni1": "Nova Iguaçu 1",
        "nova_iguacu": "Nova Iguaçu 1",
        "sjm": "São João de Meriti",
        "vilar": "Vilar dos Teles",
        "odonto_company_nova_iguacu_1": "Nova Iguaçu 1",
        "odontocompany_nova_iguacu_1": "Nova Iguaçu 1",
        "odonto_company_sao_joao_de_meriti": "São João de Meriti",
        "odontocompany_sao_joao_de_meriti": "São João de Meriti",
        "odonto_company_vilar_dos_teles": "Vilar dos Teles",
        "odontocompany_vilar_dos_teles": "Vilar dos Teles",
    }
)


def canonicalize_asaas_sales_unit(value: Optional[str]) -> Optional[str]:
    """Normaliza somente as unidades autorizaveis no rollout inicial."""
    raw = str(value or "").strip()
    if not raw or raw.casefold() in GLOBAL_UNIT_ALIASES:
        return None
    return _UNIT_BY_SLUG.get(unit_slug(raw))


def is_asaas_sandbox_ni_odontogram_type_available(
    unidade: Optional[str],
    environment: Optional[str],
    tipo_odontograma_id: object,
) -> bool:
    """Aplica a indisponibilidade aprovada, sem ampliar o rollout Asaas.

    Somente Particular (1) e Ortodontia (2) não podem iniciar novas vendas
    no Sandbox da Nova Iguaçu 1. A política não depende de variáveis de
    ambiente para não poder alterar produção ou outras unidades por engano.
    """
    return not (
        canonicalize_asaas_sales_unit(unidade) == "Nova Iguaçu 1"
        and str(environment or "").strip().casefold() == "sandbox"
        and type(tipo_odontograma_id) is int
        and tipo_odontograma_id in {1, 2}
    )


def resolve_asaas_sales_unit(
    authenticated_unit: Optional[str],
    requested_unit: Optional[str] = None,
) -> str:
    """Resolve a unidade sem aceitar troca de clinica pelo payload."""
    authenticated = canonicalize_asaas_sales_unit(authenticated_unit)
    if authenticated:
        return authenticated

    raw_authenticated = str(authenticated_unit or "").strip().casefold()
    if raw_authenticated not in GLOBAL_UNIT_ALIASES:
        raise AsaasSalesConfigError(
            "Unidade do usuário ausente ou não habilitada para vendas Asaas."
        )

    requested = canonicalize_asaas_sales_unit(requested_unit)
    if not requested:
        raise AsaasSalesConfigError(
            "Usuários de todas as unidades devem selecionar NI1, SJM ou Vilar."
        )
    return requested


def _get_enabled_units(variable_name: str) -> frozenset[str]:
    raw = os.getenv(variable_name, "")
    enabled: set[str] = set()
    invalid: list[str] = []

    for item in raw.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        canonical = canonicalize_asaas_sales_unit(candidate)
        if canonical:
            enabled.add(canonical)
        else:
            invalid.append(candidate)

    if invalid:
        raise AsaasSalesConfigError(
            f"{variable_name} contém unidade não reconhecida."
        )
    return frozenset(enabled)


def get_enabled_asaas_sales_units() -> frozenset[str]:
    """Le a allowlist. Vazio mantem o fluxo de vendas desligado."""
    return _get_enabled_units("ASAAS_SALES_ENABLED_UNITS")


def is_asaas_sales_enabled(unidade: str) -> bool:
    canonical = canonicalize_asaas_sales_unit(unidade)
    return bool(canonical and canonical in get_enabled_asaas_sales_units())


def is_asaas_sales_production_profile_enabled() -> bool:
    """Exige uma liberação global explícita antes de qualquer venda em produção."""
    raw = str(os.getenv("ASAAS_SALES_PRODUCTION_PROFILE_ENABLED", "")).strip().casefold()
    if raw in {"", "false"}:
        return False
    if raw == "true":
        return True
    raise AsaasSalesConfigError(
        "ASAAS_SALES_PRODUCTION_PROFILE_ENABLED deve ser true ou false."
    )


def get_enabled_asaas_sales_production_units() -> frozenset[str]:
    """Allowlist por unidade do perfil de produção, desligada por padrão."""
    units = _get_enabled_units("ASAAS_SALES_PRODUCTION_ENABLED_UNITS")
    if not is_asaas_sales_production_profile_enabled():
        return frozenset()
    if not units.issubset(get_enabled_asaas_sales_units()):
        raise AsaasSalesConfigError(
            "O perfil de produção deve ser subconjunto de ASAAS_SALES_ENABLED_UNITS."
        )
    return units


def _get_enabled_production_method_units(
    variable_name: str,
    method_label: str,
) -> frozenset[str]:
    units = _get_enabled_units(variable_name)
    if not is_asaas_sales_production_profile_enabled():
        return frozenset()
    if not units.issubset(get_enabled_asaas_sales_production_units()):
        raise AsaasSalesConfigError(
            f"O perfil de produção de {method_label} deve ser subconjunto das unidades de produção."
        )
    return units


def get_enabled_asaas_sales_production_carne_units() -> frozenset[str]:
    return _get_enabled_production_method_units(
        "ASAAS_SALES_PRODUCTION_CARNE_ENABLED_UNITS", "Carnê Asaas"
    )


def get_enabled_asaas_sales_production_credit_card_recurring_units() -> frozenset[str]:
    return _get_enabled_production_method_units(
        "ASAAS_SALES_PRODUCTION_CREDIT_CARD_RECURRENT_ENABLED_UNITS",
        "Cartão recorrente Asaas",
    )


def get_enabled_asaas_sales_subaccount_provisioning_units() -> frozenset[str]:
    """Allowlist Sandbox independente para preparar subcontas antes das vendas."""
    enabled = _get_enabled_units(
        "ASAAS_SALES_SUBACCOUNT_PROVISIONING_ENABLED_UNITS"
    )
    application_environment = str(os.getenv("ENVIRONMENT", "")).strip().casefold()
    asaas_environment = str(
        os.getenv("ASAAS_ENVIRONMENT", "")
    ).strip().casefold()
    if enabled and (
        application_environment not in _NON_PRODUCTION_ENVIRONMENTS
        or asaas_environment != "sandbox"
    ):
        raise AsaasSalesConfigError(
            "O provisionamento de subcontas desta fase só pode ser habilitado "
            "no Sandbox."
        )
    return enabled


def is_asaas_sales_subaccount_provisioning_enabled(unidade: str) -> bool:
    canonical = canonicalize_asaas_sales_unit(unidade)
    return bool(
        canonical
        and canonical
        in get_enabled_asaas_sales_subaccount_provisioning_units()
    )


def get_asaas_sales_operational_account_units() -> frozenset[str]:
    """Contas que precisam permanecer isoladas, mesmo antes de venderem."""
    return frozenset(
        get_enabled_asaas_sales_units()
        | get_enabled_asaas_sales_subaccount_provisioning_units()
    )


def get_enabled_asaas_sales_carne_units() -> frozenset[str]:
    """Habilita o Carnê apenas como subconjunto do rollout e fora de producao."""
    application_environment = str(os.getenv("ENVIRONMENT", "")).strip().casefold()
    if application_environment in _PRODUCTION_ENVIRONMENTS:
        if str(os.getenv("ASAAS_SALES_CARNE_ENABLED_UNITS", "")).strip():
            raise AsaasSalesConfigError(
                "ASAAS_SALES_CARNE_ENABLED_UNITS não habilita produção."
            )
        return get_enabled_asaas_sales_production_carne_units()
    raw = os.getenv("ASAAS_SALES_CARNE_ENABLED_UNITS", "")
    enabled: set[str] = set()
    invalid: list[str] = []
    for item in raw.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        canonical = canonicalize_asaas_sales_unit(candidate)
        if canonical:
            enabled.add(canonical)
        else:
            invalid.append(candidate)
    if invalid:
        raise AsaasSalesConfigError(
            "ASAAS_SALES_CARNE_ENABLED_UNITS contém unidade não reconhecida."
        )

    global_enabled = get_enabled_asaas_sales_units()
    if not enabled.issubset(global_enabled):
        raise AsaasSalesConfigError(
            "O rollout do Carnê deve ser subconjunto de ASAAS_SALES_ENABLED_UNITS."
        )
    if enabled and application_environment not in _NON_PRODUCTION_ENVIRONMENTS:
        raise AsaasSalesConfigError(
            "O Carnê Asaas desta fase só pode ser habilitado fora de produção."
        )
    return frozenset(enabled)


def is_asaas_sales_carne_enabled(unidade: str) -> bool:
    canonical = canonicalize_asaas_sales_unit(unidade)
    return bool(
        canonical and canonical in get_enabled_asaas_sales_carne_units()
    )


def _get_enabled_sandbox_method_units(
    variable_name: str,
    method_label: str,
) -> frozenset[str]:
    raw = os.getenv(variable_name, "")
    enabled: set[str] = set()
    invalid: list[str] = []
    for item in raw.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        canonical = canonicalize_asaas_sales_unit(candidate)
        if canonical:
            enabled.add(canonical)
        else:
            invalid.append(candidate)
    if invalid:
        raise AsaasSalesConfigError(
            f"{variable_name} contém unidade não reconhecida."
        )
    if not enabled.issubset(get_enabled_asaas_sales_units()):
        raise AsaasSalesConfigError(
            f"O rollout de {method_label} deve ser subconjunto de "
            "ASAAS_SALES_ENABLED_UNITS."
        )
    application_environment = str(os.getenv("ENVIRONMENT", "")).strip().casefold()
    if enabled and application_environment not in _NON_PRODUCTION_ENVIRONMENTS:
        raise AsaasSalesConfigError(
            f"{method_label} desta fase só pode ser habilitado fora de produção."
        )
    return frozenset(enabled)


def get_enabled_asaas_sales_pix_automatic_units() -> frozenset[str]:
    return _get_enabled_sandbox_method_units(
        "ASAAS_SALES_PIX_AUTOMATIC_ENABLED_UNITS",
        "Pix Recorrente Asaas",
    )


def is_asaas_sales_pix_automatic_enabled(unidade: str) -> bool:
    canonical = canonicalize_asaas_sales_unit(unidade)
    return bool(
        canonical
        and canonical in get_enabled_asaas_sales_pix_automatic_units()
    )


def is_asaas_sales_pix_automatic_split_policy_approved() -> bool:
    """Pix permanece desligado até existir política financeira aprovada."""
    return False


def get_enabled_asaas_sales_credit_card_recurring_units() -> frozenset[str]:
    if str(os.getenv("ENVIRONMENT", "")).strip().casefold() in _PRODUCTION_ENVIRONMENTS:
        if str(os.getenv("ASAAS_SALES_CREDIT_CARD_RECURRENT_ENABLED_UNITS", "")).strip():
            raise AsaasSalesConfigError(
                "ASAAS_SALES_CREDIT_CARD_RECURRENT_ENABLED_UNITS não habilita produção."
            )
        return get_enabled_asaas_sales_production_credit_card_recurring_units()
    return _get_enabled_sandbox_method_units(
        "ASAAS_SALES_CREDIT_CARD_RECURRENT_ENABLED_UNITS",
        "Cartão recorrente Asaas",
    )


def is_asaas_sales_credit_card_recurring_enabled(unidade: str) -> bool:
    canonical = canonicalize_asaas_sales_unit(unidade)
    return bool(
        canonical
        and canonical in get_enabled_asaas_sales_credit_card_recurring_units()
    )


def get_enabled_asaas_sales_entry_units() -> frozenset[str]:
    """Gate próprio da entrada, independente do Carnê principal."""
    units = _get_enabled_sandbox_method_units(
        "ASAAS_SALES_ENTRY_ENABLED_UNITS",
        "Entrada Asaas",
    )
    # A allowlist sem a aprovação financeira explícita é configuração
    # incompleta, nunca uma habilitação silenciosamente degradada.
    if units and not is_asaas_sales_entry_split_policy_approved():
        raise AsaasSalesConfigError(
            "ASAAS_SALES_ENTRY_ENABLED_UNITS requer "
            "ASAAS_SALES_SANDBOX_ENTRY_SPLIT_POLICY_APPROVED=true no Sandbox."
        )
    return units


def is_asaas_sales_entry_enabled(unidade: str) -> bool:
    canonical = canonicalize_asaas_sales_unit(unidade)
    return bool(canonical and canonical in get_enabled_asaas_sales_entry_units())


def is_asaas_sales_entry_split_policy_approved() -> bool:
    """Liberação explícita e exclusiva do Sandbox para a entrada Pix aprovada."""
    application_environment = str(os.getenv("ENVIRONMENT", "")).strip().casefold()
    asaas_environment = str(os.getenv("ASAAS_ENVIRONMENT", "")).strip().casefold()
    if (
        application_environment not in _NON_PRODUCTION_ENVIRONMENTS
        or asaas_environment != "sandbox"
    ):
        return False
    approved = str(
        os.getenv("ASAAS_SALES_SANDBOX_ENTRY_SPLIT_POLICY_APPROVED", "")
    ).strip().casefold()
    if approved in {"", "false"}:
        return False
    if approved == "true":
        return True
    raise AsaasSalesConfigError(
        "ASAAS_SALES_SANDBOX_ENTRY_SPLIT_POLICY_APPROVED deve ser true ou false."
    )


def is_asaas_sales_payment_method_enabled(
    unidade: str,
    payment_method: str,
) -> bool:
    checks = {
        "ASAAS_BOLETO_INSTALLMENT": is_asaas_sales_carne_enabled,
        "ASAAS_PIX_AUTOMATIC": is_asaas_sales_pix_automatic_enabled,
        "ASAAS_CREDIT_CARD_RECURRENT": (
            is_asaas_sales_credit_card_recurring_enabled
        ),
    }
    checker = checks.get(str(payment_method or "").strip().upper())
    return bool(checker and checker(unidade))


def is_asaas_sales_payment_method_environment_enabled(
    unidade: str,
    environment: str,
    payment_method: str,
) -> bool:
    """Autoriza uma *nova* emissão no alvo informado, sempre fail-closed.

    Reconciliações e leituras históricas deliberadamente não usam este gate:
    elas precisam continuar disponíveis durante um rollback de rollout.
    """
    normalized_environment = str(environment or "").strip().casefold()
    application_environment = str(os.getenv("ENVIRONMENT", "")).strip().casefold()
    asaas_environment = str(os.getenv("ASAAS_ENVIRONMENT", "")).strip().casefold()
    canonical = canonicalize_asaas_sales_unit(unidade)
    if not canonical:
        return False
    if normalized_environment == "sandbox":
        if (
            application_environment not in _NON_PRODUCTION_ENVIRONMENTS
            or asaas_environment != "sandbox"
        ):
            return False
        return is_asaas_sales_payment_method_enabled(canonical, payment_method)
    if normalized_environment != "production":
        return False
    if not is_asaas_sales_production_profile_enabled():
        return False
    if (
        application_environment not in _PRODUCTION_ENVIRONMENTS
        or asaas_environment not in _PRODUCTION_ENVIRONMENTS
    ):
        return False
    checks = {
        "ASAAS_BOLETO_INSTALLMENT": get_enabled_asaas_sales_production_carne_units,
        "ASAAS_CREDIT_CARD_RECURRENT": (
            get_enabled_asaas_sales_production_credit_card_recurring_units
        ),
    }
    checker = checks.get(str(payment_method or "").strip().upper())
    return bool(canonical and checker and canonical in checker())


def get_asaas_sales_checkout_callback_url() -> str:
    raw = str(os.getenv("ASAAS_SALES_CHECKOUT_CALLBACK_URL", "")).strip()
    parsed = urlparse(raw)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise AsaasSalesConfigError(
            "Callback do Checkout Asaas ausente ou inválido."
        )
    return raw.rstrip("/")


def get_asaas_sales_webhook_token(unidade: str) -> str:
    """Retorna o segredo do webhook da conta, sem fallback entre unidades."""
    canonical = canonicalize_asaas_sales_unit(unidade)
    if not canonical:
        raise AsaasSalesConfigError("Unidade de webhook Asaas não reconhecida.")

    names = tuple(
        f"ASAAS_WEBHOOK_AUTH_TOKEN_{alias}"
        for alias in _UNIT_ENV_ALIASES[canonical]
    )
    configured_tokens = [
        str(os.getenv(name, ""))
        for name in names
        if str(os.getenv(name, ""))
    ]
    if len(set(configured_tokens)) > 1:
        raise AsaasSalesConfigError(
            "Aliases do token de webhook Asaas possuem valores divergentes."
        )
    if configured_tokens:
        return _validate_webhook_token(configured_tokens[0])

    raise AsaasSalesConfigError(
        "Token de autenticação do webhook Asaas não configurado para a unidade."
    )


def get_asaas_sales_account_id(unidade: str, environment: str) -> str:
    """Identidade V3 esperada no payload do webhook, separada da wallet."""
    canonical = canonicalize_asaas_sales_unit(unidade)
    normalized_environment = validate_asaas_sales_environment(environment)
    if not canonical:
        raise AsaasSalesConfigError("Unidade de webhook Asaas não reconhecida.")
    prefix = (
        "ASAAS_PRODUCTION_ACCOUNT_ID"
        if normalized_environment == "production"
        else "ASAAS_SANDBOX_ACCOUNT_ID"
    )
    names = tuple(f"{prefix}_{alias}" for alias in _UNIT_ENV_ALIASES[canonical])
    configured = {
        str(os.getenv(name, "")).strip()
        for name in names
        if str(os.getenv(name, "")).strip()
    }
    if len(configured) > 1:
        raise AsaasSalesConfigError(
            "Aliases do ID da conta Asaas possuem valores divergentes."
        )
    if not configured:
        raise AsaasSalesConfigError(
            "ID V3 da conta Asaas não configurado para a unidade."
        )
    raw_account_id = next(iter(configured))
    try:
        account_id = str(UUID(raw_account_id))
    except (ValueError, AttributeError):
        raise AsaasSalesConfigError("ID V3 da conta Asaas inválido.") from None
    return account_id


def validate_asaas_sales_environment(asaas_environment: str) -> str:
    """Impede uso cruzado entre runtime de producao e Sandbox do Asaas."""
    application_environment = str(os.getenv("ENVIRONMENT", "")).strip().casefold()
    normalized_asaas = str(asaas_environment or "").strip().casefold()
    if application_environment in _PRODUCTION_ENVIRONMENTS:
        expected = "production"
    elif application_environment in _NON_PRODUCTION_ENVIRONMENTS:
        expected = "sandbox"
    else:
        raise AsaasSalesConfigError(
            "ENVIRONMENT deve identificar explicitamente produção ou sandbox."
        )
    if normalized_asaas != expected:
        raise AsaasSalesConfigError(
            "Ambiente da aplicação diverge do ambiente configurado no Asaas."
        )
    return normalized_asaas


def validate_asaas_sales_account_configuration(
    *,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    api_key: str,
) -> tuple[str, str, str]:
    """Valida uma conta estrita sem expor credenciais no retorno."""
    canonical = canonicalize_asaas_sales_unit(unidade)
    if not canonical:
        raise AsaasSalesConfigError("Unidade da conta Asaas não reconhecida.")
    normalized_environment = validate_asaas_sales_environment(environment)
    _validate_account_alias_consistency(canonical, normalized_environment)

    normalized_wallet = str(account_wallet_id or "").strip()
    normalized_api_key = str(api_key or "").strip()
    if (
        not normalized_wallet
        or len(normalized_wallet) > 100
        or any(char.isspace() for char in normalized_wallet)
        or normalized_wallet.casefold() in _WEBHOOK_TOKEN_PLACEHOLDERS
    ):
        raise AsaasSalesConfigError("Wallet da conta Asaas inválida.")
    if (
        len(normalized_api_key) < 20
        or any(char.isspace() for char in normalized_api_key)
        or normalized_api_key.casefold() in _WEBHOOK_TOKEN_PLACEHOLDERS
    ):
        raise AsaasSalesConfigError("Chave da API Asaas inválida.")
    return canonical, normalized_environment, normalized_wallet


def validate_asaas_sales_account_isolation(units: Iterable[str]) -> None:
    """Falha se as unidades informadas compartilharem conta, chave ou token."""
    canonical_units: set[str] = set()
    for unit in units:
        canonical = canonicalize_asaas_sales_unit(unit)
        if not canonical:
            raise AsaasSalesConfigError(
                "Unidade da conta Asaas não reconhecida."
            )
        canonical_units.add(canonical)
    if not canonical_units:
        return

    from app.asaas_sdk.environment import AsaasConfig
    from app.asaas_sdk.exceptions import AsaasConfigurationError

    wallets: set[str] = set()
    account_ids: set[str] = set()
    api_key_digests: set[str] = set()
    token_digests: set[str] = set()
    for unidade in sorted(canonical_units):
        try:
            config = AsaasConfig.from_env(unidade, strict=True)
        except AsaasConfigurationError as exc:
            raise AsaasSalesConfigError(
                "Conta Asaas estrita ausente para unidade habilitada."
            ) from exc
        _canonical, _environment, wallet = (
            validate_asaas_sales_account_configuration(
                unidade=config.unidade or unidade,
                environment=config.environment.name.casefold(),
                account_wallet_id=config.account_wallet_id or "",
                api_key=config.api_key,
            )
        )
        token = get_asaas_sales_webhook_token(unidade)
        account_id = get_asaas_sales_account_id(unidade, _environment)
        api_digest = hashlib.sha256(config.api_key.encode("utf-8")).hexdigest()
        token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if (
            wallet in wallets
            or account_id in account_ids
            or api_digest in api_key_digests
            or token_digest in token_digests
        ):
            raise AsaasSalesConfigError(
                "Unidades de vendas Asaas devem usar contas e tokens distintos."
            )
        wallets.add(wallet)
        account_ids.add(account_id)
        api_key_digests.add(api_digest)
        token_digests.add(token_digest)


def validate_enabled_asaas_sales_account_isolation() -> None:
    """Falha se contas de vendas/provisionamento compartilharem credenciais."""
    validate_asaas_sales_account_isolation(
        get_asaas_sales_operational_account_units()
    )


def validate_asaas_sales_account_target(
    *,
    unidade: str,
    environment: str,
    account_wallet_id: str,
) -> tuple[str, str, str]:
    """Confirma que o alvo interno coincide com a conta estrita configurada."""
    canonical = canonicalize_asaas_sales_unit(unidade)
    if not canonical:
        raise AsaasSalesConfigError("Unidade da conta Asaas não reconhecida.")
    validate_enabled_asaas_sales_account_isolation()

    from app.asaas_sdk.environment import AsaasConfig
    from app.asaas_sdk.exceptions import AsaasConfigurationError

    try:
        config = AsaasConfig.from_env(canonical, strict=True)
    except AsaasConfigurationError as exc:
        raise AsaasSalesConfigError(
            "Conta Asaas estrita ausente para unidade habilitada."
        ) from exc
    configured = validate_asaas_sales_account_configuration(
        unidade=config.unidade or canonical,
        environment=config.environment.name.casefold(),
        account_wallet_id=config.account_wallet_id or "",
        api_key=config.api_key,
    )
    requested = (
        canonical,
        str(environment or "").strip().casefold(),
        str(account_wallet_id or "").strip(),
    )
    if requested != configured:
        raise AsaasSalesConfigError(
            "Alvo da venda diverge da conta Asaas estrita configurada."
        )
    return configured


def build_asaas_sales_target_key(
    unidade: str,
    environment: str,
    account_wallet_id: str,
) -> str:
    """Gera chave tecnica; a wallet nao e copiada para filas ou logs."""
    canonical = canonicalize_asaas_sales_unit(unidade)
    normalized_environment = str(environment or "").strip().casefold()
    normalized_wallet = str(account_wallet_id or "").strip()
    if not canonical:
        raise AsaasSalesConfigError("Unidade de venda Asaas não reconhecida.")
    if normalized_environment not in {"sandbox", "production"}:
        raise AsaasSalesConfigError("Ambiente de venda Asaas inválido.")
    if not normalized_wallet:
        raise AsaasSalesConfigError("Conta Asaas da unidade não configurada.")
    return f"asaas-sales:{normalized_environment}:{unit_slug(canonical)}"


def _validate_webhook_token(token: str) -> str:
    if not 32 <= len(token) <= 255 or any(char.isspace() for char in token):
        raise AsaasSalesConfigError(
            "Token do webhook Asaas deve ter entre 32 e 255 caracteres sem espaços."
        )
    if token.casefold() in _WEBHOOK_TOKEN_PLACEHOLDERS:
        raise AsaasSalesConfigError("Token do webhook Asaas é um placeholder.")
    if token.casefold().startswith("$aact_"):
        raise AsaasSalesConfigError("Chave da API Asaas não pode ser token de webhook.")
    if _REPEATED_TOKEN_CHARACTER_PATTERN.search(token):
        raise AsaasSalesConfigError("Token do webhook Asaas não atende à complexidade.")
    if any(sequence in token for sequence in _SEQUENTIAL_DIGITS):
        raise AsaasSalesConfigError("Token do webhook Asaas não atende à complexidade.")

    token_bytes = token.encode("utf-8")
    for name, raw_value in os.environ.items():
        if not name.startswith("ASAAS_") or "API_KEY" not in name:
            continue
        api_key = str(raw_value or "").strip()
        if api_key and secrets.compare_digest(token_bytes, api_key.encode("utf-8")):
            raise AsaasSalesConfigError(
                "Chave da API Asaas não pode ser token de webhook."
            )
    return token


def _validate_account_alias_consistency(
    unidade: str,
    environment: str,
) -> None:
    aliases = _UNIT_ENV_ALIASES[unidade]
    api_prefix = (
        "ASAAS_PRODUCTION_API_KEY"
        if environment == "production"
        else "ASAAS_SANDBOX_API_KEY"
    )
    api_names = tuple(f"{api_prefix}_{alias}" for alias in aliases)
    if environment == "production":
        wallet_names = tuple(
            name
            for alias in aliases
            for name in (
                f"ASAAS_PRODUCTION_WALLET_ID_{alias}",
                f"ASAAS_WALLET_ID_{alias}",
            )
        )
    else:
        wallet_names = tuple(
            f"ASAAS_SANDBOX_WALLET_ID_{alias}" for alias in aliases
        )
    account_prefix = (
        "ASAAS_PRODUCTION_ACCOUNT_ID"
        if environment == "production"
        else "ASAAS_SANDBOX_ACCOUNT_ID"
    )
    account_names = tuple(f"{account_prefix}_{alias}" for alias in aliases)
    for names in (api_names, wallet_names, account_names):
        configured = {
            str(os.getenv(name, "")).strip()
            for name in names
            if str(os.getenv(name, "")).strip()
        }
        if len(configured) > 1:
            raise AsaasSalesConfigError(
                "Aliases da conta Asaas possuem valores divergentes."
            )
