"""Modèles ORM du domaine VEILLE (base de connaissances R&D en arbre/graphe).

Trois entités, globales (non rattachées à un projet) :

- :class:`WatchNode` : un nœud de l'arbre de veille. ``parent_id`` référence un
  autre nœud (auto-FK) avec ``ON DELETE CASCADE`` : supprimer un nœud efface tout
  son sous-arbre. Chaque nœud porte une note Markdown, un statut optionnel et une
  position (``pos_x``/``pos_y``) pour l'affichage en graphe côté frontend.
- :class:`WatchMedia` : un média rattaché à un nœud — soit un fichier téléversé
  (image/vidéo) stocké sur disque, soit un lien externe (``url``, ex. YouTube).
- :class:`WatchComment` : un commentaire chronologique attaché à un nœud.

Supprimer le nœud retire ses médias et commentaires en cascade ; supprimer
l'utilisateur passe ``created_by_id``/``author_id`` à ``NULL`` (contenu conservé).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import WatchMediaKind, WatchNodeType, WatchStatus
from app.models.user import User


class WatchNode(Base):
    """Nœud de l'arbre de veille R&D (domaine VEILLE)."""

    __tablename__ = "watch_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Parent dans l'arbre (NULL pour une racine). CASCADE : supprime le sous-arbre.
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("watch_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Catégorie du nœud (nœuds « custom » côté frontend). Défaut : ``theme``.
    type: Mapped[WatchNodeType] = mapped_column(
        Enum(WatchNodeType, name="watch_node_type", native_enum=False, length=20),
        nullable=False,
        default=WatchNodeType.THEME,
        server_default=WatchNodeType.THEME.name,
    )
    # Note libre au format Markdown (rendu côté frontend).
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    status: Mapped[WatchStatus | None] = mapped_column(
        Enum(WatchStatus, name="watch_status", native_enum=False, length=20),
        nullable=True,
    )
    # Position dans le graphe (côté frontend).
    pos_x: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    pos_y: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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

    created_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[created_by_id], lazy="joined"
    )
    media: Mapped[list[WatchMedia]] = relationship(
        "WatchMedia",
        back_populates="node",
        cascade="all, delete-orphan",
        order_by="WatchMedia.created_at, WatchMedia.id",
    )

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<WatchNode id={self.id} parent_id={self.parent_id} title={self.title!r}>"


class WatchMedia(Base):
    """Média rattaché à un nœud de veille : fichier téléversé ou lien externe."""

    __tablename__ = "watch_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(
        ForeignKey("watch_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[WatchMediaKind] = mapped_column(
        Enum(WatchMediaKind, name="watch_media_kind", native_enum=False, length=20),
        nullable=False,
    )
    # Métadonnées d'un fichier téléversé (NULL pour un lien externe).
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # URL externe (NULL pour un fichier téléversé), ex. lien YouTube.
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    node: Mapped[WatchNode] = relationship("WatchNode", back_populates="media")
    created_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[created_by_id], lazy="joined"
    )

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<WatchMedia id={self.id} node_id={self.node_id} kind={self.kind.value}>"


class WatchComment(Base):
    """Commentaire chronologique sur un nœud de veille."""

    __tablename__ = "watch_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(
        ForeignKey("watch_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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

    author: Mapped[User | None] = relationship("User", foreign_keys=[author_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<WatchComment id={self.id} node_id={self.node_id} author_id={self.author_id}>"
