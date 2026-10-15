"""Preflight offline e somente leitura da API independente de vendas Asaas."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence

import psycopg2

from app.asaas_sdk.environment import AsaasConfig
from app.asaas_sdk.exceptions import AsaasConfigurationError
from app.services.asaas_sale_database import (
    AsaasSaleDatabaseConfigError,
    DatabaseConnection,
)
from app.services.asaas_sales_config import (
    AsaasSalesConfigError,
    canonicalize_asaas_sales_unit,
    get_asaas_sales_operational_account_units,
    get_enabled_asaas_sales_carne_units,
    get_enabled_asaas_sales_credit_card_recurring_units,
    get_enabled_asaas_sales_entry_units,
    get_enabled_asaas_sales_pix_automatic_units,
    get_enabled_asaas_sales_units,
    is_asaas_sales_entry_split_policy_approved,
    is_asaas_sales_production_profile_enabled,
    is_asaas_sandbox_ni_odontogram_type_available,
    validate_asaas_sales_account_configuration,
    validate_asaas_sales_account_isolation,
)
from app.services.asaas_split_service import (
    AsaasSplitValidationError,
    _load_asaas_domain_rules,
    # Kept as a module attribute for compatibility with the read-only test
    # harness; Sandbox readiness never calls this legacy wallet resolver.
    resolve_asaas_company_wallet_mappings,
    validate_asaas_absorber_rules,
)
from app.services.asaas_receiver_identity_provider import (
    AsaasReceiverIdentityProvider,
    receiver_identity_provider_for_environment,
)


_REQUIRED_TABLE_PRIVILEGES: dict[str, tuple[str, ...]] = {}
_REQUIRED_COLUMN_PRIVILEGES = {
    "users": {
        "SELECT": (
            "id",
            "nome",
            "cpf",
            "email",
            "phone_country_code",
            "phone_area_code",
            "phone_number",
            "street",
            "street_number",
            "neighborhood",
            "zip_code",
            "birthdate",
            "cargo_id",
            "unidade",
            "status_aprovacao",
            "auth_version",
            "asaas_wallet_id",
            "asaas_account_id",
            "asaas_integration_status",
            "asaas_account_updated_at",
        ),
        "UPDATE": (
            "asaas_wallet_id",
            "asaas_account_id",
            "asaas_integration_status",
            "asaas_account_api_key_enc",
            "asaas_account_updated_at",
        ),
    },
    "pacientes": {
        "SELECT": ("paciente_id", "unidade", "updated_at"),
    },
    "dependentes": {
        "SELECT": ("dependente_id", "responsavel_paciente_id", "ativo"),
    },
    "dentistas": {
        "SELECT": ("id", "ativo"),
    },
    "odontogramas": {
        "SELECT": (
            "id",
            "paciente_id",
            "unidade",
            "tipo",
            "dependente_id",
            "ativo",
        ),
    },
    "odontograma_itens": {
        "SELECT": (
            "id",
            "odontograma_id",
            "produto_id",
            "valor_registrado",
        ),
    },
    "produtos": {
        "SELECT": ("id", "ativo", "valor"),
    },
    "tipos_odontograma": {
        "SELECT": ("id", "nome", "valor_base", "qtd_parcelas", "ativo"),
    },
    "pre_vendas_entradas": {
        "SELECT": (
            "pre_venda_id", "paciente_id", "dependente_id", "dentista_id",
            "unidade", "valor_solicitado", "valor_pago", "status",
            "expires_at", "metadata_json",
        ),
        "INSERT": (
            "pre_venda_id", "tipo_odontograma", "paciente_id", "dependente_id",
            "dentista_id", "unidade", "valor_solicitado", "valor_pago",
            "checkout_id", "checkout_url", "forma_pagamento_id", "status",
            "expires_at", "metadata_json",
        ),
        "UPDATE": (
            "valor_pago", "checkout_id", "checkout_url", "status", "updated_at",
        ),
    },
    "asaas_patient_customers": {
        "SELECT": (
            "id",
            "paciente_id",
            "unidade",
            "environment",
            "account_wallet_id",
            "status",
            "asaas_customer_id",
            "last_http_status",
            "last_error_code",
            "next_retry_at",
            "last_synced_patient_updated_at",
            "requested_patient_updated_at",
        ),
        "INSERT": (
            "paciente_id",
            "unidade",
            "environment",
            "account_wallet_id",
            "external_reference",
            "remote_creation_allowed",
        ),
        "UPDATE": (
            "unidade",
            "remote_creation_allowed",
            "requested_patient_updated_at",
            "status",
            "last_http_status",
            "last_error_code",
            "next_retry_at",
            "updated_at",
        ),
    },
    "patient_integration_jobs": {
        "SELECT": (
            "id",
            "paciente_id",
            "provider",
            "target_key",
            "environment",
            "patient_version",
            "status",
            "attempt_count",
            "last_http_status",
            "last_error_code",
            "last_attempt_at",
            "last_dispatched_at",
            "next_retry_at",
            "integrated_at",
            "created_at",
            "updated_at",
        ),
        "INSERT": (
            "paciente_id",
            "provider",
            "target_key",
            "environment",
            "patient_version",
            "status",
            "integrated_at",
        ),
        "UPDATE": (
            "status",
            "last_http_status",
            "last_error_code",
            "next_retry_at",
            "integrated_at",
            "updated_at",
        ),
    },
    "asaas_sale_discount_rules": {
        "SELECT": (
            "id",
            "unidade",
            "payment_method",
            "installment_min",
            "installment_max",
            "percentage",
            "active",
        ),
    },
    "vendas": {
        "SELECT": (
            "id",
            "documento_venda",
            "paciente_id",
            "odontograma_id",
            "unidade",
            "valor_liquido_total",
            "qtd_parcelas",
            "status_venda",
            "forma_pagamento_id",
            "valor_entrada",
            "pre_venda_id",
            "dentista_orcamentista_id",
            "usuario_venda_id",
            "valor_taxa_adesao",
            "entrada_automatica",
            "tipo_cobranca_inicial",
        ),
        "INSERT": (
            "documento_venda",
            "paciente_id",
            "dentista_orcamentista_id",
            "odontograma_id",
            "unidade",
            "data_venda",
            "valor_bruto_total",
            "valor_desconto_regra",
            "valor_desconto_solicitado",
            "valor_desconto_aprovado",
            "valor_liquido_total",
            "qtd_parcelas",
            "usuario_venda_id",
            "status_venda",
            "dependente_id",
            "valor_entrada",
            "tipo_cobranca_inicial",
            "entrada_automatica",
            "pre_venda_id",
        ),
        "UPDATE": ("status_venda",),
    },
    "venda_parcelas": {
        "SELECT": (
            "id",
            "venda_id",
            "numero_parcela",
            "valor_parcela",
            "data_vencimento",
            "status_parcela",
            "data_pagamento",
            "valor_pago",
        ),
        "INSERT": (
            "venda_id",
            "numero_parcela",
            "valor_parcela",
            "data_vencimento",
            "status_parcela",
            "documento_referencia",
        ),
    },
    "asaas_sale_integrations": {
        "SELECT": (
            "id",
            "venda_id",
            "asaas_patient_customer_id",
            "unidade",
            "environment",
            "account_wallet_id",
            "payment_method",
            "revision",
            "financial_fingerprint",
            "idempotency_key",
            "external_reference",
            "status",
            "last_error_code",
            "created_at",
            "updated_at",
            "request_fingerprint",
            "remote_creation_state",
            "remote_attempt_count",
            "remote_result_unknown_at",
            "remote_confirmed_at",
            "reconciliation_required",
        ),
        "INSERT": (
            "venda_id",
            "asaas_patient_customer_id",
            "unidade",
            "environment",
            "account_wallet_id",
            "payment_method",
            "revision",
            "financial_fingerprint",
            "idempotency_key",
            "external_reference",
        ),
        "UPDATE": (
            "request_fingerprint",
            "status",
            "remote_creation_state",
            "remote_attempt_count",
            "last_remote_attempt_at",
            "remote_result_unknown_at",
            "remote_confirmed_at",
            "reconciliation_required",
            "last_error_code",
            "updated_at",
        ),
    },
    "asaas_sale_resources": {
        "SELECT": (
            "id",
            "integration_id",
            "unidade",
            "environment",
            "account_wallet_id",
            "resource_type",
            "asaas_resource_id",
            "external_reference",
            "remote_status",
            "last_event_type",
            "last_event_at",
            "needs_reconciliation",
            "updated_at",
        ),
        "INSERT": (
            "integration_id",
            "unidade",
            "environment",
            "account_wallet_id",
            "resource_type",
            "asaas_resource_id",
            "external_reference",
            "remote_status",
        ),
        "UPDATE": (
            "remote_status",
            "last_event_type",
            "last_event_at",
            "needs_reconciliation",
            "updated_at",
        ),
    },
    "asaas_sale_webhook_events": {
        "SELECT": (
            "id",
            "unidade",
            "environment",
            "account_wallet_id",
            "event_id",
            "event_type",
            "technical_data",
            "resource_id",
            "status",
            "attempt_count",
            "last_error_code",
            "last_attempt_at",
            "next_retry_at",
            "processed_at",
            "received_at",
            "created_at",
            "updated_at",
        ),
        "INSERT": (
            "unidade",
            "environment",
            "account_wallet_id",
            "event_id",
            "event_type",
            "technical_data",
        ),
        "UPDATE": (
            "status",
            "attempt_count",
            "last_error_code",
            "last_attempt_at",
            "next_retry_at",
            "resource_id",
            "processed_at",
            "updated_at",
        ),
    },
    "asaas_sale_integration_jobs": {
        "SELECT": (
            "id",
            "integration_id",
            "webhook_event_id",
            "operation",
            "deduplication_key",
            "status",
            "attempt_count",
            "last_error_code",
            "last_attempt_at",
            "last_dispatched_at",
            "next_retry_at",
            "completed_at",
            "created_at",
            "updated_at",
        ),
        "INSERT": (
            "integration_id",
            "webhook_event_id",
            "operation",
            "deduplication_key",
        ),
        "UPDATE": (
            "status",
            "attempt_count",
            "last_error_code",
            "last_attempt_at",
            "last_dispatched_at",
            "next_retry_at",
            "completed_at",
            "updated_at",
        ),
    },
    "asaas_sale_items": {
        "INSERT": (
            "integration_id",
            "venda_id",
            "item_number",
            "product_id",
            "quantity",
            "unit_value",
            "total_value",
        ),
    },
    "asaas_sale_payment_links": {
        "SELECT": (
            "id",
            "integration_id",
            "venda_id",
            "resource_id",
            "numero_parcela",
        ),
        "INSERT": (
            "integration_id",
            "venda_id",
            "resource_id",
            "numero_parcela",
            "unidade",
            "environment",
            "account_wallet_id",
            "resource_type",
        ),
    },
    "asaas_entry_integrations": {
        "SELECT": (
            "id", "pre_venda_id", "asaas_patient_customer_id",
            "odontograma_id", "unidade", "environment", "account_wallet_id",
            "payment_method", "card_installments", "amount", "idempotency_key",
            "request_fingerprint", "external_reference", "status",
            "remote_creation_state", "remote_payment_id", "remote_status",
            "checkout_url", "remote_attempt_count", "last_error_code",
            "last_attempt_at", "paid_at", "created_at", "updated_at",
        ),
        "INSERT": (
            "pre_venda_id", "asaas_patient_customer_id", "odontograma_id",
            "unidade", "environment", "account_wallet_id", "payment_method",
            "card_installments", "amount", "idempotency_key",
            "request_fingerprint", "external_reference",
        ),
        "UPDATE": (
            "status", "remote_creation_state", "remote_payment_id",
            "remote_status", "checkout_url", "remote_attempt_count",
            "last_error_code", "last_attempt_at", "paid_at", "updated_at",
        ),
    },
    "asaas_entry_jobs": {
        "SELECT": (
            "id", "entry_integration_id", "operation", "status",
            "attempt_count", "last_error_code", "last_attempt_at",
            "last_dispatched_at", "next_retry_at", "completed_at",
            "created_at", "updated_at",
        ),
        "INSERT": ("entry_integration_id", "operation"),
        "UPDATE": (
            "status", "attempt_count", "last_error_code", "last_attempt_at",
            "last_dispatched_at", "next_retry_at", "completed_at", "updated_at",
        ),
    },
    "regras_split": {
        "SELECT": (
            "id",
            "tipo_odontograma_id",
            "cargo_id",
            "percentual",
            "tipo_calculo",
            "valor_fixo_brl",
            "ciclos_participacao",
            "absorve_saldo",
            "ativo",
            "unidade",
        ),
    },
    "participacao_cargo_split": {
        "SELECT": (
            "tipo_odontograma_id",
            "cargo_id",
            "ativo",
            "ordem_prioridade",
        ),
    },
    "config_limite_split": {
        "SELECT": (
            "tipo_odontograma_id",
            "max_cargos",
            "max_empresas",
        ),
    },
    "empresa_regras_split": {
        "SELECT": (
            "id",
            "empresa_id",
            "tipo_odontograma_id",
            "percentual",
            "tipo_calculo",
            "valor_fixo_brl",
            "ciclos_participacao",
            "absorve_saldo",
            "ativo",
            "unidade",
        ),
    },
    "participacao_empresa_split": {
        "SELECT": (
            "tipo_odontograma_id",
            "empresa_id",
            "ativo",
            "ordem_prioridade",
        ),
    },
    "asaas_sale_splits": {
        "SELECT": (
            "id",
            "venda_id",
            "unidade",
            "environment",
            "cargo_id",
            "user_id",
            "empresa_id",
            "wallet_id",
            "split_kind",
            "percentual_value",
            "total_fixed_value",
            "remote_account_wallet_id",
            "created_at",
        ),
        "INSERT": (
            "venda_id",
            "unidade",
            "environment",
            "cargo_id",
            "user_id",
            "empresa_id",
            "wallet_id",
            "split_kind",
            "percentual_value",
            "total_fixed_value",
            "remote_account_wallet_id",
        ),
    },
    "asaas_sale_split_plans": {
        "SELECT": (
            "id",
            "integration_id",
            "venda_id",
            "payment_method",
            "contexto",
            "unidade",
            "environment",
            "account_wallet_id",
            "charge_value",
            "plan_json",
            "payload_json",
            "plan_sha256",
            "payload_sha256",
            "lifecycle_state",
            "remote_attempt_count",
            "remote_started_at",
            "remote_confirmed_at",
            "remote_uncertain_at",
            "created_at",
            "updated_at",
        ),
        "INSERT": (
            "integration_id",
            "venda_id",
            "payment_method",
            "contexto",
            "unidade",
            "environment",
            "account_wallet_id",
            "charge_value",
            "plan_json",
            "payload_json",
            "plan_sha256",
            "payload_sha256",
            "lifecycle_state",
        ),
        "UPDATE": (
            "lifecycle_state",
            "remote_attempt_count",
            "remote_started_at",
            "remote_confirmed_at",
            "remote_uncertain_at",
            "updated_at",
        ),
    },
    "asaas_account_provision_attempts": {
        "SELECT": (
            "id",
            "user_id",
            "unidade",
            "environment",
            "attempt_token",
            "lifecycle_state",
            "remote_attempt_count",
            "updated_at",
        ),
        "INSERT": (
            "user_id",
            "unidade",
            "environment",
            "attempt_token",
            "lifecycle_state",
            "remote_attempt_count",
        ),
        "UPDATE": (
            "lifecycle_state",
            "remote_attempt_count",
            "last_error_code",
            "remote_started_at",
            "remote_confirmed_at",
            "remote_uncertain_at",
            "remote_rejected_at",
            "updated_at",
        ),
    },
}
_ALL_REQUIRED_TABLES = frozenset(
    {*_REQUIRED_TABLE_PRIVILEGES, *_REQUIRED_COLUMN_PRIVILEGES}
)
_TABLE_PRIVILEGES = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
)
_COLUMN_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "REFERENCES")
_PUBLIC_TABLE_PRIVILEGE_EXCEPTIONS = frozenset(
    {("contract_templates", "SELECT")}
)
_SANDBOX_RECEIVER_VIEW = "asaas_sandbox_receiver_link_metadata"
_SANDBOX_RECEIVER_FUNCTION = "asaas_get_verified_sandbox_receiver_cipher"
_ENTRY_SNAPSHOT_CONSUME_FUNCTION = "asaas_consume_entry_snapshot"
_RUNTIME_ROLE = "grupojf_asaas_sales_runtime"
_SANDBOX_RECEIVER_FUNCTION_BODY_SHA256 = "1d1f734230fd6ded382d340d8228937b0ff80b9896459a26a9917d20cf9b0024"
_ENTRY_SNAPSHOT_CONSUME_FUNCTION_BODY_SHA256 = "c7f04620c8dc76313cd25d3ba26f7cf7426b30c9b1104aceec824ca999467fbc"
_SANDBOX_RECEIVER_VIEW_COLUMNS = (
    "id", "user_id", "unidade", "environment", "account_id", "wallet_id",
    "credential_state",
)
_SANDBOX_RECEIVER_LINK_COLUMNS = set(_SANDBOX_RECEIVER_VIEW_COLUMNS) | {
    "credential_ciphertext",
}
_SANDBOX_RECEIVER_VIEW_DEFINITION_VARIANTS = (
    """
