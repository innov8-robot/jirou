"""create watch nodes media comments

Revision ID: e5f0b3c8d2a6
Revises: d4e9a2b7c1f5
Create Date: 2026-07-10 13:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f0b3c8d2a6"
down_revision: str | None = "d4e9a2b7c1f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- watch_nodes ------------------------------------------------------- #
    op.create_table(
        "watch_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "TO_TEST",
                "IN_PROGRESS",
                "PROMISING",
                "ABANDONED",
                name="watch_status",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("pos_x", sa.Float(), server_default="0", nullable=False),
        sa.Column("pos_y", sa.Float(), server_default="0", nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["watch_nodes.id"],
            name="fk_watch_nodes_parent_id_watch_nodes",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_watch_nodes_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_watch_nodes_parent_id"), "watch_nodes", ["parent_id"], unique=False)

    # --- watch_media ------------------------------------------------------- #
    op.create_table(
        "watch_media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "IMAGE",
                "VIDEO",
                "LINK",
                name="watch_media_kind",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("stored_path", sa.String(length=1024), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["watch_nodes.id"],
            name="fk_watch_media_node_id_watch_nodes",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_watch_media_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_watch_media_node_id"), "watch_media", ["node_id"], unique=False)

    # --- watch_comments ---------------------------------------------------- #
    op.create_table(
        "watch_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["watch_nodes.id"],
            name="fk_watch_comments_node_id_watch_nodes",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name="fk_watch_comments_author_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_watch_comments_node_id"), "watch_comments", ["node_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_watch_comments_node_id"), table_name="watch_comments")
    op.drop_table("watch_comments")

    op.drop_index(op.f("ix_watch_media_node_id"), table_name="watch_media")
    op.drop_table("watch_media")

    op.drop_index(op.f("ix_watch_nodes_parent_id"), table_name="watch_nodes")
    op.drop_table("watch_nodes")
