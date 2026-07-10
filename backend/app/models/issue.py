"""Modèles ORM ``Issue`` et ``Label`` + association N-N (EPIC-05, JIR-30/31).

L'``Issue`` est le cœur du produit : un ticket rattaché à un projet, doté d'une
clé ``PREFIXE-N`` (générée via ``Project.issue_counter``), d'un type, d'un
statut, d'une priorité, d'un rapporteur, d'un éventuel assigné, d'un éventuel
epic parent (self-FK) et d'un ensemble de labels propres au projet.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import IssuePriority, IssueStatus, IssueType
from app.models.user import User

# Table d'association N-N entre issues et labels. CASCADE des deux côtés :
# supprimer une issue ou un label retire les lignes de liaison correspondantes.
issue_labels = Table(
    "issue_labels",
    Base.metadata,
    Column(
        "issue_id",
        Integer,
        ForeignKey("issues.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "label_id",
        Integer,
        ForeignKey("labels.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Label(Base):
    """Label coloré propre à un projet (JIR-31). Unicité du nom par projet."""

    __tablename__ = "labels"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_labels_project_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    # Couleur d'affichage au format hexadécimal (ex. "#RRGGBB").
    color: Mapped[str] = mapped_column(String(32), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<Label id={self.id} name={self.name!r} project_id={self.project_id}>"


class Issue(Base):
    """Ticket applicatif (EPIC-05, JIR-30)."""

    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("key", name="uq_issues_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Clé lisible ``PREFIXE-N`` unique (ex. "JIR-42").
    key: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    type: Mapped[IssueType] = mapped_column(
        Enum(IssueType, name="issue_type", native_enum=False, length=20),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    # Description libre (HTML/markdown fourni par le front, non interprété).
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, name="issue_status", native_enum=False, length=20),
        default=IssueStatus.TODO,
        server_default=IssueStatus.TODO.value,
        nullable=False,
    )
    priority: Mapped[IssuePriority] = mapped_column(
        Enum(IssuePriority, name="issue_priority", native_enum=False, length=20),
        default=IssuePriority.MEDIUM,
        server_default=IssuePriority.MEDIUM.value,
        nullable=False,
    )
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Epic parent (self-FK). NULL pour les issues non rattachées.
    epic_id: Mapped[int | None] = mapped_column(
        ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Sprint de rattachement (EPIC-07). NULL = dans le backlog produit.
    sprint_id: Mapped[int | None] = mapped_column(
        ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True, index=True
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Position (ordre dans une colonne/liste). Float pour insertions intercalées.
    position: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    labels: Mapped[list[Label]] = relationship("Label", secondary=issue_labels, lazy="selectin")
    assignee: Mapped[User | None] = relationship("User", foreign_keys=[assignee_id], lazy="joined")
    reporter: Mapped[User] = relationship("User", foreign_keys=[reporter_id], lazy="joined")
    epic: Mapped[Issue | None] = relationship("Issue", remote_side=[id], foreign_keys=[epic_id])

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<Issue id={self.id} key={self.key!r} type={self.type.value}>"
