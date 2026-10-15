import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    BACKEND_ROOT / "migrations/add_updated_at_digital_contracts.sql"
)


class DigitalContractUpdatedAtMigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MIGRATION_PATH.read_text(encoding="utf-8")
        cls.sql = " ".join(cls.source.casefold().split())

    def _between(self, start: str, end: str) -> str:
        start_offset = self.sql.index(start)
        end_offset = self.sql.index(end, start_offset)
        return self.sql[start_offset:end_offset]

    def test_migration_is_atomic_idempotent_and_has_bounded_waits(self):
        self.assertTrue(self.sql.startswith("-- migration atomica"))
        self.assertIn("begin;", self.sql)
        self.assertIn("set local lock_timeout = '5s'", self.sql)
        self.assertIn("set local statement_timeout = '5min'", self.sql)
        self.assertIn("set local time zone 'utc'", self.sql)
        self.assertIn(
            "add column if not exists updated_at "
            "timestamp without time zone",
            self.sql,
        )
        self.assertIn(
            "alter column updated_at "
            "set default (current_timestamp at time zone 'utc')",
            self.sql,
        )
        add_column_offset = self.sql.index(
            "add column if not exists updated_at"
        )
        backfill_offset = self.sql.index(
            "update public.digital_contracts",
            add_column_offset,
        )
        default_offset = self.sql.index(
            "alter column updated_at "
            "set default (current_timestamp at time zone 'utc')",
            backfill_offset,
        )
        self.assertLess(add_column_offset, backfill_offset)
        self.assertLess(backfill_offset, default_offset)
        self.assertNotIn(
            "default (current_timestamp at time zone 'utc')",
            self.sql[add_column_offset:backfill_offset],
        )
        self.assertEqual(self.source.count("\nCOMMIT;"), 1)
        self.assertTrue(self.source.rstrip().endswith("COMMIT;"))

    def test_null_backfill_preserves_known_contract_timestamps(self):
        self.assertIn(
            "update public.digital_contracts set updated_at = coalesce( "
            "greatest(signed_at, selfie_at, sent_at, created_at), "
            "current_timestamp ) "
            "where updated_at is null",
            self.sql,
        )

    def test_reconciliation_uses_first_audited_successful_delivery(self):
        reconciliation = self._between(
            "with first_successful_delivery as",
            "create or replace trigger set_digital_contract_updated_at",
        )

        self.assertIn(
            "select distinct on (delivery.document_id)",
            reconciliation,
        )
        self.assertIn(
            "delivery.document_type = 'contrato'",
            reconciliation,
        )
        self.assertIn("delivery.status = 'enviado'", reconciliation)
        self.assertIn("delivery.sent_at is not null", reconciliation)
        self.assertIn(
            "order by delivery.document_id, delivery.sent_at asc, "
            "delivery.id asc",
            reconciliation,
        )
        self.assertIn(
            "sent_at = delivery.sent_at at time zone 'utc'",
            reconciliation,
        )
        self.assertIn(
            "updated_at = delivery.sent_at at time zone 'utc'",
            reconciliation,
        )
        self.assertNotIn("now()", reconciliation)
        self.assertNotIn("current_timestamp", reconciliation)

    def test_reconciliation_only_advances_draft_contracts(self):
        reconciliation = self._between(
            "with first_successful_delivery as",
            "create or replace trigger set_digital_contract_updated_at",
        )

        self.assertIn("set status = 'sent'", reconciliation)
        self.assertIn("contract.status = 'draft'", reconciliation)
        self.assertNotIn("update public.whatsapp_document_deliveries", self.sql)

    def test_reconciliation_locks_audit_and_aborts_for_multiple_candidates(self):
        lock_offset = self.sql.index(
            "lock table public.whatsapp_document_deliveries in share mode"
        )
        guard_offset = self.sql.index("do $migration$", lock_offset)
        reconciliation_offset = self.sql.index(
            "with first_successful_delivery as",
            guard_offset,
        )

        self.assertLess(lock_offset, guard_offset)
        self.assertLess(guard_offset, reconciliation_offset)
        guard = self.sql[guard_offset:reconciliation_offset]
        self.assertIn("select count(*)", guard)
        self.assertIn("contract.status = 'draft'", guard)
        self.assertIn("delivery.document_id = contract.id", guard)
        self.assertIn("delivery.document_type = 'contrato'", guard)
        self.assertIn("delivery.status = 'enviado'", guard)
        self.assertIn("delivery.sent_at is not null", guard)
        self.assertIn("if reconciliation_candidate_count > 1", guard)
        self.assertIn(
            "digital_contract_reconciliation_candidate_limit_exceeded",
            guard,
        )
        for shared_predicate in (
            "contract.status = 'draft'",
            "delivery.document_type = 'contrato'",
            "delivery.status = 'enviado'",
            "delivery.sent_at is not null",
        ):
            self.assertEqual(self.sql.count(shared_predicate), 2)
        self.assertNotRegex(
            self.sql,
            r"(?:contract\.id|delivery\.document_id)\s*=\s*\d+",
        )

    def test_update_trigger_is_installed_after_historical_reconciliation(self):
        backfill_offset = self.sql.index(
            "update public.digital_contracts"
        )
        reconciliation_offset = self.sql.index(
            "update public.digital_contracts as contract"
        )
        function_offset = self.sql.index(
            "create or replace function "
            "public.set_digital_contract_updated_at()"
        )
        trigger_offset = self.sql.index(
            "create or replace trigger set_digital_contract_updated_at"
        )

        self.assertLess(function_offset, backfill_offset)
        self.assertLess(backfill_offset, reconciliation_offset)
        self.assertLess(reconciliation_offset, trigger_offset)
        function_sql = self.sql[function_offset:backfill_offset]
        self.assertIn("returns trigger", function_sql)
        self.assertIn("language plpgsql", function_sql)
        self.assertIn(
            "if new.updated_at is not distinct from old.updated_at then "
            "new.updated_at := current_timestamp at time zone 'utc'",
            function_sql,
        )
        self.assertIn("end if", function_sql)
        self.assertIn("return new", function_sql)

        trigger_sql = self.sql[trigger_offset:]
        self.assertIn(
            "before update on public.digital_contracts",
            trigger_sql,
        )
        self.assertIn("for each row", trigger_sql)
        self.assertIn(
            "execute function public.set_digital_contract_updated_at()",
            trigger_sql,
        )

    def test_migration_contains_no_destructive_operations(self):
        for prohibited in (
            "drop table",
            "drop column",
            "truncate",
            "delete from",
        ):
            self.assertNotIn(prohibited, self.sql)


if __name__ == "__main__":
    unittest.main()
