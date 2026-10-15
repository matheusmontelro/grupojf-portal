"""Durable encrypted intent/receipt journal for the restricted NI operation."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Mapping

from cryptography.fernet import Fernet


class SandboxNIJournalError(RuntimeError):
    pass


_IDS = (27, 44, 47, 48, 55, 96, 118, 123, 125)


class EncryptedNIJournal:
    def __init__(self, directory: Path, cipher: Fernet) -> None:
        self.directory = directory
        self.cipher = cipher

    def start(self, user_id: int, intent: Mapping[str, object]) -> None:
        path = self._path(user_id, "intent")
        self._private_directory()
        # A receipt without a known intent is an uncertain previous response,
        # never an invitation to issue a replacement token.
        self._receipt_must_be_absent(user_id)
        try:
            fd = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
        except FileExistsError:
            raise SandboxNIJournalError("attempt_uncertain") from None

        try:
            self._write_fd(fd, {"state": "started", "intent": dict(intent)})
        except Exception:
            raise SandboxNIJournalError("journal_write_failed") from None
        finally:
            os.close(fd)

        try:
            self._fsync_directory()
        except Exception:
            raise SandboxNIJournalError("journal_write_failed") from None

    def finish(self, user_id: int, result: Mapping[str, object]) -> None:
        intent = self._path(user_id, "intent")
        receipt = self._path(user_id, "receipt")
        self._private_directory()
        self._checked_file(intent)
        try:
            fd = os.open(
                receipt,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
        except FileExistsError:
            raise SandboxNIJournalError("attempt_uncertain") from None

        try:
            self._write_fd(fd, {"state": "received", "result": dict(result)})
        except Exception:
            raise SandboxNIJournalError("journal_write_failed") from None
        finally:
            os.close(fd)

        try:
            self._fsync_directory()
        except Exception:
            raise SandboxNIJournalError("journal_write_failed") from None

    def receipt(self, user_id: int) -> Mapping[str, object]:
        """Returns only the authenticated encrypted receipt to the executor."""
        path = self._path(user_id, "receipt")
        self._private_directory()
        expected = self._checked_file(path)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                opened = os.fstat(fd)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or stat.S_IMODE(opened.st_mode) != 0o600
                    or opened.st_uid != os.geteuid()
                    or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino)
                    != (expected.st_dev, expected.st_ino)
                ):
                    raise ValueError("receipt_raced")
                raw = os.read(fd, 1024 * 1024)
            finally:
                os.close(fd)
            value = json.loads(self.cipher.decrypt(raw).decode())
            if (
                not isinstance(value, dict)
                or value.get("state") != "received"
                or not isinstance(value.get("result"), dict)
            ):
                raise ValueError
            return value["result"]
        except Exception:
            raise SandboxNIJournalError("receipt_invalid") from None

    def _path(self, user_id: int, kind: str) -> Path:
        if user_id not in _IDS:
            raise SandboxNIJournalError("journal_scope_invalid")
        return self.directory / f"ni-access-token-{user_id}.{kind}"

    def _receipt_must_be_absent(self, user_id: int) -> None:
        try:
            self._path(user_id, "receipt").lstat()
        except FileNotFoundError:
            return
        except OSError:
            raise SandboxNIJournalError("attempt_uncertain") from None
        raise SandboxNIJournalError("attempt_uncertain")

    def _private_directory(self) -> None:
        if not self.directory.is_absolute():
            raise SandboxNIJournalError("journal_directory_invalid")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        for item in (self.directory, *self.directory.parents):
            info = item.lstat()
            if item == item.parent:
                break
            if stat.S_ISLNK(info.st_mode) or (item / ".git").exists():
                raise SandboxNIJournalError("journal_directory_invalid")
        info = self.directory.stat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != os.geteuid()
        ):
            raise SandboxNIJournalError("journal_directory_invalid")

    def _checked_file(self, path: Path) -> os.stat_result:
        try:
            info = path.lstat()
        except OSError:
            raise SandboxNIJournalError("attempt_uncertain") from None
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
        ):
            raise SandboxNIJournalError("attempt_uncertain")
        return info

    def _write_fd(self, fd: int, payload: Mapping[str, object]) -> None:
        raw = self.cipher.encrypt(json.dumps(payload, sort_keys=True).encode())
        offset = 0
        while offset < len(raw):
            count = os.write(fd, raw[offset:])
            if count <= 0:
                raise OSError("short_write")
            offset += count
        os.fsync(fd)

    def _fsync_directory(self) -> None:
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
