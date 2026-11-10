"""sub-agent sessions

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-10 05:43:05.004720
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import acf.db  # noqa: F401 - autogenerate writes custom column types as acf.db.<Type>

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chats", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_chats_parent_id"), ["parent_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("chats", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chats_parent_id"))
        batch_op.drop_column("parent_id")
