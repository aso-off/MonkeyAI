"""initial schema — users, user_states, user_statistics, dialogs, reactions

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("first_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(128), nullable=True),
        sa.Column("language", sa.String(8), nullable=False, server_default="system"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_whitelisted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_interaction", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_last_interaction", "users", ["last_interaction"])
    op.create_index("ix_users_is_admin", "users", ["is_admin"])
    op.create_index("ix_users_is_whitelisted", "users", ["is_whitelisted"])

    op.create_table(
        "user_states",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("current_dialog_id", sa.String(36), nullable=True),
        sa.Column("current_dialog_ids", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("current_chat_mode", sa.String(64), nullable=False, server_default="assistant"),
        sa.Column("mini_app_chat_mode", sa.String(64), nullable=False, server_default="mini_app_assistant"),
        sa.Column("mini_app_dialog_ids", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("current_model", sa.String(64), nullable=False, server_default=""),
        sa.Column("theme", sa.String(16), nullable=False, server_default="system"),
    )

    op.create_table(
        "user_statistics",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("n_used_tokens", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("n_generated_images", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_transcribed_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "dialogs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chat_mode", sa.String(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("messages", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )

    op.create_table(
        "reactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reaction", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64), nullable=False, server_default=""),
        sa.Column("user_message", sa.String(), nullable=False, server_default=""),
        sa.Column("bot_message", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reactions_user_id", "reactions", ["user_id"])
    op.create_index("ix_reactions_reaction", "reactions", ["reaction"])
    op.create_index("ix_reactions_model", "reactions", ["model"])
    op.create_index("ix_reactions_created_at", "reactions", ["created_at"])


def downgrade() -> None:
    op.drop_table("reactions")
    op.drop_table("dialogs")
    op.drop_table("user_statistics")
    op.drop_table("user_states")
    op.drop_table("users")
