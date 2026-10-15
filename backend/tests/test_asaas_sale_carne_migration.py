import re
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    BACKEND_ROOT / "migrations/add_asaas_sale_carne_support.sql"
)
SPLIT_PLAN_MIGRATION_PATH = (
    BACKEND_ROOT / "migrations/create_asaas_sale_split_plans.sql"
)
ACCOUNT_ATTEMPT_MIGRATION_PATH = (
    BACKEND_ROOT
    / "migrations/create_asaas_account_provision_attempts.sql"
)


class AsaasSaleCarneMigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MIGRATION_PATH.read_text(encoding="utf-8")
        cls.sql = " ".join(cls.source.casefold().split())

    def _between(self, start: str, end: str) -> str:
        start_offset = self.sql.index(start)
        end_offset = self.sql.index(end, start_offset)
        return self.sql[start_offset:end_offset]

    def test_migration_is_atomic_with_bounded_waits(self):
        self.assertIn("set local lock_timeout = '5s'", self.sql)
        self.assertIn("set local statement_timeout = '10min'", self.sql)
        self.assertNotIn("concurrently", self.sql)
        self.assertEqual(self.source.count("\nCOMMIT;"), 1)
        self.assertTrue(self.source.rstrip().endswith("COMMIT;"))

    def test_migration_does_not_change_shared_payment_method_or_parcela_schema(self):
        self.assertNotIn("formas_pagamento", self.sql)
        self.assertNotIn("alter table public.venda_parcelas", self.sql)
        self.assertNotRegex(
            self.sql,
            r"create\s+(unique\s+)?index[^;]+on\s+public\.venda_parcelas",
        )
        self.assertNotIn("insert into public.vendas", self.sql)
        self.assertNotIn("insert into public.venda_parcelas", self.sql)

    def test_migration_is_additive_and_does_not_rewrite_business_rows(self):
        for table in (
            "asaas_sale_discount_rules",
            "asaas_sale_items",
            "asaas_sale_payment_links",
        ):
            self.assertIn(
                f"create table if not exists public.{table}",
                self.sql,
            )
        self.assertNotRegex(self.sql, r"\bdrop\s+(table|column)\b")
        self.assertNotRegex(self.sql, r"\btruncate\b")
        self.assertNotIn("delete from", self.sql)
        self.assertNotIn("update public.vendas", self.sql)

    def test_remote_check_constraints_are_replaceable_on_rerun(self):
        for constraint_name in (
            "chk_asaas_sale_remote_attempt_metadata",
            "chk_asaas_sale_remote_state_attempts",
            "chk_asaas_sale_remote_uncertain_state",
            "chk_asaas_sale_remote_reconciliation_state",
            "chk_asaas_sale_remote_confirmation",
        ):
            self.assertIn(
                f"drop constraint if exists {constraint_name}",
                self.sql,
            )
            self.assertIn(
                f"add constraint {constraint_name}",
                self.sql,
            )
            self.assertIn(
                f"validate constraint {constraint_name}",
                self.sql,
            )

    def test_remote_attempt_metadata_allows_remote_discovery_without_local_post(self):
        state_sql = self._between(
            "add constraint chk_asaas_sale_remote_attempt_metadata",
            "add constraint chk_asaas_sale_remote_uncertain_state",
        )
        uncertain_sql = self._between(
            "add constraint chk_asaas_sale_remote_uncertain_state",
            "add constraint chk_asaas_sale_remote_reconciliation_state",
        )

        self.assertIn(
            "remote_attempt_count = 0 and last_remote_attempt_at is null",
            state_sql,
        )
        self.assertIn(
            "remote_attempt_count > 0 and last_remote_attempt_at is not null",
            state_sql,
        )
        self.assertIn(
            "remote_creation_state = 'requisicao_iniciada' and "
            "remote_attempt_count > 0",
            state_sql,
        )
        self.assertIn(
            "remote_creation_state in ( 'resultado_incerto', "
            "'confirmado', 'falha_terminal' )",
            state_sql,
        )
        self.assertIn("remote_result_unknown_at is not null", uncertain_sql)
        self.assertIn("and reconciliation_required", uncertain_sql)
        self.assertNotIn("remote_attempt_count > 0", uncertain_sql)

    def test_request_fingerprint_supports_payload_idempotency(self):
        self.assertIn(
            "add column if not exists request_fingerprint char(64)",
            self.sql,
        )
        self.assertIn("request_fingerprint is null", self.sql)
        self.assertIn(
            "request_fingerprint ~ '^[a-f0-9]{64}$'",
            self.sql,
        )

    def test_discount_rules_are_provider_owned_empty_and_strict(self):
        table_sql = self._between(
            "create table if not exists public.asaas_sale_discount_rules",
            "create index if not exists idx_asaas_sale_discount_rule_lookup",
        )
        for column in (
            "id bigserial primary key",
            "unidade varchar(100) not null",
            "payment_method varchar(40) not null",
            "installment_min integer not null",
            "installment_max integer not null",
            "percentage numeric(5, 2) not null",
            "active boolean not null default true",
            "created_at timestamptz not null default now()",
            "updated_at timestamptz not null default now()",
        ):
            self.assertIn(column, table_sql)
        for payment_method in (
            "asaas_boleto_installment",
            "asaas_pix_automatic",
            "asaas_credit_card_recurrent",
        ):
            self.assertIn(f"'{payment_method}'", table_sql)
        self.assertIn("check (installment_min > 0)", table_sql)
        self.assertIn("check (installment_max >= installment_min)", table_sql)
        self.assertIn(
            "check (percentage >= 0 and percentage < 100)",
            table_sql,
        )
        self.assertIn(
            "unique ( unidade, payment_method, installment_min, "
            "installment_max, percentage )",
            table_sql,
        )
        self.assertNotIn("insert into public.asaas_sale_discount_rules", self.sql)

    def test_sale_item_snapshot_is_scoped_and_contains_no_description(self):
        table_sql = self._between(
            "create table if not exists public.asaas_sale_items",
            "create index if not exists idx_asaas_sale_item_product",
        )
        for column in (
            "integration_id bigint not null",
            "venda_id integer not null",
            "product_id integer not null",
            "item_number integer not null",
            "quantity integer not null",
            "unit_value numeric(12, 2) not null",
            "total_value numeric(12, 2) not null",
        ):
            self.assertIn(column, table_sql)
        self.assertIn(
            "foreign key (integration_id, venda_id) references "
            "public.asaas_sale_integrations (id, venda_id) on delete restrict",
            table_sql,
        )
        self.assertIn(
            "foreign key (product_id) references public.produtos (id) "
            "on delete restrict",
            table_sql,
        )
        self.assertIn("unique (integration_id, item_number)", table_sql)
        self.assertIn("unique (venda_id, item_number)", table_sql)
        self.assertIn("check (total_value = unit_value * quantity)", table_sql)
        for prohibited in (
            "description",
            "descricao",
            "observacao",
            "patient",
            "paciente",
        ):
            self.assertNotIn(prohibited, table_sql)

    def test_payment_link_uses_existing_sale_installment_key(self):
        table_sql = self._between(
            "create table if not exists public.asaas_sale_payment_links",
            "create index if not exists idx_asaas_sale_payment_link_venda",
        )
        self.assertNotIn("venda_parcela_id", table_sql)
        self.assertIn(
            "foreign key (venda_id, numero_parcela) references "
            "public.venda_parcelas (venda_id, numero_parcela) "
            "on delete restrict",
            table_sql,
        )
        self.assertIn(
            "references public.asaas_sale_integrations ( id, venda_id, "
            "unidade, environment, account_wallet_id ) on delete restrict",
            table_sql,
        )
        self.assertIn(
            "references public.asaas_sale_resources ( id, integration_id, "
            "unidade, environment, account_wallet_id, resource_type ) "
            "on delete restrict",
            table_sql,
        )
        self.assertIn("unique (resource_id)", table_sql)
        self.assertIn("unique (integration_id, numero_parcela)", table_sql)

    def test_va_sale_insert_requires_transaction_local_context(self):
        guard_sql = self._between(
            "create or replace function public.asaas_guard_venda_odontograma",
            "create or replace function public.asaas_protect_integrated_venda",
        )
        self.assertIn("new.documento_venda like 'va-%'", guard_sql)
        self.assertIn("tg_op = 'insert'", guard_sql)
        self.assertIn(
            "pg_catalog.current_setting( 'app.asaas_sale_creation', true )",
            guard_sql,
        )
        self.assertIn("asaas_sale_creation_context_required", guard_sql)
        self.assertNotIn("forma_pagamento", guard_sql)

    def test_integration_parent_invariant_is_preflighted_and_enforced(self):
        self.assertIn("asaas_sale_existing_integration_incompatible", self.sql)
        self.assertIn("sale.documento_venda not like 'va-%'", self.sql)
        self.assertIn("sale.forma_pagamento_id is not null", self.sql)
        self.assertIn(
            "sale.status_venda is not distinct from 'pendente asaas' and "
            "integration.remote_creation_state in ( 'nao_iniciado', "
            "'requisicao_iniciada', 'resultado_incerto' )",
            self.sql,
        )
        self.assertIn(
            "sale.status_venda is not distinct from 'efetuada' and "
            "integration.remote_creation_state = 'confirmado'",
            self.sql,
        )
        function_sql = self._between(
            "create or replace function "
            "public.asaas_validate_sale_integration_parent",
            "create or replace function public.asaas_guard_venda_odontograma",
        )
        self.assertIn("new.venda_id is distinct from old.venda_id", function_sql)
        self.assertIn("asaas_sale_integration_sale_immutable", function_sql)
        self.assertIn("app.asaas_sale_creation", function_sql)
        self.assertIn("parent_sale.documento_venda like 'va-%'", function_sql)
        self.assertIn("parent_sale.forma_pagamento_id is null", function_sql)
        self.assertIn(
            "parent_sale.status_venda = 'pendente asaas'",
            function_sql,
        )
        self.assertIn("asaas_sale_integration_parent_invalid", function_sql)
        self.assertIn(
            "before insert or update of venda_id on "
            "public.asaas_sale_integrations",
            self.sql,
        )

    def test_odontogram_guard_serializes_only_cross_flow_conflicts(self):
        guard_sql = self._between(
            "create or replace function public.asaas_guard_venda_odontograma",
            "create or replace function public.asaas_protect_integrated_venda",
        )
        self.assertIn("asaas-sale-odontograma:", guard_sql)
        self.assertIn("pg_catalog.pg_advisory_xact_lock", guard_sql)
        self.assertIn("if new_sale_is_asaas then", guard_sql)
        self.assertIn("elsif exists", guard_sql)
        self.assertIn(
            "where integration.venda_id = other_sale.id",
            guard_sql,
        )
        self.assertIn(
            "other_sale.status_venda is distinct from 'cancelada'",
            guard_sql,
        )
        self.assertIn("asaas_sale_odontogram_active_conflict", guard_sql)
        self.assertIn(
            "before insert or update of odontograma_id, status_venda, "
            "documento_venda",
            self.sql,
        )

    def test_sale_protection_returns_before_query_for_legacy_documents(self):
        protection_sql = self._between(
            "create or replace function public.asaas_protect_integrated_venda",
            "create or replace function "
            "public.asaas_protect_integrated_venda_parcela",
        )
        legacy_return = protection_sql.index(
            "old.documento_venda not like 'va-%'"
        )
        integration_query = protection_sql.index(
            "from public.asaas_sale_integrations"
        )
        self.assertLess(legacy_return, integration_query)
        self.assertIn(
            "pg_catalog.to_jsonb(new) - array['status_venda', 'updated_at']",
            protection_sql,
        )
        self.assertIn("old.status_venda = 'pendente asaas'", protection_sql)
        self.assertIn("new.status_venda = 'efetuada'", protection_sql)
        self.assertIn("integration_remote_state = 'confirmado'", protection_sql)
        self.assertIn("new.status_venda = 'cancelada'", protection_sql)
        self.assertIn(
            "integration_remote_state = 'falha_terminal'",
            protection_sql,
        )

    def test_va_installments_allow_only_initial_context_insert(self):
        parcela_sql = self._between(
            "create or replace function "
            "public.asaas_protect_integrated_venda_parcela",
            "revoke all on function public.asaas_guard_venda_odontograma",
        )
        self.assertIn("if tg_op = 'insert' then", parcela_sql)
        integration_check = parcela_sql.index(
            "from public.asaas_sale_integrations"
        )
        legacy_return = parcela_sql.index("if not parent_sale_is_asaas then")
        self.assertLess(integration_check, legacy_return)
        self.assertIn(
            "from public.vendas as parent_sale where parent_sale.id = "
            "new.venda_id and parent_sale.documento_venda like 'va-%'",
            parcela_sql,
        )
        self.assertIn(
            "coalesce(new.documento_referencia, '') not like 'va-%'",
            parcela_sql,
        )
        self.assertIn("asaas_sale_installment_document_invalid", parcela_sql)
        self.assertIn("app.asaas_sale_creation", parcela_sql)
        self.assertIn(
            "where integration.venda_id = new.venda_id",
            parcela_sql,
        )
        self.assertIn("asaas_sale_integrated_installment_immutable", parcela_sql)
        self.assertIn("before insert or update or delete", self.sql)

    def test_trigger_functions_are_hardened(self):
        self.assertEqual(self.sql.count("security definer"), 4)
        self.assertEqual(
            self.sql.count("set search_path = pg_catalog, public"),
            4,
        )
        self.assertEqual(
            self.sql.count("revoke all on function public.asaas_"),
            4,
        )
        self.assertEqual(self.sql.count("from public;"), 4)

    def test_migration_does_not_persist_sensitive_remote_material(self):
        for prohibited in (
            "raw_payload",
            "raw_response",
            "api_key",
            "access_token",
            "cpf_cnpj",
            "email_paciente",
            "telefone_paciente",
        ):
            self.assertNotIn(prohibited, self.sql)


class AsaasSplitAndAccountMigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.split_source = SPLIT_PLAN_MIGRATION_PATH.read_text(
            encoding="utf-8"
        )
        cls.split_sql = " ".join(cls.split_source.casefold().split())
        cls.account_source = ACCOUNT_ATTEMPT_MIGRATION_PATH.read_text(
            encoding="utf-8"
        )
        cls.account_sql = " ".join(cls.account_source.casefold().split())

    def test_new_migrations_are_atomic_with_bounded_waits_and_search_path(self):
        for source, sql in (
            (self.split_source, self.split_sql),
            (self.account_source, self.account_sql),
        ):
            self.assertEqual(source.count("\nBEGIN;"), 1)
            self.assertIn("set local lock_timeout = '5s'", sql)
            self.assertIn("set local statement_timeout = '10min'", sql)
            self.assertIn(
                "set local search_path = pg_catalog, public",
                sql,
            )
            self.assertEqual(source.count("\nCOMMIT;"), 1)
            self.assertTrue(source.rstrip().endswith("COMMIT;"))
            self.assertNotIn("concurrently", sql)

    def test_split_plan_fk_covers_the_full_integration_scope(self):
        self.assertIn(
            "constraint fk_asaas_sale_split_plan_integration_scope "
            "foreign key ( integration_id, venda_id, unidade, environment, "
            "account_wallet_id ) references public.asaas_sale_integrations "
            "( id, venda_id, unidade, environment, account_wallet_id ) "
            "on delete restrict",
            self.split_sql,
        )
        self.assertNotIn(
            "foreign key (integration_id) references "
            "public.asaas_sale_integrations",
            self.split_sql,
        )

    def test_split_plan_attempt_count_is_single_shot(self):
        self.assertIn(
            "constraint chk_asaas_sale_split_plans_attempt "
            "check (remote_attempt_count in (0, 1))",
            self.split_sql,
        )

    def test_split_plan_timeline_is_fail_closed_for_every_state(self):
        timeline_start = self.split_sql.index(
            "constraint chk_asaas_sale_split_plans_timeline"
        )
        timeline = self.split_sql[timeline_start:]

        self.assertIn(
            "lifecycle_state in ('sealed', 'blocked') and "
            "remote_attempt_count = 0 and remote_started_at is null and "
            "remote_confirmed_at is null and remote_uncertain_at is null",
            timeline,
        )
        self.assertIn(
            "lifecycle_state in ('started', 'rejected') and "
            "remote_attempt_count = 1 and remote_started_at is not null and "
            "remote_confirmed_at is null and remote_uncertain_at is null",
            timeline,
        )
        self.assertIn(
            "lifecycle_state = 'confirmed' and remote_attempt_count = 1 and "
            "remote_started_at is not null and "
            "remote_confirmed_at is not null and "
            "remote_confirmed_at >= remote_started_at and "
            "remote_uncertain_at is null",
            timeline,
        )
        self.assertIn(
            "lifecycle_state = 'uncertain' and remote_attempt_count = 1 and "
            "remote_started_at is not null and remote_confirmed_at is null "
            "and remote_uncertain_at is not null and "
            "remote_uncertain_at >= remote_started_at",
            timeline,
        )

    def test_account_attempts_keep_rejections_and_allow_one_new_active_retry(self):
        self.assertIn(
            "remote_rejected_at timestamptz",
            self.account_sql,
        )
        self.assertIn(
            "lifecycle_state in ( 'reserved', 'started', 'confirmed', "
            "'rejected', 'uncertain' )",
            self.account_sql,
        )
        self.assertIn(
            "lifecycle_state = 'rejected' and remote_attempt_count = 1 "
            "and remote_started_at is not null "
            "and remote_confirmed_at is null "
            "and remote_uncertain_at is null "
            "and remote_rejected_at is not null "
            "and remote_rejected_at >= remote_started_at",
            self.account_sql,
        )
        self.assertIn(
            "create unique index if not exists "
            "uq_asaas_account_provision_attempt_active_user "
            "on public.asaas_account_provision_attempts (user_id) "
            "where lifecycle_state <> 'rejected'",
            self.account_sql,
        )
        self.assertNotIn("unique (user_id)", self.account_sql)


if __name__ == "__main__":
    unittest.main()
