"""Modèle ORM ``Attachment`` (EPIC-09, JIR-65).

Une pièce jointe référence un fichier stocké sur disque (sous le dossier
``uploads``) rattaché à une issue et à l'utilisateur qui l'a téléversé. Seules
les **métadonnées** sont persistées en base ; le contenu binaire vit sur le
volume. Supprimer l'issue ou l'auteur retire la ligne en cascade (le fichier
disque est nettoyé par la couche service).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import User


class Attachment(Base):
    """Pièce jointe d'un ticket (EPIC-09, JIR-65)."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nom d'origine du fichier (tel que fourni par le client).
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Chemin relatif sur le volume ``uploads`` (ex. "12/ab34_photo.png").
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    # Taille en octets.
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    uploaded_by: Mapped[User] = relationship("User", foreign_keys=[uploaded_by_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<Attachment id={self.id} issue_id={self.issue_id} filename={self.filename!r}>"
