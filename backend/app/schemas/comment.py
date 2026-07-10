"""Schémas Pydantic v2 pour les commentaires (EPIC-09, JIR-62/64).

Contrat d'entrée/sortie de l'API ``/issues/{key}/comments`` et
``/comments/{id}`` — le frontend s'y branche. Rappel conventions : payloads en
``snake_case``, erreurs ``{"detail": ...}``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.issue import MiniUser


# --------------------------------------------------------------------------- #
# Commentaires — entrée
# --------------------------------------------------------------------------- #
class CommentCreate(BaseModel):
    """Payload de création d'un commentaire (POST /issues/{key}/comments).

    ``mention_user_ids`` liste les utilisateurs mentionnés (``@``) : une
    notification est créée pour chacun qui est membre du projet (l'auteur et les
    non-membres sont ignorés).
    """

    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1)
    mention_user_ids: list[int] = Field(default_factory=list)


class CommentUpdate(BaseModel):
    """Mise à jour d'un commentaire (PATCH /comments/{id})."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Commentaires — sortie
# --------------------------------------------------------------------------- #
class CommentRead(BaseModel):
    """Représentation d'un commentaire renvoyée par l'API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    author: MiniUser
    body: str
    created_at: datetime
    updated_at: datetime
