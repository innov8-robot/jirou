"""Schémas Pydantic v2 pour la documentation de projet (pages Markdown).

Contrat d'entrée/sortie de l'API ``/projects/{id}/documents`` et
``/documents/{id}`` — le frontend s'y branche. Rappel conventions : payloads en
``snake_case``, erreurs ``{"detail": ...}``. Le ``content`` est du Markdown brut :
le backend ne fait aucun rendu.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.issue import MiniUser


# --------------------------------------------------------------------------- #
# Documents — entrée
# --------------------------------------------------------------------------- #
class DocumentCreate(BaseModel):
    """Payload de création d'un document (POST /projects/{id}/documents)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    content: str = ""


class DocumentUpdate(BaseModel):
    """Mise à jour partielle d'un document (PATCH /documents/{id}).

    Seuls les champs explicitement fournis (``exclude_unset``) sont modifiés.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None


# --------------------------------------------------------------------------- #
# Documents — sortie
# --------------------------------------------------------------------------- #
class DocumentSummary(BaseModel):
    """Résumé d'un document pour la liste (sans le contenu)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    author: MiniUser | None = None
    updated_at: datetime


class DocumentRead(BaseModel):
    """Représentation complète d'un document renvoyée par l'API (avec contenu).

    ``project_id`` vaut ``None`` pour un document général (non rattaché à un projet).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None = None
    title: str
    content: str
    author: MiniUser | None = None
    created_at: datetime
    updated_at: datetime


class ProjectMini(BaseModel):
    """Représentation légère d'un projet, embarquée dans un résumé de document."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key: str


class GlobalDocumentSummary(BaseModel):
    """Résumé d'un document pour la liste globale ``GET /documents``.

    ``project`` vaut ``None`` pour un document général (non rattaché à un projet).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: MiniUser | None = None
    updated_at: datetime
    project: ProjectMini | None = None
