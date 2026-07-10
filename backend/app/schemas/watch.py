"""Schémas Pydantic v2 du domaine VEILLE (base de connaissances R&D).

Contrat d'entrée/sortie de l'API ``/watch`` — le frontend s'y branche. Rappel
conventions : payloads en ``snake_case``, erreurs ``{"detail": ...}``.

- ``WatchNodeSummary`` : forme légère pour construire le graphe (tous les nœuds).
- ``WatchNodeRead``    : détail d'un nœud, avec ses médias.
- ``WatchMediaRead``   : média (upload ou lien externe) ; ``download_url`` pointe
  vers le téléchargement pour un upload, ``null`` pour un lien (l'URL externe est
  alors portée par ``url``).
- ``WatchCommentRead`` : commentaire d'un nœud.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import WatchMediaKind, WatchNodeType, WatchStatus
from app.schemas.issue import MiniUser


# --------------------------------------------------------------------------- #
# Nœuds — entrée
# --------------------------------------------------------------------------- #
class WatchNodeCreate(BaseModel):
    """Payload de création d'un nœud (POST /watch/nodes)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    parent_id: int | None = None
    type: WatchNodeType = WatchNodeType.THEME
    note: str = ""
    status: WatchStatus | None = None
    pos_x: float = 0
    pos_y: float = 0


class WatchNodeUpdate(BaseModel):
    """Mise à jour partielle d'un nœud (PATCH /watch/nodes/{id})."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    type: WatchNodeType | None = None
    note: str | None = None
    status: WatchStatus | None = None
    parent_id: int | None = None
    pos_x: float | None = None
    pos_y: float | None = None


class WatchMediaLinkCreate(BaseModel):
    """Payload d'ajout d'un lien externe (POST /watch/nodes/{id}/media/link)."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=255)


class WatchCommentCreate(BaseModel):
    """Payload de création d'un commentaire (POST /watch/nodes/{id}/comments)."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1)


class WatchCommentUpdate(BaseModel):
    """Mise à jour d'un commentaire (PATCH /watch/comments/{id})."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Médias — sortie
# --------------------------------------------------------------------------- #
class WatchMediaRead(BaseModel):
    """Représentation d'un média renvoyée par l'API.

    ``download_url`` pointe vers le téléchargement sécurisé pour un upload ;
    ``null`` pour un lien externe (dont l'URL est portée par ``url``).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    kind: WatchMediaKind
    filename: str | None
    content_type: str | None
    size: int | None
    url: str | None
    title: str | None
    download_url: str | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Nœuds — sortie
# --------------------------------------------------------------------------- #
class MediaPreview(BaseModel):
    """Aperçu du premier média d'un nœud (miniature de carte, sans ouvrir le nœud).

    ``download_url`` pointe vers le téléchargement pour un upload (image/vidéo),
    ``null`` pour un lien ; ``url`` porte l'URL externe pour un lien, ``null`` sinon.
    """

    media_id: int
    kind: str
    url: str | None
    download_url: str | None
    content_type: str | None


class WatchNodeSummary(BaseModel):
    """Forme légère d'un nœud pour construire le graphe (tous les nœuds)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    title: str
    type: WatchNodeType
    status: WatchStatus | None
    pos_x: float
    pos_y: float
    media_count: int
    comment_count: int
    preview: MediaPreview | None


class WatchNodeRead(BaseModel):
    """Détail d'un nœud, avec ses médias."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    title: str
    type: WatchNodeType
    note: str
    status: WatchStatus | None
    pos_x: float
    pos_y: float
    created_by: MiniUser | None
    created_at: datetime
    updated_at: datetime
    media: list[WatchMediaRead]


# --------------------------------------------------------------------------- #
# Commentaires — sortie
# --------------------------------------------------------------------------- #
class WatchCommentRead(BaseModel):
    """Représentation d'un commentaire renvoyée par l'API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    author: MiniUser | None
    body: str
    created_at: datetime
    updated_at: datetime
