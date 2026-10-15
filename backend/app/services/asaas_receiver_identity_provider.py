"""Fonte estreita das identidades autenticadas de recebedores Asaas.

O manifesto contem somente metadados. A chave e lida somente durante a
consulta de evidencia e nunca integra identidade, plano, log ou cache.
"""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from app.asaas_sdk.environment import AsaasConfig, Environment
from app.asaas_sdk.http_client import AsaasHttpClient
from app.asaas_sales_sdk.approval_evidence import AsaasSalesApprovalEvidenceReader
from app.services.asaas_account_approval_service import AsaasApprovalTarget
from app.services.asaas_sales_config import canonicalize_asaas_sales_unit
from app.services.asaas_split_service import AsaasReceiverIdentity, AsaasSplitValidationError
from app.services.asaas_sale_database import DatabaseConnection
from app.security.asaas_account_secret import decrypt_api_key

_REF = re.compile(r"^env:(ASAAS_SALES_RECEIVER_SECRET_[A-Z0-9_]+)$")


class AsaasReceiverIdentityProvider:
    """Resolve somente tuplas declaradas explicitamente no manifesto local."""

    def __init__(self, manifest_path: str):
        self._manifest_path = Path(manifest_path)
        self._identities = self._load()

    @classmethod
    def from_environment(cls) -> "AsaasReceiverIdentityProvider":
        path = os.getenv("ASAAS_SALES_RECEIVER_IDENTITIES_FILE", "").strip()
        if not path:
            raise AsaasSplitValidationError("manifesto_recebedor_asaas_ausente")
        return cls(path)

    def _load(self) -> dict[tuple[str, int, str, str, str], AsaasReceiverIdentity]:
        try:
            raw = self._manifest_path.read_text(encoding="utf-8")
            document = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AsaasSplitValidationError("manifesto_recebedor_asaas_indisponivel") from exc
        if not isinstance(document, Mapping) or set(document) != {"schema_version", "receivers"}:
            raise AsaasSplitValidationError("manifesto_recebedor_asaas_invalido")
        if (
            type(document.get("schema_version")) is not int
            or document["schema_version"] != 1
            or not isinstance(document["receivers"], list)
        ):
            raise AsaasSplitValidationError("manifesto_recebedor_asaas_invalido")
        identities: dict[tuple[str, int, str, str, str], AsaasReceiverIdentity] = {}
        refs: set[str] = set()
        required = {"kind", "local_id", "unidade", "environment", "account_id", "wallet_id", "credential_ref"}
        for value in document["receivers"]:
            if not isinstance(value, Mapping) or set(value) != required:
                raise AsaasSplitValidationError("manifesto_recebedor_asaas_invalido")
            if (
                value.get("kind") not in {"pf", "empresa"}
                or type(value.get("local_id")) is not int
                or value["local_id"] <= 0
            ):
                raise AsaasSplitValidationError("manifesto_recebedor_asaas_invalido")
            unit = canonicalize_asaas_sales_unit(str(value.get("unidade") or ""))
            environment = value.get("environment")
            if not unit or environment not in {"sandbox", "production"} or any(
                not isinstance(value.get(field), str) or not value[field].strip()
                for field in ("account_id", "wallet_id", "credential_ref")
            ):
                raise AsaasSplitValidationError("manifesto_recebedor_asaas_invalido")
            ref = value["credential_ref"]
            if not _REF.fullmatch(ref) or ref in refs:
                raise AsaasSplitValidationError("manifesto_recebedor_asaas_invalido")
            identity = AsaasReceiverIdentity(
                kind=value["kind"], local_id=value["local_id"], unidade=unit,
                environment=environment, account_id=value["account_id"].strip(),
                wallet_id=value["wallet_id"].strip(), credential_ref=ref,
            )
            key = (identity.kind, identity.local_id, unit, environment, identity.wallet_id)
            if key in identities:
                raise AsaasSplitValidationError("manifesto_recebedor_asaas_ambiguo")
            identities[key] = identity
            refs.add(ref)
        return identities

    def resolve(self, *, kind: str, local_id: int, unidade: str, environment: str, wallet_id: str) -> AsaasReceiverIdentity:
        if kind not in {"pf", "empresa"} or type(local_id) is not int or local_id <= 0:
            raise AsaasSplitValidationError("identidade_recebedor_asaas_invalida")
        unit = canonicalize_asaas_sales_unit(unidade)
        identity = self._identities.get((kind, local_id, unit, environment, str(wallet_id)))
        if identity is None:
            raise AsaasSplitValidationError("identidade_recebedor_asaas_ausente")
        return identity

    def resolve_for_new_sale(
        self, *, kind: str, local_id: int, unidade: str, environment: str
    ) -> AsaasReceiverIdentity:
        """Resolve uma única identidade canônica, sem usar wallet legada.

        Snapshots antigos usam ``resolve`` com a tupla completa. Para uma nova
        venda, duas wallets declaradas para a mesma base são ambíguas e devem
        ser escolhidas por uma mudança operacional explícita, nunca por ordem.
        """
        if kind not in {"pf", "empresa"} or type(local_id) is not int or local_id <= 0:
            raise AsaasSplitValidationError("identidade_recebedor_asaas_invalida")
        unit = canonicalize_asaas_sales_unit(unidade)
        candidates = [
            identity for (candidate_kind, candidate_id, candidate_unit, candidate_environment, _wallet), identity
            in self._identities.items()
            if (candidate_kind, candidate_id, candidate_unit, candidate_environment)
            == (kind, local_id, unit, environment)
        ]
        if len(candidates) != 1:
            raise AsaasSplitValidationError(
                "identidade_recebedor_asaas_ausente"
                if not candidates else "identidade_recebedor_asaas_ambigua"
            )
        return candidates[0]

    @contextmanager
    def approval_reader(self, identity: AsaasReceiverIdentity) -> Iterator[AsaasSalesApprovalEvidenceReader]:
        declared = self.resolve(kind=identity.kind, local_id=identity.local_id, unidade=identity.unidade, environment=identity.environment, wallet_id=identity.wallet_id)
        if declared != identity:
            raise AsaasSplitValidationError("identidade_recebedor_asaas_divergente")
        name = _REF.fullmatch(identity.credential_ref).group(1)  # validated on load
        secret = os.getenv(name)
        if not isinstance(secret, str) or not secret.strip():
            raise AsaasSplitValidationError("credencial_recebedor_asaas_ausente")
        env = Environment.PRODUCTION if identity.environment == "production" else Environment.SANDBOX
        config = AsaasConfig(api_key=secret, environment=env, unidade=identity.unidade)
        client = AsaasHttpClient(base_url=config.base_url, headers=config.headers)
        try:
            yield AsaasSalesApprovalEvidenceReader(client, AsaasApprovalTarget(
                unidade=identity.unidade, environment=identity.environment,
                account_id=identity.account_id, wallet_id=identity.wallet_id,
            ))
        finally:
            client.close()


