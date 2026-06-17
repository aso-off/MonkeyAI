import logging

from services.openai import make_client

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_file, lang: str = "ru") -> str:
    try:
        client = make_client()
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=lang,
        )
        return response.text or ""
    except Exception:
        logger.exception("Audio transcription failed")
        return ""
