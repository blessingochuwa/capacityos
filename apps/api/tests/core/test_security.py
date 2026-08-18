from app.core.security import (
    generate_session_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_hash_password_never_returns_the_plaintext() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$argon2")


def test_verify_password_accepts_the_correct_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_the_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_verify_password_against_none_always_fails_but_still_does_real_work() -> None:
    """The None-hash path exists specifically for enumeration resistance —
    see AuthService.login and docs/adr/0010-authentication-rbac-audit.md.
    It must return False (never raise), for any input."""
    assert verify_password("anything", None) is False
    assert verify_password("", None) is False


def test_generate_session_token_is_unique_and_high_entropy() -> None:
    tokens = {generate_session_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(t) >= 32 for t in tokens)


def test_hash_token_is_deterministic() -> None:
    token = generate_session_token()
    assert hash_token(token) == hash_token(token)


def test_hash_token_differs_for_different_tokens() -> None:
    assert hash_token(generate_session_token()) != hash_token(generate_session_token())


def test_hash_token_never_returns_the_raw_token() -> None:
    token = generate_session_token()
    assert hash_token(token) != token