class AsaasSandboxReceiverIdentityProvider:
    """Fonte PF sandbox: metadados por view e cifra por função estreita.

    Esta classe deliberadamente não conhece ``users.asaas_*`` nem manifesto.
    ``credential_ref`` é apenas o id não secreto do vínculo e a cifra só vive
    durante a construção do leitor autenticado.
    """

    def __init__(self, connection_factory=DatabaseConnection):
        self._connection_factory = connection_factory

    @staticmethod
    def _link_id(identity: AsaasReceiverIdentity) -> int:
        try:
            prefix, raw = identity.credential_ref.split(":", 1)
            link_id = int(raw)
        except (AttributeError, TypeError, ValueError):
            raise AsaasSplitValidationError("identidade_recebedor_asaas_divergente") from None
        if prefix != "sandbox-link" or link_id <= 0:
            raise AsaasSplitValidationError("identidade_recebedor_asaas_divergente")
        return link_id

    def _resolve_rows(self, *, local_id: int, unidade: str, wallet_id: str | None = None):
        if type(local_id) is not int or local_id <= 0:
            raise AsaasSplitValidationError("identidade_recebedor_asaas_invalida")
        unit = canonicalize_asaas_sales_unit(unidade)
        if not unit:
            raise AsaasSplitValidationError("identidade_recebedor_asaas_invalida")
        query = """
            SELECT id, user_id, unidade, environment, account_id, wallet_id
              FROM public.asaas_sandbox_receiver_link_metadata
             WHERE user_id = %s AND unidade = %s AND credential_state = 'verified'
        """
        params: tuple[object, ...] = (local_id, unit)
        if wallet_id is not None:
            query += " AND wallet_id = %s"
            params += (str(wallet_id),)
        with self._connection_factory(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    @staticmethod
    def _identity(row) -> AsaasReceiverIdentity:
        values = row if not isinstance(row, Mapping) else (
            row.get("id"), row.get("user_id"), row.get("unidade"), row.get("environment"), row.get("account_id"), row.get("wallet_id")
        )
        if len(values) != 6 or any(not value for value in values):
            raise AsaasSplitValidationError("identidade_recebedor_asaas_ausente")
        link_id, user_id, unidade, environment, account_id, wallet_id = values
        if type(link_id) is not int or type(user_id) is not int or environment != "sandbox":
            raise AsaasSplitValidationError("identidade_recebedor_asaas_ausente")
        return AsaasReceiverIdentity("pf", user_id, str(unidade), "sandbox", str(account_id), str(wallet_id), f"sandbox-link:{link_id}")

    def resolve_for_new_sale(self, *, kind: str, local_id: int, unidade: str, environment: str) -> AsaasReceiverIdentity:
        if kind != "pf" or environment != "sandbox":
            raise AsaasSplitValidationError("identidade_recebedor_asaas_ausente")
        return self._resolve_single_identity(local_id=local_id, unidade=unidade)

    def resolve(self, *, kind: str, local_id: int, unidade: str, environment: str, wallet_id: str) -> AsaasReceiverIdentity:
        if kind != "pf" or environment != "sandbox":
            raise AsaasSplitValidationError("identidade_recebedor_asaas_ausente")
        return self._resolve_single_identity(
            local_id=local_id,
            unidade=unidade,
            wallet_id=wallet_id,
        )

    def _resolve_single_identity(
        self,
        *,
        local_id: int,
        unidade: str,
        wallet_id: str | None = None,
    ) -> AsaasReceiverIdentity:
        rows = self._resolve_rows(
            local_id=local_id,
            unidade=unidade,
            wallet_id=wallet_id,
        )
        if len(rows) != 1:
            code = (
                "identidade_recebedor_asaas_ausente"
                if not rows
                else "identidade_recebedor_asaas_ambigua"
            )
            raise AsaasSplitValidationError(code)
        return self._identity(rows[0])

    @contextmanager
    def approval_reader(self, identity: AsaasReceiverIdentity) -> Iterator[AsaasSalesApprovalEvidenceReader]:
        if identity.kind != "pf" or identity.environment != "sandbox":
            raise AsaasSplitValidationError("identidade_recebedor_asaas_divergente")
        declared = self.resolve(kind="pf", local_id=identity.local_id, unidade=identity.unidade, environment="sandbox", wallet_id=identity.wallet_id)
        if declared != identity:
            raise AsaasSplitValidationError("identidade_recebedor_asaas_divergente")
        with self._connection_factory(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT public.asaas_get_verified_sandbox_receiver_cipher(%s, %s, %s, %s, %s)",
                (self._link_id(identity), identity.local_id, identity.unidade, identity.account_id, identity.wallet_id),
            )
            row = cursor.fetchone()
        ciphertext = row[0] if row and len(row) == 1 else None
        if not isinstance(ciphertext, str) or not ciphertext.strip():
            raise AsaasSplitValidationError("credencial_recebedor_asaas_ausente")
        try:
            secret = decrypt_api_key(ciphertext)
        except Exception:
            # A cifra é dado sensível: não exponha sua cadeia de erro nem a
            # representação do provedor de decriptação.
            raise AsaasSplitValidationError("credencial_recebedor_asaas_invalida") from None
        if not isinstance(secret, str) or not secret.strip():
            raise AsaasSplitValidationError("credencial_recebedor_asaas_invalida")
        config = AsaasConfig(api_key=secret, environment=Environment.SANDBOX, unidade=identity.unidade)
        client = AsaasHttpClient(base_url=config.base_url, headers=config.headers)
        try:
            yield AsaasSalesApprovalEvidenceReader(client, AsaasApprovalTarget(identity.unidade, "sandbox", identity.account_id, identity.wallet_id))
        finally:
            client.close()


def receiver_identity_provider_for_environment(environment: str):
    """Mantém o manifesto como único caminho de produção/PJ."""
    if str(environment).strip().casefold() == "sandbox":
        return _SandboxCompositeReceiverIdentityProvider(AsaasSandboxReceiverIdentityProvider())
    return AsaasReceiverIdentityProvider.from_environment()


class _SandboxCompositeReceiverIdentityProvider:
    """PF vem da view; PJ permanece explicitamente no manifesto."""

    def __init__(self, pf):
        self._pf = pf
        self._manifest = None

    def _provider(self, kind):
        if kind == "pf":
            return self._pf
        if self._manifest is None:
            self._manifest = AsaasReceiverIdentityProvider.from_environment()
        return self._manifest

    def resolve(self, *, kind, **kwargs):
        return self._provider(kind).resolve(kind=kind, **kwargs)

    def resolve_for_new_sale(self, *, kind, **kwargs):
        return self._provider(kind).resolve_for_new_sale(kind=kind, **kwargs)

    def approval_reader(self, identity):
        return self._provider(identity.kind).approval_reader(identity)
