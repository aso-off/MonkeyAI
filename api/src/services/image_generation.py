import base64
import logging
from io import BytesIO

import httpx

from services.openai import make_client

logger = logging.getLogger(__name__)

IMAGE_MODEL = "gpt-image-1.5"
IMAGE_MODELS: frozenset[str] = frozenset({IMAGE_MODEL})


async def generate_image_b64(
    prompt: str,
    model: str = IMAGE_MODEL,
    size: str = "1024x1024",
    quality: str = "medium",
) -> str:
    """
    Generate one image and return a base64 data URI (data:image/png;base64,...).
    Used by the WebSocket endpoint — result never expires, safe to store in DB.
    If the model returns a URL instead of raw bytes, the image is downloaded and encoded.
    """
    client = make_client()
    response = await client.images.generate(
        model=model,
        prompt=prompt,
        n=1,
        size=size,
        quality=quality,
    )
    item = response.data[0]
    # gpt-image-1.5 возвращает b64_json напрямую
    if item.b64_json:
        return f"data:image/png;base64,{item.b64_json}"
    # запасной путь, если пришёл URL
    if item.url:
        async with httpx.AsyncClient(timeout=90.0) as http:
            r = await http.get(item.url)
            r.raise_for_status()
            return f"data:image/png;base64,{base64.b64encode(r.content).decode()}"
    raise ValueError("No image data in OpenAI response")


async def generate_image_url(
    prompt: str,
    model: str = IMAGE_MODEL,
    size: str = "1024x1024",
    quality: str = "medium",
) -> str:
    """
    Generate one image and return its URL (or data URI as fallback).
    Used by the mini-app streaming endpoint.
    """
    client = make_client()
    response = await client.images.generate(
        model=model,
        prompt=prompt,
        n=1,
        size=size,
        quality=quality,
    )
    item = response.data[0]
    if item.url:
        return item.url
    # Fallback: return base64 data URI so the mini-app can still display it
    return f"data:image/png;base64,{item.b64_json}"


async def generate_images(
    prompt: str,
    n_images: int = 1,
    size: str = "1024x1024",
    quality: str = "medium",
) -> list[BytesIO]:
    client = make_client()
    response = await client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        n=n_images,
        size=size,
        quality=quality,
    )
    results: list[BytesIO] = []
    for item in response.data:
        if item.url:
            async with httpx.AsyncClient() as http:
                async with http.stream("GET", item.url) as r:
                    r.raise_for_status()
                    buf = BytesIO()
                    async for chunk in r.aiter_bytes(chunk_size=65536):
                        buf.write(chunk)
        else:
            buf = BytesIO(base64.b64decode(item.b64_json))
        buf.name = "image.png"
        buf.seek(0)
        results.append(buf)
    return results