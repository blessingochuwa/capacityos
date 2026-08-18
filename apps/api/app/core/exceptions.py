"""Domain-level exceptions and their HTTP translation.

Services raise these instead of letting SQLAlchemy/database errors escape to
routes. main.py registers the handlers below so callers always get a clean
JSON error body — never a raw traceback or database error message (CLAUDE.md
§27/§28: don't expose internal stack traces or raw database errors).

Every handler logs before responding, so an operator can always answer "what
happened, on which request, in which subsystem" from logs alone (Phase 9
spec §5) — client-caused errors (404/409/422) log at INFO since they're
normal, expected flow; infrastructure/unexpected failures log at ERROR with
a full traceback via logger.exception. See
docs/adr/0009-phase-9-production-readiness.md.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger("capacityos.errors")


class DomainError(Exception):
    """Base class for errors raised by the service layer."""


class NotFoundError(DomainError):
    def __init__(self, entity: str, identifier: object) -> None:
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} not found: {identifier}")


class ConflictError(DomainError):
    """A request conflicts with existing state (e.g. duplicate membership)."""


class DomainValidationError(DomainError):
    """A business rule was violated that Pydantic's field-level validation
    can't express on its own (e.g. a cross-entity or merged-state check)."""


class UnauthenticatedError(DomainError):
    """No valid session — raised by app/api/deps.py::get_current_user
    (Phase 10). Distinguished from ForbiddenError below so a caller can
    always tell "you're not logged in" (401) from "you're logged in but not
    allowed" (403) — see docs/adr/0010-authentication-rbac-audit.md."""


class ForbiddenError(DomainError):
    """A valid, authenticated caller lacks the permission or role required
    for this action — raised by app/api/deps.py::require_permission and by
    UserService's Owner-escalation checks (Phase 10)."""


def register_exception_handlers(app: FastAPI) -> None:
    # The @app.exception_handler(SomeException) decorator (rather than
    # add_exception_handler) is what gives each handler's `exc` parameter
    # its correct narrowed type — add_exception_handler's signature only
    # accepts handlers typed for the base Exception, which pyright strict
    # correctly rejects for a handler typed to a specific subclass. The
    # trade-off: pyright's reportUnusedFunction can't see that FastAPI
    # calls these locally-nested functions at runtime via the decorator,
    # so it's suppressed explicitly below rather than left unexplained.
    #
    # Dispatch is by the exception's MRO (Starlette walks type(exc).__mro__
    # and returns the first registered class it finds), not registration
    # order — so IntegrityError's specific handler always wins over the
    # broader SQLAlchemyError handler below for that one subtype, and every
    # DomainError subtype's specific handler always wins over the final
    # catch-all Exception handler, regardless of what order these are
    # registered in.
    @app.exception_handler(NotFoundError)
    async def handle_not_found(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        logger.info(
            "not found",
            extra={"path": request.url.path, "entity": exc.entity},
        )
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(UnauthenticatedError)
    async def handle_unauthenticated(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: UnauthenticatedError
    ) -> JSONResponse:
        logger.info("unauthenticated", extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc) or "Authentication required."},
            headers={"WWW-Authenticate": "Cookie"},
        )

    @app.exception_handler(ForbiddenError)
    async def handle_forbidden(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: ForbiddenError
    ) -> JSONResponse:
        logger.info("forbidden", extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc) or "You do not have permission to perform this action."},
        )

    @app.exception_handler(ConflictError)
    async def handle_conflict(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: ConflictError
    ) -> JSONResponse:
        logger.info("conflict", extra={"path": request.url.path})
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(DomainValidationError)
    async def handle_validation(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: DomainValidationError
    ) -> JSONResponse:
        logger.info("business rule violation", extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)}
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(  # pyright: ignore[reportUnusedFunction]
        request: Request, _exc: IntegrityError
    ) -> JSONResponse:
        # Defense in depth: service-layer checks should catch conflicts first,
        # but never let a raw DB error/message reach the client.
        logger.warning(
            "integrity error reached the API layer unhandled by a service-level "
            "check — investigate the route/service for a missing conflict check",
            extra={"path": request.url.path},
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Request conflicts with existing data."},
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_unavailable(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        # Any database failure that ISN'T an IntegrityError (that handler
        # takes precedence for its subtype) — a connection drop, a timeout, a
        # locked SQLite file. Distinguished from a generic 500 so the client
        # can tell "the database is unavailable" from "the application has a
        # bug" (Phase 9 spec §7). Never includes exc's own message — it can
        # contain a connection string, table/column names, or raw SQL.
        logger.error(
            "database error",
            extra={"path": request.url.path, "exception_type": type(exc).__name__},
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "The database is temporarily unavailable. Please try again."},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: Exception
    ) -> JSONResponse:
        # The last-resort handler — anything not already caught by a more
        # specific handler above (including FastAPI's own built-in
        # HTTPException/RequestValidationError handlers, which are
        # registered separately and always take precedence via MRO lookup).
        # Never echoes exc's message to the client (CLAUDE.md §27) — only
        # the server-side log gets the real exception and traceback.
        logger.error(
            "unexpected error",
            extra={"path": request.url.path, "exception_type": type(exc).__name__},
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred. Please try again."},
        )
