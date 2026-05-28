from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from core.security import verify_service_token

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@router.get("/health/debug/500", include_in_schema=False)
async def debug_force_500(_: None = Depends(verify_service_token)) -> JSONResponse:
    """Intentional 500 for Prometheus/Grafana metrics testing. Requires service token."""
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Intentional 500 for metrics testing",
    )