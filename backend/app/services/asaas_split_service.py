"""Alocacao fail-closed de splits para cobrancas Asaas.

As regras financeiras continuam nas tabelas de configuracao do dominio, mas
este modulo resolve os recebedores diretamente para wallets Asaas. Nenhum
estado de outra integracao de pagamento participa da selecao.

O saldo nao alocado so pode permanecer na conta emissora quando uma unica
regra declara explicitamente ``absorve_saldo``. A conta emissora e registrada
no plano para auditoria, mas nunca e enviada como um auto-split.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable, List, Mapping, NoReturn, Optional, Sequence

from app.asaas_sdk.sdk_utils import normalize_money, normalize_percentage
from app.services.asaas_sales_config import (
    is_asaas_sandbox_ni_odontogram_type_available,
)
from app.services.venda_akimais_service import AKIMAIS_EMPRESA_ID

ASAAS_ELIGIBLE_PF_CARGOS = frozenset({3, 4})
ASAAS_SPLIT_CONTEXTS = frozenset({"carne", "entrada", "pix", "cartao"})
_RECURRING_CONTEXTS = frozenset({"pix", "cartao"})
_INDEFINITE_CYCLES = 999
_CENT = Decimal("0.01")


class AsaasSplitValidationError(ValueError):
    """Erro seguro de configuracao; a cobranca remota deve ser bloqueada."""


@dataclass(frozen=True)
class AsaasReceiverIdentity:
    """Vínculo não secreto e imutável de um recebedor externo."""

    kind: str
    local_id: int
    unidade: str
    environment: str
    account_id: str
    wallet_id: str
    credential_ref: str


@dataclass(frozen=True)
class AsaasDomainSplitRule:
    """Regra financeira ja associada ao recebedor selecionado."""

    wallet_id: Optional[str]
    cargo_id: Optional[int] = None
    user_id: Optional[int] = None
    empresa_id: Optional[int] = None
    percentual_value: Optional[Decimal] = None
    fixed_value: Optional[Decimal] = None
    cycles_to_participate: Optional[int] = None
    absorbs_balance: bool = False


@dataclass(frozen=True)
class AsaasSplitItem:
    """Parcela externa que pode ser serializada no payload Asaas."""

    wallet_id: str
    kind: str
    cargo_id: Optional[int] = None
    user_id: Optional[int] = None
    empresa_id: Optional[int] = None
    percentual_value: Optional[Decimal] = None
    total_fixed_value: Optional[Decimal] = None
    cycles_to_participate: Optional[int] = None
    receiver_identity: Optional[AsaasReceiverIdentity] = None


@dataclass(frozen=True)
class AsaasBalanceAbsorber:
    """Saldo mantido na conta emissora e omitido do payload remoto."""

    wallet_id: str
    absorbed_value: Decimal
    cargo_id: Optional[int] = None
    user_id: Optional[int] = None
    empresa_id: Optional[int] = None
    cycles_to_participate: Optional[int] = None


@dataclass(frozen=True)
class AsaasOmittedReceiver:
    """Registro nao sensivel de uma omissao deliberada."""

    cargo_id: Optional[int]
    user_id: Optional[int]
    empresa_id: Optional[int]
    motivo: str


@dataclass(frozen=True)
class AsaasSplitPlan:
    """Plano validado; ``items`` contem somente wallets externas."""

    items: List[AsaasSplitItem]
    contexto: str
    absorber: Optional[AsaasBalanceAbsorber] = None
    raw_metadata: List[Mapping[str, Any]] = field(default_factory=list)
    omissos: List[AsaasOmittedReceiver] = field(default_factory=list)
    schema_version: int = 1


@dataclass(frozen=True)
class AsaasSealedSplitSnapshot:
    """Plano e payload imutaveis associados a uma integracao local."""

    integration_id: int
    plan: AsaasSplitPlan
    payload: List[dict]
    plan_sha256: str
    payload_sha256: str
    lifecycle_state: str


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _clean_wallet(value: Any) -> Optional[str]:
    if value is None:
        return None
    wallet = str(value).strip()
    return wallet or None


def resolve_asaas_company_wallet_mappings(
    *,
    environment: str,
) -> Mapping[int, Optional[str]]:
    """Expoe o mesmo mapa deterministico usado pelo runtime de split."""
    if str(environment).strip().casefold() != "sandbox":
        raise AsaasSplitValidationError(
            "empresa_wallet_ambiente_nao_suportado"
        )

    mappings: dict[int, Optional[str]] = {
        int(AKIMAIS_EMPRESA_ID): _clean_wallet(
            os.getenv("ASAAS_SANDBOX_WALLET_ID_AKIMAIS")
        )
    }
    raw_partmed_id = str(os.getenv("ASAAS_PARTMED_EMPRESA_ID", "")).strip()
    if raw_partmed_id:
        try:
            partmed_id = int(raw_partmed_id)
        except ValueError:
            raise AsaasSplitValidationError(
                "mapeamento_empresa_asaas_invalido"
            ) from None
        if partmed_id in mappings:
            raise AsaasSplitValidationError(
                "mapeamento_empresa_asaas_ambiguo"
            )
        mappings[partmed_id] = _clean_wallet(
            os.getenv("ASAAS_SANDBOX_WALLET_ID_PARTMED")
        )
    return mappings


def _resolve_company_wallet(
    empresa_id: int,
    *,
    environment: str,
) -> Optional[str]:
    return resolve_asaas_company_wallet_mappings(
        environment=environment,
    ).get(int(empresa_id))


def _fetch_rule_for_cargo(
    cursor: Any,
    *,
    tipo_odontograma_id: int,
    cargo_id: int,
    unidade: str,
) -> Optional[tuple[Any, ...]]:
    cursor.execute(
        """
        SELECT rs.percentual, rs.tipo_calculo, rs.valor_fixo_brl,
               rs.ciclos_participacao, rs.absorve_saldo
          FROM regras_split rs
          JOIN participacao_cargo_split pcs
            ON pcs.tipo_odontograma_id = rs.tipo_odontograma_id
           AND pcs.cargo_id = rs.cargo_id
         WHERE rs.tipo_odontograma_id = %s
           AND rs.cargo_id = %s
           AND rs.ativo = TRUE
           AND pcs.ativo = TRUE
           AND (rs.unidade = %s OR rs.unidade IS NULL)
         ORDER BY CASE WHEN rs.unidade = %s THEN 0 ELSE 1 END,
                  pcs.ordem_prioridade,
                  rs.id
         LIMIT 1
        """,
        (int(tipo_odontograma_id), int(cargo_id), str(unidade), str(unidade)),
    )
    return cursor.fetchone()


def _rule_values(row: Sequence[Any]) -> tuple[Optional[Decimal], Optional[Decimal], Optional[int], bool]:
    percentual, tipo_calculo, valor_fixo, ciclos, absorve = row
    if str(tipo_calculo or "percentual") == "valor_fixo":
        return None, _to_decimal(valor_fixo), _coerce_cycles(ciclos), bool(absorve)
    return _to_decimal(percentual), None, _coerce_cycles(ciclos), bool(absorve)


def _coerce_cycles(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        cycles = int(value)
    except (TypeError, ValueError):
        raise AsaasSplitValidationError("ciclos_participacao_invalidos")
    if cycles <= 0:
        raise AsaasSplitValidationError("ciclos_participacao_invalidos")
    return cycles


def _coerce_receiver_limit(value: Any, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise AsaasSplitValidationError("limite_split_asaas_invalido")
    try:
        limit = int(value)
    except (TypeError, ValueError):
        raise AsaasSplitValidationError("limite_split_asaas_invalido")
    if limit < 0:
        raise AsaasSplitValidationError("limite_split_asaas_invalido")
    return limit


def _load_asaas_domain_rules(
    cursor: Any,
    *,
    venda_id: int,
    unidade: str,
    environment: str,
    tipo_odontograma_id: int,
    dentista_id: Optional[int],
    usuario_venda_id: Optional[int],
) -> List[AsaasDomainSplitRule]:
    """Le regras e wallets sem consultar estado de outra adquirente.

    Para PF, somente o vendedor elegivel e o gerente condicional da mesma
    unidade podem ser selecionados. Uma regra selecionada sem usuario ou sem
    wallet continua no retorno para que o builder bloqueie a operacao.
    """
    del venda_id, dentista_id
    if not usuario_venda_id:
        raise AsaasSplitValidationError("vendedor_asaas_ausente")

    sandbox = str(environment).strip().casefold() == "sandbox"
    cursor.execute(
        """
        SELECT id, cargo_id, {wallet_column}
          FROM users
         WHERE id = %s
           AND unidade = %s
           AND cargo_id IN (3, 4)
           {integration_predicate}
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
        """.format(
            wallet_column="NULL::text",
            integration_predicate="",
        ),
        (int(usuario_venda_id), str(unidade)),
    )
    seller = cursor.fetchone()
    if not seller:
        raise AsaasSplitValidationError("vendedor_asaas_nao_elegivel_na_unidade")

    seller_id, seller_cargo, seller_wallet = seller
    seller_cargo = int(seller_cargo)

    cursor.execute(
        """
        SELECT max_cargos, max_empresas
          FROM config_limite_split
         WHERE tipo_odontograma_id = %s
         LIMIT 1
        """,
        (int(tipo_odontograma_id),),
    )
    limits = cursor.fetchone()
    max_cargos = _coerce_receiver_limit(
        limits[0] if limits else None,
        default=3,
    )
    max_empresas = _coerce_receiver_limit(
        limits[1] if limits else None,
        default=1,
    )

    target_cargos = [seller_cargo]
    if seller_cargo == 3:
        target_cargos.append(4)

    rules: List[AsaasDomainSplitRule] = []
    for cargo_id in target_cargos[:max_cargos]:
        rule_row = _fetch_rule_for_cargo(
            cursor,
            tipo_odontograma_id=int(tipo_odontograma_id),
            cargo_id=int(cargo_id),
            unidade=str(unidade),
        )
        if not rule_row:
            raise AsaasSplitValidationError(
                "regra_split_asaas_obrigatoria_ausente"
            )

        if cargo_id == seller_cargo:
            selected_user_id = int(seller_id)
            selected_wallet = None
        else:
            cursor.execute(
                """
                SELECT id, {wallet_column}
                  FROM users
                 WHERE cargo_id = %s
                   AND unidade = %s
                   {integration_predicate}
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
                 LIMIT 2
                """.format(
                    wallet_column="NULL::text",
                    integration_predicate="",
                ),
                (int(cargo_id), str(unidade)),
            )
            receivers = cursor.fetchall() or []
            if len(receivers) > 1:
                raise AsaasSplitValidationError("gerente_asaas_ambiguo")
            receiver = receivers[0] if receivers else None
            selected_user_id = int(receiver[0]) if receiver else None
            selected_wallet = None

        percentual, fixed, cycles, absorber = _rule_values(rule_row)
        rules.append(
            AsaasDomainSplitRule(
                wallet_id=selected_wallet,
                cargo_id=int(cargo_id),
                user_id=selected_user_id,
                percentual_value=percentual,
                fixed_value=fixed,
                cycles_to_participate=cycles,
                absorbs_balance=absorber,
            )
        )

    if max_empresas > 0:
        cursor.execute(
            """
            SELECT selecionada.empresa_id,
                   selecionada.percentual,
                   selecionada.tipo_calculo,
                   selecionada.valor_fixo_brl,
                   selecionada.ciclos_participacao,
                   selecionada.absorve_saldo
              FROM (
                    SELECT DISTINCT ON (ers.empresa_id)
                           ers.empresa_id,
                           ers.percentual,
                           ers.tipo_calculo,
                           ers.valor_fixo_brl,
                           ers.ciclos_participacao,
                           ers.absorve_saldo,
                           CASE
                               WHEN ers.unidade = %s THEN 0
                               ELSE 1
                           END AS prioridade_unidade,
                           pes.ordem_prioridade,
                           ers.id AS regra_id
                      FROM empresa_regras_split ers
                      JOIN participacao_empresa_split pes
                        ON pes.tipo_odontograma_id =
                           ers.tipo_odontograma_id
                       AND pes.empresa_id = ers.empresa_id
                     WHERE ers.tipo_odontograma_id = %s
                       AND ers.ativo = TRUE
                       AND pes.ativo = TRUE
                       AND (ers.unidade = %s OR ers.unidade IS NULL)
                     ORDER BY ers.empresa_id,
                              CASE
                                  WHEN ers.unidade = %s THEN 0
                                  ELSE 1
                              END,
                              pes.ordem_prioridade,
                              ers.id
                   ) AS selecionada
             ORDER BY selecionada.prioridade_unidade,
                      selecionada.ordem_prioridade,
                      selecionada.regra_id
             LIMIT %s
            """,
            (
                str(unidade),
                int(tipo_odontograma_id),
                str(unidade),
                str(unidade),
                int(max_empresas),
            ),
        )
        for row in cursor.fetchall() or []:
            empresa_id, percentual, tipo_calculo, fixed, cycles, absorber = row
            values = _rule_values(
                (percentual, tipo_calculo, fixed, cycles, absorber)
            )
            rules.append(
                AsaasDomainSplitRule(
                    # The identity resolver is authoritative for new sales in
                    # both environments.  In particular, sandbox PF must not
                    # inherit legacy users.asaas_* state or an env wallet.
                    wallet_id=None,
                    empresa_id=int(empresa_id),
                    percentual_value=values[0],
                    fixed_value=values[1],
                    cycles_to_participate=values[2],
                    absorbs_balance=values[3],
                )
            )

    return rules


def consume_entry_cycle(
    rules: Sequence[AsaasDomainSplitRule],
) -> List[AsaasDomainSplitRule]:
    """Consome um ciclo finito sem transferir valor para outro recebedor."""
    remaining: List[AsaasDomainSplitRule] = []
    for rule in rules:
        cycles = rule.cycles_to_participate
        if rule.absorbs_balance:
            remaining.append(rule)
        elif cycles is None or cycles >= _INDEFINITE_CYCLES:
            remaining.append(rule)
        elif cycles > 1:
            remaining.append(replace(rule, cycles_to_participate=cycles - 1))
    return remaining


def _rule_to_item(
    rule: AsaasDomainSplitRule,
    *,
    contexto: str,
    charge_value: Decimal,
    remaining_installments: int,
) -> AsaasSplitItem:
    if not rule.wallet_id:
        raise AsaasSplitValidationError("recebedor_obrigatorio_sem_wallet")

    percentage = _to_decimal(rule.percentual_value)
    fixed = _to_decimal(rule.fixed_value)
    if (percentage is None) == (fixed is None):
        raise AsaasSplitValidationError("regra_deve_ter_um_unico_tipo_valor")

    cycles = rule.cycles_to_participate
    finite = cycles is not None and cycles < _INDEFINITE_CYCLES
    if contexto in _RECURRING_CONTEXTS and (fixed is not None or finite):
        raise AsaasSplitValidationError(
            "regra_nao_representavel_em_recorrencia"
        )

    common = {
        "wallet_id": str(rule.wallet_id),
        "cargo_id": rule.cargo_id,
        "user_id": rule.user_id,
        "empresa_id": rule.empresa_id,
        "cycles_to_participate": cycles,
    }

    if percentage is not None:
        if percentage <= 0:
            raise AsaasSplitValidationError("valor_split_deve_ser_positivo")
        if contexto == "carne" and finite:
            participating = min(int(cycles), int(remaining_installments))
            aggregate = (
                charge_value
                * percentage
                / Decimal("100")
                * Decimal(participating)
                / Decimal(remaining_installments)
            )
            return AsaasSplitItem(
                **common,
                kind="total_fixed",
                total_fixed_value=_money(aggregate),
            )
        return AsaasSplitItem(
            **common,
            kind="percentual",
            percentual_value=percentage,
        )

    if fixed is None or fixed <= 0:
        raise AsaasSplitValidationError("valor_split_deve_ser_positivo")
    aggregate_fixed = fixed
    if contexto == "carne":
        participating = (
            min(int(cycles), int(remaining_installments))
            if finite
            else int(remaining_installments)
        )
        aggregate_fixed = fixed * Decimal(participating)
    return AsaasSplitItem(
        **common,
        kind="total_fixed",
        total_fixed_value=_money(aggregate_fixed),
    )


def _allocated_value(item: AsaasSplitItem, charge_value: Decimal) -> Decimal:
    if item.kind == "percentual":
        return charge_value * Decimal(item.percentual_value) / Decimal("100")
    return Decimal(item.total_fixed_value)


def _metadata_for_rule(rule: AsaasDomainSplitRule) -> Mapping[str, Any]:
    return {
        "cargo_id": rule.cargo_id,
        "user_id": rule.user_id,
        "empresa_id": rule.empresa_id,
        "wallet_id": rule.wallet_id,
        "percentual_value": (
            str(rule.percentual_value)
            if rule.percentual_value is not None
            else None
        ),
        "fixed_value": (
            str(rule.fixed_value) if rule.fixed_value is not None else None
        ),
        "cycles_to_participate": rule.cycles_to_participate,
        "absorbs_balance": rule.absorbs_balance,
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _plan_to_json(plan: AsaasSplitPlan) -> dict[str, Any]:
    if type(plan.schema_version) is not int or plan.schema_version not in {1, 2}:
        raise AsaasSplitValidationError("snapshot_schema_version_invalida")
    if plan.schema_version == 2 and any(
        item.receiver_identity is None for item in plan.items
    ):
        raise AsaasSplitValidationError("snapshot_identidade_invalida")
    def item_json(item: AsaasSplitItem) -> dict[str, Any]:
        payload = {
            "wallet_id": item.wallet_id,
            "kind": item.kind,
            "cargo_id": item.cargo_id,
            "user_id": item.user_id,
            "empresa_id": item.empresa_id,
            "percentual_value": (
                str(item.percentual_value)
                if item.percentual_value is not None
                else None
            ),
            "total_fixed_value": (
                str(item.total_fixed_value)
                if item.total_fixed_value is not None
                else None
            ),
            "cycles_to_participate": item.cycles_to_participate,
        }
        if item.receiver_identity is not None:
            identity = item.receiver_identity
            payload["receiver_identity"] = {
                "kind": identity.kind,
                "local_id": identity.local_id,
                "unidade": identity.unidade,
                "environment": identity.environment,
                "account_id": identity.account_id,
                "wallet_id": identity.wallet_id,
                "credential_ref": identity.credential_ref,
            }
        return payload

    absorber = None
    if plan.absorber is not None:
        absorber = {
            "wallet_id": plan.absorber.wallet_id,
            "absorbed_value": str(plan.absorber.absorbed_value),
            "cargo_id": plan.absorber.cargo_id,
            "user_id": plan.absorber.user_id,
            "empresa_id": plan.absorber.empresa_id,
            "cycles_to_participate": (
                plan.absorber.cycles_to_participate
            ),
        }
    serialized = {
        "contexto": plan.contexto,
        "items": [item_json(item) for item in plan.items],
        "absorber": absorber,
        "raw_metadata": list(plan.raw_metadata),
        "omissos": [
            {
                "cargo_id": omitted.cargo_id,
                "user_id": omitted.user_id,
                "empresa_id": omitted.empresa_id,
                "motivo": omitted.motivo,
            }
            for omitted in plan.omissos
        ],
    }
    if plan.schema_version == 2:
        serialized["schema_version"] = 2
    return serialized


def _validate_new_v2_plan_scope(
    plan: AsaasSplitPlan,
    *,
    unidade: str,
    environment: str,
) -> None:
    """V2 is the only format that may be sealed for a newly accepted sale."""
    if type(plan.schema_version) is not int or plan.schema_version != 2:
        raise AsaasSplitValidationError("snapshot_novo_requer_identidade_v2")
    for item in plan.items:
        identity = item.receiver_identity
        expected_kind = "pf" if item.user_id is not None else "empresa"
        expected_local_id = item.user_id if expected_kind == "pf" else item.empresa_id
        if (
            identity is None
            or type(expected_local_id) is not int
            or expected_local_id <= 0
            or identity.kind != expected_kind
            or type(identity.local_id) is not int
            or identity.local_id <= 0
            or identity.local_id != expected_local_id
            or identity.wallet_id != item.wallet_id
            or identity.unidade != unidade
            or identity.environment != environment
            or not identity.account_id
            or not identity.credential_ref
            or (expected_kind == "pf" and item.empresa_id is not None)
            or (expected_kind == "empresa" and item.user_id is not None)
        ):
            raise AsaasSplitValidationError("snapshot_identidade_escopo_divergente")


def _validate_new_v2_payload(
    plan: AsaasSplitPlan,
    payload: Sequence[Mapping[str, Any]],
) -> None:
    """The remote payload must be exactly the authenticated v2 plan."""
    expected = to_asaas_payload(plan, plan.contexto)
    try:
        candidate = [dict(item) for item in payload]
    except (TypeError, ValueError):
        raise AsaasSplitValidationError("snapshot_payload_split_divergente") from None
    if _canonical_json(candidate) != _canonical_json(expected):
        raise AsaasSplitValidationError("snapshot_payload_split_divergente")


def validate_asaas_new_split_preview(
    plan: AsaasSplitPlan,
    payload: Sequence[Mapping[str, Any]],
    *,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    charge_value: Any,
    contexto: str,
) -> None:
    """Validates the exact v2 artefact before a sale transaction writes.

    This boundary intentionally has no persistence side effect, so a malformed
    callback cannot leave a local sale/outbox behind.
    """
    if plan.contexto != contexto:
        raise AsaasSplitValidationError("snapshot_split_contexto_divergente")
    _validate_new_v2_plan_scope(plan, unidade=unidade, environment=environment)
    if any(item.wallet_id == account_wallet_id for item in plan.items):
        raise AsaasSplitValidationError("auto_split_conta_emissora")
    if _to_decimal(charge_value) is None or _to_decimal(charge_value) <= 0:
        raise AsaasSplitValidationError("snapshot_split_valor_invalido")
    _validate_new_v2_payload(plan, payload)


def _json_to_plan(value: Mapping[str, Any]) -> AsaasSplitPlan:
    schema_version = value.get("schema_version", 1)
    if type(schema_version) is not int or schema_version not in {1, 2}:
        raise AsaasSplitValidationError("snapshot_schema_version_invalida")

    def identity_for(item: Mapping[str, Any]) -> Optional[AsaasReceiverIdentity]:
        identity = item.get("receiver_identity")
        if schema_version == 1:
            if identity is not None:
                raise AsaasSplitValidationError("snapshot_identidade_invalida")
            return None
        if not isinstance(identity, Mapping) or set(identity) != {
            "kind", "local_id", "unidade", "environment", "account_id",
            "wallet_id", "credential_ref",
        }:
            raise AsaasSplitValidationError("snapshot_identidade_invalida")
        if (
            identity["kind"] not in {"pf", "empresa"}
            or type(identity["local_id"]) is not int
            or identity["local_id"] <= 0
            or any(not isinstance(identity[field], str) or not identity[field] for field in (
                "unidade", "environment", "account_id", "wallet_id", "credential_ref"
            ))
        ):
            raise AsaasSplitValidationError("snapshot_identidade_invalida")
        return AsaasReceiverIdentity(**identity)

    items = [
        AsaasSplitItem(
            wallet_id=str(item["wallet_id"]),
            kind=str(item["kind"]),
            cargo_id=item.get("cargo_id"),
            user_id=item.get("user_id"),
            empresa_id=item.get("empresa_id"),
            percentual_value=_to_decimal(item.get("percentual_value")),
            total_fixed_value=_to_decimal(item.get("total_fixed_value")),
            cycles_to_participate=item.get("cycles_to_participate"),
            receiver_identity=identity_for(item),
        )
        for item in value.get("items", [])
    ]
    absorber_data = value.get("absorber")
    absorber = None
    if absorber_data:
        absorbed_value = _to_decimal(absorber_data.get("absorbed_value"))
        if absorbed_value is None:
            raise AsaasSplitValidationError("snapshot_absorvedor_invalido")
        absorber = AsaasBalanceAbsorber(
            wallet_id=str(absorber_data["wallet_id"]),
            absorbed_value=absorbed_value,
            cargo_id=absorber_data.get("cargo_id"),
            user_id=absorber_data.get("user_id"),
            empresa_id=absorber_data.get("empresa_id"),
            cycles_to_participate=absorber_data.get(
                "cycles_to_participate"
            ),
        )
    return AsaasSplitPlan(
        items=items,
        contexto=str(value["contexto"]),
        absorber=absorber,
        raw_metadata=list(value.get("raw_metadata", [])),
        omissos=[
            AsaasOmittedReceiver(
                cargo_id=item.get("cargo_id"),
                user_id=item.get("user_id"),
                empresa_id=item.get("empresa_id"),
                motivo=str(item["motivo"]),
            )
            for item in value.get("omissos", [])
        ],
        schema_version=int(schema_version),
    )


def _as_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _snapshot_from_row(
    row: Any,
    *,
    integration_id: int,
    expected_venda_id: int,
    expected_payment_method: str,
    expected_context: str,
    expected_unidade: str,
    expected_environment: str,
    expected_account_wallet_id: str,
    expected_charge_value: Any,
) -> AsaasSealedSplitSnapshot:
    def column(name: str, index: int) -> Any:
        return row[name] if isinstance(row, Mapping) else row[index]

    stored_charge_value = _to_decimal(column("charge_value", 6))
    expected_charge = _to_decimal(expected_charge_value)
    if (
        int(column("venda_id", 0)) != int(expected_venda_id)
        or str(column("payment_method", 1)) != expected_payment_method
        or str(column("contexto", 2)) != expected_context
        or str(column("unidade", 3)) != expected_unidade
        or str(column("environment", 4)) != expected_environment
        or str(column("account_wallet_id", 5))
        != expected_account_wallet_id
        or stored_charge_value is None
        or expected_charge is None
        or _money(stored_charge_value) != _money(expected_charge)
    ):
        raise AsaasSplitValidationError("snapshot_split_escopo_divergente")

    plan_json = _as_json_value(column("plan_json", 7))
    payload_json = _as_json_value(column("payload_json", 8))
    stored_plan_hash = str(column("plan_sha256", 9))
    stored_payload_hash = str(column("payload_sha256", 10))
    if (
        _sha256_json(plan_json) != stored_plan_hash
        or _sha256_json(payload_json) != stored_payload_hash
    ):
        raise AsaasSplitValidationError("snapshot_split_hash_divergente")
    plan = _json_to_plan(plan_json)
    if plan.schema_version == 2:
        _validate_new_v2_payload(plan, payload_json)
        for item in plan.items:
            identity = item.receiver_identity
            local_id = item.user_id if identity and identity.kind == "pf" else (
                item.empresa_id if identity else None
            )
            if (
                identity is None
                or identity.wallet_id != item.wallet_id
                or identity.unidade != expected_unidade
                or identity.environment != expected_environment
                or local_id != identity.local_id
                or (identity.kind == "pf" and item.empresa_id is not None)
                or (identity.kind == "empresa" and item.user_id is not None)
            ):
                raise AsaasSplitValidationError("snapshot_identidade_escopo_divergente")
    return AsaasSealedSplitSnapshot(
        integration_id=int(integration_id),
        plan=plan,
        payload=list(payload_json),
        plan_sha256=stored_plan_hash,
        payload_sha256=stored_payload_hash,
        lifecycle_state=str(column("lifecycle_state", 11)),
    )


def load_asaas_split_snapshot(
    cursor: Any,
    *,
    integration_id: int,
    venda_id: int,
    payment_method: str,
    contexto: str,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    charge_value: Any,
) -> Optional[AsaasSealedSplitSnapshot]:
    """Carrega e verifica o artefato selado de uma tentativa anterior."""
    cursor.execute(
        """
        SELECT venda_id, payment_method, contexto, unidade, environment,
               account_wallet_id, charge_value, plan_json, payload_json,
               plan_sha256, payload_sha256, lifecycle_state
          FROM asaas_sale_split_plans
         WHERE integration_id = %s
         LIMIT 1
        """,
        (int(integration_id),),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _snapshot_from_row(
        row,
        integration_id=int(integration_id),
        expected_venda_id=int(venda_id),
        expected_payment_method=str(payment_method),
        expected_context=str(contexto),
        expected_unidade=str(unidade),
        expected_environment=str(environment),
        expected_account_wallet_id=str(account_wallet_id),
        expected_charge_value=charge_value,
    )


def seal_asaas_split_snapshot(
    cursor: Any,
    *,
    integration_id: int,
    venda_id: int,
    payment_method: str,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    charge_value: Any,
    plan: AsaasSplitPlan,
    payload: Sequence[Mapping[str, Any]],
) -> AsaasSealedSplitSnapshot:
    """Insere uma vez; numa corrida, devolve e verifica o plano vencedor."""
    validate_asaas_new_split_preview(
        plan,
        payload,
        unidade=str(unidade),
        environment=str(environment),
        account_wallet_id=str(account_wallet_id),
        charge_value=charge_value,
        contexto=plan.contexto,
    )
    plan_json = _plan_to_json(plan)
    payload_json = [dict(item) for item in payload]
    plan_hash = _sha256_json(plan_json)
    payload_hash = _sha256_json(payload_json)
    cursor.execute(
        """
        INSERT INTO asaas_sale_split_plans (
            integration_id, venda_id, payment_method, contexto, unidade,
            environment, account_wallet_id, charge_value, plan_json,
            payload_json, plan_sha256, payload_sha256, lifecycle_state
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
            %s, %s, 'sealed'
        )
        ON CONFLICT (integration_id) DO NOTHING
        RETURNING venda_id, payment_method, contexto, unidade, environment,
                  account_wallet_id, charge_value, plan_json, payload_json,
                  plan_sha256, payload_sha256, lifecycle_state
        """,
        (
            int(integration_id),
            int(venda_id),
            str(payment_method),
            str(plan.contexto),
            str(unidade),
            str(environment),
            str(account_wallet_id),
            str(_money(Decimal(str(charge_value)))),
            _canonical_json(plan_json),
            _canonical_json(payload_json),
            plan_hash,
            payload_hash,
        ),
    )
    row = cursor.fetchone()
    if row is None:
        return load_asaas_split_snapshot(
            cursor,
            integration_id=int(integration_id),
            venda_id=int(venda_id),
            payment_method=str(payment_method),
            contexto=plan.contexto,
            unidade=str(unidade),
            environment=str(environment),
            account_wallet_id=str(account_wallet_id),
            charge_value=charge_value,
        ) or (_raise_missing_snapshot())
    return _snapshot_from_row(
        row,
        integration_id=int(integration_id),
        expected_venda_id=int(venda_id),
        expected_payment_method=str(payment_method),
        expected_context=plan.contexto,
        expected_unidade=str(unidade),
        expected_environment=str(environment),
        expected_account_wallet_id=str(account_wallet_id),
        expected_charge_value=charge_value,
    )


def _raise_missing_snapshot() -> NoReturn:
    raise AsaasSplitValidationError("snapshot_split_nao_persistido")


def validate_asaas_absorber_rules(
    rules: Sequence[AsaasDomainSplitRule], *, account_wallet_id: Optional[str]
) -> Optional[AsaasDomainSplitRule]:
    """Shared non-financial invariant for selected effective split rules."""
    absorbers = [rule for rule in rules if rule.absorbs_balance]
    if len(absorbers) > 1:
        raise AsaasSplitValidationError("mais_de_um_absorvedor_de_saldo")
    absorber = absorbers[0] if absorbers else None
    if absorber:
        wallet = _clean_wallet(absorber.wallet_id)
        root = _clean_wallet(account_wallet_id)
        if not wallet:
            raise AsaasSplitValidationError("absorvedor_obrigatorio_sem_wallet")
        if not root:
            raise AsaasSplitValidationError("wallet_conta_emissora_ausente")
        if wallet != root:
            raise AsaasSplitValidationError("absorvedor_externo_nao_suportado")
    return absorber


def build_asaas_split_for_sale(
    cursor: Any,
    *,
    venda_id: Optional[int],
    unidade: str,
    environment: str,
    tipo_odontograma_id: int,
    dentista_id: Optional[int],
    usuario_venda_id: Optional[int],
    valor_liquido_total: Any,
    tem_entrada: bool,
    contexto: str = "carne",
    account_wallet_id: Optional[str] = None,
    remaining_installments: int = 1,
    receiver_identity_resolver: Optional[
        Callable[[str, int, str, str, str], AsaasReceiverIdentity]
    ] = None,
    receiver_identity_for_new_sale_resolver: Optional[
        Callable[[str, int, str, str], AsaasReceiverIdentity]
    ] = None,
    frozen_receiver_identities: Optional[
        Mapping[tuple[str, int], AsaasReceiverIdentity]
    ] = None,
    domain_rules: Optional[Sequence[AsaasDomainSplitRule]] = None,
) -> AsaasSplitPlan:
    """Constroi um plano deterministico ou bloqueia antes da chamada remota."""
    if not is_asaas_sandbox_ni_odontogram_type_available(
        unidade, environment, tipo_odontograma_id
    ):
        raise AsaasSplitValidationError(
            "asaas_sandbox_ni_odontogram_type_unavailable"
        )
    if contexto not in ASAAS_SPLIT_CONTEXTS:
        raise AsaasSplitValidationError(f"contexto_invalido:{contexto}")

    charge_value = _to_decimal(valor_liquido_total)
    if charge_value is None or charge_value <= 0:
        raise AsaasSplitValidationError("valor_cobranca_invalido")
    try:
        installment_count = int(remaining_installments)
    except (TypeError, ValueError):
        raise AsaasSplitValidationError("parcelas_restantes_invalidas")
    if installment_count <= 0:
        raise AsaasSplitValidationError("parcelas_restantes_invalidas")

    # The entry and the remaining booklet are derived from one immutable
    # decision.  A caller that already read the domain rules may provide that
    # exact set; this avoids a second, potentially changed, configuration read.
    rules = list(domain_rules) if domain_rules is not None else _load_asaas_domain_rules(
        cursor,
        venda_id=venda_id,
        unidade=str(unidade),
        environment=str(environment),
        tipo_odontograma_id=int(tipo_odontograma_id),
        dentista_id=dentista_id,
        usuario_venda_id=usuario_venda_id,
    )
    if tem_entrada and contexto != "entrada":
        rules = consume_entry_cycle(rules)
    if not rules:
        raise AsaasSplitValidationError(
            "configuracao_split_asaas_ausente"
        )

    def frozen_identity(kind: str, local_id: int) -> AsaasReceiverIdentity:
        if frozen_receiver_identities is None:
            raise AsaasSplitValidationError("identidade_recebedor_asaas_ausente")
        identity = frozen_receiver_identities.get((kind, local_id))
        if identity is None:
            raise AsaasSplitValidationError("identidade_recebedor_asaas_ausente")
        return identity

    if frozen_receiver_identities is not None or receiver_identity_for_new_sale_resolver is not None:
        bound_rules: list[AsaasDomainSplitRule] = []
        for rule in rules:
            kind = "pf" if rule.user_id is not None and rule.empresa_id is None else "empresa"
            local_id = rule.user_id if kind == "pf" else rule.empresa_id
            if type(local_id) is not int:
                raise AsaasSplitValidationError("identidade_recebedor_asaas_invalida")
            identity = (
                frozen_identity(kind, local_id)
                if frozen_receiver_identities is not None
                else receiver_identity_for_new_sale_resolver(
                    kind, local_id, str(unidade), str(environment)
                )
            )
            if (
                identity.kind != kind or identity.local_id != local_id
                or identity.unidade != str(unidade) or identity.environment != str(environment)
            ):
                raise AsaasSplitValidationError("identidade_recebedor_asaas_divergente")
            bound_rules.append(replace(rule, wallet_id=identity.wallet_id))
        rules = bound_rules
    # Production never accepts a caller-supplied legacy wallet for a new
    # sale.  Sandbox likewise requires the provider whenever a live rule has
    # no sealed wallet; frozen identities above are the replay exception.
    elif str(environment).strip().casefold() == "production" or any(
        not rule.wallet_id for rule in rules
    ):
        raise AsaasSplitValidationError("identidade_recebedor_asaas_ausente")

    absorber_rule = validate_asaas_absorber_rules(rules, account_wallet_id=account_wallet_id)
    root_wallet = _clean_wallet(account_wallet_id)

    items = [
        _rule_to_item(
            rule,
            contexto=contexto,
            charge_value=charge_value,
            remaining_installments=installment_count,
        )
        for rule in rules
        if not rule.absorbs_balance
    ]

    if frozen_receiver_identities is not None or receiver_identity_resolver is not None:
        bound_items: list[AsaasSplitItem] = []
        for item in items:
            if item.user_id is not None and item.empresa_id is None:
                identity = (frozen_identity("pf", int(item.user_id))
                    if frozen_receiver_identities is not None else receiver_identity_resolver(
                        "pf", int(item.user_id), str(unidade), str(environment), item.wallet_id
                    ))
            elif item.empresa_id is not None and item.user_id is None:
                identity = (frozen_identity("empresa", int(item.empresa_id))
                    if frozen_receiver_identities is not None else receiver_identity_resolver(
                        "empresa", int(item.empresa_id), str(unidade), str(environment), item.wallet_id
                    ))
            else:
                raise AsaasSplitValidationError("identidade_recebedor_asaas_invalida")
            expected_kind = "pf" if item.user_id is not None else "empresa"
            expected_local_id = item.user_id if item.user_id is not None else item.empresa_id
            if (
                identity.wallet_id != item.wallet_id
                or identity.kind != expected_kind
                or identity.local_id != expected_local_id
                or identity.unidade != str(unidade)
                or identity.environment != str(environment)
            ):
                raise AsaasSplitValidationError("identidade_recebedor_asaas_divergente")
            bound_items.append(replace(item, receiver_identity=identity))
        items = bound_items

    wallets = [item.wallet_id for item in items]
    if len(wallets) != len(set(wallets)):
        raise AsaasSplitValidationError("wallet_duplicada_no_plano")
    if root_wallet and root_wallet in wallets:
        raise AsaasSplitValidationError("auto_split_conta_emissora")

    charge_money = _money(charge_value)
    allocated = _money(
        sum(
            (
                _money(_allocated_value(item, charge_money))
                for item in items
            ),
            Decimal("0"),
        )
    )
    if allocated > charge_money:
        raise AsaasSplitValidationError(
            f"alocacao_excede_valor:{allocated}>{charge_money}"
        )

    residual = charge_money - allocated
    if residual > Decimal("0") and not absorber_rule:
        raise AsaasSplitValidationError("saldo_residual_sem_absorvedor")

    absorber = None
    if absorber_rule:
        absorber = AsaasBalanceAbsorber(
            wallet_id=str(root_wallet),
            absorbed_value=residual,
            cargo_id=absorber_rule.cargo_id,
            user_id=absorber_rule.user_id,
            empresa_id=absorber_rule.empresa_id,
            cycles_to_participate=absorber_rule.cycles_to_participate,
        )

    return AsaasSplitPlan(
        items=items,
        contexto=contexto,
        absorber=absorber,
        raw_metadata=[_metadata_for_rule(rule) for rule in rules],
        schema_version=2 if receiver_identity_resolver is not None else 1,
    )


def to_asaas_payload(
    plan: AsaasSplitPlan,
    contexto: Optional[str] = None,
) -> List[dict]:
    """Serializa somente recebedores externos; sem campo de absorcao."""
    chosen_context = contexto or plan.contexto
    if chosen_context not in ASAAS_SPLIT_CONTEXTS:
        raise AsaasSplitValidationError(f"contexto_invalido:{chosen_context}")

    payload: List[dict] = []
    for item in plan.items:
        entry: dict[str, Any] = {"walletId": item.wallet_id}
        if item.kind == "percentual":
            if item.percentual_value is None or item.percentual_value <= 0:
                raise AsaasSplitValidationError("item_percentual_invalido")
            entry["percentualValue"] = float(
                normalize_percentage(item.percentual_value)
            )
        elif item.kind == "total_fixed":
            if item.total_fixed_value is None or item.total_fixed_value <= 0:
                raise AsaasSplitValidationError("item_fixed_invalido")
            field_name = (
                "fixedValue" if chosen_context == "entrada" else "totalFixedValue"
            )
            entry[field_name] = float(normalize_money(item.total_fixed_value))
        else:
            raise AsaasSplitValidationError("tipo_split_invalido")
        payload.append(entry)
    return payload


def persist_asaas_sale_splits(
    cursor: Any,
    plan: AsaasSplitPlan,
    *,
    venda_id: int,
    unidade: str,
    environment: str,
    account_wallet_id: str,
) -> None:
    """Mantem o registro por recebedor para compatibilidade operacional.

    O insert e append-only por venda/wallet. O snapshot imutavel da tentativa
    remota e persistido separadamente pelo worker.
    """
    for item in plan.items:
        cursor.execute(
            """
            INSERT INTO asaas_sale_splits (
                venda_id, unidade, environment, cargo_id, user_id,
                empresa_id, wallet_id, split_kind, percentual_value,
                total_fixed_value, remote_account_wallet_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (venda_id, wallet_id) DO NOTHING
            """,
            (
                int(venda_id),
                str(unidade),
                str(environment),
                item.cargo_id,
                item.user_id,
                item.empresa_id,
                str(item.wallet_id),
                str(item.kind),
                (
                    float(normalize_percentage(item.percentual_value))
                    if item.percentual_value is not None
                    else None
                ),
                (
                    float(normalize_money(item.total_fixed_value))
                    if item.total_fixed_value is not None
                    else None
                ),
                str(account_wallet_id),
            ),
        )
