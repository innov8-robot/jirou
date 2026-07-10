"""create activity_log and saved_views

Revision ID: e44e5dd72fa1
Revises: b7e2a1c4d9f0
Create Date: 2026-07-10 12:05:29.213881

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e44e5dd72fa1"
down_revision: str | None = "b7e2a1c4d9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- activity_logs ----------------------------------------------------- #
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("field", sa.String(length=50), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["issues.id"],
            name="fk_activity_logs_issue_id_issues",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_activity_logs_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_activity_logs_actor_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activity_logs_issue_id"), "activity_logs", ["issue_id"], unique=False)
    op.create_index(
        op.f("ix_activity_logs_project_id"), "activity_logs", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_activity_logs_actor_id"), "activity_logs", ["actor_id"], unique=False)

    # --- saved_views ------------------------------------------------------- #
    op.create_table(
        "saved_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_saved_views_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_saved_views_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "project_id", "name", name="uq_saved_views_user_project_name"
        ),
    )
    op.create_index(op.f("ix_saved_views_user_id"), "saved_views", ["user_id"], unique=False)
    op.create_index(op.f("ix_saved_views_project_id"), "saved_views", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_saved_views_project_id"), table_name="saved_views")
    op.drop_index(op.f("ix_saved_views_user_id"), table_name="saved_views")
    op.drop_table("saved_views")

    op.drop_index(op.f("ix_activity_logs_actor_id"), table_name="activity_logs")
    op.drop_index(op.f("ix_activity_logs_project_id"), table_name="activity_logs")
    op.drop_index(op.f("ix_activity_logs_issue_id"), table_name="activity_logs")
    op.drop_table("activity_logs")
