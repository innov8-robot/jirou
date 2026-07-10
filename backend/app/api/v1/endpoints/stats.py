"""Endpoint du tableau de bord projet (EPIC-10, JIR-71).

``GET /api/v1/projects/{project_id}/stats`` renvoie les répartitions et
l'avancement du sprint actif. Réservé aux membres du projet.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ProjectContext, get_project_membership
from app.core.database import get_db
from app.schemas.issue import IssueRead, MiniUser
from app.schemas.sprint import SprintRead
from app.schemas.stats import (
    ActiveSprintStats,
    AssigneeCount,
    ProjectStats,
    StatusCounts,
    TypeCounts,
)
from app.services import sprint as sprint_service
from app.services import stats as stats_service

project_router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@project_router.get(
    "/{project_id}/stats",
    response_model=ProjectStats,
    summary="Statistiques / tableau de bord d'un projet",
)
def get_project_stats(
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
) -> ProjectStats:
    """Répartition par statut/type/assigné, tickets récents et sprint actif."""
    data = stats_service.get_project_stats(db, ctx.project)

    active_sprint = None
    if data.active_sprint is not None:
        sprint_read = SprintRead.model_validate(data.active_sprint.sprint)
        sprint_read.issue_count = sprint_service.count_sprint_issues(
            db, data.active_sprint.sprint.id
        )
        active_sprint = ActiveSprintStats(
            sprint=sprint_read,
            done=data.active_sprint.done,
            total=data.active_sprint.total,
            points_done=data.active_sprint.points_done,
            points_total=data.active_sprint.points_total,
        )

    return ProjectStats(
        total=data.total,
        by_status=StatusCounts(**{status.value: count for status, count in data.by_status.items()}),
        by_type=TypeCounts(**{type_.value: count for type_, count in data.by_type.items()}),
        by_assignee=[
            AssigneeCount(
                user=MiniUser.model_validate(user) if user is not None else None,
                count=count,
            )
            for user, count in data.by_assignee
        ],
        recent=[IssueRead.model_validate(issue) for issue in data.recent],
        active_sprint=active_sprint,
    )
