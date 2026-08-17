"""The two new catch-all error handlers (Phase 9 spec §7): unexpected
exceptions and database-unavailable errors must both return a safe, generic
body and never leak internals. Client-caused errors (404/409/422) are
already covered extensively by existing per-entity API tests, so these
focus only on what's new. Each test builds its own minimal, throwaway
FastAPI app wired with the real register_exception_handlers — no shared
state with the main `app` singleton, no route-table cleanup needed.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.exceptions import register_exception_handlers


def _make_test_app() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)
    return test_app


def test_unexpected_exception_returns_a_safe_generic_500() -> None:
    test_app = _make_test_app()

    @test_app.get("/boom")
    def _boom() -> None:  # pyright: ignore[reportUnusedFunction]
        raise RuntimeError("a secret internal detail that must never reach the client")

    with TestClient(test_app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/boom")

    assert response.status_code == 500
    assert "secret internal detail" not in response.text
    assert response.json() == {"detail": "An unexpected error occurred. Please try again."}


def test_database_error_returns_503_not_a_generic_500() -> None:
    test_app = _make_test_app()

    @test_app.get("/db-boom")
    def _db_boom() -> None:  # pyright: ignore[reportUnusedFunction]
        raise OperationalError("SELECT 1", {}, Exception("password=hunter2"))

    with TestClient(test_app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/db-boom")

    assert response.status_code == 503
    assert "hunter2" not in response.text
    assert response.json() == {
        "detail": "The database is temporarily unavailable. Please try again."
    }


def test_integrity_error_still_takes_precedence_over_the_broader_database_handler() -> None:
    """IntegrityError is a subtype of SQLAlchemyError — its own, more
    specific handler (409, "conflicts with existing data") must still win
    over the new, broader SQLAlchemyError handler (503), proving MRO-based
    dispatch picks the most specific registered handler."""
    from sqlalchemy.exc import IntegrityError

    test_app = _make_test_app()

    @test_app.get("/integrity-boom")
    def _integrity_boom() -> None:  # pyright: ignore[reportUnusedFunction]
        raise IntegrityError("INSERT ...", {}, Exception("unique constraint"))

    with TestClient(test_app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/integrity-boom")

    assert response.status_code == 409
    assert response.json() == {"detail": "Request conflicts with existing data."}
