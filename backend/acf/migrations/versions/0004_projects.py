"""projects

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-10 09:12:41.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import acf.db  # noqa: F401 - autogenerate writes custom column types as acf.db.<Type>

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("folder", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_projects_user_id"), ["user_id"], unique=False)
    with op.batch_alter_table("chats", schema=None) as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_chats_project_id"), ["project_id"], unique=False)
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_tasks_project_id"), ["project_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tasks_project_id"))
        batch_op.drop_column("project_id")
    with op.batch_alter_table("chats", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chats_project_id"))
        batch_op.drop_column("project_id")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_projects_user_id"))
    op.drop_table("projects")
