import base64
import logging
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from openai import BadRequestError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import verify_service_token
from db.db import get_session
from db.repositories import users as user_repo
from schemas.media import ImageGenerateRequest, ImageGenerateResponse, TranscribeResponse
from services.image import generate_images
from services.image_service import upload_to_imgbb
from services.voice import transcribe_audio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/media", tags=["media"])


@router.post("/images/generate", response_model=ImageGenerateResponse)
async def images_generate(
    req: ImageGenerateRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
):
    """Generate images via OpenAI. Returns list of base64-encoded PNG."""
    try:
        buffers = await generate_images(
            prompt=req.prompt,
            n_images=req.n_images,
            size=req.size,
            quality=req.quality,
        )
    except BadRequestError as exc:
        logger.warning("Image generation blocked by OpenAI safety: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="moderation_blocked",
        ) from exc
    except Exception as exc:
        logger.error("Image generation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    images_b64 = []
    for buf in buffers:
        buf.seek(0)
        images_b64.append(base64.b64encode(buf.read()).decode())

    # Upload each PNG to ImgBB so bot-generated images appear in the gallery.
    imgbb_urls: list[str] = []
    if settings.imgbb_api_key:
        for raw_b64 in images_b64:
            try:
                url = await upload_to_imgbb(raw_b64, settings.imgbb_api_key)
                logger.info("Bot image uploaded to ImgBB: %s", url)
            except Exception:
                logger.warning("ImgBB upload failed for bot image")
                url = ""
            imgbb_urls.append(url)

    if req.user_id is not None:
        try:
            await user_repo.increment_n_generated_images(session, req.user_id, len(images_b64))
        except Exception:
            logger.warning("Could not update image counter for user %d", req.user_id)

    return ImageGenerateResponse(images_b64=images_b64, imgbb_urls=imgbb_urls)


@router.post("/audio/transcribe", response_model=TranscribeResponse)
async def audio_transcribe(
    user_id: int,
    lang: str = "ru",
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
):
    """Transcribe voice/audio file. Updates user transcription counter in DB."""
    content = await file.read()
    if len(content) > 10_000_000:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")
    audio_buf = BytesIO(content)
    audio_buf.name = file.filename or "voice.oga"

    text = await transcribe_audio(audio_buf, lang)

    # Estimate duration from file size (~16kbps OGG Opus)
    duration_seconds = len(content) / 2000.0

    try:
        from db.repositories.users import increment_n_transcribed_seconds
        await increment_n_transcribed_seconds(session, user_id, duration_seconds)
    except Exception:
        logger.warning("Could not update transcription counter for user %d", user_id)

    return TranscribeResponse(text=text, duration_seconds=duration_seconds)
