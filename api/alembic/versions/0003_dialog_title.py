"""dialogs.title — заголовок чата

Revision ID: 0003_dialog_title
Revises: 0002_retention_reactions
Create Date: 2026-06-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_dialog_title"
down_revision: Union[str, None] = "0002_retention_reactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dialogs", sa.Column("title", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("dialogs", "title")
