"""Modèle ORM ``Sprint`` (EPIC-07, JIR-47).

Un ``Sprint`` regroupe des issues d'un projet sur une itération temporelle. Son
cycle de vie est ``future`` → ``active`` → ``completed`` (voir
:class:`app.models.enums.SprintStatus`). Un seul sprint ``active`` par projet à
la fois (garanti par la couche service, pas par une contrainte SQL).

À la clôture, ``committed_points`` et ``completed_points`` figent des snapshots
(somme des story points engagés / terminés) pour la vélocité historique, même si
les issues sont ensuite déplacées ou modifiées.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import SprintStatus


class Sprint(Base):
    """Sprint d'un projet (EPIC-07, JIR-47)."""

    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SprintStatus] = mapped_column(
        Enum(SprintStatus, name="sprint_status", native_enum=False, length=20),
        default=SprintStatus.FUTURE,
        server_default=SprintStatus.FUTURE.value,
        nullable=False,
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Ordre d'affichage dans le backlog. Float pour insertions intercalées.
    order: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Snapshots figés à la clôture pour la vélocité historique.
    committed_points: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    completed_points: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<Sprint id={self.id} name={self.name!r} status={self.status.value}>"
