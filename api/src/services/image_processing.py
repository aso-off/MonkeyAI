"""
Image post-processing service.

Converts OpenAI base64 PNG → optimised WebP in memory, then uploads to ImgBB
for permanent CDN hosting.  The Mini App receives a short HTTPS URL rather than
a large inline base64 blob, which avoids Cloudflare Tunnel dropping oversized
WebSocket frames.
"""

import base64
import io
import logging

import httpx
from PIL import Image

logger = logging.getLogger(__name__)


def process_generated_image(b64_data: str, quality: int = 82) -> dict:
    """
    Decode base64 PNG from OpenAI, convert to WebP, return as base64.

    Parameters
    ----------
    b64_data : str
        Raw base64 string OR data URI  ``data:image/png;base64,...``.
    quality : int
        WebP quality 1-100.  82 gives ~150-400 KB vs 800+ KB PNG.

    Returns
    -------
    dict
        ``data``    — base64-encoded WebP bytes (ASCII, no data-URI prefix),
        ``size_kb`` — compressed size in kilobytes.
    """
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]

    raw_bytes = base64.b64decode(b64_data)
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, optimize=True, method=6)
    webp_bytes = buf.getvalue()
    size_kb = round(len(webp_bytes) / 1024, 1)
    logger.info("Processed generated image (%.1f KB WebP)", size_kb)

    return {
        "data": base64.b64encode(webp_bytes).decode("ascii"),
        "size_kb": size_kb,
    }


async def upload_to_imgbb(b64_data: str, api_key: str) -> str:
    """
    Upload a base64-encoded WebP to ImgBB and return the permanent direct URL.

    Parameters
    ----------
    b64_data : str
        Base64 string WITHOUT the data-URI prefix.
    api_key : str
        ImgBB API key.

    Returns
    -------
    str
        Direct image URL, e.g. ``https://i.ibb.co/abc123/image.webp``.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.imgbb.com/1/upload",
            params={"key": api_key},
            data={"image": b64_data},
        )
        resp.raise_for_status()
        return resp.json()["data"]["url"]