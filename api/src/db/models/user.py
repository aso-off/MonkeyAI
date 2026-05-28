import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="system")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_whitelisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_interaction: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    current_dialog_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Active dialog per chat_mode, e.g. {"assistant": "<uuid>", "code_assistant": "<uuid>"}
    current_dialog_ids: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    current_chat_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="assistant")
    # Mini-app has its own chat mode column so bot's assistant is never overwritten
    mini_app_chat_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="mini_app_assistant")
    # Active mini-app dialog per mini_app_chat_mode (separate from bot history)
    mini_app_dialog_ids: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    current_model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    theme: Mapped[str] = mapped_column(String(16), nullable=False, default="system")

    n_used_tokens: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    n_generated_images: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_transcribed_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    dialogs: Mapped[list["Dialog"]] = relationship("Dialog", back_populates="user", lazy="select")

    __table_args__ = (
        Index("ix_users_last_interaction", "last_interaction"),
        Index("ix_users_is_admin", "is_admin"),
        Index("ix_users_is_whitelisted", "is_whitelisted"),
    )


class Dialog(Base):
    __tablename__ = "dialogs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    chat_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    messages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    user: Mapped["User"] = relationship("User", back_populates="dialogs")


class MessageReaction(Base):
    __tablename__ = "message_reactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    reaction: Mapped[str] = mapped_column(String(8), nullable=False)   # "like" | "dislike"
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    user_message: Mapped[str] = mapped_column(String, nullable=False, default="")
    bot_message: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("ix_reactions_user_id", "user_id"),
        Index("ix_reactions_reaction", "reaction"),
        Index("ix_reactions_model", "model"),
        Index("ix_reactions_created_at", "created_at"),
    )
