"""task model

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-13 13:09:08.766006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import acf.db  # noqa: F401 - autogenerate writes custom column types as acf.db.<Type>

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing tasks keep running on the user's default model ("").
    op.add_column("tasks", sa.Column("model", sa.String(length=300), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_column("model")
