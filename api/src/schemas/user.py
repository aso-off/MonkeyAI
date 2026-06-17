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

    @classmethod
    def from_orm_user(cls, user) -> "UserRead":
        """Собирает плоский DTO из нормализованных users + user_states + user_statistics."""
        st = user.state
        stats = user.statistics
        return cls(
            id=user.id,
            chat_id=user.chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=user.language,
            is_admin=user.is_admin,
            is_whitelisted=user.is_whitelisted,
            first_seen=user.first_seen,
            last_interaction=user.last_interaction,
            current_dialog_id=st.current_dialog_id,
            current_chat_mode=st.current_chat_mode,
            mini_app_chat_mode=st.mini_app_chat_mode,
            current_model=st.current_model,
            theme=st.theme,
            n_used_tokens=stats.n_used_tokens,
            n_generated_images=stats.n_generated_images,
            n_transcribed_seconds=stats.n_transcribed_seconds,
        )


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
