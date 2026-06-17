"""dialogs.pinned_at — закрепление диалогов

Revision ID: 0005_dialog_pinned
Revises: 0004_generated_images
Create Date: 2026-06-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_dialog_pinned"
down_revision: str | None = "0004_generated_images"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dialogs", sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("dialogs", "pinned_at")
