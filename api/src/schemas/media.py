from pydantic import BaseModel


class ImageGenerateRequest(BaseModel):
    prompt: str
    n_images: int = 1
    size: str = "1024x1024"
    quality: str = "medium"
    user_id: int | None = None


class ImageGenerateResponse(BaseModel):
    images_b64: list[str]
    imgbb_urls: list[str] = []


class TranscribeResponse(BaseModel):
    text: str
    duration_seconds: float
