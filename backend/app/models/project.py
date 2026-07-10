"""Modèles ORM ``Project`` et ``ProjectMember`` (EPIC-04, JIR-23).

Un ``Project`` est le conteneur de tous les tickets/sprints/boards. Sa ``key``
(préfixe unique de 2 à 5 majuscules) sert à générer les clés de tickets
``KEY-N`` via ``issue_counter`` (utilisé en EPIC-05).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ProjectRole
from app.models.user import User


class Project(Base):
    """Projet applicatif (JIR-23)."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Préfixe des clés de tickets, unique, 2-5 majuscules (ex. "JIR").
    key: Mapped[str] = mapped_column(String(5), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Couleur d'affichage (ex. code hexadécimal "#RRGGBB").
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    # Compteur de tickets émis : sert à numéroter les clés KEY-N (EPIC-05).
    issue_counter: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
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

    lead: Mapped[User] = relationship("User", foreign_keys=[lead_id], lazy="joined")
    members: Mapped[list[ProjectMember]] = relationship(
        "ProjectMember",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<Project id={self.id} key={self.key!r}>"


class ProjectMember(Base):
    """Appartenance d'un utilisateur à un projet, avec son rôle projet (JIR-23)."""

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[ProjectRole] = mapped_column(
        Enum(ProjectRole, name="project_role", native_enum=False, length=20),
        default=ProjectRole.MEMBER,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[Project] = relationship("Project", back_populates="members")
    user: Mapped[User] = relationship("User", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return (
            f"<ProjectMember project_id={self.project_id} "
            f"user_id={self.user_id} role={self.role.value}>"
        )
