"""retention: dialogs.last_activity + reactions references (mid/dialog_id)

Revision ID: 0002_retention_reactions
Revises: 0001_initial
Create Date: 2026-06-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_retention_reactions"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dialogs",
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE dialogs SET last_activity = COALESCE(start_time, now())")
    op.alter_column("dialogs", "last_activity", nullable=False)
    op.create_index("ix_dialogs_last_activity", "dialogs", ["last_activity"])

    op.drop_column("reactions", "user_message")
    op.drop_column("reactions", "bot_message")
    op.drop_index("ix_reactions_user_id", table_name="reactions")
    op.drop_column("reactions", "user_id")
    op.add_column("reactions", sa.Column("dialog_id", sa.String(36), nullable=True))
    op.add_column("reactions", sa.Column("mid", sa.String(32), nullable=True))
    op.create_foreign_key(
        "fk_reactions_dialog_id",
        "reactions",
        "dialogs",
        ["dialog_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_reactions_dialog_id", "reactions", type_="foreignkey")
    op.drop_column("reactions", "mid")
    op.drop_column("reactions", "dialog_id")
    op.add_column("reactions", sa.Column("user_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_reactions_user_id", "reactions", ["user_id"])
    op.add_column(
        "reactions",
        sa.Column("user_message", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "reactions",
        sa.Column("bot_message", sa.String(), nullable=False, server_default=""),
    )

    op.drop_index("ix_dialogs_last_activity", table_name="dialogs")
    op.drop_column("dialogs", "last_activity")
