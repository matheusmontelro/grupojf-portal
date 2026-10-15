import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from app.services import asaas_sales_preflight as preflight
from app.services.asaas_split_service import AsaasDomainSplitRule, AsaasReceiverIdentity


_CARNE_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "add_asaas_sale_carne_support.sql"
).read_text(encoding="utf-8")
_FUNCTION_BODIES = dict(
    re.findall(
        r"CREATE OR REPLACE FUNCTION public\.(\w+)\(\).*?"
        r"AS \$function\$(.*?)\$function\$;",
        _CARNE_MIGRATION,
        flags=re.DOTALL,
    )
)
_SNAPSHOT_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "add_asaas_sandbox_entry_split_snapshot.sql"
).read_text(encoding="utf-8")
_ENTRY_SNAPSHOT_CONSUME_BODY = (
    _SNAPSHOT_MIGRATION.split(
        "CREATE OR REPLACE FUNCTION public.asaas_consume_entry_snapshot", 1
    )[1].split("AS $function$", 1)[1].split("$function$;", 1)[0]
)


class _DatabaseContext:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class _ReadyCursor:
    """Simula o catálogo PostgreSQL esperado pelo preflight."""

    _DENIED_COLUMNS = {
        "users": {"senha"},
        "pacientes": {"nome"},
        "vendas": {"created_at"},
        "venda_parcelas": {"created_at"},
        "asaas_sale_integrations": {"last_remote_attempt_at"},
        "asaas_sale_resources": {"created_at"},
        "asaas_sale_items": {"id", "created_at"},
        "asaas_sale_payment_links": {"created_at", "updated_at"},
    }

    def __init__(
        self,
        *,
        runtime_role_ready=True,
        rls_table=None,
        missing_column=None,
        table_privilege_overrides=None,
        column_privilege_overrides=None,
        unexpected_privileges=None,
        runtime_has_sandbox_receiver_view_privilege=False,
        runtime_has_entry_snapshot_privilege=False,
        missing_sequence_table=None,
        sequence_privilege_overrides=None,
        unrelated_sequence_privileges=None,
        missing_index=None,
        index_predicate_overrides=None,
        index_metadata_overrides=None,
        index_catalog_state_overrides=None,
        insecure_function=None,
        function_body_overrides=None,
        unexpected_security_definer=False,
        function_owner_table_privilege_overrides=None,
        function_owner_column_privilege_overrides=None,
        function_owner_unexpected_privileges=None,
        function_owner_owns_sandbox_receiver_view=False,
        function_owner_sequence_privileges=None,
        owner_unexpected_security_definer=False,
        external_roles_ready=True,
        external_privilege_kind=None,
        external_privilege_role="grupojf_asaas_sales_runtime",
        missing_trigger=None,
        extra_triggers=None,
        missing_constraint=None,
        constraint_definition_overrides=None,
        constraint_metadata_overrides=None,
        constraint_catalog_state_overrides=None,
        role_absorber_rule=False,
        company_absorber_rule=False,
        pf_exclusions_valid=True,
        pf_subaccounts_incomplete=False,
        sandbox_receiver_acl_ready=True,
        sandbox_receiver_view_definition=None,
        snapshot_contract_ready=True,
        entry_snapshot_consume_owner="grupojf_asaas_sales_owner",
        relation_acl_ready=True,
        runtime_role="grupojf_asaas_sales_runtime",
        eligible_pf_rows=None,
    ):
        self.runtime_role_ready = runtime_role_ready
        self.rls_table = rls_table
        self.missing_column = missing_column
        self.table_privilege_overrides = table_privilege_overrides or {}
        self.column_privilege_overrides = (
            column_privilege_overrides or {}
        )
        self.unexpected_privileges = unexpected_privileges or (
            ("contract_templates", "SELECT"),
        )
        self.runtime_has_sandbox_receiver_view_privilege = (
            runtime_has_sandbox_receiver_view_privilege
        )
        self.runtime_has_entry_snapshot_privilege = (
            runtime_has_entry_snapshot_privilege
        )
        self.missing_sequence_table = missing_sequence_table
        self.sequence_privilege_overrides = (
            sequence_privilege_overrides or {}
        )
        self.unrelated_sequence_privileges = (
            unrelated_sequence_privileges or {}
        )
        self.missing_index = missing_index
        self.index_predicate_overrides = (
            index_predicate_overrides or {}
        )
        self.index_metadata_overrides = index_metadata_overrides or {}
        self.index_catalog_state_overrides = (
            index_catalog_state_overrides or {}
        )
        self.insecure_function = insecure_function
        self.function_body_overrides = function_body_overrides or {}
        self.unexpected_security_definer = unexpected_security_definer
        self.function_owner_table_privilege_overrides = (
            function_owner_table_privilege_overrides or {}
        )
        self.function_owner_column_privilege_overrides = (
            function_owner_column_privilege_overrides or {}
        )
        self.function_owner_unexpected_privileges = (
            function_owner_unexpected_privileges
            if function_owner_unexpected_privileges is not None
            else (("contract_templates", "SELECT"),)
        )
        self.function_owner_owns_sandbox_receiver_view = (
            function_owner_owns_sandbox_receiver_view
        )
        self.function_owner_sequence_privileges = (
            function_owner_sequence_privileges or ()
        )
        self.owner_unexpected_security_definer = (
            owner_unexpected_security_definer
        )
        self.external_roles_ready = external_roles_ready
        self.external_privilege_kind = external_privilege_kind
        self.external_privilege_role = external_privilege_role
        self.missing_trigger = missing_trigger
        self.extra_triggers = extra_triggers or ()
        self.missing_constraint = missing_constraint
        self.constraint_definition_overrides = (
            constraint_definition_overrides or {}
        )
        self.constraint_metadata_overrides = (
            constraint_metadata_overrides or {}
        )
        self.constraint_catalog_state_overrides = (
            constraint_catalog_state_overrides or {}
        )
        self.role_absorber_rule = role_absorber_rule
        self.company_absorber_rule = company_absorber_rule
        self.pf_exclusions_valid = pf_exclusions_valid
        self.pf_subaccounts_incomplete = pf_subaccounts_incomplete
        self.sandbox_receiver_acl_ready = sandbox_receiver_acl_ready
        self.sandbox_receiver_view_definition = sandbox_receiver_view_definition
        self.snapshot_contract_ready = snapshot_contract_ready
        self.entry_snapshot_consume_owner = entry_snapshot_consume_owner
        self.relation_acl_ready = relation_acl_ready
        self.runtime_role = runtime_role
        self.eligible_pf_rows = eligible_pf_rows if eligible_pf_rows is not None else [
            (57, "São João de Meriti", 3),
            (58, "São João de Meriti", 3),
        ]
        self.last_query = ""
        self.last_params = ()
        self.queries = []

    @property
    def columns(self):
        columns_by_table = {
            table: {
                column
                for values in privilege_map.values()
                for column in values
            }
            for table, privilege_map in (
                preflight._REQUIRED_COLUMN_PRIVILEGES.items()
            )
        }
        for table, columns in self._DENIED_COLUMNS.items():
            columns_by_table[table].update(columns)
        for table, privileges in (
            preflight._REQUIRED_FUNCTION_OWNER_COLUMN_PRIVILEGES.items()
        ):
            columns_by_table.setdefault(table, set()).update(
                column
                for values in privileges.values()
                for column in values
            )
        columns = {
            (table, column)
            for table, table_columns in columns_by_table.items()
            for column in table_columns
        }
        if self.missing_column:
            columns.discard(self.missing_column)
        return columns

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query).split())
        self.last_params = params or ()
        self.queries.append((self.last_query, params))

    def fetchone(self):
        query = self.last_query
        params = self.last_params
        if query == "SELECT current_user AS runtime_role":
            return (self.runtime_role,)
        if "runtime.rolcanlogin" in query:
            values = [True] * 8
            if not self.runtime_role_ready:
                values[-1] = False
            return tuple(values)

        if "external_audited_roles_complete" in query:
            return (self.external_roles_ready,)

        if "incompatible_role_absorber_rule_exists" in query:
            return (
                self.role_absorber_rule,
                self.company_absorber_rule,
            )

        if "pf_exclusions_match_eligible_users" in query:
            return (self.pf_exclusions_valid,)

        if "pf_subaccounts_incomplete" in query:
            return (self.pf_subaccounts_incomplete,)

        if "view_record.relkind = 'v'" in query:
            body = """
    SELECT link.credential_ciphertext
    FROM public.asaas_receiver_environment_links AS link
    WHERE link.id = p_link_id
      AND link.user_id = p_user_id
      AND link.unidade = p_unidade
      AND link.environment = 'sandbox'
      AND link.account_id = p_account_id
      AND link.wallet_id = p_wallet_id
      AND link.credential_state = 'verified'
      AND link.credential_ciphertext IS NOT NULL
      AND BTRIM(link.credential_ciphertext) <> ''
    LIMIT 1
"""
            values = [
                True,
                True,
                self.sandbox_receiver_view_definition
                or "SELECT id, user_id, unidade, environment, account_id, wallet_id, credential_state FROM public.asaas_receiver_environment_links WHERE environment = 'sandbox'",
                True,
                True,
                True,
                True,
                True,
                body,
            ]
            if not self.sandbox_receiver_acl_ready:
                values[0] = False
            return tuple(values)

        if "snapshot_contract_complete" in query:
            return (True, True, self.snapshot_contract_ready)

        if "entry_snapshot_consume_owner" in query:
            return (self.entry_snapshot_consume_owner,)

        if (
            "procedure.pronargs = 2" in query
            and preflight._ENTRY_SNAPSHOT_CONSUME_FUNCTION in params
        ):
            return (True, True, True, True, True, _ENTRY_SNAPSHOT_CONSUME_BODY)

        if "CROSS JOIN LATERAL pg_catalog.aclexplode" in query and "relation.relacl" in query:
            return None

        if "pg_catalog.pg_get_serial_sequence" in query:
            table = str(params[0]).removeprefix("public.")
            if table == self.missing_sequence_table:
                return (None,)
            return (f"public.{table}_id_seq",)

        if (
            "pg_catalog.has_sequence_privilege" in query
            and len(params) == 2
        ):
            sequence, privilege = params
            expected = privilege == "USAGE"
            granted = self.sequence_privilege_overrides.get(
                (sequence, privilege),
                expected,
            )
            return (granted,)

        if (
            "pg_catalog.has_sequence_privilege" in query
            and len(params) == 3
        ):
            sequence = params[0]
            return (
                self.unrelated_sequence_privileges.get(sequence, False),
            )

        raise AssertionError(f"fetchone sem mock para consulta: {query}")

    def fetchall(self):
        query = self.last_query
        params = self.last_params

        if "SELECT id, unidade, cargo_id FROM users" in query:
            return self.eligible_pf_rows
        if "SELECT DISTINCT p.tipo_odontograma_id" in query:
            return [(1,)]

        external_privilege_markers = {
            "unexpected_external_schema_privilege": "schema",
            "unexpected_external_relation_privilege": "relation",
            "unexpected_external_sequence_privilege": "sequence",
            "unexpected_external_security_definer_privilege": (
                "security_definer"
            ),
        }

        if "relation.relacl" in query and "aclexplode" in query:
            return [] if self.relation_acl_ready else [
                ("legacy_grantee", "SELECT", False)
            ]

        if "relation.relname = 'asaas_entry_financial_snapshots'" in query:
            snapshot_columns = (
                "entry_integration_id", "intent_version", "intent_sha256",
                "snapshot_json", "entry_plan_json", "entry_split_json",
                "carne_plan_json", "carne_split_json", "consumed_venda_id",
                "created_at",
            )
            if "aclexplode" not in query:
                return [(column,) for column in snapshot_columns]
            immutable = set(snapshot_columns) - {"consumed_venda_id"}
            return (
                [(column, self.runtime_role, "SELECT", False)
                 for column in snapshot_columns]
                + [(column, self.runtime_role, "INSERT", False)
                   for column in immutable - {"created_at"}]
                + [
                    ("entry_integration_id", self.entry_snapshot_consume_owner, "SELECT", False),
                    ("consumed_venda_id", self.entry_snapshot_consume_owner, "SELECT", False),
                    ("consumed_venda_id", self.entry_snapshot_consume_owner, "UPDATE", False),
                ]
            )
        for marker, privilege_kind in external_privilege_markers.items():
            if marker in query:
                if self.external_privilege_kind == privilege_kind:
                    return [
                        (
                            self.external_privilege_role,
                            privilege_kind,
                        )
                    ]
                return []

        if "function_owner_table_privilege" in query:
            _owner_name, privileges, tables = params
            return [
                (
                    table,
                    privilege,
                    self.function_owner_table_privilege_overrides.get(
                        (table, privilege),
                        False,
                    ),
                )
                for table in tables
                for privilege in privileges
            ]

        if "attribute.attacl" in query:
            return [
                (column, self.runtime_role, "SELECT", False)
                for column in preflight._SANDBOX_RECEIVER_VIEW_COLUMNS
            ]

        if (
            "procedure.proacl" in query
            and params
            and (
                params[0] == preflight._SANDBOX_RECEIVER_FUNCTION
                or params[0] == preflight._ENTRY_SNAPSHOT_CONSUME_FUNCTION
            )
        ):
            return [(self.runtime_role, "EXECUTE", False)]

        if "asaas_receiver_environment_links" in query and "pg_catalog.has_column_privilege(function_owner.oid" in query:
            columns = {"id", "user_id", "unidade", "environment", "account_id", "wallet_id", "credential_state", "credential_ciphertext", "unexpected"}
            allowed = columns - {"unexpected"}
            return [("asaas_receiver_environment_links", column, privilege, privilege == "SELECT" and column in allowed, False) for column in columns for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES")]

        if "function_owner_column_privilege" in query:
            _owner_name, privileges, tables = params
            return [
                (
                    table,
                    column,
                    privilege,
                    self.function_owner_column_privilege_overrides.get(
                        (table, column, privilege),
                        self._expected_function_owner_column_privilege(
                            table,
                            column,
                            privilege,
                        ),
                    ),
                )
                for table, column in sorted(self.columns)
                if table in set(tables)
                for privilege in privileges
            ]

        if "function_owner_unexpected_privilege" in query:
            rows = list(self.function_owner_unexpected_privileges)
            if (
                self.function_owner_owns_sandbox_receiver_view
                and "relation.relname = %s" not in query
            ):
                rows.append((preflight._SANDBOX_RECEIVER_VIEW, "SELECT"))
            return rows

        if "function_owner_sequence_privilege" in query:
            return [
                (sequence,)
                for sequence in self.function_owner_sequence_privileges
            ]

        if "relation.relrowsecurity" in query:
            return [
                (table, table == self.rls_table, False)
                for table in params[0]
            ]

        if (
            "FROM pg_catalog.pg_attribute AS attribute" in query
            and "pg_catalog.has_column_privilege" not in query
            and "pg_catalog.pg_trigger" not in query
        ):
            requested_tables = set(params[0])
            return sorted(
                (table, column)
                for table, column in self.columns
                if table in requested_tables
            )

        if "relation.relkind IN ('r', 'p', 'v', 'm', 'f')" in query:
            rows = list(self.unexpected_privileges)
            if (
                self.runtime_has_sandbox_receiver_view_privilege
                and "receiver_function.proowner = relation.relowner" not in query
            ):
                rows.append((preflight._SANDBOX_RECEIVER_VIEW, "SELECT"))
            if (
                self.runtime_has_entry_snapshot_privilege
                and "snapshot_attribute.attname = 'entry_integration_id'" not in query
            ):
                rows.append(("asaas_entry_financial_snapshots", "SELECT"))
            return rows

        if "pg_catalog.has_table_privilege" in query:
            privileges, tables = params
            return [
                (
                    table,
                    privilege,
                    self.table_privilege_overrides.get(
                        (table, privilege),
                        privilege
                        in preflight._REQUIRED_TABLE_PRIVILEGES.get(
                            table,
                            (),
                        ),
                    ),
                )
                for table in tables
                for privilege in privileges
            ]

        if "pg_catalog.has_column_privilege" in query:
            privileges, tables = params
            return [
                (
                    table,
                    column,
                    privilege,
                    self.column_privilege_overrides.get(
                        (table, column, privilege),
                        self._expected_column_privilege(
                            table,
                            column,
                            privilege,
                        ),
                    ),
                )
                for table, column in sorted(self.columns)
                if table in set(tables)
                for privilege in privileges
            ]

        if "pg_catalog.quote_ident(namespace.nspname)" in query:
            required = [
                (f"public.{table}_id_seq",)
                for table in preflight._SEQUENCE_TABLES
                if table != self.missing_sequence_table
            ]
            unrelated = [
                (sequence,)
                for sequence in self.unrelated_sequence_privileges
            ]
            return required + unrelated

        if "FROM pg_catalog.pg_index AS index_record" in query:
            return [
                (
                    name,
                    self.index_metadata_overrides.get(
                        name,
                        (table, unique, keys),
                    )[0],
                    self.index_metadata_overrides.get(
                        name,
                        (table, unique, keys),
                    )[1],
                    list(
                        self.index_metadata_overrides.get(
                            name,
                            (table, unique, keys),
                        )[2]
                    ),
                    self.index_predicate_overrides.get(
                        name,
                        predicate,
                    ),
                )
                for name, (
                    table,
                    unique,
                    keys,
                    predicate,
                ) in preflight._REQUIRED_INDEXES.items()
                if name != self.missing_index
                if self.index_catalog_state_overrides.get(
                    name,
                    (True, True),
                ) == (True, True)
            ]

        if "public_security_definer_privilege" in query:
            owner_name = params[0]
            rows = [
                (owner_name, function_name, 0, "f")
                for function_name in preflight._REQUIRED_FUNCTIONS
            ]
            rows.extend(
                [
                    (owner_name, preflight._SANDBOX_RECEIVER_FUNCTION, 5, "f"),
                    (owner_name, preflight._ENTRY_SNAPSHOT_CONSUME_FUNCTION, 2, "f"),
                ]
            )
            rows.append(
                (
                    self.runtime_role,
                    preflight._SANDBOX_RECEIVER_FUNCTION,
                    5,
                    "f",
                )
            )
            rows.append(
                (
                    self.runtime_role,
                    preflight._ENTRY_SNAPSHOT_CONSUME_FUNCTION,
                    2,
                    "f",
                )
            )
            if self.unexpected_security_definer:
                rows.append(
                    (
                        "grupojf_asaas_sales_runtime",
                        "unexpected_runtime_security_definer",
                        0,
                        "f",
                    )
                )
            if self.owner_unexpected_security_definer:
                rows.append(
                    (
                        owner_name,
                        "unexpected_owner_security_definer",
                        0,
                        "f",
                    )
                )
            return rows

        if "procedure.prosecdef" in query:
            rows = []
            for name in preflight._REQUIRED_FUNCTIONS:
                booleans = [True] * 10
                if name == self.insecure_function:
                    booleans[8] = False
                rows.append(
                    (
                        name,
                        *booleans,
                        "grupojf_asaas_sales_owner",
                        "plpgsql",
                        self.function_body_overrides.get(
                            name,
                            _FUNCTION_BODIES[name],
                        ),
                        ["search_path=pg_catalog, pg_temp"],
                    )
                )
            return rows

        if "FROM pg_catalog.pg_trigger AS trigger_record" in query:
            required_triggers = [
                (
                    name,
                    table,
                    "public",
                    function,
                    trigger_type,
                    list(update_columns),
                    "O",
                    True,
                )
                for name, (
                    table,
                    function,
                    trigger_type,
                    update_columns,
                ) in preflight._REQUIRED_TRIGGERS.items()
                if name != self.missing_trigger
            ]
            return required_triggers + list(self.extra_triggers)

        if "FROM pg_catalog.pg_constraint AS constraint_record" in query:
            types = {"fk_": "f", "uq_": "u", "chk_": "c"}
            return [
                (
                    name,
                    self.constraint_metadata_overrides.get(
                        name,
                        (
                            table,
                            next(
                                constraint_type
                                for prefix, constraint_type in types.items()
                                if name.startswith(prefix)
                            ),
                        ),
                    )[0],
                    self.constraint_metadata_overrides.get(
                        name,
                        (
                            table,
                            next(
                                constraint_type
                                for prefix, constraint_type in types.items()
                                if name.startswith(prefix)
                            ),
                        ),
                    )[1],
                    self.constraint_definition_overrides.get(
                        name,
                        preflight._REQUIRED_CONSTRAINT_DEFINITIONS[name],
                    ),
                )
                for name, table in preflight._REQUIRED_CONSTRAINTS.items()
                if name != self.missing_constraint
                if self.constraint_catalog_state_overrides.get(
                    name,
                    (True, False),
                ) == (True, False)
            ]

        raise AssertionError(f"fetchall sem mock para consulta: {query}")

    @staticmethod
    def _expected_column_privilege(table, column, privilege):
        return (
            privilege
            in preflight._REQUIRED_TABLE_PRIVILEGES.get(table, ())
            or column
            in preflight._REQUIRED_COLUMN_PRIVILEGES.get(
                table,
                {},
            ).get(privilege, ())
        )

    @staticmethod
    def _expected_function_owner_column_privilege(
        table,
        column,
        privilege,
    ):
        return column in (
            preflight._REQUIRED_FUNCTION_OWNER_COLUMN_PRIVILEGES.get(
                table,
                {},
            ).get(privilege, ())
        )


class AsaasSalesPreflightTests(unittest.TestCase):
    environment = {
        "JWT_SECRET": "configured",
        "ENVIRONMENT": "development",
        "ASAAS_ENVIRONMENT": "sandbox",
    }

    def test_runtime_contract_covers_split_rules_without_reading_secret(self):
        users_select = set(
            preflight._REQUIRED_COLUMN_PRIVILEGES["users"]["SELECT"]
        )
        users_update = set(
            preflight._REQUIRED_COLUMN_PRIVILEGES["users"]["UPDATE"]
        )

        self.assertNotIn("asaas_account_api_key_enc", users_select)
        self.assertIn("asaas_account_api_key_enc", users_update)
        self.assertTrue(
            {
                "nome",
                "cpf",
                "cargo_id",
                "unidade",
                "status_aprovacao",
                "asaas_wallet_id",
                "asaas_integration_status",
            }.issubset(users_select)
        )
        for table in (
            "regras_split",
            "participacao_cargo_split",
            "config_limite_split",
            "empresa_regras_split",
            "participacao_empresa_split",
            "asaas_sale_splits",
            "asaas_sale_split_plans",
        ):
            with self.subTest(table=table):
                self.assertIn(
                    table,
                    preflight._REQUIRED_COLUMN_PRIVILEGES,
                )

        plan_privileges = preflight._REQUIRED_COLUMN_PRIVILEGES[
            "asaas_sale_split_plans"
        ]
        self.assertNotIn("plan_json", plan_privileges["UPDATE"])
        self.assertNotIn("payload_json", plan_privileges["UPDATE"])
        self.assertNotIn("plan_sha256", plan_privileges["UPDATE"])
        self.assertNotIn("payload_sha256", plan_privileges["UPDATE"])
        self.assertIn("asaas_sale_split_plans", preflight._SEQUENCE_TABLES)
        account_attempt_privileges = preflight._REQUIRED_COLUMN_PRIVILEGES[
            "asaas_account_provision_attempts"
        ]
        self.assertIn(
            "remote_rejected_at",
            account_attempt_privileges["UPDATE"],
        )
        self.assertNotIn(
            "remote_rejected_at",
            account_attempt_privileges["SELECT"],
        )
        self.assertIn(
            "asaas_account_provision_attempts",
            preflight._SEQUENCE_TABLES,
        )

    def _run_with_cursor(
        self,
        cursor,
        units=("SJM",),
        *,
        allow_no_units=False,
        enabled_units=frozenset(),
        operational_units=frozenset(),
        excluded_pf_user_ids=(),
        company_wallets=None,
        environment=None,
    ):
        connection = MagicMock()
        connection.cursor.return_value = cursor
        wallets_by_unit = {
            "Nova Iguaçu 1": "wallet-ni1",
            "São João de Meriti": "wallet-sjm",
            "Vilar dos Teles": "wallet-vilar",
        }

        def resolve_account_targets(selected_units):
            return tuple(
                (unit, "sandbox", wallets_by_unit[unit])
                for unit in selected_units
            )

        with (
            patch.dict(
                os.environ,
                environment or self.environment,
                clear=True,
            ),
            patch.object(
                preflight,
                "get_enabled_asaas_sales_units",
                return_value=enabled_units,
            ),
            patch.object(
                preflight,
                "get_asaas_sales_operational_account_units",
                return_value=operational_units,
            ),
            patch.object(
                preflight,
                "get_enabled_asaas_sales_carne_units",
                return_value=frozenset(),
            ),
            patch.object(
                preflight,
                "validate_asaas_sales_account_isolation",
            ) as account_check,
            patch.object(
                preflight,
                "_resolve_preflight_account_targets",
                side_effect=resolve_account_targets,
            ),
            patch.object(
                preflight,
                "resolve_asaas_company_wallet_mappings",
                return_value=company_wallets or {},
            ),
            patch.object(
                preflight,
                "receiver_identity_provider_for_environment",
                return_value=MagicMock(),
            ),
            patch.object(
                preflight,
                "_load_asaas_domain_rules",
                return_value=(),
            ),
            patch.object(
                preflight,
                "DatabaseConnection",
                return_value=_DatabaseContext(connection),
            ) as database,
        ):
            result = preflight.run_asaas_sales_preflight(
                units,
                allow_no_units=allow_no_units,
                excluded_pf_user_ids=excluded_pf_user_ids,
            )
        return result, account_check, database

    def _assert_database_error(self, cursor, expected_code):
        with self.assertRaises(preflight.AsaasSalesPreflightError) as error:
            self._run_with_cursor(cursor)
        self.assertEqual(error.exception.code, expected_code)

    def test_explicit_units_validate_exact_catalog_and_database_read_only(self):
        class CompleteCursor(_ReadyCursor):
            def fetchall(self):
                if "SELECT DISTINCT p.tipo_odontograma_id" in self.last_query:
                    return [(1,)]
                return super().fetchall()

        cursor = CompleteCursor(eligible_pf_rows=[
            (118, "Nova Iguaçu 1", 3),
            (57, "São João de Meriti", 3),
            (96, "Vilar dos Teles", 3),
        ])
        with patch.object(preflight, "_load_asaas_domain_rules", return_value=()):
            result, account_check, database = self._run_with_cursor(
                cursor,
                ("Vilar", "NI1", "SJM", "SJM"),
            )

        self.assertEqual(
            result.units,
            ("Nova Iguaçu 1", "São João de Meriti", "Vilar dos Teles"),
        )
        account_check.assert_called_once_with(result.units)
        database.assert_called_once_with(read_only=True)
        self.assertTrue(
            all(
                query.lstrip().upper().startswith("SELECT")
                for query, _ in cursor.queries
            )
        )
        self.assertTrue(
            any(
                "pg_catalog.has_column_privilege" in query
                for query, _ in cursor.queries
            )
        )
        self.assertTrue(
            any(
                "pg_catalog.pg_index AS index_record" in query
                for query, _ in cursor.queries
            )
        )

    def test_health_mode_allows_empty_rollout_but_checks_database(self):
        cursor = _ReadyCursor()
        result, account_check, database = self._run_with_cursor(
            cursor,
            None,
            allow_no_units=True,
        )

        self.assertEqual(result.units, ())
        account_check.assert_called_once_with(())
        database.assert_called_once_with(read_only=True)

    def test_health_rejects_each_invalid_recurring_method_allowlist(self):
        for variable_name in (
            "ASAAS_SALES_PIX_AUTOMATIC_ENABLED_UNITS",
            "ASAAS_SALES_CREDIT_CARD_RECURRENT_ENABLED_UNITS",
        ):
            with self.subTest(variable_name=variable_name):
                environment = {
                    **self.environment,
                    variable_name: "Unidade inexistente",
                }
                with self.assertRaises(
                    preflight.AsaasSalesPreflightError
                ) as error:
                    self._run_with_cursor(
                        _ReadyCursor(),
                        None,
                        allow_no_units=True,
                        environment=environment,
                    )
                self.assertEqual(
                    error.exception.code,
                    "rollout_configuration_invalid",
                )

    def test_provisioning_only_audits_account_without_pf_readiness_or_split(self):
        cursor = _ReadyCursor(pf_subaccounts_incomplete=True)
        result, account_check, database = self._run_with_cursor(
            cursor,
            None,
            allow_no_units=True,
            operational_units=frozenset({"São João de Meriti"}),
        )

        self.assertEqual(result.units, ("São João de Meriti",))
        account_check.assert_called_once_with(("São João de Meriti",))
        database.assert_called_once_with(read_only=True)
        self.assertFalse(
            any(
                "pf_subaccounts_incomplete" in query
                or "incompatible_role_absorber_rule_exists" in query
                for query, _ in cursor.queries
            )
        )

    def test_provisioning_only_still_audits_manifest_drift(self):
        cursor = _ReadyCursor()
        result, _, _ = self._run_with_cursor(
            cursor,
            None,
            allow_no_units=True,
            operational_units=frozenset({"São João de Meriti"}),
            excluded_pf_user_ids=(57,),
        )

        self.assertEqual(result.excluded_pf_user_ids, (57,))
        drift_query, drift_params = next(
            (query, params)
            for query, params in cursor.queries
            if "pf_exclusions_match_eligible_users" in query
        )
        self.assertNotIn("api_key", drift_query.casefold())
        self.assertEqual(
            drift_params,
            (1, [57], [None], ["São João de Meriti"]),
        )
        self.assertFalse(
            any(
                "pf_subaccounts_incomplete" in query
                for query, _ in cursor.queries
            )
        )

    def test_sandbox_readiness_does_not_read_legacy_pf_credentials(self):
        cursor = _ReadyCursor(pf_subaccounts_incomplete=True)
        self._run_with_cursor(cursor)
        self.assertFalse(any("asaas_integration_status" in query for query, _ in cursor.queries))

    def test_sandbox_readiness_resolves_pf_through_environment_provider(self):
        class Provider:
            def __init__(self):
                self.calls = []

            def resolve_for_new_sale(self, **kwargs):
                self.calls.append(kwargs)
                return MagicMock(wallet_id="wallet-pf")

        class Cursor(_ReadyCursor):
            def fetchall(self):
                if "SELECT DISTINCT p.tipo_odontograma_id" in self.last_query:
                    return [(1,)]
                return super().fetchall()

        cursor = Cursor(eligible_pf_rows=[(57, "São João de Meriti", 3)])
        provider = Provider()
        with patch.object(preflight, "_load_asaas_domain_rules", return_value=()):
            preflight._validate_receiver_identities(
                cursor,
                ("São João de Meriti",),
                (("São João de Meriti", "sandbox", "wallet-sjm"),),
                (), provider, environment="sandbox",
            )
        self.assertEqual(provider.calls, [{
            "kind": "pf", "local_id": 57,
            "unidade": "São João de Meriti", "environment": "sandbox",
        }])
        self.assertFalse(any("asaas_wallet_id" in query for query, _ in cursor.queries))

    def test_sandbox_ni_preflight_skips_only_blocked_odontogram_types(self):
        class Provider:
            def resolve_for_new_sale(self, **_kwargs):
                return MagicMock(wallet_id="wallet-pf")

        class Cursor(_ReadyCursor):
            def fetchall(self):
                if "SELECT DISTINCT p.tipo_odontograma_id" in self.last_query:
                    return [(1,), (2,), (6,)]
                return super().fetchall()

        cursor = Cursor(eligible_pf_rows=[(118, "Nova Iguaçu 1", 3)])
        with patch.object(preflight, "_load_asaas_domain_rules", return_value=()) as loader:
            preflight._validate_receiver_identities(
                cursor,
                ("Nova Iguaçu 1",),
                (("Nova Iguaçu 1", "sandbox", "wallet-ni"),),
                (),
                Provider(),
                environment="sandbox",
            )

        self.assertEqual(
            [call.kwargs["tipo_odontograma_id"] for call in loader.call_args_list],
            [6],
        )

    def test_sandbox_receiver_identity_rejects_eligible_pf_without_type_scenario(self):
        class Provider:
            def resolve_for_new_sale(self, **_kwargs):
                return MagicMock(wallet_id="wallet-pf")

        class EmptyTypeCursor(_ReadyCursor):
            def fetchall(self):
                if "SELECT DISTINCT p.tipo_odontograma_id" in self.last_query:
                    return []
                return super().fetchall()

        cursor = EmptyTypeCursor(eligible_pf_rows=[(57, "São João de Meriti", 3)])
        with self.assertRaisesRegex(preflight.AsaasSalesPreflightError, "account_configuration_invalid"):
            preflight._validate_receiver_identities(
                cursor, ("São João de Meriti",),
                (("São João de Meriti", "sandbox", "wallet-sjm"),),
                (), Provider(), environment="sandbox",
            )

    def test_receiver_identity_requires_non_excluded_pf_for_each_selected_unit(self):
        class Provider:
            def __init__(self): self.calls = []
            def resolve_for_new_sale(self, **kwargs): self.calls.append(kwargs)

        cases = (
            ("empty", [], (), ("São João de Meriti",)),
            ("all_excluded", [(63, "São João de Meriti", 3)], (preflight._PfExclusion(63, None),), ("São João de Meriti",)),
            ("one_of_two_empty", [(57, "São João de Meriti", 3)], (), ("São João de Meriti", "Venda Nova")),
        )
        for _name, rows, exclusions, units in cases:
            with self.subTest(_name):
                cursor, provider = _ReadyCursor(eligible_pf_rows=rows), Provider()
                with self.assertRaisesRegex(preflight.AsaasSalesPreflightError, "pf_subaccounts_incomplete"):
                    preflight._validate_receiver_identities(
                        cursor, units,
                        tuple((unit, "sandbox", f"wallet-{index}") for index, unit in enumerate(units)),
                        exclusions, provider, environment="sandbox",
                    )
                self.assertEqual(provider.calls, [])

    def test_production_receiver_identity_wrapper_keeps_empty_pf_compatibility(self):
        preflight._validate_production_receiver_identities(
            _ReadyCursor(eligible_pf_rows=[]),
            ("São João de Meriti",),
            (("São João de Meriti", "production", "wallet-sjm"),),
            (),
            MagicMock(),
        )

    def test_sandbox_receiver_rules_resolve_pf_and_empresa_through_composite_provider(self):
        class Cursor:
            def __init__(self): self.queries = []
            def execute(self, query, params): self.queries.append((query, params))
            def fetchall(self):
                query = self.queries[-1][0]
                if "SELECT id, unidade, cargo_id FROM users" in query:
                    return [(57, "São João de Meriti", 3)]
                if "SELECT DISTINCT p.tipo_odontograma_id" in query:
                    return [(1,)]
                raise AssertionError("unexpected direct query")

        class Provider:
            def __init__(self, company_wallet): self.calls, self.company_wallet = [], company_wallet
            def resolve_for_new_sale(self, **kwargs):
                self.calls.append(kwargs)
                wallet = self.company_wallet if kwargs["kind"] == "empresa" else "wallet-pf"
                return AsaasReceiverIdentity(kwargs["kind"], kwargs["local_id"], kwargs["unidade"], kwargs["environment"], "account", wallet, "ref")

        rules = (
            AsaasDomainSplitRule(None, user_id=57),
            AsaasDomainSplitRule(None, empresa_id=4, absorbs_balance=True),
        )
        cursor, provider = Cursor(), Provider("wallet-root")
        with patch.object(preflight, "_load_asaas_domain_rules", return_value=rules), patch.object(
            preflight, "resolve_asaas_company_wallet_mappings", side_effect=AssertionError("legacy resolver")
        ):
            preflight._validate_receiver_identities(
                cursor, ("São João de Meriti",),
                (("São João de Meriti", "sandbox", "wallet-root"),), (), provider,
                environment="sandbox",
            )
        assert provider.calls == [
            {"kind": "pf", "local_id": 57, "unidade": "São João de Meriti", "environment": "sandbox"},
            {"kind": "pf", "local_id": 57, "unidade": "São João de Meriti", "environment": "sandbox"},
            {"kind": "empresa", "local_id": 4, "unidade": "São João de Meriti", "environment": "sandbox"},
        ]

        cursor, provider = Cursor(), Provider("external-wallet")
        with patch.object(preflight, "_load_asaas_domain_rules", return_value=rules), patch.object(
            preflight, "resolve_asaas_company_wallet_mappings", side_effect=AssertionError("legacy resolver")
        ):
            with self.assertRaisesRegex(preflight.AsaasSalesPreflightError, "account_configuration_invalid"):
                preflight._validate_receiver_identities(
                    cursor, ("São João de Meriti",),
                    (("São João de Meriti", "sandbox", "wallet-root"),), (), provider,
                    environment="sandbox",
                )

    def test_sandbox_pf_exclusion_is_not_reintroduced_by_type_scenarios(self):
        class Cursor:
            def __init__(self): self.queries = []
            def execute(self, query, params): self.queries.append((query, params))
            def fetchall(self):
                query = self.queries[-1][0]
                if "SELECT id, unidade, cargo_id FROM users" in query:
                    return [(63, "São João de Meriti", 3), (57, "São João de Meriti", 3)]
                if "SELECT DISTINCT p.tipo_odontograma_id" in query:
                    return [(1,)]
                raise AssertionError("unexpected direct query")

        class Provider:
            def __init__(self): self.calls = []
            def resolve_for_new_sale(self, **kwargs):
                self.calls.append(kwargs)
                return AsaasReceiverIdentity(kwargs["kind"], kwargs["local_id"], kwargs["unidade"], kwargs["environment"], "account", "wallet", "ref")

        loaded_for_users = []
        def load_rules(_cursor, **kwargs):
            loaded_for_users.append(kwargs["usuario_venda_id"])
            return ()

        provider = Provider()
        with patch.object(preflight, "_load_asaas_domain_rules", side_effect=load_rules):
            preflight._validate_receiver_identities(
                Cursor(), ("São João de Meriti",),
                (("São João de Meriti", "sandbox", "wallet-root"),),
                (preflight._PfExclusion(63, None),), provider, environment="sandbox",
            )
        assert [call["local_id"] for call in provider.calls] == [57]
        assert loaded_for_users == [57]

    def test_explicit_pf_exclusion_is_audited_and_readiness_only(self):
        cursor = _ReadyCursor()
        result, _, _ = self._run_with_cursor(
            cursor,
            excluded_pf_user_ids=(57,),
        )

        self.assertEqual(result.excluded_pf_user_ids, (57,))
        self.assertEqual(result.as_dict()["excluded_pf_user_ids"], [57])
        drift_query, drift_params = next(
            (query, params)
            for query, params in cursor.queries
            if "SELECT id, unidade, cargo_id FROM users" in query
        )
        self.assertEqual(drift_params, (["São João de Meriti"],))
        self.assertNotIn("asaas_", drift_query)

    def test_pf_exclusion_drift_fails_closed(self):
        cursor = _ReadyCursor(eligible_pf_rows=[])
        with self.assertRaises(preflight.AsaasSalesPreflightError) as error:
            self._run_with_cursor(
                cursor,
                excluded_pf_user_ids=(57,),
            )

        self.assertEqual(error.exception.code, "pf_exclusion_drift")
        self.assertTrue(
            any(
                "SELECT id, unidade, cargo_id FROM users" in query
                for query, _ in cursor.queries
            )
        )

    def test_pf_exclusion_ids_must_be_positive_and_unique(self):
        for invalid_ids in ((0,), (-1,), (True,), (57, 57), ("057",)):
            with self.subTest(invalid_ids=invalid_ids):
                with self.assertRaises(
                    preflight.AsaasSalesPreflightError
                ) as error:
                    self._run_with_cursor(
                        _ReadyCursor(),
                        excluded_pf_user_ids=invalid_ids,
                    )
                self.assertEqual(
                    error.exception.code,
                    "pf_exclusion_configuration_invalid",
                )

    def test_default_manifest_is_strict_sandbox_and_unit_scoped(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "exclusions.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "environment": "sandbox",
                        "excluded_pf_users": [
                            {
                                "user_id": 57,
                                "unidade": "São João de Meriti",
                                "reason": "Provisionamento operacional pendente.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            environment = {
                **self.environment,
                "ASAAS_SALES_PF_EXCLUSIONS_FILE": str(manifest_path),
            }
            result, _, _ = self._run_with_cursor(
                _ReadyCursor(),
                excluded_pf_user_ids=None,
                environment=environment,
            )

        self.assertEqual(result.excluded_pf_user_ids, (57,))

    def test_explicit_pf_ids_override_manifest_file(self):
        environment = {
            **self.environment,
            "ASAAS_SALES_PF_EXCLUSIONS_FILE": "/missing/manifest.json",
        }
        result, _, _ = self._run_with_cursor(
            _ReadyCursor(),
            excluded_pf_user_ids=(58,),
            environment=environment,
        )

        self.assertEqual(result.excluded_pf_user_ids, (58,))

    def test_invalid_or_cross_unit_manifest_fails_before_database(self):
        invalid_manifests = (
            {
                "schema_version": 2,
                "environment": "sandbox",
                "excluded_pf_users": [],
            },
            {
                "schema_version": 1,
                "environment": "production",
                "excluded_pf_users": [],
            },
            {
                "schema_version": 1,
                "environment": "sandbox",
                "excluded_pf_users": [
                    {
                        "user_id": 57,
                        "unidade": "Nova Iguaçu 1",
                        "reason": "Unidade fora do alvo selecionado.",
                    }
                ],
            },
        )
        for manifest in invalid_manifests:
            with self.subTest(manifest=manifest):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    manifest_path = (
                        Path(temporary_directory) / "exclusions.json"
                    )
                    manifest_path.write_text(
                        json.dumps(manifest),
                        encoding="utf-8",
                    )
                    environment = {
                        **self.environment,
                        "ASAAS_SALES_PF_EXCLUSIONS_FILE": str(manifest_path),
                    }
                    with self.assertRaises(
                        preflight.AsaasSalesPreflightError
                    ) as error:
                        self._run_with_cursor(
                            _ReadyCursor(),
                            excluded_pf_user_ids=None,
                            environment=environment,
                        )
                self.assertEqual(
                    error.exception.code,
                    "pf_exclusion_configuration_invalid",
                )

    def test_manifest_rejects_duplicate_keys_at_every_object_level(self):
        duplicate_manifests = (
            (
                '{"schema_version":1,"environment":"sandbox",'
                '"environment":"production","excluded_pf_users":[]}'
            ),
            (
                '{"schema_version":1,"environment":"sandbox",'
                '"excluded_pf_users":[{"user_id":57,"user_id":58,'
                '"unidade":"São João de Meriti","reason":"Pendente."}]}'
            ),
        )
        for raw_manifest in duplicate_manifests:
            with self.subTest(raw_manifest=raw_manifest):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    manifest_path = (
                        Path(temporary_directory) / "exclusions.json"
                    )
                    manifest_path.write_text(
                        raw_manifest,
                        encoding="utf-8",
                    )
                    environment = {
                        **self.environment,
                        "ASAAS_SALES_PF_EXCLUSIONS_FILE": str(manifest_path),
                    }
                    with self.assertRaises(
                        preflight.AsaasSalesPreflightError
                    ) as error:
                        self._run_with_cursor(
                            _ReadyCursor(),
                            excluded_pf_user_ids=None,
                            environment=environment,
                        )
                self.assertEqual(
                    error.exception.code,
                    "pf_exclusion_configuration_invalid",
                )

    def test_nonempty_manifest_requires_an_operational_account_target(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "exclusions.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "environment": "sandbox",
                        "excluded_pf_users": [
                            {
                                "user_id": 57,
                                "unidade": "São João de Meriti",
                                "reason": "Pendencia temporaria de bootstrap.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            environment = {
                **self.environment,
                "ASAAS_SALES_PF_EXCLUSIONS_FILE": str(manifest_path),
            }
            with (
                patch.dict(os.environ, environment, clear=True),
                patch.object(
                    preflight,
                    "get_enabled_asaas_sales_units",
                    return_value=frozenset(),
                ),
                patch.object(
                    preflight,
                    "get_asaas_sales_operational_account_units",
                    return_value=frozenset(),
                ),
                patch.object(preflight, "DatabaseConnection") as database,
            ):
                with self.assertRaises(
                    preflight.AsaasSalesPreflightError
                ) as error:
                    preflight.run_asaas_sales_preflight(
                        allow_no_units=True
                    )

        self.assertEqual(
            error.exception.code,
            "pf_exclusion_configuration_invalid",
        )
        database.assert_not_called()

    def test_sandbox_preflight_does_not_use_legacy_wallets_for_absorbers(self):
        cursor = _ReadyCursor()
        self._run_with_cursor(
            cursor,
            company_wallets={91: "wallet-sjm"},
        )

        self.assertFalse(any("incompatible_role_absorber_rule_exists" in query for query, _ in cursor.queries))

    def test_legacy_role_absorber_flag_is_not_used_by_sandbox_preflight(self):
        cursor = _ReadyCursor(role_absorber_rule=True)

        self._run_with_cursor(cursor)

    def test_legacy_company_absorber_flag_is_not_used_by_sandbox_preflight(self):
        cursor = _ReadyCursor(company_absorber_rule=True)

        self._run_with_cursor(cursor)

    def test_missing_jwt_fails_before_account_or_database_checks(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                preflight,
                "validate_asaas_sales_account_isolation",
            ) as account_check,
            patch.object(preflight, "DatabaseConnection") as database,
        ):
            with self.assertRaises(preflight.AsaasSalesPreflightError) as error:
                preflight.run_asaas_sales_preflight(
                    ["SJM"],
                    allow_no_units=True,
                )

        self.assertEqual(error.exception.code, "jwt_configuration_missing")
        account_check.assert_not_called()
        database.assert_not_called()

    def test_sandbox_environment_is_explicit_even_with_empty_rollout(self):
        invalid_environments = (
            {
                "JWT_SECRET": "configured",
                "ENVIRONMENT": "production",
                "ASAAS_ENVIRONMENT": "sandbox",
            },
            {
                "JWT_SECRET": "configured",
                "ENVIRONMENT": "development",
                "ASAAS_ENVIRONMENT": "production",
            },
            {
                "JWT_SECRET": "configured",
            },
        )
        for environment in invalid_environments:
            with self.subTest(environment=environment):
                with (
                    patch.dict(os.environ, environment, clear=True),
                    patch.object(preflight, "DatabaseConnection") as database,
                ):
                    with self.assertRaises(
                        preflight.AsaasSalesPreflightError
                    ) as error:
                        preflight.run_asaas_sales_preflight(
                            allow_no_units=True
                        )
                self.assertEqual(
                    error.exception.code,
                    "sandbox_environment_required",
                )
                database.assert_not_called()

    def test_production_runtime_allows_profile_off_without_declaring_rollout(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "ASAAS_ENVIRONMENT": "production",
            },
            clear=True,
        ):
            preflight._validate_sandbox_runtime()

    def test_runtime_role_must_be_fully_isolated(self):
        self._assert_database_error(
            _ReadyCursor(runtime_role_ready=False),
            "database_role_not_isolated",
        )

    def test_external_non_system_schema_privileges_are_rejected(self):
        scenarios = (
            ("schema", "grupojf_asaas_sales_runtime"),
            ("relation", "grupojf_asaas_sales_owner"),
            ("sequence", "grupojf_asaas_sales_runtime"),
            ("security_definer", "grupojf_asaas_sales_owner"),
        )
        for privilege_kind, role in scenarios:
            with self.subTest(
                privilege_kind=privilege_kind,
                role=role,
            ):
                self._assert_database_error(
                    _ReadyCursor(
                        external_privilege_kind=privilege_kind,
                        external_privilege_role=role,
                    ),
                    "database_privileges_excessive",
                )

    def test_external_privilege_audit_requires_runtime_and_owner(self):
        self._assert_database_error(
            _ReadyCursor(external_roles_ready=False),
            "database_functions_incomplete",
        )

    def test_rls_is_rejected_for_the_runtime_contract(self):
        self._assert_database_error(
            _ReadyCursor(rls_table="vendas"),
            "database_rls_unsupported",
        )

    def test_missing_required_column_fails_without_database_details(self):
        cursor = _ReadyCursor(missing_column=("users", "auth_version"))
        with self.assertRaises(preflight.AsaasSalesPreflightError) as error:
            self._run_with_cursor(cursor)

        self.assertEqual(error.exception.code, "database_schema_incomplete")
        self.assertNotIn("auth_version", str(error.exception))

    def test_missing_required_column_privilege_is_rejected(self):
        for table, column in (
            ("users", "email"),
            ("vendas", "valor_entrada"),
        ):
            with self.subTest(table=table, column=column):
                self._assert_database_error(
                    _ReadyCursor(
                        column_privilege_overrides={
                            (table, column, "SELECT"): False,
                        }
                    ),
                    "database_privileges_incomplete",
                )

    def test_table_privileges_are_exact(self):
        for table in ("asaas_sale_integrations", "users"):
            with self.subTest(table=table):
                self._assert_database_error(
                    _ReadyCursor(
                        table_privilege_overrides={
                            (table, "SELECT"): True,
                        },
                    ),
                    "database_privileges_excessive",
                )

    def test_extra_column_privilege_is_rejected(self):
        for table, column in (
            ("users", "senha"),
            ("asaas_sale_integrations", "last_remote_attempt_at"),
            ("asaas_sale_items", "id"),
            ("asaas_sale_payment_links", "created_at"),
        ):
            with self.subTest(table=table, column=column):
                self._assert_database_error(
                    _ReadyCursor(
                        column_privilege_overrides={
                            (table, column, "SELECT"): True,
                        }
                    ),
                    "database_privileges_excessive",
                )

    def test_function_owner_column_privileges_are_exact(self):
        scenarios = (
            (
                _ReadyCursor(
                    function_owner_column_privilege_overrides={
                        ("vendas", "status_venda", "SELECT"): False,
                    }
                ),
                "database_privileges_incomplete",
            ),
            (
                _ReadyCursor(
                    function_owner_column_privilege_overrides={
                        ("vendas", "paciente_id", "SELECT"): True,
                    }
                ),
                "database_privileges_excessive",
            ),
            (
                _ReadyCursor(
                    function_owner_table_privilege_overrides={
                        ("asaas_sale_integrations", "SELECT"): True,
                    }
                ),
                "database_privileges_excessive",
            ),
            (
                _ReadyCursor(
                    function_owner_unexpected_privileges=(
                        ("contract_templates", "SELECT"),
                        ("audit_log", "SELECT"),
                    )
                ),
                "database_privileges_excessive",
            ),
        )
        for cursor, expected_code in scenarios:
            with self.subTest(expected_code=expected_code):
                self._assert_database_error(cursor, expected_code)

    def test_function_owner_cannot_use_public_sequences(self):
        self._assert_database_error(
            _ReadyCursor(
                function_owner_sequence_privileges=(
                    "public.vendas_id_seq",
                )
            ),
            "database_privileges_excessive",
        )

    def test_function_owner_implicit_view_privilege_is_limited_to_validated_view(self):
        cursor = _ReadyCursor(function_owner_owns_sandbox_receiver_view=True)
        self._run_with_cursor(cursor)
        queries = [
            (query, params)
            for query, params in cursor.queries
            if "function_owner_unexpected_privilege" in query
        ]
        self.assertEqual(len(queries), 1)
        query, params = queries[0]
        self.assertIn("relation.relkind = 'v'", query)
        self.assertIn("relation.relowner = (", query)
        self.assertEqual(params[2], preflight._SANDBOX_RECEIVER_VIEW)
        self.assertEqual(params[3], "grupojf_asaas_sales_owner")

    def test_public_contract_template_select_is_the_only_exception(self):
        self._run_with_cursor(
            _ReadyCursor(
                unexpected_privileges=(
                    ("contract_templates", "SELECT"),
                )
            )
        )
        self._assert_database_error(
            _ReadyCursor(
                unexpected_privileges=(
                    ("contract_templates", "SELECT"),
                    ("audit_log", "SELECT"),
                )
            ),
            "database_privileges_excessive",
        )

    def test_runtime_column_select_on_validated_sandbox_view_is_not_broad_privilege(self):
        cursor = _ReadyCursor(
            runtime_has_sandbox_receiver_view_privilege=True,
            runtime_has_entry_snapshot_privilege=True,
        )
        self._run_with_cursor(cursor)
        queries = [
            (query, params)
            for query, params in cursor.queries
            if "receiver_function.proowner = relation.relowner" in query
        ]
        self.assertEqual(len(queries), 1)
        query, params = queries[0]
        self.assertIn("relation.relkind = 'v'", query)
        self.assertEqual(params[2:], (
            preflight._SANDBOX_RECEIVER_VIEW,
            preflight._SANDBOX_RECEIVER_FUNCTION,
            "asaas_entry_financial_snapshots",
        ))

    def test_sequences_exist_and_allow_only_usage(self):
        scenarios = (
            (
                _ReadyCursor(missing_sequence_table="vendas"),
                "database_schema_incomplete",
            ),
            (
                _ReadyCursor(
                    sequence_privilege_overrides={
                        ("public.vendas_id_seq", "UPDATE"): True,
                    }
                ),
                "database_privileges_excessive",
            ),
        )
        for cursor, expected_code in scenarios:
            with self.subTest(expected_code=expected_code):
                self._assert_database_error(cursor, expected_code)

    def test_missing_or_changed_index_metadata_is_rejected(self):
        with self.subTest(reason="missing"):
            self._assert_database_error(
                _ReadyCursor(
                    missing_index="idx_asaas_sale_webhook_dispatch"
                ),
                "database_indexes_incomplete",
            )
        with self.subTest(reason="predicate"):
            self._assert_database_error(
                _ReadyCursor(
                    index_predicate_overrides={
                        "idx_asaas_sale_webhook_dispatch": (
                            "status = 'erro_terminal'"
                        )
                    }
                ),
                "database_indexes_incomplete",
            )

    def test_postgresql_16_catalog_rendering_is_accepted_only_for_active_attempt_index(self):
        cursor = _ReadyCursor(
            index_predicate_overrides={
                "uq_asaas_account_provision_attempt_active_user": (
                    "((lifecycle_state)::text <> 'rejected'::text)"
                ),
            }
        )

        self._run_with_cursor(cursor)

    def test_active_attempt_index_rejects_missing_or_changed_catalog_metadata(self):
        scenarios = (
            _ReadyCursor(
                missing_index="uq_asaas_account_provision_attempt_active_user"
            ),
            _ReadyCursor(
                index_metadata_overrides={
                    "uq_asaas_account_provision_attempt_active_user": (
                        "asaas_sale_integrations",
                        True,
                        ("user_id",),
                    )
                }
            ),
            _ReadyCursor(
                index_metadata_overrides={
                    "uq_asaas_account_provision_attempt_active_user": (
                        "asaas_account_provision_attempts",
                        False,
                        ("user_id",),
                    )
                }
            ),
            _ReadyCursor(
                index_metadata_overrides={
                    "uq_asaas_account_provision_attempt_active_user": (
                        "asaas_account_provision_attempts",
                        True,
                        ("unidade",),
                    )
                }
            ),
            _ReadyCursor(
                index_catalog_state_overrides={
                    "uq_asaas_account_provision_attempt_active_user": (
                        False,
                        True,
                    )
                }
            ),
            _ReadyCursor(
                index_catalog_state_overrides={
                    "uq_asaas_account_provision_attempt_active_user": (
                        True,
                        False,
                    )
                }
            ),
            _ReadyCursor(
                index_predicate_overrides={
                    "uq_asaas_account_provision_attempt_active_user": (
                        "((lifecycle_state)::text <> 'cancelled'::text)"
                    )
                }
            ),
        )
        for cursor in scenarios:
            with self.subTest(cursor=cursor):
                self._assert_database_error(
                    cursor,
                    "database_indexes_incomplete",
                )

    def test_postgresql_16_catalog_rendering_is_accepted_only_for_split_kind_constraint(self):
        cursor = _ReadyCursor(
            constraint_definition_overrides={
                "chk_asaas_sale_splits_split_kind": (
                    "CHECK (split_kind::text = ANY "
                    "(ARRAY['percentual'::character varying::text, "
                    "'total_fixed'::character varying::text]))"
                ),
            }
        )

        self._run_with_cursor(cursor)

    def test_split_kind_constraint_rejects_missing_or_changed_catalog_metadata(self):
        expected = (
            "CHECK (split_kind::text = ANY "
            "(ARRAY['percentual'::character varying::text, "
            "'total_fixed'::character varying::text]))"
        )
        scenarios = (
            _ReadyCursor(
                missing_constraint="chk_asaas_sale_splits_split_kind"
            ),
            _ReadyCursor(
                constraint_metadata_overrides={
                    "chk_asaas_sale_splits_split_kind": (
                        "asaas_sale_split_plans",
                        "c",
                    )
                }
            ),
            _ReadyCursor(
                constraint_catalog_state_overrides={
                    "chk_asaas_sale_splits_split_kind": (False, False)
                }
            ),
            _ReadyCursor(
                constraint_catalog_state_overrides={
                    "chk_asaas_sale_splits_split_kind": (True, True)
                }
            ),
            _ReadyCursor(
                constraint_metadata_overrides={
                    "chk_asaas_sale_splits_split_kind": (
                        "asaas_sale_splits",
                        "u",
                    )
                }
            ),
            _ReadyCursor(
                constraint_definition_overrides={
                    "chk_asaas_sale_splits_split_kind": expected.replace(
                        "split_kind",
                        "contexto",
                    )
                }
            ),
            _ReadyCursor(
                constraint_definition_overrides={
                    "chk_asaas_sale_splits_split_kind": expected.replace(
                        "'total_fixed'::character varying::text",
                        "'total_fixed'::character varying::text, "
                        "'extra'::character varying::text",
                    )
                }
            ),
            _ReadyCursor(
                constraint_definition_overrides={
                    "chk_asaas_sale_splits_split_kind": expected.replace(
                        " = ANY ",
                        " <> ANY ",
                    )
                }
            ),
            _ReadyCursor(
                constraint_definition_overrides={
                    "chk_asaas_sale_splits_split_kind": expected.replace(
                        "'percentual'",
                        "'percentual_invalido'",
                    )
                }
            ),
            _ReadyCursor(
                constraint_definition_overrides={
                    "chk_asaas_sale_splits_split_kind": expected.replace(
                        "ARRAY[",
                        "ARRAY[] || ARRAY[",
                    )
                }
            ),
            _ReadyCursor(
                constraint_definition_overrides={
                    "chk_asaas_sale_splits_split_kind": expected.replace(
                        "character varying::text",
                        "text",
                    )
                }
            ),
        )
        for cursor in scenarios:
            with self.subTest(cursor=cursor):
                self._assert_database_error(
                    cursor,
                    "database_constraints_incomplete",
                )

    def test_catalog_rendering_variants_are_scoped_to_exact_object_names(self):
        index_variant = "((lifecycle_state)::text <> 'rejected'::text)"
        constraint_variant = (
            "CHECK (split_kind::text = ANY "
            "(ARRAY['percentual'::character varying::text, "
            "'total_fixed'::character varying::text]))"
        )

        self.assertNotEqual(
            preflight._canonicalize_index_predicate(
                "idx_asaas_account_provision_attempts_unit_state",
                index_variant,
            ),
            preflight._canonicalize_index_predicate(
                "uq_asaas_account_provision_attempt_active_user",
                index_variant,
            ),
        )
        self.assertNotEqual(
            preflight._canonicalize_constraint_definition(
                "chk_asaas_sale_splits_percentual_value",
                constraint_variant,
            ),
            preflight._canonicalize_constraint_definition(
                "chk_asaas_sale_splits_split_kind",
                constraint_variant,
            ),
        )

    def test_function_trigger_and_constraint_metadata_are_exact(self):
        scenarios = (
            (
                _ReadyCursor(
                    insecure_function="asaas_protect_integrated_venda"
                ),
                "database_functions_incomplete",
            ),
            (
                _ReadyCursor(
                    function_body_overrides={
                        "asaas_protect_integrated_venda": "\nBEGIN\n"
                        "    RETURN NEW;\nEND\n",
                    }
                ),
                "database_functions_incomplete",
            ),
            (
                _ReadyCursor(unexpected_security_definer=True),
                "database_privileges_excessive",
            ),
            (
                _ReadyCursor(
                    missing_trigger=(
                        "trg_asaas_protect_integrated_venda_parcela"
                    )
                ),
                "database_triggers_incomplete",
            ),
            (
                _ReadyCursor(
                    missing_constraint="chk_asaas_sale_job_retry_schedule"
                ),
                "database_constraints_incomplete",
            ),
            (
                _ReadyCursor(
                    constraint_definition_overrides={
                        "chk_asaas_sale_job_retry_schedule": "CHECK (TRUE)",
                    }
                ),
                "database_constraints_incomplete",
            ),
        )
        for cursor, expected_code in scenarios:
            with self.subTest(expected_code=expected_code):
                self._assert_database_error(cursor, expected_code)

    def test_public_security_definer_allowlist_rejects_owner_extra(self):
        self._assert_database_error(
            _ReadyCursor(owner_unexpected_security_definer=True),
            "database_privileges_excessive",
        )

    def test_function_catalog_query_binds_allowlist_and_special_signatures_in_sql_order(self):
        cursor = _ReadyCursor()
        self._run_with_cursor(cursor)
        query, params = next(
            (query, params)
            for query, params in cursor.queries
            if (
                "owned_function.proname::TEXT = ANY(%s)" in query
                and "procedure.proname::TEXT = ANY(%s)" in query
            )
        )
        self.assertEqual(query.count("ANY(%s)"), 2)
        self.assertEqual(params, (
            list(preflight._REQUIRED_FUNCTIONS),
            preflight._SANDBOX_RECEIVER_FUNCTION,
            preflight._ENTRY_SNAPSHOT_CONSUME_FUNCTION,
            list(preflight._REQUIRED_FUNCTIONS),
        ))

    def test_disabled_extra_trigger_on_any_writable_table_is_rejected(self):
        cursor = _ReadyCursor(
            extra_triggers=(
                (
                    "trg_unexpected_disabled",
                    "asaas_sale_items",
                    "public",
                    "unexpected_trigger_function",
                    7,
                    [],
                    "D",
                    True,
                ),
            )
        )
        self._assert_database_error(
            cursor,
            "database_triggers_incomplete",
        )

        trigger_query, params = next(
            (query, params)
            for query, params in cursor.queries
            if "FROM pg_catalog.pg_trigger AS trigger_record" in query
        )
        self.assertEqual(
            set(params[0]),
            set(preflight._SEQUENCE_TABLES),
        )
        self.assertNotIn(
            "trigger_record.tgenabled IN",
            trigger_query,
        )

    def test_cli_returns_classified_failure_without_secret_values(self):
        output = io.StringIO()
        with (
            patch.object(
                preflight,
                "run_asaas_sales_preflight",
                side_effect=preflight.AsaasSalesPreflightError(
                    "account_configuration_invalid"
                ),
            ),
            redirect_stdout(output),
        ):
            exit_code = preflight.main(["--unit", "SJM"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(
            output.getvalue().strip(),
            '{"reason": "account_configuration_invalid", "status": "failed"}',
        )

    def test_cli_repeats_pf_exclusions_and_reports_effective_ids(self):
        result = preflight.AsaasSalesPreflightResult(
            units=("São João de Meriti",),
            excluded_pf_user_ids=(57, 58),
        )
        output = io.StringIO()
        with (
            patch.object(
                preflight,
                "run_asaas_sales_preflight",
                return_value=result,
            ) as run,
            redirect_stdout(output),
        ):
            exit_code = preflight.main(
                [
                    "--unit",
                    "SJM",
                    "--exclude-pf-user-id",
                    "57",
                    "--exclude-pf-user-id",
                    "58",
                ]
            )

        self.assertEqual(exit_code, 0)
        run.assert_called_once_with(
            ["SJM"],
            allow_no_units=False,
            excluded_pf_user_ids=["57", "58"],
        )
        self.assertEqual(
            json.loads(output.getvalue())["excluded_pf_user_ids"],
            [57, 58],
        )

    def test_cli_can_run_startup_gate_with_empty_allowlists(self):
        result = preflight.AsaasSalesPreflightResult(units=())
        with (
            patch.object(
                preflight,
                "run_asaas_sales_preflight",
                return_value=result,
            ) as run,
            redirect_stdout(io.StringIO()),
        ):
            exit_code = preflight.main(["--allow-no-units"])

        self.assertEqual(exit_code, 0)
        run.assert_called_once_with(
            None,
            allow_no_units=True,
            excluded_pf_user_ids=None,
        )
        self.assertEqual(
            result.as_dict()["checks"]["accounts"],
            "not_selected",
        )

    def test_sandbox_receiver_acl_requires_exact_view_and_function_contract(self):
        preflight._validate_sandbox_receiver_acl(_ReadyCursor())
        with self.assertRaisesRegex(
            preflight.AsaasSalesPreflightError, "sandbox_receiver_acl_invalid"
        ):
            preflight._validate_sandbox_receiver_acl(
                _ReadyCursor(sandbox_receiver_acl_ready=False)
            )

    def test_sandbox_receiver_acl_accepts_only_exact_pg16_view_deparse_variant(self):
        pg16_view_definition = """ SELECT id,
    user_id,
    unidade,
    environment,
    account_id,
    wallet_id,
    credential_state
   FROM asaas_receiver_environment_links
  WHERE environment::text = 'sandbox'::text;"""
        preflight._validate_sandbox_receiver_acl(
            _ReadyCursor(
                sandbox_receiver_view_definition=pg16_view_definition
            )
        )
        with self.assertRaisesRegex(
            preflight.AsaasSalesPreflightError, "sandbox_receiver_acl_invalid"
        ):
            preflight._validate_sandbox_receiver_acl(
                _ReadyCursor(
                    sandbox_receiver_view_definition=pg16_view_definition.replace(
                        "'sandbox'::text", "'production'::text"
                    )
                )
            )

    def test_sandbox_receiver_acl_rejects_public_view_or_function_grants(self):
        for marker in ("attribute.attacl", "procedure.proacl"):
            cursor = _ReadyCursor()
            original = cursor.fetchall
            def with_public_grant(marker=marker):
                rows = original()
                if marker in cursor.last_query:
                    return rows + [("id", "PUBLIC", "SELECT", False)] if marker == "attribute.attacl" else rows + [("PUBLIC", "EXECUTE", False)]
                return rows
            cursor.fetchall = with_public_grant
            with self.subTest(marker=marker), self.assertRaisesRegex(preflight.AsaasSalesPreflightError, "sandbox_receiver_acl_invalid"):
                preflight._validate_sandbox_receiver_acl(cursor)

    def test_sandbox_receiver_acl_rejects_missing_view_column_or_owner_write(self):
        scenarios = (
            ("missing_view_column", "attribute.attacl"),
            ("owner_can_update_cipher", "asaas_receiver_environment_links"),
        )
        for scenario, marker in scenarios:
            with self.subTest(scenario=scenario):
                cursor = _ReadyCursor()
                original_fetchall = cursor.fetchall

                def hostile_fetchall(scenario=scenario, marker=marker):
                    rows = original_fetchall()
                    if marker not in cursor.last_query:
                        return rows
                    if scenario == "missing_view_column":
                        return rows[:-1]
                    return [
                        (
                            table,
                            column,
                            "UPDATE" if column == "credential_ciphertext"
                            and privilege == "UPDATE" else privilege,
                            True if column == "credential_ciphertext"
                            and privilege == "UPDATE" else granted,
                            table_granted,
                        )
                        for table, column, privilege, granted, table_granted in rows
                    ]

                cursor.fetchall = hostile_fetchall
                with self.assertRaisesRegex(
                    preflight.AsaasSalesPreflightError,
                    "sandbox_receiver_acl_invalid",
                ):
                    preflight._validate_sandbox_receiver_acl(cursor)

    def test_sandbox_receiver_acl_uses_effective_nondefault_runtime_role(self):
        preflight._validate_sandbox_receiver_acl(
            _ReadyCursor(runtime_role="runtime_por_unidade")
        )

    def test_sandbox_receiver_acl_rejects_named_relation_grants(self):
        with self.assertRaisesRegex(
            preflight.AsaasSalesPreflightError, "sandbox_receiver_acl_invalid"
        ):
            preflight._validate_sandbox_receiver_acl(
                _ReadyCursor(relation_acl_ready=False)
            )

    def test_snapshot_acl_rejects_any_mutable_financial_column_or_public_grant(self):
        cursor = _ReadyCursor()
        original_fetchall = cursor.fetchall

        def mutated_fetchall():
            rows = original_fetchall()
            if "asaas_entry_financial_snapshots" in cursor.last_query and "aclexplode" in cursor.last_query:
                return rows + [("snapshot_json", "PUBLIC", "UPDATE", False)]
            return rows

        cursor.fetchall = mutated_fetchall
        with self.assertRaisesRegex(
            preflight.AsaasSalesPreflightError, "entry_snapshot_acl_invalid"
        ):
            preflight._validate_entry_snapshot_acl(cursor)

    def test_snapshot_acl_rejects_missing_required_read_or_append_grant(self):
        for removed in (
            ("consumed_venda_id", "SELECT"),
            ("snapshot_json", "INSERT"),
            ("entry_integration_id", "SELECT"),
        ):
            with self.subTest(removed=removed):
                cursor = _ReadyCursor()
                original_fetchall = cursor.fetchall

                def hostile_fetchall(removed=removed):
                    rows = original_fetchall()
                    if (
                        "asaas_entry_financial_snapshots" in cursor.last_query
                        and "attribute.attacl" in cursor.last_query
                    ):
                        return [
                            row for row in rows
                            if not (
                                (row[0], row[2]) == removed
                                and (
                                    removed[0] != "entry_integration_id"
                                    or row[1]
                                    == cursor.entry_snapshot_consume_owner
                                )
                            )
                        ]
                    return rows

                cursor.fetchall = hostile_fetchall
                with self.assertRaisesRegex(
                    preflight.AsaasSalesPreflightError,
                    "entry_snapshot_acl_invalid",
                ):
                    preflight._validate_entry_snapshot_acl(cursor)

    def test_snapshot_acl_rejects_extra_owner_or_runtime_update_grants(self):
        for extra in (
            ("snapshot_json", "grupojf_asaas_sales_owner", "UPDATE", False),
            ("consumed_venda_id", "grupojf_asaas_sales_runtime", "UPDATE", False),
        ):
            with self.subTest(extra=extra):
                cursor = _ReadyCursor()
                original_fetchall = cursor.fetchall

                def hostile_fetchall(extra=extra):
                    rows = original_fetchall()
                    if (
                        "asaas_entry_financial_snapshots" in cursor.last_query
                        and "attribute.attacl" in cursor.last_query
                    ):
                        return rows + [extra]
                    return rows

                cursor.fetchall = hostile_fetchall
                with self.assertRaisesRegex(
                    preflight.AsaasSalesPreflightError,
                    "entry_snapshot_acl_invalid",
                ):
                    preflight._validate_entry_snapshot_acl(cursor)

    def test_snapshot_acl_uses_nonpretty_index_predicate_and_rejects_bad_metadata(self):
        cursor = _ReadyCursor()
        preflight._validate_entry_snapshot_acl(cursor)
        query, _params = next(
            (query, params)
            for query, params in cursor.queries
            if "uq_asaas_entry_snapshot_consumed_venda" in query
        )
        self.assertIn(
            "pg_get_expr(index_record.indpred, index_record.indrelid, false)",
            query,
        )
        self.assertNotIn(
            "pg_get_expr(index_record.indpred, index_record.indrelid, true)",
            query,
        )
        with self.assertRaisesRegex(
            preflight.AsaasSalesPreflightError, "entry_snapshot_acl_invalid"
        ):
            preflight._validate_entry_snapshot_acl(
                _ReadyCursor(snapshot_contract_ready=False)
            )

    def test_snapshot_acl_rejects_named_relation_grants(self):
        with self.assertRaisesRegex(
            preflight.AsaasSalesPreflightError, "entry_snapshot_acl_invalid"
        ):
            preflight._validate_entry_snapshot_acl(
                _ReadyCursor(relation_acl_ready=False)
            )


if __name__ == "__main__":
    unittest.main()
