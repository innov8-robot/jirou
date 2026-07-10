"""Schémas Pydantic v2 pour la gestion des utilisateurs (JIR-15).

Réutilise ``UserRead`` défini dans :mod:`app.schemas.auth` pour la sortie ;
ajoute les payloads de mise à jour de profil, de mot de passe et d'administration.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole


class UserProfileUpdate(BaseModel):
    """Mise à jour partielle du profil de l'utilisateur courant.

    Tous les champs sont optionnels : seuls ceux explicitement fournis sont
    modifiés. ``avatar_url`` peut être mis à ``null`` pour retirer l'avatar.
    """

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024)


class PasswordChange(BaseModel):
    """Changement de mot de passe de l'utilisateur courant."""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserAdminUpdate(BaseModel):
    """Modification d'un utilisateur par un administrateur (rôle / activation)."""

    model_config = ConfigDict(extra="forbid")

    role: UserRole | None = None
    is_active: bool | None = None
