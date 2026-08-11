from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.allocations import router as allocations_router
from app.api.v1.availability_exceptions import router as availability_exceptions_router
from app.api.v1.health import router as health_router
from app.api.v1.people import router as people_router
from app.api.v1.projects import router as projects_router
from app.api.v1.teams import router as teams_router
from app.api.v1.working_schedules import router as working_schedules_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers

settings = get_settings()

app = FastAPI(title="CapacityOS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(people_router)
app.include_router(teams_router)
app.include_router(projects_router)
app.include_router(allocations_router)
app.include_router(working_schedules_router)
app.include_router(availability_exceptions_router)
