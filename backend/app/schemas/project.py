"""Schémas Pydantic v2 pour les projets et leurs membres (EPIC-04).

Contrat d'entrée/sortie de l'API ``/projects`` — le frontend s'y branche.
Rappel conventions : payloads en ``snake_case``, erreurs ``{"detail": ...}``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import ProjectRole, UserRole

# Préfixe de clé : commence par une lettre, 2 à 5 caractères alphanumériques
# majuscules (ex. "JIR", "AB", "TEAM5").
KEY_PATTERN = r"^[A-Z][A-Z0-9]{1,4}$"


class ProjectCreate(BaseModel):
    """Payload de création d'un projet (POST /projects)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    key: str = Field(min_length=2, max_length=5, pattern=KEY_PATTERN)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, max_length=32)

    @field_validator("key", mode="before")
    @classmethod
    def _normalize_key(cls, value: object) -> object:
        """Normalise la clé en majuscules (et retire les espaces) avant validation."""
        if isinstance(value, str):
            return value.strip().upper()
        return value


class ProjectUpdate(BaseModel):
    """Mise à jour partielle d'un projet (PATCH /projects/{id}).

    La clé n'est volontairement pas modifiable (elle préfixe des clés de tickets).
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, max_length=32)
    is_archived: bool | None = None


class MemberUser(BaseModel):
    """Sous-ensemble public d'un utilisateur, embarqué dans un membre de projet."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    avatar_url: str | None = None
    role: UserRole


class ProjectMemberRead(BaseModel):
    """Représentation d'un membre de projet (avec l'utilisateur associé)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    role: ProjectRole
    joined_at: datetime
    user: MemberUser


class ProjectMemberCreate(BaseModel):
    """Ajout d'un membre par email (POST /projects/{id}/members)."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: ProjectRole = ProjectRole.MEMBER


class ProjectMemberUpdate(BaseModel):
    """Changement du rôle d'un membre (PATCH /projects/{id}/members/{user_id})."""

    model_config = ConfigDict(extra="forbid")

    role: ProjectRole


class ProjectRead(BaseModel):
    """Représentation d'un projet renvoyée par l'API.

    ``member_count`` et ``my_role`` sont calculés pour le contexte de l'appelant
    (gating UI). ``my_role`` vaut ``null`` si l'appelant n'est pas membre (cas
    d'un admin global consultant un projet dont il n'est pas membre).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key: str
    description: str | None = None
    color: str | None = None
    lead_id: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    member_count: int
    my_role: ProjectRole | None = None


class ProjectDetail(ProjectRead):
    """Détail d'un projet : ``ProjectRead`` enrichi de la liste des membres."""

    members: list[ProjectMemberRead] = Field(default_factory=list)
