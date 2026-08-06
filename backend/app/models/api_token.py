"""Modèle ORM des jetons d'API personnels (accès machine à l'API Jirou).

Un :class:`ApiToken` est un identifiant porteur, rattaché à un utilisateur, qui
authentifie un client non interactif — typiquement le serveur MCP consommé par
Claude Code — sans lui confier le mot de passe du compte.

Propriétés de sécurité :

- **le secret n'est jamais stocké** : seule son empreinte SHA-256 l'est, et le
  jeton en clair n'est affiché qu'une fois, à la création ;
- **révocable** : ``revoked_at`` coupe l'accès immédiatement, sans toucher au
  mot de passe ni aux autres jetons ;
- **expiration optionnelle** : ``expires_at`` borne la durée de vie ;
- **traçable** : ``last_used_at`` permet de repérer un jeton dormant ou actif à
  tort (rafraîchi au plus une fois par minute, cf. le service).

Le jeton porte **exactement les droits de son propriétaire** : c'est une
délégation d'identité, pas une portée réduite. Supprimer l'utilisateur supprime
ses jetons (``ON DELETE CASCADE``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import User


class ApiToken(Base):
    """Jeton d'API personnel d'un utilisateur (accès machine)."""

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Libellé libre choisi par l'utilisateur (« Claude Code — portable »).
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Empreinte SHA-256 du jeton en clair (jamais le secret lui-même).
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # Début du jeton, conservé en clair pour l'identifier dans l'interface.
    prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    # Dernière utilisation (NULL si jamais utilisé).
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Expiration optionnelle (NULL = sans limite de durée).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Révocation manuelle (NULL = actif).
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover - aide au debug
        return f"<ApiToken id={self.id} user_id={self.user_id} name={self.name!r}>"
