import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import MaxBodySizeMiddleware, RequestContextMiddleware
from app.api.v1.access_grants import router as access_grants_router
from app.api.v1.ai import router as ai_router
from app.api.v1.allocations import router as allocations_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.availability_exceptions import router as availability_exceptions_router
from app.api.v1.capacity import router as capacity_router
from app.api.v1.exports import router as exports_router
from app.api.v1.health import router as health_router
from app.api.v1.imports import router as imports_router
from app.api.v1.insights import router as insights_router
from app.api.v1.people import router as people_router
from app.api.v1.projects import router as projects_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.skills import router as skills_router
from app.api.v1.teams import router as teams_router
from app.api.v1.users import router as users_router
from app.api.v1.working_schedules import router as working_schedules_router
from app.core.config import ProductionConfigError, get_settings, validate_production_config
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("capacityos.startup")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    # A hard startup failure (never a silent warning) when environment=
    # production still has a development-only default in effect — see
    # docs/adr/0009-phase-9-production-readiness.md. Never raised for
    # "development"/"test", where these defaults are intentional.
    if settings.environment == "production":
        problems = validate_production_config(settings)
        if problems:
            for problem in problems:
                logger.error("unsafe production configuration", extra={"problem": problem})
            raise ProductionConfigError(
                "Refusing to start with environment=production and unsafe configuration: "
                + "; ".join(problems)
            )
    logger.info(
        "CapacityOS API starting",
        extra={
            "environment": settings.environment,
            "ai_provider": settings.ai_provider,
            "database_backend": settings.database_url.split(":", 1)[0],
        },
    )
    yield
    logger.info("CapacityOS API shutting down")


app = FastAPI(title="CapacityOS API", version="0.1.0", lifespan=lifespan)

# Middleware order: each add_middleware call wraps the ones already added,
# so the LAST call here is the OUTERMOST layer, run first on the way in and
# last on the way out. RequestContextMiddleware is added last so its timing
# and request-id logging cover the complete request — including CORS
# preflight handling and a body-size rejection — not just routing.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_body_bytes)
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(audit_router)
app.include_router(people_router)
app.include_router(teams_router)
app.include_router(projects_router)
app.include_router(access_grants_router)
app.include_router(allocations_router)
app.include_router(working_schedules_router)
app.include_router(availability_exceptions_router)
app.include_router(capacity_router)
app.include_router(scenarios_router)
app.include_router(insights_router)
app.include_router(imports_router)
app.include_router(exports_router)
app.include_router(skills_router)
app.include_router(ai_router)
