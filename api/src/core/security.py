import hmac
import hashlib
import os
import time
from urllib.parse import unquote, parse_qsl

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings

_SERVICE_TOKEN = os.environ.get("API_SERVICE_TOKEN", "")

# Set SKIP_WEBAPP_AUTH=true in .env to bypass initData validation in development.
_SKIP_WEBAPP_AUTH = os.environ.get("SKIP_WEBAPP_AUTH", "").lower() in ("1", "true", "yes")

# Shown in Swagger UI as a lock icon — click "Authorize" and enter the token value.
_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="ServiceToken",
    description=(
        "Internal bot→API token. Click **Authorize** and paste the value of "
        "`API_SERVICE_TOKEN` (without the `Bearer ` prefix — Swagger adds it)."
    ),
)


async def verify_service_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Bot → API internal calls. Authorization: Bearer <API_SERVICE_TOKEN>."""
    if not _SERVICE_TOKEN:
        return
    token = credentials.credentials if credentials else None
    if token != _SERVICE_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")


def _verify_init_data(init_data: str, bot_token: str, max_age_seconds: int = 3600) -> dict:
    """
    Validate Telegram Mini App initData HMAC signature.
    Returns parsed fields dict on success, raises ValueError on failure.
    Spec: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    params = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = params.pop("hash", None)

    if not received_hash:
        raise ValueError("hash missing")

    auth_date = params.get("auth_date")
    if not auth_date:
        raise ValueError("auth_date missing")
    if time.time() - int(auth_date) > max_age_seconds:
        raise ValueError("initData expired")

    data_check_string = "\n".join(
        f"{k}={unquote(v)}" for k, v in sorted(params.items())
    )

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        raise ValueError("invalid hash")

    return params


async def verify_webapp_init_data(request: Request) -> dict:
    """
    FastAPI dependency for Telegram Mini App routes.
    Reads initData from Authorization header: 'tma <initData>'.
    Returns the parsed initData fields.

    In development, set SKIP_WEBAPP_AUTH=true to bypass HMAC validation.
    """
    if _SKIP_WEBAPP_AUTH:
        # Dev bypass: skip HMAC check but still parse the actual initData from the header.
        # This lets mock data from mockEnv.ts (see mini-app/src/mockEnv.ts) pass through as-is.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("tma "):
            params = dict(parse_qsl(auth_header[4:]))
            params.pop("hash", None)
            params.pop("signature", None)
            return params
        # Dev fallback: use X-Dev-User-Id header to impersonate any user, default to 1.
        # In Swagger: send this header in "Try it out" to test as a specific user.
        import json as _json
        try:
            uid = int(request.headers.get("X-Dev-User-Id", "1"))
        except ValueError:
            uid = 1
        return {"user": _json.dumps({"id": uid, "first_name": "Dev", "language_code": "ru"})}

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("tma "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Telegram initData")

    init_data = auth_header[4:]
    bot_token = settings.telegram_token.get_secret_value()
    try:
        return _verify_init_data(init_data, bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