SELECT id, user_id, unidade, environment, account_id, wallet_id, credential_state
FROM public.asaas_receiver_environment_links
WHERE environment = 'sandbox'
""",
    """
SELECT id, user_id, unidade, environment, account_id, wallet_id, credential_state
FROM asaas_receiver_environment_links
WHERE environment = 'sandbox'
""",
    """
 SELECT id,
    user_id,
    unidade,
    environment,
    account_id,
    wallet_id,
    credential_state
   FROM asaas_receiver_environment_links
  WHERE environment::text = 'sandbox'::text;
""",
    """
SELECT asaas_receiver_environment_links.id, asaas_receiver_environment_links.user_id,
       asaas_receiver_environment_links.unidade, asaas_receiver_environment_links.environment,
       asaas_receiver_environment_links.account_id, asaas_receiver_environment_links.wallet_id,
       asaas_receiver_environment_links.credential_state
FROM public.asaas_receiver_environment_links
WHERE ((asaas_receiver_environment_links.environment)::text = 'sandbox'::text)
""",
    """
SELECT asaas_receiver_environment_links.id, asaas_receiver_environment_links.user_id,
       asaas_receiver_environment_links.unidade, asaas_receiver_environment_links.environment,
       asaas_receiver_environment_links.account_id, asaas_receiver_environment_links.wallet_id,
       asaas_receiver_environment_links.credential_state
