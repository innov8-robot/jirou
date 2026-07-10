"""Modèle ORM ``Comment`` (EPIC-09, JIR-62/64).

Un commentaire est rattaché à une issue et à son auteur. Le corps (``body``)
est du texte riche (HTML fourni par le front, non interprété côté serveur). La
suppression de l'issue ou de l'auteur retire les commentaires en cascade.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import User


class Comment(Base):
    """Commentaire sur un ticket (EPIC-09, JIR-62)."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Contenu rich text (HTML fourni par le front, non interprété).
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    author: Mapped[User] = relationship("User", foreign_keys=[author_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<Comment id={self.id} issue_id={self.issue_id} author_id={self.author_id}>"
