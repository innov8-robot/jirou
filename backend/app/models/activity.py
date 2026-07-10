"""Modèle ORM ``ActivityLog`` (EPIC-10, JIR-69).

Journal d'audit d'une issue : chaque mutation significative (création, changement
de champ, commentaire) laisse une trace horodatée, attribuée à un acteur
(nullable). Supprimer l'issue ou le projet retire les entrées en cascade ;
supprimer l'acteur les conserve (``actor_id`` passe à ``NULL``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import User


class ActivityLog(Base):
    """Entrée d'activité sur une issue (EPIC-10, JIR-69)."""

    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Auteur de l'action, nullable (conservé si l'utilisateur est supprimé).
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Étiquette d'action : "created", "updated", "commented".
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # Champ concerné pour une action "updated" (ex. "status"), sinon NULL.
    field: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<ActivityLog id={self.id} issue_id={self.issue_id} action={self.action!r}>"
