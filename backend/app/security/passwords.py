import hashlib
import hmac
import re
from typing import Tuple

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128

_LEGACY_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_COMMON_PASSWORDS = {
    "123456789012345",
    "administrador123",
    "grupo jf 123456",
    "odontocompany123",
    "passwordpassword",
    "senha123456789",
}

# Parâmetros mínimos recomendados pela OWASP para Argon2id.
_PASSWORD_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19_456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


class PasswordPolicyError(ValueError):
    """Senha nova não atende à política do portal."""


def validate_new_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"A senha deve ter no máximo {MAX_PASSWORD_LENGTH} caracteres."
        )
    if password.casefold().strip() in _COMMON_PASSWORDS:
        raise PasswordPolicyError("Escolha uma senha menos comum.")


def hash_password(password: str, *, enforce_policy: bool = True) -> str:
    if enforce_policy:
        validate_new_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, stored_hash: str) -> Tuple[bool, bool]:
    """Retorna (válida, precisa_rehash) sem expor o algoritmo ao chamador."""
    if not stored_hash:
        return False, False

    if _LEGACY_SHA256_PATTERN.fullmatch(stored_hash):
        candidate = hashlib.sha256(password.encode("utf-8")).hexdigest()
        is_valid = hmac.compare_digest(candidate, stored_hash)
        return is_valid, is_valid

    try:
        is_valid = _PASSWORD_HASHER.verify(stored_hash, password)
        return is_valid, is_valid and _PASSWORD_HASHER.check_needs_rehash(stored_hash)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False, False