FROM asaas_receiver_environment_links
WHERE ((asaas_receiver_environment_links.environment)::text = 'sandbox'::text)
""",
)
_REQUIRED_FUNCTION_OWNER_COLUMN_PRIVILEGES = {
    "vendas": {
        "SELECT": (
            "id",
            "documento_venda",
            "forma_pagamento_id",
            "status_venda",
            "odontograma_id",
        ),
    },
    "asaas_sale_integrations": {
        "SELECT": ("venda_id", "remote_creation_state"),
    },
    "asaas_receiver_environment_links": {
        "SELECT": (
            "id", "user_id", "unidade", "environment", "account_id",
            "wallet_id", "credential_state", "credential_ciphertext",
        ),
    },
    "asaas_entry_financial_snapshots": {
        "SELECT": ("entry_integration_id", "consumed_venda_id"),
        "UPDATE": ("consumed_venda_id",),
    },
}
_SEQUENCE_TABLES = (
    "asaas_patient_customers",
    "patient_integration_jobs",
    "vendas",
    "venda_parcelas",
    "asaas_sale_integrations",
    "asaas_sale_resources",
    "asaas_sale_webhook_events",
    "asaas_sale_integration_jobs",
    "asaas_sale_items",
    "asaas_sale_payment_links",
    "pre_vendas_entradas",
    "asaas_entry_integrations",
    "asaas_entry_jobs",
    "asaas_sale_splits",
    "asaas_sale_split_plans",
    "asaas_account_provision_attempts",
)
_REQUIRED_FUNCTIONS = frozenset(
    {
        "asaas_validate_sale_integration_parent",
        "asaas_guard_venda_odontograma",
        "asaas_protect_integrated_venda",
        "asaas_protect_integrated_venda_parcela",
    }
)
_REQUIRED_FUNCTION_BODY_SHA256 = {
    "asaas_guard_venda_odontograma": (
        "2bf3987dfab1ec7d1f3abf881f8a7536377711c72ea70dc0de1ad2bf33acb4c0"
    ),
    "asaas_protect_integrated_venda": (
        "ac60710ed8132b7921bc61ad1025c00eb2ffc43589793b44ec8e2e6c34e0d1ae"
    ),
    "asaas_protect_integrated_venda_parcela": (
        "bbe662d116dade6fde9b32c6f0926d7b650ccc0863844e8b550342fc87170c9e"
    ),
    "asaas_validate_sale_integration_parent": (
        "530d924f87ec811b3d2dac813b854302ccddad7c47087235004253bb4ecc3398"
    ),
}
_REQUIRED_TRIGGERS = {
    "trg_asaas_validate_sale_integration_parent": (
        "asaas_sale_integrations",
        "asaas_validate_sale_integration_parent",
        23,
        ("venda_id",),
    ),
    "trg_asaas_guard_venda_odontograma": (
        "vendas",
        "asaas_guard_venda_odontograma",
        23,
        ("documento_venda", "odontograma_id", "status_venda"),
    ),
    "trg_asaas_protect_integrated_venda": (
        "vendas",
        "asaas_protect_integrated_venda",
        27,
        (),
    ),
    "trg_asaas_protect_integrated_venda_parcela": (
        "venda_parcelas",
        "asaas_protect_integrated_venda_parcela",
        31,
        (),
    ),
}
_REQUIRED_CONSTRAINTS = {
    "fk_asaas_sale_integration_customer_scope": "asaas_sale_integrations",
    "uq_asaas_sale_integration_id_scope": "asaas_sale_integrations",
    "fk_asaas_sale_resource_integration_scope": "asaas_sale_resources",
    "uq_asaas_sale_resource_id_scope": "asaas_sale_resources",
    "chk_asaas_sale_webhook_retry_schedule": "asaas_sale_webhook_events",
    "chk_asaas_sale_webhook_processing_claim": "asaas_sale_webhook_events",
    "chk_asaas_sale_webhook_terminal_timestamp": "asaas_sale_webhook_events",
    "fk_asaas_sale_webhook_resource_scope": "asaas_sale_webhook_events",
    "chk_asaas_sale_job_single_subject": "asaas_sale_integration_jobs",
    "chk_asaas_sale_job_retry_schedule": "asaas_sale_integration_jobs",
    "chk_asaas_sale_job_processing_claim": "asaas_sale_integration_jobs",
    "chk_asaas_sale_job_terminal_timestamp": "asaas_sale_integration_jobs",
    "chk_asaas_sale_remote_attempt_metadata": "asaas_sale_integrations",
    "chk_asaas_sale_remote_state_attempts": "asaas_sale_integrations",
    "chk_asaas_sale_remote_uncertain_state": "asaas_sale_integrations",
    "chk_asaas_sale_remote_reconciliation_state": "asaas_sale_integrations",
    "chk_asaas_sale_remote_confirmation": "asaas_sale_integrations",
    "uq_asaas_sale_discount_rule_exact": "asaas_sale_discount_rules",
    "chk_asaas_sale_item_total": "asaas_sale_items",
    "fk_asaas_sale_item_integration_sale_scope": "asaas_sale_items",
    "fk_asaas_sale_item_product": "asaas_sale_items",
    "uq_asaas_sale_item_integration_number": "asaas_sale_items",
    "uq_asaas_sale_item_sale_number": "asaas_sale_items",
    "fk_asaas_sale_payment_link_integration_scope": (
        "asaas_sale_payment_links"
    ),
    "fk_asaas_sale_payment_link_resource_scope": "asaas_sale_payment_links",
    "fk_asaas_sale_payment_link_parcela_scope": "asaas_sale_payment_links",
    "uq_asaas_sale_payment_link_resource": "asaas_sale_payment_links",
    "uq_asaas_sale_payment_link_numero": "asaas_sale_payment_links",
    "fk_asaas_entry_customer_scope": "asaas_entry_integrations",
    "uq_asaas_entry_id_scope": "asaas_entry_integrations",
    "chk_asaas_entry_card_installments": "asaas_entry_integrations",
    "chk_asaas_entry_remote_identity": "asaas_entry_integrations",
    "chk_asaas_entry_job_retry": "asaas_entry_jobs",
    "chk_asaas_sale_splits_split_kind": "asaas_sale_splits",
    "chk_asaas_sale_splits_percentual_value": "asaas_sale_splits",
    "fk_asaas_sale_split_plan_integration_scope": (
        "asaas_sale_split_plans"
    ),
    "uq_asaas_sale_split_plans_integration": "asaas_sale_split_plans",
    "chk_asaas_sale_split_plans_context": "asaas_sale_split_plans",
    "chk_asaas_sale_split_plans_state": "asaas_sale_split_plans",
    "chk_asaas_sale_split_plans_charge": "asaas_sale_split_plans",
    "chk_asaas_sale_split_plans_attempt": "asaas_sale_split_plans",
    "chk_asaas_sale_split_plans_timeline": "asaas_sale_split_plans",
    "fk_asaas_account_provision_attempt_user": (
        "asaas_account_provision_attempts"
    ),
    "uq_asaas_account_provision_attempt_token": (
        "asaas_account_provision_attempts"
    ),
    "chk_asaas_account_provision_attempt_environment": (
        "asaas_account_provision_attempts"
    ),
    "chk_asaas_account_provision_attempt_state": (
        "asaas_account_provision_attempts"
    ),
    "chk_asaas_account_provision_attempt_count": (
        "asaas_account_provision_attempts"
    ),
    "chk_asaas_account_provision_attempt_timeline": (
        "asaas_account_provision_attempts"
    ),
}
_REQUIRED_CONSTRAINT_DEFINITIONS = {
    "chk_asaas_sale_item_total": (
        "CHECK (total_value = (unit_value * quantity::numeric))"
    ),
    "chk_asaas_sale_job_processing_claim": (
        "CHECK (status::text <> 'processando'::text OR attempt_count > 0 "
        "AND last_attempt_at IS NOT NULL)"
    ),
    "chk_asaas_sale_job_retry_schedule": (
        "CHECK ((status::text = 'retry'::text) = "
        "(next_retry_at IS NOT NULL))"
    ),
    "chk_asaas_sale_job_single_subject": (
        "CHECK (num_nonnulls(integration_id, webhook_event_id) = 1)"
    ),
    "chk_asaas_sale_job_terminal_timestamp": (
        "CHECK ((status::text = ANY (ARRAY['integrado'::character varying, "
        "'conflito'::character varying, 'erro_terminal'::character varying, "
        "'superseded'::character varying]::text[])) = "
        "(completed_at IS NOT NULL))"
    ),
    "chk_asaas_sale_remote_attempt_metadata": (
        "CHECK (remote_attempt_count = 0 AND last_remote_attempt_at IS NULL "
        "OR remote_attempt_count > 0 AND last_remote_attempt_at IS NOT NULL)"
    ),
    "chk_asaas_sale_remote_confirmation": (
        "CHECK ((remote_creation_state::text = 'confirmado'::text) = "
        "(remote_confirmed_at IS NOT NULL))"
    ),
    "chk_asaas_sale_remote_reconciliation_state": (
        "CHECK (reconciliation_required = "
        "(remote_creation_state::text = ANY "
        "(ARRAY['requisicao_iniciada'::character varying, "
        "'resultado_incerto'::character varying]::text[])))"
    ),
    "chk_asaas_sale_remote_state_attempts": (
        "CHECK (remote_creation_state::text = 'nao_iniciado'::text "
        "AND remote_attempt_count = 0 OR remote_creation_state::text = "
        "'requisicao_iniciada'::text AND remote_attempt_count > 0 OR "
        "(remote_creation_state::text = ANY "
        "(ARRAY['resultado_incerto'::character varying, "
        "'confirmado'::character varying, "
        "'falha_terminal'::character varying]::text[])))"
    ),
    "chk_asaas_sale_remote_uncertain_state": (
        "CHECK (remote_creation_state::text <> 'resultado_incerto'::text "
        "OR remote_result_unknown_at IS NOT NULL "
        "AND reconciliation_required)"
    ),
    "chk_asaas_sale_webhook_processing_claim": (
        "CHECK (status::text <> 'processando'::text OR attempt_count > 0 "
        "AND last_attempt_at IS NOT NULL)"
    ),
    "chk_asaas_sale_webhook_retry_schedule": (
        "CHECK ((status::text = 'retry'::text) = "
        "(next_retry_at IS NOT NULL))"
    ),
    "chk_asaas_sale_webhook_terminal_timestamp": (
        "CHECK ((status::text = ANY "
        "(ARRAY['processado'::character varying, "
        "'ignorado'::character varying, "
        "'erro_terminal'::character varying]::text[])) = "
        "(processed_at IS NOT NULL))"
    ),
    "fk_asaas_sale_integration_customer_scope": (
        "FOREIGN KEY (asaas_patient_customer_id, unidade, environment, "
        "account_wallet_id) REFERENCES asaas_patient_customers"
        "(id, unidade, environment, account_wallet_id) ON DELETE RESTRICT"
    ),
    "fk_asaas_sale_item_integration_sale_scope": (
        "FOREIGN KEY (integration_id, venda_id) REFERENCES "
        "asaas_sale_integrations(id, venda_id) ON DELETE RESTRICT"
    ),
    "fk_asaas_sale_item_product": (
        "FOREIGN KEY (product_id) REFERENCES produtos(id) ON DELETE RESTRICT"
    ),
    "fk_asaas_sale_payment_link_integration_scope": (
        "FOREIGN KEY (integration_id, venda_id, unidade, environment, "
        "account_wallet_id) REFERENCES asaas_sale_integrations"
        "(id, venda_id, unidade, environment, account_wallet_id) "
        "ON DELETE RESTRICT"
    ),
    "fk_asaas_sale_payment_link_parcela_scope": (
        "FOREIGN KEY (venda_id, numero_parcela) REFERENCES "
        "venda_parcelas(venda_id, numero_parcela) ON DELETE RESTRICT"
    ),
    "fk_asaas_sale_payment_link_resource_scope": (
        "FOREIGN KEY (resource_id, integration_id, unidade, environment, "
        "account_wallet_id, resource_type) REFERENCES asaas_sale_resources"
        "(id, integration_id, unidade, environment, account_wallet_id, "
        "resource_type) ON DELETE RESTRICT"
    ),
    "fk_asaas_sale_resource_integration_scope": (
        "FOREIGN KEY (integration_id, unidade, environment, "
        "account_wallet_id) REFERENCES asaas_sale_integrations"
        "(id, unidade, environment, account_wallet_id) ON DELETE RESTRICT"
    ),
    "fk_asaas_sale_webhook_resource_scope": (
        "FOREIGN KEY (resource_id, unidade, environment, account_wallet_id) "
        "REFERENCES asaas_sale_resources"
        "(id, unidade, environment, account_wallet_id) ON DELETE RESTRICT"
    ),
    "uq_asaas_sale_discount_rule_exact": (
        "UNIQUE (unidade, payment_method, installment_min, installment_max, "
        "percentage)"
    ),
    "uq_asaas_sale_integration_id_scope": (
        "UNIQUE (id, unidade, environment, account_wallet_id)"
    ),
    "uq_asaas_sale_item_integration_number": (
        "UNIQUE (integration_id, item_number)"
    ),
    "uq_asaas_sale_item_sale_number": "UNIQUE (venda_id, item_number)",
    "uq_asaas_sale_payment_link_numero": (
        "UNIQUE (integration_id, numero_parcela)"
    ),
    "uq_asaas_sale_payment_link_resource": "UNIQUE (resource_id)",
    "uq_asaas_sale_resource_id_scope": (
        "UNIQUE (id, unidade, environment, account_wallet_id)"
    ),
    "fk_asaas_entry_customer_scope": (
        "FOREIGN KEY (asaas_patient_customer_id, unidade, environment, "
        "account_wallet_id) REFERENCES asaas_patient_customers"
        "(id, unidade, environment, account_wallet_id) ON DELETE RESTRICT"
    ),
    "uq_asaas_entry_id_scope": (
        "UNIQUE (id, unidade, environment, account_wallet_id)"
    ),
    "chk_asaas_entry_card_installments": (
        "CHECK (payment_method::text = 'ASAAS_ENTRY_CREDIT_CARD'::text OR "
        "card_installments = 1)"
    ),
    "chk_asaas_entry_remote_identity": (
        "CHECK (remote_payment_id IS NULL AND checkout_url IS NULL OR "
        "remote_payment_id IS NOT NULL AND checkout_url IS NOT NULL)"
    ),
    "chk_asaas_entry_job_retry": (
        "CHECK ((status::text = 'retry'::text) = (next_retry_at IS NOT NULL))"
    ),
    "chk_asaas_sale_splits_split_kind": (
        "CHECK (split_kind::text = ANY"
        " (ARRAY['percentual'::character varying, "
        "'total_fixed'::character varying]::text[]))"
    ),
    "chk_asaas_sale_splits_percentual_value": (
        "CHECK (percentual_value >= 0::numeric AND "
        "percentual_value <= 100::numeric)"
    ),
    "fk_asaas_sale_split_plan_integration_scope": (
        "FOREIGN KEY (integration_id, venda_id, unidade, environment, "
        "account_wallet_id) REFERENCES asaas_sale_integrations"
        "(id, venda_id, unidade, environment, account_wallet_id) "
        "ON DELETE RESTRICT"
    ),
    "uq_asaas_sale_split_plans_integration": "UNIQUE (integration_id)",
    "chk_asaas_sale_split_plans_context": (
        "CHECK (contexto::text = ANY "
        "(ARRAY['carne'::character varying, 'pix'::character varying, "
        "'cartao'::character varying, "
        "'entrada'::character varying]::text[]))"
    ),
    "chk_asaas_sale_split_plans_state": (
        "CHECK (lifecycle_state::text = ANY "
        "(ARRAY['sealed'::character varying, 'started'::character varying, "
        "'confirmed'::character varying, "
        "'uncertain'::character varying, "
        "'blocked'::character varying, "
        "'rejected'::character varying]::text[]))"
    ),
    "chk_asaas_sale_split_plans_charge": (
        "CHECK (charge_value > 0::numeric)"
    ),
    "chk_asaas_sale_split_plans_attempt": (
        "CHECK (remote_attempt_count = ANY (ARRAY[0, 1]))"
    ),
    "chk_asaas_sale_split_plans_timeline": (
        "CHECK ((lifecycle_state::text = ANY "
        "(ARRAY['sealed'::character varying, "
        "'blocked'::character varying]::text[])) "
        "AND remote_attempt_count = 0 "
        "AND remote_started_at IS NULL "
        "AND remote_confirmed_at IS NULL "
        "AND remote_uncertain_at IS NULL "
        "OR (lifecycle_state::text = ANY "
        "(ARRAY['started'::character varying, "
        "'rejected'::character varying]::text[])) "
        "AND remote_attempt_count = 1 "
        "AND remote_started_at IS NOT NULL "
        "AND remote_confirmed_at IS NULL "
        "AND remote_uncertain_at IS NULL "
        "OR lifecycle_state::text = 'confirmed'::text "
        "AND remote_attempt_count = 1 "
        "AND remote_started_at IS NOT NULL "
        "AND remote_confirmed_at IS NOT NULL "
        "AND remote_confirmed_at >= remote_started_at "
        "AND remote_uncertain_at IS NULL "
        "OR lifecycle_state::text = 'uncertain'::text "
        "AND remote_attempt_count = 1 "
        "AND remote_started_at IS NOT NULL "
        "AND remote_confirmed_at IS NULL "
        "AND remote_uncertain_at IS NOT NULL "
        "AND remote_uncertain_at >= remote_started_at)"
    ),
    "fk_asaas_account_provision_attempt_user": (
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT"
    ),
    "uq_asaas_account_provision_attempt_token": "UNIQUE (attempt_token)",
    "chk_asaas_account_provision_attempt_environment": (
        "CHECK (environment::text = 'sandbox'::text)"
    ),
    "chk_asaas_account_provision_attempt_state": (
        "CHECK (lifecycle_state::text = ANY "
        "(ARRAY['reserved'::character varying, "
        "'started'::character varying, "
        "'confirmed'::character varying, "
        "'rejected'::character varying, "
        "'uncertain'::character varying]::text[]))"
    ),
    "chk_asaas_account_provision_attempt_count": (
        "CHECK (remote_attempt_count = ANY (ARRAY[0, 1]))"
    ),
    "chk_asaas_account_provision_attempt_timeline": (
        "CHECK (lifecycle_state::text = 'reserved'::text "
        "AND remote_attempt_count = 0 "
        "AND remote_started_at IS NULL "
        "AND remote_confirmed_at IS NULL "
        "AND remote_uncertain_at IS NULL "
        "AND remote_rejected_at IS NULL "
        "OR lifecycle_state::text = 'started'::text "
        "AND remote_attempt_count = 1 "
        "AND remote_started_at IS NOT NULL "
        "AND remote_confirmed_at IS NULL "
        "AND remote_uncertain_at IS NULL "
        "AND remote_rejected_at IS NULL "
        "OR lifecycle_state::text = 'confirmed'::text "
        "AND remote_attempt_count = 1 "
        "AND remote_started_at IS NOT NULL "
        "AND remote_confirmed_at IS NOT NULL "
        "AND remote_confirmed_at >= remote_started_at "
        "AND remote_uncertain_at IS NULL "
        "AND remote_rejected_at IS NULL "
        "OR lifecycle_state::text = 'rejected'::text "
        "AND remote_attempt_count = 1 "
        "AND remote_started_at IS NOT NULL "
        "AND remote_confirmed_at IS NULL "
        "AND remote_uncertain_at IS NULL "
        "AND remote_rejected_at IS NOT NULL "
        "AND remote_rejected_at >= remote_started_at "
        "OR lifecycle_state::text = 'uncertain'::text "
        "AND remote_attempt_count = 1 "
        "AND remote_started_at IS NOT NULL "
        "AND remote_confirmed_at IS NULL "
        "AND remote_uncertain_at IS NOT NULL "
        "AND remote_uncertain_at >= remote_started_at "
        "AND remote_rejected_at IS NULL)"
    ),
}
_REQUIRED_INDEXES = {
    "uq_asaas_entry_idempotency": (
        "asaas_entry_integrations", True,
        ("environment", "account_wallet_id", "idempotency_key"), None,
    ),
    "uq_asaas_entry_external_reference": (
        "asaas_entry_integrations", True,
        ("environment", "account_wallet_id", "external_reference"), None,
    ),
    "uq_asaas_entry_remote_payment": (
        "asaas_entry_integrations", True,
        ("environment", "account_wallet_id", "remote_payment_id"),
        "(remote_payment_id IS NOT NULL)",
    ),
    "idx_asaas_entry_dispatch": (
        "asaas_entry_integrations", False,
        ("unidade", "status", "updated_at"), None,
    ),
    "uq_asaas_entry_active_job": (
        "asaas_entry_jobs", True,
        ("entry_integration_id", "operation"),
        "((status)::text = ANY ((ARRAY['pendente'::character varying, "
        "'processando'::character varying, 'retry'::character varying])::text[]))",
    ),
    "idx_asaas_entry_job_dispatch": (
        "asaas_entry_jobs", False,
        ("status", "next_retry_at", "last_dispatched_at", "created_at"),
        "((status)::text = ANY ((ARRAY['pendente'::character varying, "
        "'retry'::character varying, 'processando'::character varying])::text[]))",
    ),
    "uq_vendas_asaas_pre_venda": (
        "vendas", True, ("pre_venda_id",),
        "((pre_venda_id)::text ~~ 'PV-AS-%'::text)",
    ),
    "uq_asaas_patient_customer_account": (
        "asaas_patient_customers",
        True,
        ("paciente_id", "environment", "account_wallet_id"),
        None,
    ),
    "uq_asaas_customer_remote_account": (
        "asaas_patient_customers",
        True,
        ("environment", "account_wallet_id", "asaas_customer_id"),
        "(asaas_customer_id IS NOT NULL)",
    ),
    "uq_asaas_customer_external_reference": (
        "asaas_patient_customers",
        True,
        ("environment", "account_wallet_id", "external_reference"),
        None,
    ),
    "uq_patient_integration_job_version": (
        "patient_integration_jobs",
        True,
        (
            "paciente_id",
            "provider",
            "target_key",
            "environment",
            "patient_version",
        ),
        None,
    ),
    "uq_patient_integration_job_active": (
        "patient_integration_jobs",
        True,
        ("paciente_id", "provider", "target_key", "environment"),
        "((status)::text = 'processando'::text)",
    ),
    "uq_asaas_patient_customer_id_scope": (
        "asaas_patient_customers",
        True,
        ("id", "unidade", "environment", "account_wallet_id"),
        None,
    ),
    "uq_asaas_sale_integration_sale_account": (
        "asaas_sale_integrations",
        True,
        ("venda_id", "environment", "account_wallet_id"),
        None,
    ),
    "uq_asaas_sale_integration_sale": (
        "asaas_sale_integrations",
        True,
        ("venda_id",),
        None,
    ),
    "uq_asaas_sale_integration_idempotency": (
        "asaas_sale_integrations",
        True,
        ("environment", "account_wallet_id", "idempotency_key"),
        None,
    ),
    "uq_asaas_sale_integration_external_reference": (
        "asaas_sale_integrations",
        True,
        ("environment", "account_wallet_id", "external_reference"),
        None,
    ),
    "idx_asaas_sale_integration_unit_status": (
        "asaas_sale_integrations",
        False,
        ("unidade", "status", "updated_at"),
        None,
    ),
    "uq_asaas_sale_resource_remote": (
        "asaas_sale_resources",
        True,
        (
            "environment",
            "account_wallet_id",
            "resource_type",
            "asaas_resource_id",
        ),
        None,
    ),
    "idx_asaas_sale_resource_integration": (
        "asaas_sale_resources",
        False,
        ("integration_id", "resource_type"),
        None,
    ),
    "idx_asaas_sale_resource_external_reference": (
        "asaas_sale_resources",
        False,
        ("environment", "account_wallet_id", "external_reference"),
        "(external_reference IS NOT NULL)",
    ),
    "uq_asaas_sale_webhook_event_account": (
        "asaas_sale_webhook_events",
        True,
        ("environment", "account_wallet_id", "event_id"),
        None,
    ),
    "idx_asaas_sale_webhook_dispatch": (
        "asaas_sale_webhook_events",
        False,
        ("status", "next_retry_at", "received_at"),
        (
            "((status)::text = ANY ((ARRAY['pendente'::character varying, "
            "'retry'::character varying])::text[]))"
        ),
    ),
    "uq_asaas_sale_job_deduplication": (
        "asaas_sale_integration_jobs",
        True,
        ("operation", "deduplication_key"),
        None,
    ),
    "uq_asaas_sale_job_active_subject": (
        "asaas_sale_integration_jobs",
        True,
        (
            "COALESCE(integration_id, 0)",
            "COALESCE(webhook_event_id, 0)",
            "operation",
        ),
        (
            "((status)::text = ANY ((ARRAY['pendente'::character varying, "
            "'processando'::character varying, "
            "'retry'::character varying])::text[]))"
        ),
    ),
    "idx_asaas_sale_job_dispatch": (
        "asaas_sale_integration_jobs",
        False,
        (
            "status",
            "next_retry_at",
            "last_dispatched_at",
            "created_at",
        ),
        (
            "((status)::text = ANY ((ARRAY['pendente'::character varying, "
            "'retry'::character varying])::text[]))"
        ),
    ),
    "idx_asaas_sale_job_stale_claim": (
        "asaas_sale_integration_jobs",
        False,
        ("status", "last_attempt_at"),
        "((status)::text = 'processando'::text)",
    ),
    "uq_asaas_sale_integration_carne_scope": (
        "asaas_sale_integrations",
        True,
        (
            "id",
            "venda_id",
            "unidade",
            "environment",
            "account_wallet_id",
        ),
        None,
    ),
    "uq_asaas_sale_integration_item_scope": (
        "asaas_sale_integrations",
        True,
        ("id", "venda_id"),
        None,
    ),
    "uq_asaas_sale_resource_carne_scope": (
        "asaas_sale_resources",
        True,
        (
            "id",
            "integration_id",
            "unidade",
            "environment",
            "account_wallet_id",
            "resource_type",
        ),
        None,
    ),
    "idx_asaas_sale_discount_rule_lookup": (
        "asaas_sale_discount_rules",
        False,
        (
            "unidade",
            "payment_method",
            "active",
            "installment_min",
            "installment_max",
        ),
        None,
    ),
    "idx_asaas_sale_item_product": (
        "asaas_sale_items",
        False,
        ("product_id",),
        None,
    ),
    "idx_asaas_sale_payment_link_venda": (
        "asaas_sale_payment_links",
        False,
        ("venda_id", "numero_parcela"),
        None,
    ),
    "uq_asaas_sale_splits_venda_wallet": (
        "asaas_sale_splits",
        True,
        ("venda_id", "wallet_id"),
        None,
    ),
    "idx_asaas_sale_splits_venda": (
        "asaas_sale_splits",
        False,
        ("venda_id",),
        None,
    ),
    "idx_asaas_sale_splits_unidade_env": (
        "asaas_sale_splits",
        False,
        ("unidade", "environment"),
        None,
    ),
    "idx_asaas_sale_split_plans_sale": (
        "asaas_sale_split_plans",
        False,
        ("venda_id",),
        None,
    ),
    "idx_asaas_account_provision_attempts_unit_state": (
        "asaas_account_provision_attempts",
        False,
        ("unidade", "lifecycle_state"),
        None,
    ),
    "uq_asaas_account_provision_attempt_active_user": (
        "asaas_account_provision_attempts",
        True,
        ("user_id",),
        "(lifecycle_state::text <> 'rejected'::text)",
    ),
}
_SANDBOX_APPLICATION_ENVIRONMENTS = frozenset(
    {"dev", "development", "sandbox", "staging", "test", "testing"}
)

# PostgreSQL 16 may render these two catalog expressions with additional,
# semantically-neutral cast parentheses. Keep these alternatives tied to the
# exact catalog objects rather than weakening the general catalog comparison.
_POSTGRESQL_16_INDEX_PREDICATE_VARIANTS = {
    "uq_asaas_account_provision_attempt_active_user": (
        "(lifecycle_state::text <> 'rejected'::text)",
        "((lifecycle_state)::text <> 'rejected'::text)",
    ),
}
_POSTGRESQL_16_CONSTRAINT_DEFINITION_VARIANTS = {
    "chk_asaas_account_provision_attempt_environment": (
        _REQUIRED_CONSTRAINT_DEFINITIONS[
            "chk_asaas_account_provision_attempt_environment"
        ],
        "CHECK (environment::text = ANY (ARRAY['sandbox'::character varying, "
        "'production'::character varying]::text[]))",
    ),
    "chk_asaas_sale_splits_split_kind": (
        _REQUIRED_CONSTRAINT_DEFINITIONS[
            "chk_asaas_sale_splits_split_kind"
        ],
        "CHECK (split_kind::text = ANY "
        "(ARRAY['percentual'::character varying::text, "
        "'total_fixed'::character varying::text]))",
    ),
}


class AsaasSalesPreflightError(RuntimeError):
    """Falha classificada que nunca carrega valores de credenciais."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


_PF_EXCLUSIONS_FILE_ENV = "ASAAS_SALES_PF_EXCLUSIONS_FILE"
_PF_EXCLUSIONS_SCHEMA_VERSION = 1
_PF_EXCLUSIONS_MAX_BYTES = 64 * 1024
_PF_EXCLUSION_REASON_MAX_LENGTH = 500


