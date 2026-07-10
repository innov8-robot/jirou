"""add type to watch_nodes

Revision ID: f6a1c9d3e7b2
Revises: e5f0b3c8d2a6
Create Date: 2026-07-10 13:45:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a1c9d3e7b2"
down_revision: str | None = "e5f0b3c8d2a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Type non natif (VARCHAR + CHECK) — cohérent avec ``watch_status``/``watch_media_kind``.
# Les valeurs stockées sont les *noms* des membres de l'énumération.
_watch_node_type = sa.Enum(
    "THEME",
    "TECHNO",
    "SOLUTION",
    "RESOURCE",
    name="watch_node_type",
    native_enum=False,
    length=20,
)


def upgrade() -> None:
    # ``server_default`` applique ``theme`` (stocké ``THEME``) aux lignes existantes.
    op.add_column(
        "watch_nodes",
        sa.Column(
            "type",
            _watch_node_type,
            nullable=False,
            server_default="THEME",
        ),
    )
    # ``add_column`` n'émet pas la contrainte CHECK d'un Enum non natif : on l'ajoute
    # explicitement (cohérent avec ``watch_status``/``watch_media_kind``).
    op.create_check_constraint(
        "watch_node_type",
        "watch_nodes",
        "type IN ('THEME', 'TECHNO', 'SOLUTION', 'RESOURCE')",
    )


def downgrade() -> None:
    op.drop_constraint("watch_node_type", "watch_nodes", type_="check")
    op.drop_column("watch_nodes", "type")
