import hashlib
import unittest
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations/add_asaas_entry_payments.sql"
)


class AsaasEntryMigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MIGRATION.read_text(encoding="utf-8")
        cls.sql = " ".join(cls.source.casefold().split())

    def test_is_atomic_additive_and_bounded(self):
        self.assertIn("set local lock_timeout = '5s'", self.sql)
        self.assertIn("set local statement_timeout = '10min'", self.sql)
        self.assertTrue(self.source.rstrip().endswith("COMMIT;"))
        self.assertNotIn("delete from", self.sql)
        self.assertNotIn("truncate", self.sql)
        self.assertNotIn("drop table", self.sql)

    def test_is_sandbox_only_and_new_snapshot_is_additive(self):
        self.assertIn("check (environment = 'sandbox')", self.sql)
        self.assertIn("'asaas_entry_pix'", self.sql)
        self.assertIn("card_installments between 1 and 12", self.sql)
        split_migration = (
            MIGRATION.parent / "add_asaas_sandbox_entry_split_snapshot.sql"
        ).read_text(encoding="utf-8").casefold()
        self.assertNotIn("drop constraint", split_migration)
        self.assertIn("asaas_entry_financial_snapshots", split_migration)
        self.assertIn("create table if not exists public.asaas_entry_financial_snapshots", split_migration)

    def test_sandbox_receiver_view_never_exposes_cipher_and_reader_is_tuple_bound(self):
        source = (
            MIGRATION.parent / "add_asaas_sandbox_entry_split_snapshot.sql"
        ).read_text(encoding="utf-8")
        sql = " ".join(source.casefold().split())
        view_start = sql.index("create or replace view public.asaas_sandbox_receiver_link_metadata")
        view_end = sql.index("revoke all on table public.asaas_sandbox_receiver_link_metadata", view_start)
        self.assertNotIn("credential_ciphertext", sql[view_start:view_end])
        self.assertIn("where environment = 'sandbox'", sql[view_start:view_end])
        self.assertIn("security definer", sql)
        self.assertIn("link.id = p_link_id", sql)
        self.assertIn("link.user_id = p_user_id", sql)
        self.assertIn("link.unidade = p_unidade", sql)
        self.assertIn("link.account_id = p_account_id", sql)
        self.assertIn("link.wallet_id = p_wallet_id", sql)
        self.assertIn("link.credential_state = 'verified'", sql)
        self.assertIn("revoke all on function public.asaas_get_verified_sandbox_receiver_cipher", sql)

    def test_outbox_and_single_consumption_are_enforced(self):
        self.assertIn("create table if not exists public.asaas_entry_jobs", self.sql)
        self.assertIn("uq_asaas_entry_active_job", self.sql)
        self.assertIn("uq_vendas_asaas_pre_venda", self.sql)
        self.assertIn("where pre_venda_id like 'pv-as-%'", self.sql)

    def test_snapshot_consumption_is_compare_and_set_security_definer(self):
        split_source = (
            MIGRATION.parent / "add_asaas_sandbox_entry_split_snapshot.sql"
        ).read_text(encoding="utf-8")
        split_migration = split_source.casefold()
        self.assertIn(
            "create or replace function public.asaas_consume_entry_snapshot(\n"
            "    p_entry_integration_id bigint,\n    p_venda_id bigint\n) returns bigint",
            split_migration,
        )
        self.assertIn("security definer", split_migration)
        self.assertIn("volatile", split_migration)
        self.assertIn("strict", split_migration)
        self.assertIn("set search_path = pg_catalog, pg_temp", split_migration)
        self.assertIn("and snapshot.consumed_venda_id is null", split_migration)
        self.assertIn("returning snapshot.consumed_venda_id", split_migration)
        self.assertIn(
            "revoke all on function public.asaas_consume_entry_snapshot(bigint, bigint)\n"
            "    from public",
            split_migration,
        )
        body = (
            split_source.split(
                "CREATE OR REPLACE FUNCTION public.asaas_consume_entry_snapshot",
                1,
            )[1]
            .split("AS $function$", 1)[1]
            .split("$function$;", 1)[0]
        )
        self.assertEqual(
            hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "c7f04620c8dc76313cd25d3ba26f7cf7426b30c9b1104aceec824ca999467fbc",
        )

    def test_snapshot_consumption_cas_binds_both_ids_and_only_unconsumed_row(self):
        source = (
            MIGRATION.parent / "add_asaas_sandbox_entry_split_snapshot.sql"
        ).read_text(encoding="utf-8")
        body = source.split(
            "CREATE OR REPLACE FUNCTION public.asaas_consume_entry_snapshot",
            1,
        )[1].split("AS $function$", 1)[1].split("$function$;", 1)[0]
        sql = " ".join(body.casefold().split())
        self.assertIn(
            "set consumed_venda_id = p_venda_id where p_entry_integration_id > 0 "
            "and p_venda_id > 0 and snapshot.entry_integration_id = "
            "p_entry_integration_id and snapshot.consumed_venda_id is null "
            "returning snapshot.consumed_venda_id",
            sql,
        )


if __name__ == "__main__":
    unittest.main()
