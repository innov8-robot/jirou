"""Logique métier du tableau de bord projet (EPIC-10, JIR-71).

Agrège les répartitions (statut, type, assigné), les tickets récemment mis à
jour et l'avancement du sprint actif. Les comptages utilisent des ``GROUP BY``
pour rester efficaces ; les tickets récents sont eager-loadés (pas de N+1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.enums import IssueStatus, IssueType
from app.models.issue import Issue
from app.models.project import Project
from app.models.sprint import Sprint
from app.models.user import User
from app.services import sprint as sprint_service

RECENT_LIMIT = 5


@dataclass
class ActiveSprintData:
    """Avancement brut du sprint actif."""

    sprint: Sprint
    done: int
    total: int
    points_done: int
    points_total: int


@dataclass
class ProjectStatsData:
    """Statistiques brutes d'un projet, sérialisées par la couche endpoint."""

    total: int
    by_status: dict[IssueStatus, int]
    by_type: dict[IssueType, int]
    by_assignee: list[tuple[User | None, int]]
    recent: list[Issue] = field(default_factory=list)
    active_sprint: ActiveSprintData | None = None


def get_project_stats(db: Session, project: Project) -> ProjectStatsData:
    """Construit les statistiques agrégées d'un projet."""
    project_id = project.id

    total = int(
        db.execute(
            select(func.count()).select_from(Issue).where(Issue.project_id == project_id)
        ).scalar_one()
    )

    by_status = dict.fromkeys(IssueStatus, 0)
    for status, count in db.execute(
        select(Issue.status, func.count())
        .where(Issue.project_id == project_id)
        .group_by(Issue.status)
    ).all():
        by_status[status] = int(count)

    by_type = dict.fromkeys(IssueType, 0)
    for type_, count in db.execute(
        select(Issue.type, func.count()).where(Issue.project_id == project_id).group_by(Issue.type)
    ).all():
        by_type[type_] = int(count)

    # Répartition par assigné (bucket "non assigné" inclus), du plus chargé au moins.
    assignee_rows = db.execute(
        select(Issue.assignee_id, func.count())
        .where(Issue.project_id == project_id)
        .group_by(Issue.assignee_id)
    ).all()
    users_by_id = {
        user.id: user
        for user in db.execute(
            select(User).where(User.id.in_([aid for aid, _ in assignee_rows if aid is not None]))
        )
        .scalars()
        .all()
    }
    by_assignee = sorted(
        (
            (users_by_id.get(aid) if aid is not None else None, int(count))
            for aid, count in assignee_rows
        ),
        key=lambda item: (-item[1], item[0].id if item[0] is not None else 0),
    )

    recent_stmt = (
        select(Issue)
        .where(Issue.project_id == project_id)
        .options(
            selectinload(Issue.labels),
            joinedload(Issue.assignee),
            joinedload(Issue.reporter),
        )
        .order_by(Issue.updated_at.desc(), Issue.id.desc())
        .limit(RECENT_LIMIT)
    )
    recent = list(db.execute(recent_stmt).unique().scalars().all())

    active_sprint = _active_sprint_stats(db, project_id)

    return ProjectStatsData(
        total=total,
        by_status=by_status,
        by_type=by_type,
        by_assignee=by_assignee,
        recent=recent,
        active_sprint=active_sprint,
    )


def _active_sprint_stats(db: Session, project_id: int) -> ActiveSprintData | None:
    """Avancement du sprint actif du projet, ou ``None`` s'il n'y en a pas."""
    sprint = sprint_service.get_active_sprint(db, project_id)
    if sprint is None:
        return None

    total, points_total = db.execute(
        select(func.count(), func.coalesce(func.sum(Issue.story_points), 0)).where(
            Issue.sprint_id == sprint.id
        )
    ).one()
    done, points_done = db.execute(
        select(func.count(), func.coalesce(func.sum(Issue.story_points), 0)).where(
            Issue.sprint_id == sprint.id, Issue.status == IssueStatus.DONE
        )
    ).one()

    return ActiveSprintData(
        sprint=sprint,
        done=int(done),
        total=int(total),
        points_done=int(points_done),
        points_total=int(points_total),
    )
