"""dialogs.title — заголовок чата

Revision ID: 0003_dialog_title
Revises: 0002_retention_reactions
Create Date: 2026-06-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_dialog_title"
down_revision: str | None = "0002_retention_reactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dialogs", sa.Column("title", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("dialogs", "title")
