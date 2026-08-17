"""Liveness vs readiness (Phase 9 spec §6) — deliberately two different
questions, two different routes, two different failure meanings.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine

router = APIRouter(prefix="/api/v1", tags=["health"])
logger = logging.getLogger("capacityos.health")


@router.get("/health")
def get_health() -> dict[str, str]:
    """Liveness — "is the application process alive?" Checks nothing
    external: a response here only means the ASGI app is up and routing
    requests, not that its dependencies are reachable. Deliberately cheap —
    safe for a tight liveness-probe interval, and never blocks on the
    database or the AI provider."""
    return {"status": "ok"}


@router.get("/health/ready")
def get_readiness() -> JSONResponse:
    """Readiness — "can this instance currently serve requests that need its
    dependencies?" Checks database connectivity only, via a dedicated,
    isolated connection (never the request-scoped get_db session, so a
    failed probe can't interact with that session's commit/rollback
    lifecycle). Deliberately does NOT check AI provider availability — AI is
    explicitly optional (CLAUDE.md §21/docs/adr/0008-phase-8-ai-insight-layer.md),
    so a missing, misconfigured, or unreachable AI provider must never make
    an otherwise-healthy instance report "not ready"; see GET /api/v1/ai/status
    for AI-specific availability."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.error("readiness check failed: database unreachable")
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "unreachable"},
        )
    return JSONResponse(status_code=200, content={"status": "ok", "database": "ok"})
