"""Modèle ORM ``Notification`` (EPIC-09, JIR-67).

Une notification in-app destinée à ``user_id`` (le destinataire), déclenchée par
un ``actor`` (l'auteur du commentaire ou l'assignateur, nullable) et rattachée à
une issue (nullable). Le type distingue une mention d'une assignation. Supprimer
le destinataire retire ses notifications ; supprimer l'acteur les conserve
(``actor_id`` passe à ``NULL``) ; supprimer l'issue les retire en cascade.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import NotificationType
from app.models.issue import Issue
from app.models.user import User


class Notification(Base):
    """Notification in-app (EPIC-09, JIR-67)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Destinataire de la notification.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", native_enum=False, length=20),
        nullable=False,
    )
    # Auteur de l'action (mention/assignation), nullable.
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Issue concernée, nullable.
    issue_id: Mapped[int | None] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), nullable=True, index=True
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_id], lazy="joined")
    issue: Mapped[Issue | None] = relationship("Issue", foreign_keys=[issue_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<Notification id={self.id} user_id={self.user_id} type={self.type.value}>"
