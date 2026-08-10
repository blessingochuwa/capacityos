from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
def get_health() -> dict[str, str]:
    return {"status": "ok"}
