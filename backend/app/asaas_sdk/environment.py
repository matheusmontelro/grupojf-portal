"""Configuracao de ambiente para o SDK do Asaas."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
import re
from typing import Iterable, Tuple

from .exceptions import AsaasConfigurationError


class Environment(Enum):
    SANDBOX = "https://api-sandbox.asaas.com/v3"
    PRODUCTION = "https://api.asaas.com/v3"


def _slugify_unidade(unidade: str) -> str:
    normalized = unidade.strip().upper()
    normalized = (
        normalized.replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace(".", "_")
    )
    normalized = normalized.translate(
        str.maketrans(
            {
                "Á": "A",
                "À": "A",
                "Â": "A",
                "Ã": "A",
                "É": "E",
                "Ê": "E",
                "Í": "I",
                "Ó": "O",
                "Ô": "O",
                "Õ": "O",
                "Ú": "U",
                "Ç": "C",
            }
        )
    )
    return re.sub(r"[^A-Z0-9_]", "", normalized)


_UNIT_ENV_ALIASES = {
    # Nomes mantidos no servidor antes da adocao do slug completo.
    "VILAR_DOS_TELES": ("VILAR", "VILAR_DOS_TELES"),
}


def _unit_aliases(unidade: str) -> Tuple[str, ...]:
    slug = _slugify_unidade(unidade)
    configured = _UNIT_ENV_ALIASES.get(slug, (slug,))
    return tuple(dict.fromkeys(configured))


def _first_configured(names: Iterable[str]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _parse_environment() -> Environment:
    raw_name = os.getenv("ASAAS_ENVIRONMENT") or os.getenv("ENVIRONMENT") or "sandbox"
    env_name = raw_name.strip().lower()
    if env_name == "production":
        return Environment.PRODUCTION
    if env_name in {"sandbox", "development", "test", "testing"}:
        return Environment.SANDBOX
    raise AsaasConfigurationError(
        "ASAAS_ENVIRONMENT invalido; use 'sandbox' ou 'production'."
    )


@dataclass
class AsaasConfig:
    """Configuracao do cliente Asaas e da conta-mae da unidade."""

    api_key: str = field(repr=False)
    environment: Environment = Environment.SANDBOX
    unidade: str | None = None
    user_agent: str = "grupojf-backend/1.0"
    account_wallet_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.environment, Environment):
            raise AsaasConfigurationError(
                "Ambiente Asaas invalido; use Environment.SANDBOX ou Environment.PRODUCTION."
            )
        self.api_key = str(self.api_key or "").strip()
        if not self.api_key:
            raise AsaasConfigurationError("Chave da API Asaas nao configurada.")
        if self.unidade is not None:
            self.unidade = self.unidade.strip() or None
        if self.account_wallet_id is not None:
            self.account_wallet_id = self.account_wallet_id.strip() or None

    @property
    def base_url(self) -> str:
        return self.environment.value

    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "access_token": self.api_key,
        }

    @classmethod
    def from_env(
        cls,
        unidade: str | None = None,
        *,
        strict: bool = False,
    ) -> "AsaasConfig":
        """Carrega configuracao.

        ``strict=False`` preserva o fallback global usado pelos checkouts
        existentes. ``strict=True`` e destinado ao worker: exige unidade e um
        par chave/wallet da mesma conta, sem qualquer fallback global.
        """
        environment = _parse_environment()
        if strict:
            api_key, account_wallet_id = cls._resolve_strict_account(
                unidade=unidade,
                environment=environment,
            )
        else:
            api_key = cls._resolve_api_key(unidade=unidade, environment=environment)
            account_wallet_id = cls._resolve_optional_wallet(
                unidade=unidade,
                environment=environment,
            )

        user_agent = os.getenv("ASAAS_USER_AGENT", "grupojf-backend/1.0")
        return cls(
            api_key=api_key,
            environment=environment,
            unidade=unidade,
            user_agent=user_agent,
            account_wallet_id=account_wallet_id,
        )

    @staticmethod
    def _api_key_prefix(environment: Environment) -> str:
        if environment == Environment.PRODUCTION:
            return "ASAAS_PRODUCTION_API_KEY"
        return "ASAAS_SANDBOX_API_KEY"

    @staticmethod
    def _wallet_names(alias: str, environment: Environment) -> Tuple[str, ...]:
        if environment == Environment.PRODUCTION:
            return (
                f"ASAAS_PRODUCTION_WALLET_ID_{alias}",
                f"ASAAS_WALLET_ID_{alias}",
            )
        return (f"ASAAS_SANDBOX_WALLET_ID_{alias}",)

    @classmethod
    def _resolve_strict_account(
        cls,
        unidade: str | None,
        environment: Environment,
    ) -> Tuple[str, str]:
        if not unidade or not unidade.strip():
            raise AsaasConfigurationError(
                "Unidade obrigatoria para configuracao estrita do Asaas."
            )

        prefix = cls._api_key_prefix(environment)
        expected_names = []
        for alias in _unit_aliases(unidade):
            api_key_name = f"{prefix}_{alias}"
            wallet_names = cls._wallet_names(alias, environment)
            expected_names.extend((api_key_name, *wallet_names))
            api_key = _first_configured((api_key_name,))
            wallet_id = _first_configured(wallet_names)
            if api_key and wallet_id:
                return api_key, wallet_id

        raise AsaasConfigurationError(
            "Configuracao estrita do Asaas incompleta para a unidade. "
            "Configure um par de conta-mae: " + ", ".join(expected_names)
        )

    @classmethod
    def _resolve_optional_wallet(
        cls,
        unidade: str | None,
        environment: Environment,
    ) -> str | None:
        if not unidade:
            return None
        for alias in _unit_aliases(unidade):
            wallet_id = _first_configured(cls._wallet_names(alias, environment))
            if wallet_id:
                return wallet_id
        return None

    @classmethod
    def _resolve_api_key(
        cls,
        unidade: str | None,
        environment: Environment,
    ) -> str:
        env_prefix = cls._api_key_prefix(environment)

        candidates = []
        if unidade:
            for unidade_key in _unit_aliases(unidade):
                candidates.extend(
                    [
                        f"{env_prefix}_{unidade_key}",
                        f"ASAAS_API_KEY_{unidade_key}",
                    ]
                )

        candidates.extend([env_prefix, "ASAAS_API_KEY"])
        api_key = _first_configured(candidates)
        if api_key:
            return api_key

        raise AsaasConfigurationError(
            "Nenhuma chave do Asaas configurada. Variaveis esperadas: "
            + ", ".join(candidates)
        )
