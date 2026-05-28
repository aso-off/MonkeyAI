from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    username: str | None
    first_name: str
    last_name: str | None
    language: str
    is_admin: bool
    is_whitelisted: bool
    first_seen: datetime
    last_interaction: datetime
    current_dialog_id: str | None
    current_chat_mode: str
    mini_app_chat_mode: str
    current_model: str
    theme: str
    n_used_tokens: dict
    n_generated_images: int
    n_transcribed_seconds: float


class UserCreate(BaseModel):
    id: int
    chat_id: int
    username: str | None = None
    first_name: str = ""
    last_name: str | None = None
    language: str = "system"


class UserUpdate(BaseModel):
    language: str | None = None
    current_chat_mode: str | None = None
    current_model: str | None = None
    is_admin: bool | None = None
    is_whitelisted: bool | None = None