@dataclass(frozen=True)
class _PfExclusion:
    user_id: int
    unidade: str | None


@dataclass(frozen=True)
class AsaasSalesPreflightResult:
    units: tuple[str, ...]
    excluded_pf_user_ids: tuple[int, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "ok",
            "units": list(self.units),
            "excluded_pf_user_ids": list(self.excluded_pf_user_ids),
            "checks": {
                "jwt": "ok",
                "configuration": "ok",
                "accounts": "ok" if self.units else "not_selected",
                "database": "ok",
            },
        }


def run_asaas_sales_preflight(
    units: Iterable[str] | None = None,
    *,
    allow_no_units: bool = False,
    excluded_pf_user_ids: Iterable[int | str] | None = None,
) -> AsaasSalesPreflightResult:
    """Valida runtime, contas locais e banco sem chamar o Asaas nem escrever."""
    _validate_jwt_configuration()
    _validate_sandbox_runtime()
    selected_units = _resolve_preflight_units(units)
    account_units = _resolve_preflight_account_units(selected_units)
    if not account_units and not allow_no_units:
        raise AsaasSalesPreflightError("no_units_selected")
    pf_exclusions = _resolve_pf_exclusions(
        excluded_pf_user_ids,
        selected_units=account_units,
    )
    try:
        # Valida sintaxe, subconjunto e trava de ambiente de cada método.
        get_enabled_asaas_sales_carne_units()
        get_enabled_asaas_sales_pix_automatic_units()
        get_enabled_asaas_sales_credit_card_recurring_units()
        # O getter combina allowlist, política explícita e trava Sandbox.
        get_enabled_asaas_sales_entry_units()
    except AsaasSalesConfigError as exc:
        raise AsaasSalesPreflightError(
            "rollout_configuration_invalid"
        ) from exc
    try:
        validate_asaas_sales_account_isolation(account_units)
        account_targets = _resolve_preflight_account_targets(account_units)
        target_environments = {
            environment
            for _unit, environment, _wallet in account_targets
        }
        if len(target_environments) > 1:
            raise AsaasSalesConfigError(
                "Contas Asaas selecionadas possuem ambientes divergentes."
            )
        receiver_provider = None
        company_wallets = {}
        if target_environments and selected_units:
            receiver_provider = receiver_identity_provider_for_environment(
                next(iter(target_environments))
            )
    except (
        AsaasConfigurationError,
        AsaasSalesConfigError,
        AsaasSplitValidationError,
    ) as exc:
        raise AsaasSalesPreflightError("account_configuration_invalid") from exc
    _validate_database(
        account_units,
        readiness_units=selected_units,
        account_targets=account_targets,
        company_wallets=company_wallets,
        pf_exclusions=pf_exclusions,
        receiver_provider=receiver_provider,
        receiver_environment=(next(iter(target_environments)) if target_environments else None),
    )
    return AsaasSalesPreflightResult(
        units=account_units,
        excluded_pf_user_ids=tuple(
            exclusion.user_id for exclusion in pf_exclusions
        ),
    )


def _validate_jwt_configuration() -> None:
    if not str(os.getenv("JWT_SECRET", "")).strip():
        raise AsaasSalesPreflightError("jwt_configuration_missing")


def _validate_sandbox_runtime() -> None:
    application_environment = str(
        os.getenv("ENVIRONMENT", "")
    ).strip().casefold()
    asaas_environment = str(
        os.getenv("ASAAS_ENVIRONMENT", "")
    ).strip().casefold()
    if (
        application_environment in _SANDBOX_APPLICATION_ENVIRONMENTS
        and asaas_environment == "sandbox"
    ):
        return
    if application_environment in {"prod", "production"} and asaas_environment in {
        "prod",
        "production",
    }:
        # O perfil pode permanecer desligado em produção: isto não declara
        # rollout pronto, apenas permite validar a configuração fail-closed.
        try:
            is_asaas_sales_production_profile_enabled()
        except AsaasSalesConfigError as exc:
            raise AsaasSalesPreflightError("rollout_configuration_invalid") from exc
        return
    raise AsaasSalesPreflightError("sandbox_environment_required")


def _resolve_preflight_units(
    units: Iterable[str] | None,
) -> tuple[str, ...]:
    if units is None:
        try:
            return tuple(sorted(get_enabled_asaas_sales_units()))
        except AsaasSalesConfigError as exc:
            raise AsaasSalesPreflightError(
                "rollout_configuration_invalid"
            ) from exc

    canonical_units: set[str] = set()
    for value in units:
        canonical = canonicalize_asaas_sales_unit(value)
        if not canonical:
            raise AsaasSalesPreflightError("unsupported_unit")
        canonical_units.add(canonical)
    return tuple(sorted(canonical_units))


def _resolve_preflight_account_units(
    selected_units: tuple[str, ...],
) -> tuple[str, ...]:
    """Inclui alvos já operacionais ao comparar contas de uma seleção futura."""
    try:
        return tuple(
            sorted(
                set(selected_units)
                | set(get_asaas_sales_operational_account_units())
            )
        )
    except AsaasSalesConfigError as exc:
        raise AsaasSalesPreflightError(
            "rollout_configuration_invalid"
        ) from exc


def is_asaas_sales_pf_user_excluded(
    user_id: int,
    unidade: str,
) -> bool:
    """Consulta somente o manifesto operacional; nunca altera readiness/split."""
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    if (
        type(user_id) is not int
        or user_id <= 0
        or canonical_unit is None
    ):
        raise AsaasSalesPreflightError(
            "pf_exclusion_configuration_invalid"
        )
    operational_units = _resolve_preflight_account_units(())
    exclusions = _resolve_pf_exclusions(
        None,
        selected_units=operational_units,
    )
    return any(
        exclusion.user_id == user_id
        and exclusion.unidade == canonical_unit
        for exclusion in exclusions
    )


def _resolve_pf_exclusions(
    excluded_pf_user_ids: Iterable[int | str] | None,
    *,
    selected_units: tuple[str, ...],
) -> tuple[_PfExclusion, ...]:
    if excluded_pf_user_ids is not None:
        return tuple(
            _PfExclusion(user_id=user_id, unidade=None)
            for user_id in _normalize_excluded_pf_user_ids(
                excluded_pf_user_ids
            )
        )

    if _PF_EXCLUSIONS_FILE_ENV not in os.environ:
        return ()
    manifest_path = str(os.environ[_PF_EXCLUSIONS_FILE_ENV]).strip()
    if not manifest_path:
        raise AsaasSalesPreflightError(
            "pf_exclusion_configuration_invalid"
        )
    path = Path(manifest_path)
    if not path.is_absolute():
        raise AsaasSalesPreflightError(
            "pf_exclusion_configuration_invalid"
        )
    try:
        raw_manifest = path.read_bytes()
    except OSError as exc:
        raise AsaasSalesPreflightError(
            "pf_exclusion_configuration_invalid"
        ) from exc
    if len(raw_manifest) > _PF_EXCLUSIONS_MAX_BYTES:
        raise AsaasSalesPreflightError(
            "pf_exclusion_configuration_invalid"
        )
    try:
        manifest = json.loads(
            raw_manifest.decode("utf-8"),
            object_pairs_hook=_strict_json_object,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise AsaasSalesPreflightError(
            "pf_exclusion_configuration_invalid"
        ) from exc
    if (
        not isinstance(manifest, dict)
        or set(manifest)
        != {"schema_version", "environment", "excluded_pf_users"}
        or type(manifest["schema_version"]) is not int
        or manifest["schema_version"] != _PF_EXCLUSIONS_SCHEMA_VERSION
        or manifest["environment"] != "sandbox"
        or not isinstance(manifest["excluded_pf_users"], list)
    ):
        raise AsaasSalesPreflightError(
            "pf_exclusion_configuration_invalid"
        )

    exclusions: list[_PfExclusion] = []
    seen_user_ids: set[int] = set()
    for entry in manifest["excluded_pf_users"]:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"user_id", "unidade", "reason"}
            or type(entry["user_id"]) is not int
            or entry["user_id"] <= 0
            or not isinstance(entry["unidade"], str)
            or not isinstance(entry["reason"], str)
        ):
            raise AsaasSalesPreflightError(
                "pf_exclusion_configuration_invalid"
            )
        canonical_unit = canonicalize_asaas_sales_unit(entry["unidade"])
        reason = entry["reason"].strip()
        if (
            not canonical_unit
            or entry["unidade"].strip() != canonical_unit
            or canonical_unit not in selected_units
            or not reason
            or len(reason) > _PF_EXCLUSION_REASON_MAX_LENGTH
            or not reason.isprintable()
            or entry["user_id"] in seen_user_ids
        ):
            raise AsaasSalesPreflightError(
                "pf_exclusion_configuration_invalid"
            )
        seen_user_ids.add(entry["user_id"])
        exclusions.append(
            _PfExclusion(
                user_id=entry["user_id"],
                unidade=canonical_unit,
            )
        )
    return tuple(sorted(exclusions, key=lambda exclusion: exclusion.user_id))


