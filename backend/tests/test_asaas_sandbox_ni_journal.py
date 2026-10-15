import os
from types import SimpleNamespace

from cryptography.fernet import Fernet
import pytest

from app.services.asaas_sandbox_ni_journal import EncryptedNIJournal, SandboxNIJournalError
import app.services.asaas_sandbox_ni_journal as journal_module


def test_started_attempt_is_fsynced_encrypted_and_blocks_replay(tmp_path):
    journal = EncryptedNIJournal(tmp_path / "private", Fernet(Fernet.generate_key()))
    journal.start(27, {"account_id": "account-27"})
    raw = (tmp_path / "private" / "ni-access-token-27.intent").read_bytes()
    assert b"account-27" not in raw
    with pytest.raises(SandboxNIJournalError, match="attempt_uncertain"):
        journal.start(27, {"account_id": "account-27"})


def test_finished_attempt_cannot_be_reopened_and_non_ni_is_rejected(tmp_path):
    journal = EncryptedNIJournal(tmp_path / "private", Fernet(Fernet.generate_key()))
    journal.start(27, {"x": "y"}); journal.finish(27, {"credential_ciphertext": "cipher", "verified": True})
    assert journal.receipt(27) == {"credential_ciphertext": "cipher", "verified": True}
    with pytest.raises(SandboxNIJournalError, match="attempt_uncertain"):
        journal.start(27, {})
    with pytest.raises(SandboxNIJournalError, match="journal_scope_invalid"):
        journal.start(134, {})


def test_empty_or_symlink_intent_is_never_reused(tmp_path):
    directory = tmp_path / "private"; directory.mkdir(mode=0o700)
    journal = EncryptedNIJournal(directory, Fernet(Fernet.generate_key()))
    (directory / "ni-access-token-27.intent").touch(mode=0o600)
    with pytest.raises(SandboxNIJournalError, match="attempt_uncertain"):
        journal.start(27, {})
    (directory / "ni-access-token-44.intent").symlink_to(directory / "ni-access-token-27.intent")
    with pytest.raises(SandboxNIJournalError, match="attempt_uncertain"):
        journal.start(44, {})


def test_orphan_or_symlink_receipt_blocks_intent_before_any_post(tmp_path):
    directory = tmp_path / "private"; directory.mkdir(mode=0o700)
    journal = EncryptedNIJournal(directory, Fernet(Fernet.generate_key()))
    (directory / "ni-access-token-27.receipt").touch(mode=0o600)
    with pytest.raises(SandboxNIJournalError, match="attempt_uncertain"):
        journal.start(27, {})
    (directory / "ni-access-token-44.receipt").symlink_to(
        directory / "ni-access-token-27.receipt"
    )
    with pytest.raises(SandboxNIJournalError, match="attempt_uncertain"):
        journal.start(44, {})


def test_receipt_inspection_error_blocks_intent(tmp_path, monkeypatch):
    journal = EncryptedNIJournal(tmp_path / "private", Fernet(Fernet.generate_key()))
    journal._private_directory()
    original_lstat = journal_module.Path.lstat
    def denied_lstat(path):
        if path.name == "ni-access-token-55.receipt":
            raise PermissionError("denied")
        return original_lstat(path)
    monkeypatch.setattr(journal_module.Path, "lstat", denied_lstat)
    with pytest.raises(SandboxNIJournalError, match="attempt_uncertain"):
        journal.start(55, {})


def test_hardlinked_intent_cannot_be_finished_or_reused(tmp_path):
    journal = EncryptedNIJournal(tmp_path / "private", Fernet(Fernet.generate_key()))
    journal.start(27, {"x": "y"})
    intent = tmp_path / "private" / "ni-access-token-27.intent"
    os.link(intent, tmp_path / "private" / "duplicate")
    with pytest.raises(SandboxNIJournalError, match="attempt_uncertain"):
        journal.finish(27, {"credential_ciphertext": "cipher"})


def test_short_write_or_directory_fsync_failure_leaves_uncertain_marker(tmp_path, monkeypatch):
    directory = tmp_path / "private"
    journal = EncryptedNIJournal(directory, Fernet(Fernet.generate_key()))
    monkeypatch.setattr(journal_module.os, "write", lambda _fd, _data: 0)
    with pytest.raises(SandboxNIJournalError, match="journal_write_failed"):
        journal.start(27, {})
    with pytest.raises(SandboxNIJournalError, match="attempt_uncertain"):
        journal.start(27, {})

    journal = EncryptedNIJournal(tmp_path / "private-two", Fernet(Fernet.generate_key()))
    monkeypatch.undo()
    monkeypatch.setattr(journal, "_fsync_directory", lambda: (_ for _ in ()).throw(OSError("fsync")))
    with pytest.raises(SandboxNIJournalError, match="journal_write_failed"):
        journal.start(44, {})
    with pytest.raises(SandboxNIJournalError, match="attempt_uncertain"):
        journal.start(44, {})


def test_receipt_rejects_inode_swap_between_lstat_and_open(tmp_path, monkeypatch):
    journal = EncryptedNIJournal(tmp_path / "private", Fernet(Fernet.generate_key()))
    journal.start(27, {}); journal.finish(27, {"credential_ciphertext": "cipher"})
    actual_fstat = journal_module.os.fstat
    def raced_fstat(fd):
        info = actual_fstat(fd)
        return SimpleNamespace(st_mode=info.st_mode, st_uid=info.st_uid, st_nlink=info.st_nlink,
                               st_dev=info.st_dev, st_ino=info.st_ino + 1)
    monkeypatch.setattr(journal_module.os, "fstat", raced_fstat)
    with pytest.raises(SandboxNIJournalError, match="receipt_invalid"):
        journal.receipt(27)
