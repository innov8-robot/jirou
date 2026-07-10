"""Modèle ORM ``IssueDependency`` (EPIC-08, JIR-61).

Une dépendance relie deux tickets d'un même projet : l'issue ``from`` **bloque**
l'issue ``to`` (sémantique du type par défaut ``blocks``). Les deux extrémités
sont supprimées en cascade avec l'issue correspondante. L'unicité porte sur le
triplet ``(from_issue_id, to_issue_id, type)`` : impossible de créer deux fois la
même dépendance.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DependencyType
from app.models.issue import Issue


class IssueDependency(Base):
    """Dépendance orientée entre deux tickets (EPIC-08, JIR-61).

    ``from_issue`` bloque ``to_issue``. CASCADE des deux côtés : supprimer l'une
    des issues retire la dépendance.
    """

    __tablename__ = "issue_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "from_issue_id",
            "to_issue_id",
            "type",
            name="uq_issue_dependencies_from_to_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[DependencyType] = mapped_column(
        Enum(DependencyType, name="dependency_type", native_enum=False, length=20),
        default=DependencyType.BLOCKS,
        server_default=DependencyType.BLOCKS.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    from_issue: Mapped[Issue] = relationship("Issue", foreign_keys=[from_issue_id])
    to_issue: Mapped[Issue] = relationship("Issue", foreign_keys=[to_issue_id])

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return (
            f"<IssueDependency id={self.id} from={self.from_issue_id} "
            f"to={self.to_issue_id} type={self.type.value}>"
        )
