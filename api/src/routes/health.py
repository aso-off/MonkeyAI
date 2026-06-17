import asyncio

from core.redis import get_redis
from core.security import verify_service_token
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> JSONResponse:
    redis_status = "ok"
    try:
        await asyncio.wait_for(get_redis().ping(), timeout=1.0)
    except Exception:
        redis_status = "down"

    overall = "ok" if redis_status == "ok" else "degraded"
    return JSONResponse({"status": overall, "redis": redis_status})


@router.get("/health/debug/500", include_in_schema=False)
async def debug_force_500(_: None = Depends(verify_service_token)) -> JSONResponse:
    """Intentional 500 for Prometheus/Grafana metrics testing. Requires service token."""
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Intentional 500 for metrics testing",
    )
