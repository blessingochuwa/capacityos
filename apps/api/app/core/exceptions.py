"""Domain-level exceptions and their HTTP translation.

Services raise these instead of letting SQLAlchemy/database errors escape to
routes. main.py registers the handlers below so callers always get a clean
JSON error body — never a raw traceback or database error message (CLAUDE.md
§27/§28: don't expose internal stack traces or raw database errors).
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


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


def register_exception_handlers(app: FastAPI) -> None:
    # The @app.exception_handler(SomeException) decorator (rather than
    # add_exception_handler) is what gives each handler's `exc` parameter
    # its correct narrowed type — add_exception_handler's signature only
    # accepts handlers typed for the base Exception, which pyright strict
    # correctly rejects for a handler typed to a specific subclass. The
    # trade-off: pyright's reportUnusedFunction can't see that FastAPI
    # calls these locally-nested functions at runtime via the decorator,
    # so it's suppressed explicitly below rather than left unexplained.
    @app.exception_handler(NotFoundError)
    async def handle_not_found(  # pyright: ignore[reportUnusedFunction]
        _request: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def handle_conflict(  # pyright: ignore[reportUnusedFunction]
        _request: Request, exc: ConflictError
    ) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(DomainValidationError)
    async def handle_validation(  # pyright: ignore[reportUnusedFunction]
        _request: Request, exc: DomainValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)}
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(  # pyright: ignore[reportUnusedFunction]
        _request: Request, _exc: IntegrityError
    ) -> JSONResponse:
        # Defense in depth: service-layer checks should catch conflicts first,
        # but never let a raw DB error/message reach the client.
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Request conflicts with existing data."},
        )
