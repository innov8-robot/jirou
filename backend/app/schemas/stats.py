"""Schémas Pydantic v2 pour le tableau de bord projet (EPIC-10, JIR-71).

Contrat de sortie de ``GET /projects/{id}/stats`` : répartitions (statut, type,
assigné), tickets récemment mis à jour et avancement du sprint actif.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.issue import IssueRead, MiniUser
from app.schemas.sprint import SprintRead


class StatusCounts(BaseModel):
    """Répartition des tickets par statut."""

    todo: int = 0
    in_progress: int = 0
    in_review: int = 0
    done: int = 0


class TypeCounts(BaseModel):
    """Répartition des tickets par type."""

    epic: int = 0
    story: int = 0
    task: int = 0
    bug: int = 0


class AssigneeCount(BaseModel):
    """Nombre de tickets pour un assigné donné (``user`` null = non assignés)."""

    user: MiniUser | None = None
    count: int


class ActiveSprintStats(BaseModel):
    """Avancement du sprint actif : issues et points terminés sur le total."""

    sprint: SprintRead
    done: int
    total: int
    points_done: int
    points_total: int


class ProjectStats(BaseModel):
    """Statistiques agrégées d'un projet pour le tableau de bord."""

    total: int
    by_status: StatusCounts
    by_type: TypeCounts
    by_assignee: list[AssigneeCount] = Field(default_factory=list)
    recent: list[IssueRead] = Field(default_factory=list)
    active_sprint: ActiveSprintStats | None = None
