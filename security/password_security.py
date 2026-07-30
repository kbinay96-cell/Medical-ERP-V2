"""
Password Security
Layer: Security Utility (consumed by Engine only)
Responsibility: One-way hashing and verification using Argon2id.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,   # 64 MB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

ALGO_NAME = "ARGON2ID"


class PasswordSecurity:

    @staticmethod
    def hash_password(plain_password: str) -> str:
        return _hasher.hash(plain_password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return _hasher.verify(hashed_password, plain_password)
        except (VerifyMismatchError, InvalidHash):
            return False

    @staticmethod
    def needs_rehash(hashed_password: str) -> bool:
        return _hasher.check_needs_rehash(hashed_password)
