"""Schémas Pydantic v2 pour les tickets et labels (EPIC-05).

Contrat d'entrée/sortie de l'API ``/issues`` et ``/labels`` — le frontend s'y
branche. Rappel conventions : payloads en ``snake_case``, erreurs
``{"detail": ...}``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (
    DependencyType,
    IssuePriority,
    IssueStatus,
    IssueType,
    UserRole,
)

# Couleur hexadécimale ``#RGB`` ou ``#RRGGBB``.
HEX_COLOR_PATTERN = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


# --------------------------------------------------------------------------- #
# Sous-schémas embarqués
# --------------------------------------------------------------------------- #
class MiniUser(BaseModel):
    """Représentation légère d'un utilisateur, embarquée dans un ticket."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    avatar_url: str | None = None
    role: UserRole


class MiniIssue(BaseModel):
    """Représentation légère d'un ticket, embarquée dans une dépendance (JIR-61)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    summary: str
    type: IssueType
    status: IssueStatus


class DependencyLink(BaseModel):
    """Dépendance vue depuis une issue donnée (embarquée dans ``IssueDetail``).

    - ``outward`` : l'issue courante **bloque** ``issue`` ;
    - ``inward``  : l'issue courante **est bloquée par** ``issue``.
    """

    id: int
    type: DependencyType
    direction: Literal["outward", "inward"]
    issue: MiniIssue


class LabelRead(BaseModel):
    """Représentation d'un label renvoyée par l'API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str
    project_id: int


# --------------------------------------------------------------------------- #
# Labels — entrée
# --------------------------------------------------------------------------- #
class LabelCreate(BaseModel):
    """Payload de création d'un label (POST /projects/{id}/labels)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    color: str = Field(pattern=HEX_COLOR_PATTERN)


class LabelUpdate(BaseModel):
    """Mise à jour partielle d'un label (PATCH /labels/{id})."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=HEX_COLOR_PATTERN)


# --------------------------------------------------------------------------- #
# Issues — entrée
# --------------------------------------------------------------------------- #
class IssueCreate(BaseModel):
    """Payload de création d'un ticket (POST /projects/{id}/issues).

    ``status`` et ``reporter`` ne sont pas fournis : le statut vaut ``todo`` par
    défaut et le rapporteur est l'utilisateur courant.
    """

    model_config = ConfigDict(extra="forbid")

    type: IssueType
    summary: str = Field(min_length=1, max_length=500)
    description: str | None = None
    priority: IssuePriority = IssuePriority.MEDIUM
    story_points: int | None = Field(default=None, ge=0)
    assignee_id: int | None = None
    epic_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None
    label_ids: list[int] = Field(default_factory=list)


class IssueUpdate(BaseModel):
    """Mise à jour partielle d'un ticket (PATCH /issues/{key}).

    Tous les champs sont optionnels ; seuls ceux explicitement fournis
    (``exclude_unset``) sont modifiés. ``assignee_id``/``epic_id`` peuvent être
    mis à ``null`` pour détacher.
    """

    model_config = ConfigDict(extra="forbid")

    type: IssueType | None = None
    summary: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: IssueStatus | None = None
    priority: IssuePriority | None = None
    story_points: int | None = Field(default=None, ge=0)
    assignee_id: int | None = None
    epic_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None
    position: float | None = None
    label_ids: list[int] | None = None


# --------------------------------------------------------------------------- #
# Issues — sortie
# --------------------------------------------------------------------------- #
class IssueRead(BaseModel):
    """Représentation d'un ticket renvoyée par l'API (sans description)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    project_id: int
    type: IssueType
    summary: str
    status: IssueStatus
    priority: IssuePriority
    story_points: int | None = None
    assignee_id: int | None = None
    reporter_id: int
    epic_id: int | None = None
    sprint_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None
    position: float
    created_at: datetime
    updated_at: datetime
    labels: list[LabelRead] = Field(default_factory=list)
    assignee: MiniUser | None = None
    reporter: MiniUser


class IssueProgress(BaseModel):
    """Progression d'un epic : nombre d'enfants ``done`` sur le total."""

    done: int
    total: int


# --------------------------------------------------------------------------- #
# Board Kanban (EPIC-06, JIR-40)
# --------------------------------------------------------------------------- #
class BoardColumn(BaseModel):
    """Une colonne du board : un statut et ses tickets ordonnés."""

    status: IssueStatus
    issues: list[IssueRead] = Field(default_factory=list)


class BoardRead(BaseModel):
    """Board d'un projet : les 4 colonnes de statut, toujours présentes et ordonnées.

    Ordre garanti : ``todo``, ``in_progress``, ``in_review``, ``done`` — même
    lorsqu'une colonne est vide. Dans chaque colonne, les issues sont triées par
    ``position`` croissant puis ``created_at``.
    """

    columns: list[BoardColumn]


class IssueMove(BaseModel):
    """Payload de déplacement/réordonnancement d'une issue (drag & drop).

    ``status`` est la colonne de destination ; ``position`` l'index 0-based cible
    dans cette colonne. ``position`` est clampé dans ``[0, len(colonne)]`` côté
    service, un index hors bornes ne provoque donc pas d'erreur.
    """

    model_config = ConfigDict(extra="forbid")

    status: IssueStatus
    position: int


class IssueDetail(IssueRead):
    """Détail d'un ticket : ``IssueRead`` + description, enfants et progression.

    ``children`` liste les issues rattachées si ``type=epic`` (sinon vide) ;
    ``progress`` agrège leur avancement pour un epic, sinon ``null``.
    """

    description: str | None = None
    children: list[IssueRead] = Field(default_factory=list)
    progress: IssueProgress | None = None
    dependencies: list[DependencyLink] = Field(default_factory=list)
