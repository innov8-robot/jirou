"""documents project_id nullable

Revision ID: d4e9a2b7c1f5
Revises: c3d8f1a2b6e4
Create Date: 2026-07-10 13:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e9a2b7c1f5"
down_revision: str | None = "c3d8f1a2b6e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Un document général n'est rattaché à aucun projet : ``project_id`` NULL.
    op.alter_column("documents", "project_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("documents", "project_id", existing_type=sa.Integer(), nullable=False)