def _strict_json_object(
    pairs: Sequence[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _normalize_excluded_pf_user_ids(
    values: Iterable[int | str],
) -> tuple[int, ...]:
    normalized: list[int] = []
    seen: set[int] = set()
    try:
        iterator = iter(values)
    except TypeError as exc:
        raise AsaasSalesPreflightError(
            "pf_exclusion_configuration_invalid"
        ) from exc
    for value in iterator:
        if isinstance(value, bool):
            raise AsaasSalesPreflightError(
                "pf_exclusion_configuration_invalid"
            )
        if type(value) is int:
            user_id = value
        elif isinstance(value, str) and re.fullmatch(
            r"[1-9][0-9]*",
            value,
        ):
            user_id = int(value)
        else:
            raise AsaasSalesPreflightError(
                "pf_exclusion_configuration_invalid"
            )
        if user_id <= 0 or user_id in seen:
            raise AsaasSalesPreflightError(
                "pf_exclusion_configuration_invalid"
            )
        seen.add(user_id)
        normalized.append(user_id)
    return tuple(sorted(normalized))


def _resolve_preflight_account_targets(
    units: tuple[str, ...],
) -> tuple[tuple[str, str, str], ...]:
    targets: list[tuple[str, str, str]] = []
    for unit in units:
        config = AsaasConfig.from_env(unit, strict=True)
        canonical, environment, wallet = (
            validate_asaas_sales_account_configuration(
                unidade=config.unidade or unit,
                environment=config.environment.name.casefold(),
                account_wallet_id=config.account_wallet_id or "",
                api_key=config.api_key,
            )
        )
        if canonical != unit:
            raise AsaasSalesConfigError(
                "Conta Asaas estrita diverge da unidade selecionada."
            )
        targets.append((canonical, environment, wallet))
    return tuple(targets)


def _validate_database(
    account_units: tuple[str, ...],
    *,
    readiness_units: tuple[str, ...],
    account_targets: tuple[tuple[str, str, str], ...],
    company_wallets: Mapping[int, str | None],
    pf_exclusions: tuple[_PfExclusion, ...],
    receiver_provider: AsaasReceiverIdentityProvider | None = None,
    receiver_environment: str | None = None,
    production_provider: AsaasReceiverIdentityProvider | None = None,
) -> None:
    # Kept as a compatibility boundary for the production composition tests.
    # Runtime calls always use the environment-neutral provider above.
    if receiver_provider is None and production_provider is not None:
        receiver_provider = production_provider
        receiver_environment = "production"
    try:
        with DatabaseConnection(read_only=True) as conn:
            cursor = conn.cursor()
            _validate_runtime_role(cursor)
            _validate_tables_and_privileges(cursor)
            _validate_sequences(cursor)
            _validate_indexes(cursor)
            _validate_functions(cursor)
            _validate_sandbox_receiver_acl(cursor)
            _validate_entry_snapshot_acl(cursor)
            _validate_triggers(cursor)
            _validate_constraints(cursor)
            readiness_targets = tuple(
                target for target in account_targets
                if target[0] in readiness_units
            )
            if receiver_provider is None:
                _validate_pf_subaccounts(cursor, account_units, readiness_units=readiness_units, pf_exclusions=pf_exclusions)
            else:
                if receiver_environment == "production":
                    if pf_exclusions:
                        raise AsaasSalesPreflightError("pf_exclusion_configuration_invalid")
                    _validate_production_receiver_identities(
                        cursor, readiness_units, readiness_targets, (), receiver_provider
                    )
                else:
                    _validate_receiver_identities(
                        cursor,
                        readiness_units,
                        readiness_targets,
                        pf_exclusions,
                        receiver_provider,
                        environment=receiver_environment or "",
                    )
            if receiver_provider is None:
                _validate_split_semantics(cursor, readiness_units, account_targets=readiness_targets, company_wallets=company_wallets)
    except AsaasSalesPreflightError:
        raise
    except AsaasSaleDatabaseConfigError as exc:
        raise AsaasSalesPreflightError(
            "database_configuration_missing"
        ) from exc
    except psycopg2.Error as exc:
        raise AsaasSalesPreflightError("database_unavailable") from exc
    except Exception as exc:
        raise AsaasSalesPreflightError("database_check_failed") from exc


def _validate_pf_subaccounts(
    cursor,
    account_units: tuple[str, ...],
    *,
    readiness_units: tuple[str, ...],
    pf_exclusions: tuple[_PfExclusion, ...],
) -> None:
    if not account_units:
        if pf_exclusions:
            raise AsaasSalesPreflightError(
                "pf_exclusion_configuration_invalid"
            )
        return

    excluded_user_ids = [
        exclusion.user_id for exclusion in pf_exclusions
    ]
    if pf_exclusions:
        expected_units = [
            exclusion.unidade for exclusion in pf_exclusions
        ]
        cursor.execute(
            """
            SELECT
                COUNT(*) = %s AS pf_exclusions_match_eligible_users
              FROM UNNEST(
                       %s::bigint[],
                       %s::text[]
                   ) AS requested_exclusion(user_id, expected_unit)
              JOIN users AS excluded_pf
                ON excluded_pf.id = requested_exclusion.user_id
               AND (
                       requested_exclusion.expected_unit IS NULL
                       OR excluded_pf.unidade =
                          requested_exclusion.expected_unit
                   )
             WHERE excluded_pf.unidade = ANY(%s::text[])
               AND excluded_pf.cargo_id IN (3, 4)
               AND excluded_pf.status_aprovacao = 'aprovado'
               AND LENGTH(
                       REGEXP_REPLACE(
                           COALESCE(excluded_pf.cpf, ''),
                           '[^0-9]',
                           '',
                           'g'
                       )
                   ) = 11
               AND (
                       excluded_pf.asaas_integration_status
                           IS DISTINCT FROM 'integrado'
                       OR NULLIF(
                              BTRIM(excluded_pf.asaas_wallet_id),
                              ''
                          ) IS NULL
                       OR NULLIF(
                              BTRIM(excluded_pf.asaas_account_id),
                              ''
                          ) IS NULL
                   )
            """,
            (
                len(pf_exclusions),
                excluded_user_ids,
                expected_units,
                list(account_units),
            ),
        )
        exclusion_row = cursor.fetchone()
        if exclusion_row is None or not bool(exclusion_row[0]):
            raise AsaasSalesPreflightError("pf_exclusion_drift")

    if not readiness_units:
        return

    cursor.execute(
        """
        SELECT
            EXISTS (
                SELECT 1
                  FROM users AS eligible_pf
                 WHERE eligible_pf.unidade = ANY(%s::text[])
                   AND eligible_pf.cargo_id IN (3, 4)
                   AND eligible_pf.status_aprovacao = 'aprovado'
                   AND LENGTH(
                           REGEXP_REPLACE(
                               COALESCE(eligible_pf.cpf, ''),
                               '[^0-9]',
                               '',
                               'g'
                           )
                       ) = 11
                   AND NOT (
                       eligible_pf.id = ANY(%s::bigint[])
                   )
                   AND (
                       eligible_pf.asaas_integration_status
                           IS DISTINCT FROM 'integrado'
                       OR NULLIF(
                              BTRIM(eligible_pf.asaas_wallet_id),
                              ''
                          ) IS NULL
                       OR NULLIF(
                              BTRIM(eligible_pf.asaas_account_id),
                              ''
                          ) IS NULL
                   )
            ) AS pf_subaccounts_incomplete
        """,
        (list(readiness_units), excluded_user_ids),
    )
    readiness_row = cursor.fetchone()
    if readiness_row is None or bool(readiness_row[0]):
        raise AsaasSalesPreflightError("pf_subaccounts_incomplete")


def _validate_receiver_identities(
    cursor,
    units: tuple[str, ...],
    account_targets: tuple[tuple[str, str, str], ...],
    exclusions: tuple[_PfExclusion, ...],
    provider: AsaasReceiverIdentityProvider,
    *,
    environment: str,
) -> None:
    """Checks runtime receiver bindings, never legacy wallet/key columns."""
    if not units:
        return
    roots = {unit: wallet for unit, _environment, wallet in account_targets}
    if (
        len(roots) != len(units)
        or set(roots) != set(units)
        or any(not str(wallet).strip() for wallet in roots.values())
    ):
        raise AsaasSalesPreflightError("account_configuration_invalid")
    cursor.execute(
        """SELECT id, unidade, cargo_id FROM users
             WHERE unidade = ANY(%s::text[]) AND cargo_id IN (3, 4)
               AND status_aprovacao = 'aprovado'
               AND LENGTH(REGEXP_REPLACE(COALESCE(cpf, ''), '[^0-9]', '', 'g')) = 11""",
        (list(units),),
    )
    try:
        pf_rows = cursor.fetchall() or []
    except Exception as exc:
        raise AsaasSalesPreflightError("pf_subaccounts_incomplete") from exc
    eligible_exclusions = {
        (int(user_id), str(unit)) for user_id, unit, _cargo in pf_rows
        if any(item.user_id == int(user_id) and (item.unidade is None or item.unidade == str(unit)) for item in exclusions)
    }
    if len(eligible_exclusions) != len(exclusions):
        raise AsaasSalesPreflightError("pf_exclusion_drift")
    eligible_units = {
        str(unit) for user_id, unit, _cargo in pf_rows
        if not any(
            item.user_id == int(user_id)
            and (item.unidade is None or item.unidade == str(unit))
            for item in exclusions
        )
    }
    if environment == "sandbox" and eligible_units != set(units):
        raise AsaasSalesPreflightError("pf_subaccounts_incomplete")
    for user_id, unit, _cargo in pf_rows:
        if any(item.user_id == int(user_id) and (item.unidade is None or item.unidade == str(unit)) for item in exclusions):
            continue
        try:
            provider.resolve_for_new_sale(kind="pf", local_id=int(user_id), unidade=str(unit), environment=environment)
        except AsaasSplitValidationError as exc:
            raise AsaasSalesPreflightError("pf_subaccounts_incomplete") from exc
    # Reuse the runtime selector for every real PF/type scenario; it owns
    # unit overrides, limits and manager ambiguity.
    for user_id, unit, _cargo in pf_rows:
        if any(
            item.user_id == int(user_id)
            and (item.unidade is None or item.unidade == str(unit))
            for item in exclusions
        ):
            continue
        cursor.execute(
            """SELECT DISTINCT p.tipo_odontograma_id FROM participacao_cargo_split p
                 JOIN regras_split r ON r.tipo_odontograma_id = p.tipo_odontograma_id
                  AND r.cargo_id = p.cargo_id
                 WHERE p.ativo = TRUE AND r.ativo = TRUE
                   AND (r.unidade IS NULL OR r.unidade = %s)""",
            (str(unit),),
        )
        type_rows = cursor.fetchall() or []
        if environment == "sandbox" and not type_rows:
            raise AsaasSalesPreflightError("account_configuration_invalid")
        for type_row in type_rows:
            if not is_asaas_sandbox_ni_odontogram_type_available(
                str(unit), environment, int(type_row[0])
            ):
                continue
            try:
                rules = _load_asaas_domain_rules(cursor, venda_id=None, unidade=str(unit), environment=environment, tipo_odontograma_id=int(type_row[0]), dentista_id=None, usuario_venda_id=int(user_id))
                bound = []
                for rule in rules:
                    kind = "pf" if rule.user_id is not None else "empresa"
                    local_id = rule.user_id if kind == "pf" else rule.empresa_id
                    identity = provider.resolve_for_new_sale(kind=kind, local_id=int(local_id), unidade=str(unit), environment=environment)
                    bound.append(replace(rule, wallet_id=identity.wallet_id))
                validate_asaas_absorber_rules(bound, account_wallet_id=roots[str(unit)])
            except (AsaasSplitValidationError, TypeError, ValueError) as exc:
                raise AsaasSalesPreflightError("account_configuration_invalid") from exc


def _validate_production_receiver_identities(
    cursor,
    units: tuple[str, ...],
    account_targets: tuple[tuple[str, str, str], ...],
    exclusions: tuple[_PfExclusion, ...],
    provider: AsaasReceiverIdentityProvider,
) -> None:
    """Compatibility wrapper for callers that explicitly audit production."""
    _validate_receiver_identities(
        cursor, units, account_targets, exclusions, provider,
        environment="production",
    )


def _validate_split_semantics(
    cursor,
    units: tuple[str, ...],
    *,
    account_targets: tuple[tuple[str, str, str], ...],
    company_wallets: Mapping[int, str | None],
) -> None:
    if not units:
        return
    target_units = [target[0] for target in account_targets]
    target_environments = [target[1] for target in account_targets]
    target_wallets = [target[2] for target in account_targets]
    if (
        len(account_targets) != len(units)
        or set(target_units) != set(units)
        or len(set(target_units)) != len(target_units)
        or any(
            environment not in {"sandbox", "production"}
            or not str(wallet).strip()
            for environment, wallet in zip(
                target_environments,
                target_wallets,
            )
        )
        or len(set(zip(target_environments, target_wallets)))
        != len(account_targets)
    ):
        raise AsaasSalesPreflightError("account_configuration_invalid")

    normalized_company_wallets = sorted(
        (
            int(company_id),
            str(wallet).strip() if wallet is not None else None,
        )
        for company_id, wallet in company_wallets.items()
    )
    company_ids = [item[0] for item in normalized_company_wallets]
    company_wallet_values = [item[1] for item in normalized_company_wallets]
    cursor.execute(
        """
        SELECT
            EXISTS (
                SELECT 1
                FROM (
                    SELECT DISTINCT ON (
                               selected_account.unidade,
                               role_rule.tipo_odontograma_id,
                               role_rule.cargo_id
                           )
                           selected_account.unidade,
                           selected_account.environment,
                           selected_account.account_wallet_id,
                           role_rule.tipo_odontograma_id,
                           role_rule.cargo_id,
                           role_rule.absorve_saldo
                      FROM UNNEST(
                               %s::text[],
                               %s::text[],
                               %s::text[]
                           ) AS selected_account(
                               unidade,
                               environment,
                               account_wallet_id
                           )
                      JOIN regras_split AS role_rule
                        ON (
                               role_rule.unidade IS NULL
                               OR role_rule.unidade =
                                  selected_account.unidade
                           )
                      JOIN participacao_cargo_split AS role_participation
                        ON role_participation.tipo_odontograma_id =
                           role_rule.tipo_odontograma_id
                       AND role_participation.cargo_id =
                           role_rule.cargo_id
                     WHERE role_rule.ativo = TRUE
                       AND role_participation.ativo = TRUE
                       AND role_rule.cargo_id IN (3, 4)
                     ORDER BY
                           selected_account.unidade,
                           role_rule.tipo_odontograma_id,
                           role_rule.cargo_id,
                           CASE
                               WHEN role_rule.unidade =
                                    selected_account.unidade
                               THEN 0
                               ELSE 1
                           END,
                           role_participation.ordem_prioridade,
                           role_rule.id
                ) AS effective_role_rule
                JOIN LATERAL (
                    SELECT
                        COUNT(*) AS receiver_count,
                        COUNT(
                            NULLIF(BTRIM(receiver.asaas_wallet_id), '')
                        ) AS receiver_wallet_count,
                        COUNT(
                            DISTINCT NULLIF(
                                BTRIM(receiver.asaas_wallet_id),
                                ''
                            )
                        ) AS distinct_receiver_wallet_count,
                        BOOL_AND(
                            NULLIF(BTRIM(receiver.asaas_wallet_id), '') =
                            effective_role_rule.account_wallet_id
                        ) AS every_receiver_uses_root_wallet
                      FROM users AS receiver
                     WHERE receiver.cargo_id =
                           effective_role_rule.cargo_id
                       AND receiver.unidade =
                           effective_role_rule.unidade
                       AND receiver.asaas_integration_status = 'integrado'
                       AND receiver.status_aprovacao = 'aprovado'
                       AND LENGTH(
                               REGEXP_REPLACE(
                                   COALESCE(receiver.cpf, ''),
                                   '[^0-9]',
                                   '',
                                   'g'
                               )
                           ) = 11
                ) AS receiver_mapping ON TRUE
                WHERE effective_role_rule.absorve_saldo = TRUE
                  AND (
                        receiver_mapping.receiver_count = 0
                        OR receiver_mapping.receiver_wallet_count <>
                           receiver_mapping.receiver_count
                        OR receiver_mapping.distinct_receiver_wallet_count <> 1
                        OR NOT COALESCE(
                            receiver_mapping.every_receiver_uses_root_wallet,
                            FALSE
                        )
                      )
            ) AS incompatible_role_absorber_rule_exists,
            EXISTS (
                SELECT 1
                FROM (
                    SELECT DISTINCT ON (
                               selected_account.unidade,
                               company_rule.tipo_odontograma_id,
                               company_rule.empresa_id
                           )
                           selected_account.unidade,
                           selected_account.environment,
                           selected_account.account_wallet_id,
                           company_rule.tipo_odontograma_id,
                           company_rule.empresa_id,
                           company_rule.absorve_saldo
                      FROM UNNEST(
                               %s::text[],
                               %s::text[],
                               %s::text[]
                           ) AS selected_account(
                               unidade,
                               environment,
                               account_wallet_id
                           )
                      JOIN empresa_regras_split AS company_rule
                        ON (
                               company_rule.unidade IS NULL
                               OR company_rule.unidade =
                                  selected_account.unidade
                           )
                      JOIN participacao_empresa_split AS company_participation
                        ON company_participation.tipo_odontograma_id =
                           company_rule.tipo_odontograma_id
                       AND company_participation.empresa_id =
                           company_rule.empresa_id
                     WHERE company_rule.ativo = TRUE
                       AND company_participation.ativo = TRUE
                     ORDER BY
                           selected_account.unidade,
                           company_rule.tipo_odontograma_id,
                           company_rule.empresa_id,
                           CASE
                               WHEN company_rule.unidade =
                                    selected_account.unidade
                               THEN 0
                               ELSE 1
                           END,
                           company_participation.ordem_prioridade,
                           company_rule.id
                ) AS effective_company_rule
                LEFT JOIN UNNEST(
                              %s::bigint[],
                              %s::text[]
                          ) AS company_wallet(
                              empresa_id,
                              wallet_id
                          )
                  ON company_wallet.empresa_id =
                     effective_company_rule.empresa_id
                WHERE effective_company_rule.absorve_saldo = TRUE
                  AND (
                        NULLIF(BTRIM(company_wallet.wallet_id), '') IS NULL
                        OR company_wallet.wallet_id <>
                           effective_company_rule.account_wallet_id
                      )
            ) AS incompatible_company_absorber_rule_exists
        """,
        (
            target_units,
            target_environments,
            target_wallets,
            target_units,
            target_environments,
            target_wallets,
            company_ids,
            company_wallet_values,
        ),
    )
    row = cursor.fetchone()
    if row is None or bool(row[0]) or bool(row[1]):
        raise AsaasSalesPreflightError(
            "split_external_absorber_unsupported"
        )


def _validate_runtime_role(cursor) -> None:
    cursor.execute(
        """
        SELECT
            runtime.rolcanlogin
            AND NOT runtime.rolsuper
            AND NOT runtime.rolcreatedb
            AND NOT runtime.rolcreaterole
            AND NOT runtime.rolreplication
            AND NOT runtime.rolbypassrls,
            NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_auth_members AS membership
                WHERE membership.member = runtime.oid
                   OR membership.roleid = runtime.oid
            ),
            NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_class AS owned_relation
                WHERE owned_relation.relowner = runtime.oid
            ),
            NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_proc AS owned_function
                WHERE owned_function.proowner = runtime.oid
            ),
            NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_namespace AS owned_namespace
                WHERE owned_namespace.nspowner = runtime.oid
            )
                AND NOT EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_database AS owned_database
                    WHERE owned_database.datdba = runtime.oid
                ),
            pg_catalog.has_schema_privilege(
                current_user,
                'public',
                'USAGE'
            ),
            NOT pg_catalog.has_schema_privilege(
                current_user,
                'public',
                'CREATE'
            ),
            pg_catalog.regexp_replace(
                pg_catalog.current_setting('search_path'),
                '[[:space:]]',
                '',
                'g'
            ) = 'pg_catalog,public,pg_temp'
        FROM pg_catalog.pg_roles AS runtime
        WHERE runtime.rolname = current_user
        """
    )
    row = cursor.fetchone()
    if not row or len(row) != 8 or not all(value is True for value in row):
        raise AsaasSalesPreflightError("database_role_not_isolated")


def _validate_tables_and_privileges(cursor) -> None:
    cursor.execute(
        """
        SELECT
            relation.relname,
            relation.relrowsecurity,
            relation.relforcerowsecurity
        FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relkind IN ('r', 'p')
          AND relation.relname::TEXT = ANY(%s)
        """,
        (list(_ALL_REQUIRED_TABLES),),
    )
    table_rows = cursor.fetchall()
    existing_tables = {str(row[0]) for row in table_rows}
    if existing_tables != _ALL_REQUIRED_TABLES:
        raise AsaasSalesPreflightError("database_schema_incomplete")
    if any(bool(row[1]) or bool(row[2]) for row in table_rows):
        raise AsaasSalesPreflightError("database_rls_unsupported")

    cursor.execute(
        """
        SELECT relation.relname, attribute.attname
        FROM pg_catalog.pg_attribute AS attribute
        JOIN pg_catalog.pg_class AS relation
          ON relation.oid = attribute.attrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname::TEXT = ANY(%s)
          AND attribute.attnum > 0
          AND NOT attribute.attisdropped
        """,
        (list(_REQUIRED_COLUMN_PRIVILEGES),),
    )
    existing_columns = {
        (str(row[0]), str(row[1])) for row in cursor.fetchall()
    }
    required_columns = {
        (table, column)
        for table, privilege_map in _REQUIRED_COLUMN_PRIVILEGES.items()
        for columns in privilege_map.values()
        for column in columns
    }
    if not required_columns.issubset(existing_columns):
        raise AsaasSalesPreflightError("database_schema_incomplete")

    cursor.execute(
        """
        SELECT
            relation.relname,
            requested_privilege.name,
            pg_catalog.has_table_privilege(
                current_user,
                relation.oid,
                requested_privilege.name
            )
        FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        CROSS JOIN pg_catalog.unnest(%s::TEXT[]) AS requested_privilege(name)
        WHERE namespace.nspname = 'public'
          AND relation.relname::TEXT = ANY(%s)
        """,
        (list(_TABLE_PRIVILEGES), list(_ALL_REQUIRED_TABLES)),
    )
    table_privilege_rows = cursor.fetchall()
    if len(table_privilege_rows) != (
        len(_ALL_REQUIRED_TABLES) * len(_TABLE_PRIVILEGES)
    ):
        raise AsaasSalesPreflightError("database_privileges_incomplete")
    for table, privilege, granted in table_privilege_rows:
        expected = privilege in _REQUIRED_TABLE_PRIVILEGES.get(table, ())
        if bool(granted) != expected:
            code = (
                "database_privileges_incomplete"
                if expected
                else "database_privileges_excessive"
            )
            raise AsaasSalesPreflightError(code)

    cursor.execute(
        """
        SELECT
            relation.relname,
            attribute.attname,
            requested_privilege.name,
            pg_catalog.has_column_privilege(
                current_user,
                relation.oid,
                attribute.attnum,
                requested_privilege.name
            )
        FROM pg_catalog.pg_attribute AS attribute
        JOIN pg_catalog.pg_class AS relation
          ON relation.oid = attribute.attrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        CROSS JOIN pg_catalog.unnest(%s::TEXT[]) AS requested_privilege(name)
        WHERE namespace.nspname = 'public'
          AND relation.relname = ANY(%s)
          AND attribute.attnum > 0
          AND NOT attribute.attisdropped
        """,
        (
            list(_COLUMN_PRIVILEGES),
            list(_REQUIRED_COLUMN_PRIVILEGES),
        ),
    )
    column_privilege_rows = cursor.fetchall()
    expected_row_count = len(existing_columns) * len(_COLUMN_PRIVILEGES)
    if len(column_privilege_rows) != expected_row_count:
        raise AsaasSalesPreflightError("database_privileges_incomplete")
    for table, column, privilege, granted in column_privilege_rows:
        expected = (
            privilege in _REQUIRED_TABLE_PRIVILEGES.get(table, ())
            or column
            in _REQUIRED_COLUMN_PRIVILEGES.get(
                table,
                {},
            ).get(privilege, ())
        )
        if bool(granted) != expected:
            code = (
                "database_privileges_incomplete"
                if expected
                else "database_privileges_excessive"
            )
            raise AsaasSalesPreflightError(code)

    cursor.execute(
        """
        SELECT relation.relname, requested_privilege.name
        FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        CROSS JOIN pg_catalog.unnest(%s::TEXT[]) AS requested_privilege(name)
        WHERE namespace.nspname = 'public'
          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND relation.relname::TEXT <> ALL(%s)
          AND NOT (
              (
                  relation.relkind = 'v'
                  AND relation.relname = %s
                  AND EXISTS (
                      SELECT 1
                      FROM pg_catalog.pg_proc AS receiver_function
                      JOIN pg_catalog.pg_namespace AS receiver_namespace
                        ON receiver_namespace.oid = receiver_function.pronamespace
                      WHERE receiver_namespace.nspname = 'public'
                        AND receiver_function.proname = %s
                        AND receiver_function.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int4'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype]::oidvector
                        AND receiver_function.proowner = relation.relowner
                  )
              )
              OR (
                  relation.relkind = 'r'
                  AND relation.relname = %s
                  AND EXISTS (
                      SELECT 1
                      FROM pg_catalog.pg_attribute AS snapshot_attribute
                      WHERE snapshot_attribute.attrelid = relation.oid
                        AND snapshot_attribute.attname = 'entry_integration_id'
                        AND snapshot_attribute.attnum > 0
                        AND NOT snapshot_attribute.attisdropped
                  )
              )
          )
          AND (
              pg_catalog.has_table_privilege(
                  current_user,
                  relation.oid,
                  requested_privilege.name
              )
              OR (
                  requested_privilege.name IN (
                      'SELECT',
                      'INSERT',
                      'UPDATE',
                      'REFERENCES'
                  )
                  AND pg_catalog.has_any_column_privilege(
                      current_user,
                      relation.oid,
                      requested_privilege.name
                  )
              )
          )
        """,
        (
            list(_TABLE_PRIVILEGES),
            list(_ALL_REQUIRED_TABLES),
            _SANDBOX_RECEIVER_VIEW,
            _SANDBOX_RECEIVER_FUNCTION,
            'asaas_entry_financial_snapshots',
        ),
    )
    unexpected_privileges = {
        (str(row[0]), str(row[1])) for row in cursor.fetchall()
    } - _PUBLIC_TABLE_PRIVILEGE_EXCEPTIONS
    if unexpected_privileges:
        raise AsaasSalesPreflightError("database_privileges_excessive")


def _validate_sequences(cursor) -> None:
    required_sequences: set[str] = set()
    for table in _SEQUENCE_TABLES:
        cursor.execute(
            "SELECT pg_catalog.pg_get_serial_sequence(%s, 'id')",
            (f"public.{table}",),
        )
        row = cursor.fetchone()
        sequence = str(row[0]) if row and row[0] else ""
        if not sequence:
            raise AsaasSalesPreflightError("database_schema_incomplete")
        required_sequences.add(sequence)
        for privilege in ("USAGE", "SELECT", "UPDATE"):
            cursor.execute(
                """
                SELECT pg_catalog.has_sequence_privilege(
                    current_user,
                    %s,
                    %s
                )
                """,
                (sequence, privilege),
            )
            privilege_row = cursor.fetchone()
            granted = bool(privilege_row and privilege_row[0])
            expected = privilege == "USAGE"
            if granted != expected:
                code = (
                    "database_privileges_incomplete"
                    if expected
                    else "database_privileges_excessive"
                )
                raise AsaasSalesPreflightError(code)

    cursor.execute(
        """
        SELECT
            pg_catalog.quote_ident(namespace.nspname)
                || '.'
                || pg_catalog.quote_ident(sequence.relname)
        FROM pg_catalog.pg_class AS sequence
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = sequence.relnamespace
        WHERE namespace.nspname = 'public'
          AND sequence.relkind = 'S'
        """
    )
    for (sequence,) in cursor.fetchall():
        if str(sequence) in required_sequences:
            continue
        cursor.execute(
            """
            SELECT
                pg_catalog.has_sequence_privilege(
                    current_user,
                    %s,
                    'USAGE'
                )
                OR pg_catalog.has_sequence_privilege(
                    current_user,
                    %s,
                    'SELECT'
                )
                OR pg_catalog.has_sequence_privilege(
                    current_user,
                    %s,
                    'UPDATE'
                )
            """,
            (sequence, sequence, sequence),
        )
        row = cursor.fetchone()
        if row and row[0]:
            raise AsaasSalesPreflightError(
                "database_privileges_excessive"
            )


def _validate_indexes(cursor) -> None:
    cursor.execute(
        """
        SELECT
            index_relation.relname,
            table_relation.relname,
            index_record.indisunique,
            ARRAY(
                SELECT pg_catalog.pg_get_indexdef(
                    index_record.indexrelid,
                    key_position,
                    TRUE
                )
                FROM pg_catalog.generate_series(
                    1,
                    index_record.indnkeyatts
                ) AS key_position
                ORDER BY key_position
            ),
            pg_catalog.pg_get_expr(
                index_record.indpred,
                index_record.indrelid
            )
        FROM pg_catalog.pg_index AS index_record
        JOIN pg_catalog.pg_class AS index_relation
          ON index_relation.oid = index_record.indexrelid
        JOIN pg_catalog.pg_class AS table_relation
          ON table_relation.oid = index_record.indrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = table_relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND index_relation.relname::TEXT = ANY(%s)
          AND index_record.indisvalid
          AND index_record.indisready
        """,
        (list(_REQUIRED_INDEXES),),
    )
    indexes = {
        (
            str(row[0]),
            str(row[1]),
            bool(row[2]),
            _canonicalize_index_keys(
                str(row[0]), str(row[1]), bool(row[2]), row[3], row[4]
            ),
            _canonicalize_index_predicate(str(row[0]), row[4]),
        )
        for row in cursor.fetchall()
    }
    expected = {
        (
            name,
            table,
            unique,
            tuple(_normalize_index_key(value) for value in keys),
            _canonicalize_index_predicate(name, predicate),
        )
        for name, (
            table,
            unique,
            keys,
            predicate,
        ) in _REQUIRED_INDEXES.items()
    }
    if indexes != expected:
        raise AsaasSalesPreflightError("database_indexes_incomplete")


def _normalize_index_key(value: object) -> str:
    normalized = re.sub(
        r"::(?:pg_catalog\.)?(?:bigint|integer)",
        "",
        str(value),
        flags=re.IGNORECASE,
    )
    return "".join(normalized.split()).replace('"', "").casefold()


def _canonicalize_index_keys(
    name: str, table: str, unique: bool, keys: object, predicate: object | None
) -> tuple[str, ...]:
    normalized = tuple(_normalize_index_key(value) for value in keys)
    # Migration adds environment only to this exact partial unique index. The
    # legacy shape remains valid until the migration is applied.
    if (name == "uq_asaas_account_provision_attempt_active_user"
            and table == "asaas_account_provision_attempts" and unique
            and normalized == ("user_id", "environment")
            and _canonicalize_index_predicate(name, predicate)
            == _canonicalize_index_predicate(
                name, "(lifecycle_state::text <> 'rejected'::text)")):
        return ("user_id",)
    return normalized


def _normalize_index_predicate(value: object | None) -> str | None:
    if value is None:
        return None
    return "".join(str(value).split()).replace('"', "").casefold()


def _canonical_sql(value: object) -> str:
    """Compara a definição inteira, tolerando apenas formatação do catálogo."""
    return " ".join(str(value).strip().rstrip(";").split()).casefold()


def _runtime_role_name(cursor) -> str:
    """Usa a role efetiva, já validada pelo preflight, sem nome fixo."""
    cursor.execute("SELECT current_user AS runtime_role")
    row = cursor.fetchone()
    if not row or len(row) != 1 or not isinstance(row[0], str) or not row[0].strip():
        raise AsaasSalesPreflightError("database_role_not_isolated")
    return row[0].strip()


def _canonicalize_index_predicate(
    name: str,
    value: object | None,
) -> str | None:
    normalized = _normalize_index_predicate(value)
    variants = _POSTGRESQL_16_INDEX_PREDICATE_VARIANTS.get(name)
    if variants is None:
        return normalized
    normalized_variants = tuple(
        _normalize_index_predicate(variant) for variant in variants
    )
    if normalized in normalized_variants:
        return normalized_variants[0]
    return normalized


def _validate_sandbox_receiver_acl(cursor) -> None:
    """Audita o único caminho runtime para PF sandbox, sem aceitar ACL ampla."""
    cursor.execute(
        """
        SELECT
          view_record.relkind = 'v',
          view_record.reloptions @> ARRAY['security_barrier=true'],
          pg_catalog.pg_get_viewdef(view_record.oid, TRUE),
          NOT view_owner.rolcanlogin AND NOT view_owner.rolsuper
            AND NOT view_owner.rolcreatedb AND NOT view_owner.rolcreaterole
            AND NOT view_owner.rolreplication AND NOT view_owner.rolbypassrls
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members membership WHERE membership.member = view_owner.oid OR membership.roleid = view_owner.oid)
            AND view_owner.oid = function_owner.oid
            AND NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_class owned_relation
                JOIN pg_catalog.pg_namespace owned_namespace ON owned_namespace.oid = owned_relation.relnamespace
                WHERE owned_relation.relowner = view_owner.oid
                  AND (owned_namespace.nspname, owned_relation.relname, owned_relation.relkind)
                    <> ('public', %s, 'v')
            ),
          procedure.prosecdef AND procedure.prokind = 'f' AND language.lanname = 'sql',
          procedure.pronargs = 5
            AND procedure.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int4'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype]::oidvector
            AND procedure.prorettype = 'pg_catalog.text'::pg_catalog.regtype,
          procedure.proconfig = ARRAY['search_path=pg_catalog, pg_temp'],
          NOT function_owner.rolcanlogin AND NOT function_owner.rolsuper
            AND NOT function_owner.rolcreatedb AND NOT function_owner.rolcreaterole
            AND NOT function_owner.rolreplication AND NOT function_owner.rolbypassrls
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members membership WHERE membership.member = function_owner.oid OR membership.roleid = function_owner.oid),
          procedure.prosrc
        FROM pg_catalog.pg_class view_record
        JOIN pg_catalog.pg_namespace view_namespace ON view_namespace.oid = view_record.relnamespace
        JOIN pg_catalog.pg_roles view_owner ON view_owner.oid = view_record.relowner
        CROSS JOIN pg_catalog.pg_proc procedure
        JOIN pg_catalog.pg_namespace function_namespace ON function_namespace.oid = procedure.pronamespace
        JOIN pg_catalog.pg_roles function_owner ON function_owner.oid = procedure.proowner
        JOIN pg_catalog.pg_language language ON language.oid = procedure.prolang
        WHERE view_namespace.nspname = 'public' AND view_record.relname = %s
          AND function_namespace.nspname = 'public' AND procedure.proname = %s
          AND procedure.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int4'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype]::oidvector
          AND (SELECT count(*) FROM pg_catalog.pg_proc matching
               JOIN pg_catalog.pg_namespace matching_namespace ON matching_namespace.oid = matching.pronamespace
               WHERE matching_namespace.nspname = 'public'
                 AND matching.proname = %s
                 AND matching.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int4'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype]::oidvector) = 1
        """,
        (_SANDBOX_RECEIVER_VIEW, _SANDBOX_RECEIVER_VIEW, _SANDBOX_RECEIVER_FUNCTION, _SANDBOX_RECEIVER_FUNCTION),
    )
    row = cursor.fetchone()
    if (
        not row or len(row) != 9 or any(value is not True for value in (row[0], row[1], row[3], row[4], row[5], row[6], row[7]))
        or _canonical_sql(row[2]) not in {
            _canonical_sql(variant)
            for variant in _SANDBOX_RECEIVER_VIEW_DEFINITION_VARIANTS
        }
        or hashlib.sha256(str(row[8]).encode("utf-8")).hexdigest()
        != _SANDBOX_RECEIVER_FUNCTION_BODY_SHA256
    ):
        raise AsaasSalesPreflightError("sandbox_receiver_acl_invalid")
    runtime_role = _runtime_role_name(cursor)
    cursor.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE role.rolname END,
               acl.privilege_type, acl.is_grantable
        FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(relation.relacl, pg_catalog.acldefault('r', relation.relowner))
        ) acl
        LEFT JOIN pg_catalog.pg_roles role ON role.oid = acl.grantee
        WHERE namespace.nspname = 'public' AND relation.relname = %s
          AND acl.grantee <> relation.relowner
        """,
        (_SANDBOX_RECEIVER_VIEW,),
    )
    if cursor.fetchall():
        raise AsaasSalesPreflightError("sandbox_receiver_acl_invalid")
    cursor.execute(
        """
        SELECT attribute.attname,
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE role.rolname END,
               acl.privilege_type, acl.is_grantable
        FROM pg_catalog.pg_class view_record
        JOIN pg_catalog.pg_namespace view_namespace ON view_namespace.oid = view_record.relnamespace
        JOIN pg_catalog.pg_attribute attribute ON attribute.attrelid = view_record.oid AND attribute.attnum > 0 AND NOT attribute.attisdropped
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(attribute.attacl, pg_catalog.acldefault('c', view_record.relowner))
        ) acl
        LEFT JOIN pg_catalog.pg_roles role ON role.oid = acl.grantee
        WHERE view_namespace.nspname = 'public' AND view_record.relname = %s
          AND acl.grantee <> view_record.relowner
        """,
        (_SANDBOX_RECEIVER_VIEW,),
    )
    view_rows = cursor.fetchall()
    expected_view_acl = {(column, runtime_role, "SELECT", False) for column in _SANDBOX_RECEIVER_VIEW_COLUMNS}
    if set(tuple(row) for row in view_rows) != expected_view_acl:
        raise AsaasSalesPreflightError("sandbox_receiver_acl_invalid")
    cursor.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE role.rolname END,
               acl.privilege_type, acl.is_grantable
        FROM pg_catalog.pg_proc procedure
        JOIN pg_catalog.pg_namespace function_namespace ON function_namespace.oid = procedure.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(procedure.proacl, pg_catalog.acldefault('f', procedure.proowner))) acl
        LEFT JOIN pg_catalog.pg_roles role ON role.oid = acl.grantee
        WHERE function_namespace.nspname = 'public' AND procedure.proname = %s
          AND procedure.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int4'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype]::oidvector
          AND acl.grantee <> procedure.proowner
        """,
        (_SANDBOX_RECEIVER_FUNCTION,),
    )
    if set(tuple(row) for row in cursor.fetchall()) != {(runtime_role, "EXECUTE", False)}:
        raise AsaasSalesPreflightError("sandbox_receiver_acl_invalid")
    cursor.execute(
        """
        SELECT relation.relname, attribute.attname, privilege.name,
               pg_catalog.has_column_privilege(function_owner.oid, relation.oid, attribute.attnum, privilege.name),
               pg_catalog.has_table_privilege(function_owner.oid, relation.oid, privilege.name)
        FROM pg_catalog.pg_proc procedure
        JOIN pg_catalog.pg_namespace function_namespace ON function_namespace.oid = procedure.pronamespace
        JOIN pg_catalog.pg_roles function_owner ON function_owner.oid = procedure.proowner
        JOIN pg_catalog.pg_class relation ON relation.relname = 'asaas_receiver_environment_links'
        JOIN pg_catalog.pg_namespace relation_namespace ON relation_namespace.oid = relation.relnamespace AND relation_namespace.nspname = 'public'
        JOIN pg_catalog.pg_attribute attribute ON attribute.attrelid = relation.oid AND attribute.attnum > 0 AND NOT attribute.attisdropped
        CROSS JOIN pg_catalog.unnest(ARRAY['SELECT','INSERT','UPDATE','REFERENCES']::TEXT[]) privilege(name)
        WHERE function_namespace.nspname = 'public' AND procedure.proname = %s
          AND procedure.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int4'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype]::oidvector
        """,
        (_SANDBOX_RECEIVER_FUNCTION,),
    )
    expected = _SANDBOX_RECEIVER_LINK_COLUMNS
    rows = cursor.fetchall()
    if not rows:
        raise AsaasSalesPreflightError("sandbox_receiver_acl_invalid")
    for _table, column, privilege, granted, table_granted in rows:
        if bool(table_granted) or bool(granted) != (str(privilege) == "SELECT" and str(column) in expected):
            raise AsaasSalesPreflightError("sandbox_receiver_acl_invalid")


