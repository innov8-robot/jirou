"""Schémas Pydantic v2 pour les sprints, le backlog et la vélocité (EPIC-07).

Contrat d'entrée/sortie de l'API ``/sprints`` et ``/projects/{id}/backlog`` — le
frontend s'y branche. Rappel conventions : payloads en ``snake_case``, erreurs
``{"detail": ...}``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SprintStatus
from app.schemas.issue import IssueRead


# --------------------------------------------------------------------------- #
# Sprints — entrée
# --------------------------------------------------------------------------- #
class SprintCreate(BaseModel):
    """Payload de création d'un sprint (POST /projects/{id}/sprints).

    Le sprint est créé au statut ``future``. Les dates se posent plutôt au
    démarrage (voir :class:`SprintStart`) mais restent éditables via PATCH.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    goal: str | None = None


class SprintUpdate(BaseModel):
    """Mise à jour partielle d'un sprint (PATCH /sprints/{id})."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class SprintStart(BaseModel):
    """Payload de démarrage d'un sprint (POST /sprints/{id}/start)."""

    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None


class SprintComplete(BaseModel):
    """Payload de clôture d'un sprint (POST /sprints/{id}/complete).

    ``move_incomplete_to`` décide du sort des issues non ``done`` :
    ``backlog`` (défaut) les détache, ``next`` les envoie vers le prochain
    sprint ``future`` du projet (par ``order``) s'il existe, sinon le backlog.
    """

    model_config = ConfigDict(extra="forbid")

    move_incomplete_to: Literal["backlog", "next"] = "backlog"


class BacklogMove(BaseModel):
    """Déplacement d'une issue entre backlog et sprints (PATCH /issues/{key}/backlog-move).

    ``sprint_id`` cible un sprint (même projet) ou ``null`` pour le backlog.
    ``position`` est l'index 0-based dans le bucket cible (clampé côté service).
    """

    model_config = ConfigDict(extra="forbid")

    sprint_id: int | None = None
    position: int = Field(ge=0)


# --------------------------------------------------------------------------- #
# Sprints — sortie
# --------------------------------------------------------------------------- #
class SprintRead(BaseModel):
    """Représentation d'un sprint renvoyée par l'API.

    ``issue_count`` = nombre d'issues actuellement rattachées.
    ``committed_points`` / ``completed_points`` sont les snapshots figés à la
    clôture (0 tant que le sprint n'est pas ``completed``).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    goal: str | None = None
    status: SprintStatus
    start_date: date | None = None
    end_date: date | None = None
    order: float
    completed_at: datetime | None = None
    committed_points: int
    completed_points: int
    issue_count: int = 0


class SprintCompleteResult(BaseModel):
    """Récapitulatif renvoyé à la clôture d'un sprint (JIR-52)."""

    sprint: SprintRead
    completed_points: int
    committed_points: int
    done_count: int
    not_done_count: int
    # "backlog", "next" ou "sprint:{id}" (destination effective des non-done).
    moved_to: str


# --------------------------------------------------------------------------- #
# Backlog (JIR-49)
# --------------------------------------------------------------------------- #
class BacklogBucket(BaseModel):
    """Un sprint et ses issues dans la vue backlog, avec la somme des points."""

    sprint: SprintRead
    issues: list[IssueRead] = Field(default_factory=list)
    points: int


class BacklogList(BaseModel):
    """Le backlog produit (issues sans sprint) et la somme des points."""

    issues: list[IssueRead] = Field(default_factory=list)
    points: int


class BacklogRead(BaseModel):
    """Vue backlog complète : le backlog produit + les sprints future/active."""

    backlog: BacklogList
    sprints: list[BacklogBucket] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Vélocité / reporting (JIR-53, JIR-54)
# --------------------------------------------------------------------------- #
class VelocityPoint(BaseModel):
    """Point de vélocité pour un sprint clôturé (points engagés vs complétés)."""

    sprint_id: int
    name: str
    committed_points: int
    completed_points: int
