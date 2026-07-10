"""Modèle ORM ``SavedView`` (EPIC-10, JIR-70).

Une vue sauvegardée mémorise un jeu de filtres nommé, propre à un utilisateur et
(le plus souvent) à un projet. Les filtres sont stockés tels quels en JSON pour
rester agnostiques du constructeur de filtres côté front. Unicité du nom par
couple (utilisateur, projet).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SavedView(Base):
    """Vue de filtres sauvegardée par un utilisateur (EPIC-10, JIR-70)."""

    __tablename__ = "saved_views"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", "name", name="uq_saved_views_user_project_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Projet de rattachement ; NULL pour une vue transverse (tous projets).
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Critères de filtre libres (objet JSON fourni par le front).
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<SavedView id={self.id} user_id={self.user_id} name={self.name!r}>"
