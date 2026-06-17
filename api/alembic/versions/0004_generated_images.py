"""generated_images — галерея сгенерированных картинок

Revision ID: 0004_generated_images
Revises: 0003_dialog_title
Create Date: 2026-06-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_generated_images"
down_revision: str | None = "0003_dialog_title"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generated_images",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "dialog_id",
            sa.String(36),
            sa.ForeignKey("dialogs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("prompt", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_generated_images_user_id", "generated_images", ["user_id"])
    op.create_index("ix_generated_images_created_at", "generated_images", ["created_at"])


def downgrade() -> None:
    op.drop_table("generated_images")