def _validate_entry_snapshot_acl(cursor) -> None:
    """Ensures the evidence row is immutable except for one-way consumption."""
    required = {
        "entry_integration_id", "intent_version", "intent_sha256", "snapshot_json",
        "entry_plan_json", "entry_split_json", "carne_plan_json",
        "carne_split_json", "consumed_venda_id", "created_at",
    }
    cursor.execute(
        """
        SELECT relation.relkind = 'r' AS snapshot_contract_complete,
               EXISTS (
                 SELECT 1 FROM pg_catalog.pg_constraint constraint_record
                 JOIN pg_catalog.pg_attribute primary_key_attribute
                   ON primary_key_attribute.attrelid = relation.oid
                  AND primary_key_attribute.attname = 'entry_integration_id'
                  AND primary_key_attribute.attnum > 0
                  AND NOT primary_key_attribute.attisdropped
                 WHERE constraint_record.conrelid = relation.oid
                   AND constraint_record.contype = 'p'
                   AND constraint_record.conkey = ARRAY[primary_key_attribute.attnum]::smallint[]
                   AND NOT constraint_record.condeferrable
                   AND NOT constraint_record.condeferred
               ),
               EXISTS (
                 SELECT 1 FROM pg_catalog.pg_index index_record
                 JOIN pg_catalog.pg_class index_class ON index_class.oid = index_record.indexrelid
                 JOIN pg_catalog.pg_namespace index_namespace ON index_namespace.oid = index_class.relnamespace
                 JOIN pg_catalog.pg_attribute consumed_attribute
                   ON consumed_attribute.attrelid = relation.oid
                  AND consumed_attribute.attname = 'consumed_venda_id'
                  AND consumed_attribute.attnum > 0
                  AND NOT consumed_attribute.attisdropped
               WHERE index_record.indrelid = relation.oid
                   AND index_namespace.nspname = 'public'
                   AND index_class.relname = 'uq_asaas_entry_snapshot_consumed_venda'
                   AND index_record.indisunique
                   AND index_record.indisvalid
                   AND index_record.indisready
                   AND index_record.indnkeyatts = 1
                   AND index_record.indnatts = 1
                   AND index_record.indkey[0] = consumed_attribute.attnum
                   AND index_record.indexprs IS NULL
                   AND pg_catalog.pg_get_expr(index_record.indpred, index_record.indrelid, false)
                       = '(consumed_venda_id IS NOT NULL)'
               )
        FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relname = 'asaas_entry_financial_snapshots'
        """
    )
    if cursor.fetchone() != (True, True, True):
        raise AsaasSalesPreflightError("entry_snapshot_acl_invalid")
    cursor.execute(
        """
        SELECT attribute.attname
        FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        JOIN pg_catalog.pg_attribute attribute ON attribute.attrelid = relation.oid
          AND attribute.attnum > 0 AND NOT attribute.attisdropped
        WHERE namespace.nspname = 'public' AND relation.relname = 'asaas_entry_financial_snapshots'
        """
    )
    if {str(row[0]) for row in cursor.fetchall()} != required:
        raise AsaasSalesPreflightError("entry_snapshot_acl_invalid")
    runtime_role = _runtime_role_name(cursor)
    cursor.execute(
        """
        SELECT owner.rolname AS entry_snapshot_consume_owner
        FROM pg_catalog.pg_proc AS procedure
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = procedure.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.oid = procedure.proowner
        WHERE namespace.nspname = 'public'
          AND procedure.proname = %s
          AND procedure.pronargs = 2
          AND procedure.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int8'::pg_catalog.regtype]::oidvector
        """,
        (_ENTRY_SNAPSHOT_CONSUME_FUNCTION,),
    )
    owner_row = cursor.fetchone()
    if (
        not owner_row
        or len(owner_row) != 1
        or not isinstance(owner_row[0], str)
        or not owner_row[0].strip()
    ):
        raise AsaasSalesPreflightError("entry_snapshot_acl_invalid")
    consume_owner = owner_row[0].strip()
    cursor.execute(
        """
        SELECT attribute.attname,
               CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE role.rolname END,
               acl.privilege_type, acl.is_grantable
        FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        JOIN pg_catalog.pg_attribute attribute ON attribute.attrelid = relation.oid
          AND attribute.attnum > 0 AND NOT attribute.attisdropped
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(attribute.attacl, pg_catalog.acldefault('c', relation.relowner))
        ) acl
        LEFT JOIN pg_catalog.pg_roles role ON role.oid = acl.grantee
        WHERE namespace.nspname = 'public' AND relation.relname = 'asaas_entry_financial_snapshots'
          AND acl.grantee <> relation.relowner
        """
    )
    immutable = required - {"consumed_venda_id"}
    expected = (
        {(column, runtime_role, "SELECT", False) for column in required}
        | {(column, runtime_role, "INSERT", False) for column in immutable - {"created_at"}}
        | {
            ("entry_integration_id", consume_owner, "SELECT", False),
            ("consumed_venda_id", consume_owner, "SELECT", False),
            ("consumed_venda_id", consume_owner, "UPDATE", False),
        }
    )
    if {tuple(row) for row in cursor.fetchall()} != expected:
        raise AsaasSalesPreflightError("entry_snapshot_acl_invalid")
    cursor.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE role.rolname END,
               acl.privilege_type, acl.is_grantable
        FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(relation.relacl, pg_catalog.acldefault('r', relation.relowner))
        ) acl
        LEFT JOIN pg_catalog.pg_roles role ON role.oid = acl.grantee
        WHERE namespace.nspname = 'public'
          AND relation.relname = 'asaas_entry_financial_snapshots'
          AND acl.grantee <> relation.relowner
        """
    )
    if cursor.fetchall():
        raise AsaasSalesPreflightError("entry_snapshot_acl_invalid")


def _validate_functions(cursor) -> None:
    cursor.execute(
        """
        SELECT
            procedure.proname,
            procedure.prosecdef,
            procedure.prorettype = 'pg_catalog.trigger'::pg_catalog.regtype,
            NOT owner.rolcanlogin
                AND NOT owner.rolsuper
                AND NOT owner.rolcreatedb
                AND NOT owner.rolcreaterole
                AND NOT owner.rolreplication
                AND NOT owner.rolbypassrls,
            NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_auth_members AS membership
                WHERE membership.member = owner.oid
                   OR membership.roleid = owner.oid
            ),
            NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_class AS owned_relation
                JOIN pg_catalog.pg_namespace AS owned_relation_namespace
                  ON owned_relation_namespace.oid = owned_relation.relnamespace
                WHERE owned_relation.relowner = owner.oid
                  AND NOT (
                    owned_relation_namespace.nspname = 'public'
                    AND owned_relation.relkind = 'v'
                    AND owned_relation.relname = 'asaas_sandbox_receiver_link_metadata'
                  )
            )
                AND NOT EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_namespace AS owned_namespace
                    WHERE owned_namespace.nspowner = owner.oid
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_database AS owned_database
                    WHERE owned_database.datdba = owner.oid
                ),
            NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_proc AS owned_function
                JOIN pg_catalog.pg_namespace AS owned_function_namespace
                  ON owned_function_namespace.oid =
                        owned_function.pronamespace
                WHERE owned_function.proowner = owner.oid
                  AND (
                      owned_function_namespace.nspname <> 'public'
                      OR NOT (
                          (owned_function.pronargs = 0
                           AND owned_function.proname::TEXT = ANY(%s))
                          OR (owned_function.proname = %s
                              AND owned_function.pronargs = 5
                              AND owned_function.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int4'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype, 'varchar'::pg_catalog.regtype]::oidvector)
                          OR (owned_function.proname = %s
                              AND owned_function.pronargs = 2
                              AND owned_function.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int8'::pg_catalog.regtype]::oidvector)
                      )
                  )
            ),
            pg_catalog.has_schema_privilege(
                owner.oid,
                'public',
                'USAGE'
            )
                AND NOT pg_catalog.has_schema_privilege(
                    owner.oid,
                    'public',
                    'CREATE'
                ),
            NOT EXISTS (
                SELECT 1
                FROM pg_catalog.aclexplode(
                    COALESCE(
                        procedure.proacl,
                        pg_catalog.acldefault('f', procedure.proowner)
                    )
                ) AS function_acl
                WHERE function_acl.grantee = 0
                  AND function_acl.privilege_type = 'EXECUTE'
            ),
            EXISTS (
                SELECT 1
                FROM pg_catalog.unnest(
                    COALESCE(procedure.proconfig, ARRAY[]::TEXT[])
                ) AS setting
                WHERE pg_catalog.regexp_replace(
                    setting,
                    '[[:space:]]',
                    '',
                    'g'
                ) = 'search_path=pg_catalog,pg_temp'
            ),
            NOT pg_catalog.has_function_privilege(
                current_user,
                procedure.oid,
                'EXECUTE'
            ),
            owner.rolname,
            language.lanname,
            procedure.prosrc,
            procedure.proconfig
        FROM pg_catalog.pg_proc AS procedure
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = procedure.pronamespace
        JOIN pg_catalog.pg_roles AS owner
          ON owner.oid = procedure.proowner
        JOIN pg_catalog.pg_language AS language
          ON language.oid = procedure.prolang
        WHERE namespace.nspname = 'public'
          AND procedure.prokind = 'f'
          AND procedure.pronargs = 0
          AND procedure.proname::TEXT = ANY(%s)
        """,
        (
            list(_REQUIRED_FUNCTIONS),
            _SANDBOX_RECEIVER_FUNCTION,
            _ENTRY_SNAPSHOT_CONSUME_FUNCTION,
            list(_REQUIRED_FUNCTIONS),
        ),
    )
    rows = cursor.fetchall()
    names = {str(row[0]) for row in rows}
    owners = {str(row[11]) for row in rows}
    if (
        names != _REQUIRED_FUNCTIONS
        or len(owners) != 1
        or any(
            value is not True
            for row in rows
            for value in row[1:11]
        )
        or any(
            str(row[12]) != "plpgsql"
            or hashlib.sha256(str(row[13]).encode("utf-8")).hexdigest()
            != _REQUIRED_FUNCTION_BODY_SHA256.get(str(row[0]))
            or tuple(
                "".join(str(setting).split()).casefold()
                for setting in (row[14] or ())
            )
            != ("search_path=pg_catalog,pg_temp",)
            for row in rows
        )
    ):
        raise AsaasSalesPreflightError(
            "database_functions_incomplete"
        )

    owner_name = next(iter(owners))
    cursor.execute(
        """
        SELECT
            procedure.prosecdef AND procedure.prokind = 'f',
            procedure.pronargs = 2
              AND procedure.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int8'::pg_catalog.regtype]::oidvector
              AND procedure.prorettype = 'int8'::pg_catalog.regtype
              AND procedure.provolatile = 'v'
              AND procedure.proisstrict,
            language.lanname = 'sql',
            procedure.proconfig = ARRAY['search_path=pg_catalog, pg_temp'],
            procedure.proowner = owner.oid,
            procedure.prosrc
        FROM pg_catalog.pg_proc AS procedure
        JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
        JOIN pg_catalog.pg_roles AS owner ON owner.rolname = %s
        JOIN pg_catalog.pg_language AS language ON language.oid = procedure.prolang
        WHERE namespace.nspname = 'public'
          AND procedure.proname = %s
          AND procedure.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int8'::pg_catalog.regtype]::oidvector
          AND (SELECT count(*) FROM pg_catalog.pg_proc matching
               JOIN pg_catalog.pg_namespace matching_namespace ON matching_namespace.oid = matching.pronamespace
               WHERE matching_namespace.nspname = 'public'
                 AND matching.proname = %s
                 AND matching.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int8'::pg_catalog.regtype]::oidvector) = 1
        """,
        (owner_name, _ENTRY_SNAPSHOT_CONSUME_FUNCTION, _ENTRY_SNAPSHOT_CONSUME_FUNCTION),
    )
    consume_row = cursor.fetchone()
    if (
        not consume_row
        or len(consume_row) != 6
        or any(value is not True for value in consume_row[:5])
        or hashlib.sha256(str(consume_row[5]).encode("utf-8")).hexdigest()
        != _ENTRY_SNAPSHOT_CONSUME_FUNCTION_BODY_SHA256
    ):
        raise AsaasSalesPreflightError("database_functions_incomplete")
    runtime_role = _runtime_role_name(cursor)
    cursor.execute(
        """
        SELECT CASE WHEN acl.grantee = 0 THEN 'PUBLIC' ELSE role.rolname END,
               acl.privilege_type, acl.is_grantable
        FROM pg_catalog.pg_proc procedure
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = procedure.pronamespace
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(procedure.proacl, pg_catalog.acldefault('f', procedure.proowner))
        ) acl
        LEFT JOIN pg_catalog.pg_roles role ON role.oid = acl.grantee
        WHERE namespace.nspname = 'public'
          AND procedure.proname = %s
          AND procedure.proargtypes = ARRAY['int8'::pg_catalog.regtype, 'int8'::pg_catalog.regtype]::oidvector
          AND acl.grantee <> procedure.proowner
        """,
        (_ENTRY_SNAPSHOT_CONSUME_FUNCTION,),
    )
    if set(tuple(row) for row in cursor.fetchall()) != {(runtime_role, "EXECUTE", False)}:
        raise AsaasSalesPreflightError("database_privileges_excessive")
    _validate_function_owner_privileges(cursor, owner_name)
    _validate_external_schema_privileges(cursor, owner_name)

    cursor.execute(
        """
        SELECT
            audited_role.rolname,
            procedure.proname AS public_security_definer_privilege,
            procedure.pronargs,
            procedure.prokind
        FROM pg_catalog.pg_roles AS audited_role
        CROSS JOIN pg_catalog.pg_proc AS procedure
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = procedure.pronamespace
        WHERE (
                  audited_role.rolname = current_user
                  OR audited_role.rolname::TEXT = %s
              )
          AND namespace.nspname = 'public'
          AND procedure.prosecdef
          AND pg_catalog.has_function_privilege(
              audited_role.oid,
              procedure.oid,
              'EXECUTE'
          )
        """,
        (owner_name,),
    )
    public_security_definer_rows = cursor.fetchall()
    public_security_definer_privileges = {
        (
            str(row[0]),
            str(row[1]),
            int(row[2]),
            str(row[3]),
        )
        for row in public_security_definer_rows
    }
    expected_owner_privileges = {
        (owner_name, function_name, 0, "f")
        for function_name in _REQUIRED_FUNCTIONS
    }
    expected_owner_privileges |= {
        (owner_name, _SANDBOX_RECEIVER_FUNCTION, 5, "f"),
        (owner_name, _ENTRY_SNAPSHOT_CONSUME_FUNCTION, 2, "f"),
    }
    expected_runtime_cipher_privilege = {
        (runtime_role, _SANDBOX_RECEIVER_FUNCTION, 5, "f")
    }
    expected_runtime_consume_privilege = {
        (runtime_role, _ENTRY_SNAPSHOT_CONSUME_FUNCTION, 2, "f")
    }
    if not expected_owner_privileges.issubset(
        public_security_definer_privileges
    ):
        raise AsaasSalesPreflightError(
            "database_functions_incomplete"
        )
    if (
        public_security_definer_privileges
        != expected_owner_privileges | expected_runtime_cipher_privilege | expected_runtime_consume_privilege
        or len(public_security_definer_rows)
        != len(expected_owner_privileges | expected_runtime_cipher_privilege | expected_runtime_consume_privilege)
    ):
        raise AsaasSalesPreflightError(
            "database_privileges_excessive"
        )


def _validate_function_owner_privileges(cursor, owner_name: str) -> None:
    owner_tables = frozenset(
        _REQUIRED_FUNCTION_OWNER_COLUMN_PRIVILEGES
    )
    cursor.execute(
        """
        SELECT
            relation.relname,
            requested_privilege.name,
            pg_catalog.has_table_privilege(
                %s,
                relation.oid,
                requested_privilege.name
            ) AS function_owner_table_privilege
        FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        CROSS JOIN pg_catalog.unnest(
            %s::TEXT[]
        ) AS requested_privilege(name)
        WHERE namespace.nspname = 'public'
          AND relation.relname::TEXT = ANY(%s)
        """,
        (
            owner_name,
            list(_TABLE_PRIVILEGES),
            list(owner_tables),
        ),
    )
    table_privilege_rows = cursor.fetchall()
    if len(table_privilege_rows) != (
        len(owner_tables) * len(_TABLE_PRIVILEGES)
    ):
        raise AsaasSalesPreflightError(
            "database_privileges_incomplete"
        )
    if any(bool(row[2]) for row in table_privilege_rows):
        raise AsaasSalesPreflightError(
            "database_privileges_excessive"
        )

    cursor.execute(
        """
        SELECT
            relation.relname,
            attribute.attname,
            requested_privilege.name,
            pg_catalog.has_column_privilege(
                %s,
                relation.oid,
                attribute.attnum,
                requested_privilege.name
            ) AS function_owner_column_privilege
        FROM pg_catalog.pg_attribute AS attribute
        JOIN pg_catalog.pg_class AS relation
          ON relation.oid = attribute.attrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        CROSS JOIN pg_catalog.unnest(
            %s::TEXT[]
        ) AS requested_privilege(name)
        WHERE namespace.nspname = 'public'
          AND relation.relname::TEXT = ANY(%s)
          AND attribute.attnum > 0
          AND NOT attribute.attisdropped
        """,
        (
            owner_name,
            list(_COLUMN_PRIVILEGES),
            list(owner_tables),
        ),
    )
    column_privilege_rows = cursor.fetchall()
    expected_required_rows = {
        (table, column, privilege)
        for table, privilege_map
        in _REQUIRED_FUNCTION_OWNER_COLUMN_PRIVILEGES.items()
        for privilege, columns in privilege_map.items()
        for column in columns
    }
    observed_rows = {
        (str(table), str(column), str(privilege))
        for table, column, privilege, _granted
        in column_privilege_rows
    }
    if not expected_required_rows.issubset(observed_rows):
        raise AsaasSalesPreflightError(
            "database_privileges_incomplete"
        )
    for table, column, privilege, granted in column_privilege_rows:
        expected = column in (
            _REQUIRED_FUNCTION_OWNER_COLUMN_PRIVILEGES.get(
                str(table),
                {},
            ).get(str(privilege), ())
        )
        if bool(granted) != expected:
            code = (
                "database_privileges_incomplete"
                if expected
                else "database_privileges_excessive"
            )
            raise AsaasSalesPreflightError(code)

    cursor.execute(
        """
        SELECT
            relation.relname,
            requested_privilege.name
                AS function_owner_unexpected_privilege
        FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        CROSS JOIN pg_catalog.unnest(
            %s::TEXT[]
        ) AS requested_privilege(name)
        WHERE namespace.nspname = 'public'
          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND relation.relname::TEXT <> ALL(%s)
          AND NOT (
              relation.relkind = 'v'
              AND relation.relname = %s
              AND relation.relowner = (
                  SELECT view_owner.oid
                  FROM pg_catalog.pg_roles AS view_owner
                  WHERE view_owner.rolname = %s
              )
          )
          AND (
              pg_catalog.has_table_privilege(
                  %s,
                  relation.oid,
                  requested_privilege.name
              )
              OR (
                  requested_privilege.name IN (
                      'SELECT',
                      'INSERT',
                      'UPDATE',
                      'REFERENCES'
                  )
                  AND pg_catalog.has_any_column_privilege(
                      %s,
                      relation.oid,
                      requested_privilege.name
                  )
              )
          )
        """,
        (
            list(_TABLE_PRIVILEGES),
            list(owner_tables),
            _SANDBOX_RECEIVER_VIEW,
            owner_name,
            owner_name,
            owner_name,
        ),
    )
    unexpected_privileges = {
        (str(row[0]), str(row[1])) for row in cursor.fetchall()
    } - _PUBLIC_TABLE_PRIVILEGE_EXCEPTIONS
    if unexpected_privileges:
        raise AsaasSalesPreflightError(
            "database_privileges_excessive"
        )

    cursor.execute(
        """
        SELECT
            sequence.oid AS function_owner_sequence_privilege
        FROM pg_catalog.pg_class AS sequence
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = sequence.relnamespace
        WHERE namespace.nspname = 'public'
          AND sequence.relkind = 'S'
          AND EXISTS (
              SELECT 1
              FROM pg_catalog.unnest(
                  %s::TEXT[]
              ) AS requested_privilege(name)
              WHERE pg_catalog.has_sequence_privilege(
                  %s,
                  sequence.oid,
                  requested_privilege.name
              )
          )
        """,
        (
            ["USAGE", "SELECT", "UPDATE"],
            owner_name,
        ),
    )
    if cursor.fetchall():
        raise AsaasSalesPreflightError(
            "database_privileges_excessive"
        )


def _validate_external_schema_privileges(
    cursor,
    owner_name: str,
) -> None:
    cursor.execute(
        """
        SELECT (
            SELECT pg_catalog.count(*)
            FROM pg_catalog.pg_roles AS role_record
            WHERE role_record.rolname = current_user
               OR role_record.rolname::TEXT = %s
        ) = 2 AS external_audited_roles_complete
        """,
        (owner_name,),
    )
    role_row = cursor.fetchone()
    if not role_row or role_row != (True,):
        raise AsaasSalesPreflightError(
            "database_functions_incomplete"
        )

    cursor.execute(
        """
        SELECT
            audited_role.rolname,
            namespace.nspname
                AS unexpected_external_schema_privilege
        FROM pg_catalog.pg_roles AS audited_role
        CROSS JOIN pg_catalog.pg_namespace AS namespace
        WHERE (
                  audited_role.rolname = current_user
                  OR audited_role.rolname::TEXT = %s
              )
          AND namespace.nspname <> 'public'
          AND namespace.nspname <> 'information_schema'
          AND namespace.nspname !~ '^pg_'
          AND (
              pg_catalog.has_schema_privilege(
                  audited_role.oid,
                  namespace.oid,
                  'USAGE'
              )
              OR pg_catalog.has_schema_privilege(
                  audited_role.oid,
                  namespace.oid,
                  'CREATE'
              )
          )
        """,
        (owner_name,),
    )
    if cursor.fetchall():
        raise AsaasSalesPreflightError(
            "database_privileges_excessive"
        )

    cursor.execute(
        """
        SELECT
            audited_role.rolname,
            relation.oid AS unexpected_external_relation_privilege
        FROM pg_catalog.pg_roles AS audited_role
        CROSS JOIN pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE (
                  audited_role.rolname = current_user
                  OR audited_role.rolname::TEXT = %s
              )
          AND namespace.nspname <> 'public'
          AND namespace.nspname <> 'information_schema'
          AND namespace.nspname !~ '^pg_'
          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND (
              EXISTS (
                  SELECT 1
                  FROM pg_catalog.unnest(
                      %s::TEXT[]
                  ) AS requested_table_privilege(name)
                  WHERE pg_catalog.has_table_privilege(
                      audited_role.oid,
                      relation.oid,
                      requested_table_privilege.name
                  )
              )
              OR EXISTS (
                  SELECT 1
                  FROM pg_catalog.unnest(
                      %s::TEXT[]
                  ) AS requested_column_privilege(name)
                  WHERE pg_catalog.has_any_column_privilege(
                      audited_role.oid,
                      relation.oid,
                      requested_column_privilege.name
                  )
              )
          )
        """,
        (
            owner_name,
            list(_TABLE_PRIVILEGES),
            list(_COLUMN_PRIVILEGES),
        ),
    )
    if cursor.fetchall():
        raise AsaasSalesPreflightError(
            "database_privileges_excessive"
        )

    cursor.execute(
        """
        SELECT
            audited_role.rolname,
            sequence.oid AS unexpected_external_sequence_privilege
        FROM pg_catalog.pg_roles AS audited_role
        CROSS JOIN pg_catalog.pg_class AS sequence
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = sequence.relnamespace
        WHERE (
                  audited_role.rolname = current_user
                  OR audited_role.rolname::TEXT = %s
              )
          AND namespace.nspname <> 'public'
          AND namespace.nspname <> 'information_schema'
          AND namespace.nspname !~ '^pg_'
          AND sequence.relkind = 'S'
          AND EXISTS (
              SELECT 1
              FROM pg_catalog.unnest(
                  %s::TEXT[]
              ) AS requested_privilege(name)
              WHERE pg_catalog.has_sequence_privilege(
                  audited_role.oid,
                  sequence.oid,
                  requested_privilege.name
              )
          )
        """,
        (
            owner_name,
            ["USAGE", "SELECT", "UPDATE"],
        ),
    )
    if cursor.fetchall():
        raise AsaasSalesPreflightError(
            "database_privileges_excessive"
        )

    cursor.execute(
        """
        SELECT
            audited_role.rolname,
            procedure.oid
                AS unexpected_external_security_definer_privilege
        FROM pg_catalog.pg_roles AS audited_role
        CROSS JOIN pg_catalog.pg_proc AS procedure
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = procedure.pronamespace
        WHERE (
                  audited_role.rolname = current_user
                  OR audited_role.rolname::TEXT = %s
              )
          AND namespace.nspname <> 'public'
          AND namespace.nspname <> 'information_schema'
          AND namespace.nspname !~ '^pg_'
          AND procedure.prosecdef
          AND pg_catalog.has_function_privilege(
              audited_role.oid,
              procedure.oid,
              'EXECUTE'
          )
        """,
        (owner_name,),
    )
    if cursor.fetchall():
        raise AsaasSalesPreflightError(
            "database_privileges_excessive"
        )


def _validate_triggers(cursor) -> None:
    cursor.execute(
        """
        SELECT
            trigger_record.tgname,
            relation.relname,
            procedure_namespace.nspname,
            procedure.proname,
            trigger_record.tgtype,
            ARRAY(
                SELECT attribute.attname
                FROM pg_catalog.pg_attribute AS attribute
                WHERE attribute.attrelid = relation.oid
                  AND attribute.attnum = ANY(
                      trigger_record.tgattr::SMALLINT[]
                )
                ORDER BY attribute.attname
            ),
            trigger_record.tgenabled,
            trigger_record.tgqual IS NULL
        FROM pg_catalog.pg_trigger AS trigger_record
        JOIN pg_catalog.pg_class AS relation
          ON relation.oid = trigger_record.tgrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        JOIN pg_catalog.pg_proc AS procedure
          ON procedure.oid = trigger_record.tgfoid
        JOIN pg_catalog.pg_namespace AS procedure_namespace
          ON procedure_namespace.oid = procedure.pronamespace
        WHERE namespace.nspname = 'public'
          AND NOT trigger_record.tgisinternal
          AND relation.relname::TEXT = ANY(%s)
        """,
        (list(_SEQUENCE_TABLES),),
    )
    triggers = {
        (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
            int(row[4]),
            tuple(str(value) for value in row[5]),
            str(row[6]),
            bool(row[7]),
        )
        for row in cursor.fetchall()
    }
    expected = {
        (
            name,
            table,
            "public",
            function,
            trigger_type,
            update_columns,
            "O",
            True,
        )
        for name, (
            table,
            function,
            trigger_type,
            update_columns,
        ) in _REQUIRED_TRIGGERS.items()
    }
    if triggers != expected:
        raise AsaasSalesPreflightError("database_triggers_incomplete")


def _validate_constraints(cursor) -> None:
    cursor.execute(
        """
        SELECT
            constraint_record.conname,
            relation.relname,
            constraint_record.contype,
            pg_catalog.pg_get_constraintdef(
                constraint_record.oid,
                TRUE
            )
        FROM pg_catalog.pg_constraint AS constraint_record
        JOIN pg_catalog.pg_class AS relation
          ON relation.oid = constraint_record.conrelid
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND constraint_record.convalidated
          AND NOT constraint_record.condeferrable
          AND constraint_record.conname::TEXT = ANY(%s)
        """,
        (list(_REQUIRED_CONSTRAINTS),),
    )
    constraints = {
        (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            _canonicalize_constraint_definition(str(row[0]), row[3]),
        )
        for row in cursor.fetchall()
    }
    constraint_type_by_prefix = {"fk_": "f", "uq_": "u", "chk_": "c"}
    expected = {
        (
            name,
            table,
            next(
                constraint_type
                for prefix, constraint_type in constraint_type_by_prefix.items()
                if name.startswith(prefix)
            ),
            _canonicalize_constraint_definition(
                name,
                _REQUIRED_CONSTRAINT_DEFINITIONS[name]
            ),
        )
        for name, table in _REQUIRED_CONSTRAINTS.items()
    }
    if constraints != expected:
        raise AsaasSalesPreflightError(
            "database_constraints_incomplete"
        )


def _normalize_constraint_definition(value: object) -> str:
    return "".join(str(value).split()).replace('"', "").casefold()


def _canonicalize_constraint_definition(name: str, value: object) -> str:
    normalized = _normalize_constraint_definition(value)
    variants = _POSTGRESQL_16_CONSTRAINT_DEFINITION_VARIANTS.get(name)
    if variants is None:
        return normalized
    normalized_variants = tuple(
        _normalize_constraint_definition(variant) for variant in variants
    )
    if normalized in normalized_variants:
        return normalized_variants[0]
    return normalized


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Valida a configuração local do fluxo de vendas Asaas sem "
            "chamar o provedor ou escrever no banco."
        )
    )
    parser.add_argument(
        "--unit",
        action="append",
        dest="units",
        help="Unidade a validar; repita a opção para validar isolamento.",
    )
    parser.add_argument(
        "--allow-no-units",
        action="store_true",
        help=(
            "Permite validar um runtime ainda inativo, com as allowlists "
            "vazias."
        ),
    )
    parser.add_argument(
        "--exclude-pf-user-id",
        action="append",
        dest="excluded_pf_user_ids",
        help=(
            "ID operacional PF a excluir somente do gate de prontidao; "
            "repita a opcao. Quando informado, substitui o manifesto."
        ),
    )
    args = parser.parse_args(argv)
    try:
        result = run_asaas_sales_preflight(
            args.units,
            allow_no_units=args.allow_no_units,
            excluded_pf_user_ids=args.excluded_pf_user_ids,
        )
    except AsaasSalesPreflightError as exc:
        print(
            json.dumps(
                {"status": "failed", "reason": exc.code},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
