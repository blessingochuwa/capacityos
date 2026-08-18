"""Password hashing and session-token primitives (Phase 10).

Password hashing: argon2-cffi (Argon2id), not passlib — see
docs/adr/0010-authentication-rbac-audit.md for why. Session tokens are
random opaque values (secrets.token_urlsafe), never signed/encrypted, so no
SESSION_SECRET_KEY exists anywhere in this codebase — only their SHA-256
hash is ever persisted (hash_token), so a read-only database compromise
cannot be replayed as a valid session cookie.
"""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_password_hasher = PasswordHasher()

# A fixed, validly-formatted-but-unusable hash, verified against on every
# login attempt for an email that doesn't match any user — keeps failed-
# login response time close to constant regardless of whether the account
# exists, so timing can't be used to enumerate registered emails (see G in
# the ADR). Generated once, at import time, from a random value never used
# as a real password anywhere.
_DUMMY_HASH = _password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Always performs a real Argon2 verify, even when password_hash is
    None (verifies against _DUMMY_HASH instead) — see module docstring."""
    try:
        _password_hasher.verify(password_hash or _DUMMY_HASH, password)
        return password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_session_token() -> str:
    """A high-entropy opaque token — the raw value the client's cookie
    carries. Never stored; see hash_token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 is intentional, not Argon2: this hash is looked up on every
    authenticated request (a fast, deterministic hash is correct here),
    unlike a password hash which is deliberately slow and only checked once
    per login. The token itself already carries 256 bits of entropy from
    secrets.token_urlsafe, so a fast hash doesn't reintroduce a brute-force
    risk the way it would for a low-entropy password."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
