"""Modèle ORM ``Document`` (documentation, pages Markdown).

Un ``Document`` est une page de documentation, soit rattachée à un projet, soit
**générale** (``project_id`` NULL, visible par tout utilisateur connecté). Son
``content`` est du Markdown stocké en texte brut : le backend ne fait aucun
rendu, celui-ci est effectué côté frontend. La suppression du projet retire ses
documents en cascade ; la suppression de l'auteur passe ``author_id`` à ``NULL``
(la page est conservée, sans auteur).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.project import Project
from app.models.user import User


class Document(Base):
    """Page de documentation Markdown (rattachée à un projet, ou générale)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL pour un document général (non rattaché à un projet).
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Contenu Markdown brut (peut être vide) ; le rendu est côté frontend.
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    author: Mapped[User | None] = relationship("User", foreign_keys=[author_id], lazy="joined")
    project: Mapped[Project | None] = relationship(
        "Project", foreign_keys=[project_id], lazy="joined"
    )

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<Document id={self.id} project_id={self.project_id} title={self.title!r}>"
