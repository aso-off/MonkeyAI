import sys
from pathlib import Path

# Ensure /app/src is on sys.path (core, db, routes, …).
# Dockerfile sets PYTHONPATH=/app/src, but manual runs may omit it.
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import asyncio
from contextlib import asynccontextmanager, suppress

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.types import ASGIApp, Receive, Scope, Send

from core.logger import logger
from core.redis import init_redis, close_redis
from db.db import init_db, engine
from routes.health import router as health_router
from routes.users import router as users_router
from routes.dialogs import router as dialogs_router
from routes.chat import router as chat_router
from routes.media import router as media_router
from routes.webapp import router as webapp_router
from routes.ws import router as ws_router
from monitoring.prometheus import (
    api_client_http_status_class_total,
    api_client_request_duration_seconds,
    api_client_requests_total,
    api_requests_in_flight,
    api_response_size_bytes,
    http_status_class,
    normalize_path,
    time_seconds,
)


class PrometheusMiddleware:
    """Pure ASGI middleware for Prometheus metrics — avoids BaseHTTPMiddleware overhead."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        t0 = time_seconds()()
        status_code = 500
        response_size = 0

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code, response_size
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    response_size += len(body)
            await send(message)

        api_requests_in_flight.inc()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            api_requests_in_flight.dec()
            if path != "/metrics":
                norm = normalize_path(path)
                api_client_requests_total.labels(method, norm, str(status_code)).inc()
                api_client_http_status_class_total.labels(
                    method, norm, http_status_class(status_code)
                ).inc()
                api_client_request_duration_seconds.labels(method, norm).observe(
                    time_seconds()() - t0
                )
                if response_size > 0:
                    api_response_size_bytes.labels(method, norm).observe(response_size)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os
    if not os.environ.get("API_SERVICE_TOKEN"):
        raise RuntimeError("API_SERVICE_TOKEN is not set — refusing to start")

    logger.info("API starting...")
    await init_db()
    logger.info("DB initialized")

    await init_redis()

    # Sync admin/whitelist flags from user-ids.yml into DB
    from db.db import Session
    from db.repositories.users import sync_auth_from_yaml
    from core.config import settings as s
    from services import whitelist
    async with Session() as session:
        await sync_auth_from_yaml(session, admin_ids=s.admin_ids, allowed_ids=s.allowed_user_ids)
    await whitelist.rebuild(set(s.admin_ids) | set(s.allowed_user_ids))
    logger.info("Auth flags synced from user-ids.yml")

    retention_task: asyncio.Task | None = None
    if s.retention_enabled:
        from services.retention import retention_loop
        retention_task = asyncio.create_task(retention_loop())
        logger.info("Retention task started")

    yield

    if retention_task is not None:
        retention_task.cancel()
        with suppress(asyncio.CancelledError):
            await retention_task
    await engine.dispose()
    await close_redis()
    logger.info("API stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        title="Monkey AI API",
        version="2.0.0",
        docs_url="/docs",
        redoc_url=None,
        openapi_tags=[
            {"name": "health"},
            {"name": "users",   "description": "🔒 `Bearer <API_SERVICE_TOKEN>`"},
            {"name": "dialogs", "description": "🔒 `Bearer <API_SERVICE_TOKEN>`"},
            {"name": "chat",    "description": "🔒 `Bearer <API_SERVICE_TOKEN>`"},
            {"name": "media",   "description": "🔒 `Bearer <API_SERVICE_TOKEN>`"},
            {
                "name": "webapp",
                "description": "Telegram Mini App. Auth: `Authorization: tma <initData>`.",
            },
        ],
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "tryItOutEnabled": True,
            "defaultModelsExpandDepth": 1,
            "docExpansion": "list",
        },
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = uuid.uuid4().hex[:12]
        logger.exception("Unhandled error [%s] %s %s", request_id, request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )

    app.include_router(health_router)
    app.include_router(users_router)
    app.include_router(dialogs_router)
    app.include_router(chat_router)
    app.include_router(media_router)
    app.include_router(webapp_router)
    app.include_router(ws_router)

    # Override /openapi.json to pre-compute the schema and set explicit
    # Content-Length so Cloudflare never truncates the response mid-transfer.
    import json as _json

    @app.get("/openapi.json", include_in_schema=False)
    async def _openapi_json() -> Response:
        content = _json.dumps(app.openapi()).encode()
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Length": str(len(content)), "Cache-Control": "no-store"},
        )

    # Prometheus — pure ASGI, no BaseHTTPMiddleware interference.
    # Added first → will be innermost (outermost = CORS below).
    app.add_middleware(PrometheusMiddleware)

    # CORS — added last → becomes outermost middleware layer.
    # Auth is via HMAC-signed Telegram initData, not cookies → allow_origins="*" is safe.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    return app


app = create_app()