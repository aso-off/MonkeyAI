"""timestamp-колонки → NOT NULL (выравнивание с моделями)

Revision ID: 0006_timestamps_not_null
Revises: 0005_dialog_pinned
Create Date: 2026-06-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_timestamps_not_null"
down_revision: str | None = "0005_dialog_pinned"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    ("dialogs", "start_time"),
    ("generated_images", "created_at"),
    ("reactions", "created_at"),
    ("users", "first_seen"),
    ("users", "last_interaction"),
)


def upgrade() -> None:
    for table, column in _COLUMNS:
        # подстраховка: старые строки без значения не дадут поставить NOT NULL
        op.execute(f"UPDATE {table} SET {column} = now() WHERE {column} IS NULL")
        op.alter_column(table, column, existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(table, column, existing_type=sa.DateTime(timezone=True), nullable=True)
