"""create issue_dependencies

Revision ID: a3f4c9d2e5b7
Revises: 812b101cdc96
Create Date: 2026-07-10 11:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f4c9d2e5b7"
down_revision: str | None = "812b101cdc96"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_FROM = "fk_issue_dependencies_from_issue_id_issues"
_FK_TO = "fk_issue_dependencies_to_issue_id_issues"
_UQ = "uq_issue_dependencies_from_to_type"


def upgrade() -> None:
    op.create_table(
        "issue_dependencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_issue_id", sa.Integer(), nullable=False),
        sa.Column("to_issue_id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "BLOCKS",
                name="dependency_type",
                native_enum=False,
                length=20,
            ),
            server_default="blocks",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["from_issue_id"], ["issues.id"], name=_FK_FROM, ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["to_issue_id"], ["issues.id"], name=_FK_TO, ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_issue_id", "to_issue_id", "type", name=_UQ),
    )
    op.create_index(
        op.f("ix_issue_dependencies_from_issue_id"),
        "issue_dependencies",
        ["from_issue_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_issue_dependencies_to_issue_id"),
        "issue_dependencies",
        ["to_issue_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_issue_dependencies_to_issue_id"), table_name="issue_dependencies")
    op.drop_index(op.f("ix_issue_dependencies_from_issue_id"), table_name="issue_dependencies")
    op.drop_table("issue_dependencies")
