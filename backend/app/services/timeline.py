"""Logique métier de la timeline / roadmap (EPIC-08, JIR-56).

Assemble, pour un projet, la liste de ses epics (avec dates, enfants rattachés et
progression) et les dépendances epic↔epic — de quoi tracer une vue Gantt côté
front. Les requêtes sont eager-loadées pour éviter les N+1.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.dependency import IssueDependency
from app.models.enums import IssueStatus, IssueType
from app.models.issue import Issue
from app.models.project import Project


@dataclass
class TimelineEpicData:
    """Données brutes d'un epic de la timeline (avant sérialisation)."""

    epic: Issue
    children: list[Issue]
    done: int
    total: int


@dataclass
class TimelineData:
    """Données brutes de la timeline d'un projet (avant sérialisation)."""

    epics: list[TimelineEpicData]
    dependencies: list[tuple[str, str]]


def build_timeline(db: Session, project: Project) -> TimelineData:
    """Construit les données de timeline d'un projet (JIR-56).

    - ``epics`` : toutes les issues ``type=epic`` du projet, triées par
      ``start_date`` (NULLS LAST) puis ``created_at``. Chaque epic est renvoyé
      même sans dates.
    - ``children`` : issues rattachées à l'epic (``epic_id``), triées par
      ``start_date`` (NULLS LAST) puis ``created_at``.
    - progression : ``done`` = enfants ``status=done`` ; ``total`` = nb enfants.
    - ``dependencies`` : dépendances (couples de clés) dont **les deux
      extrémités** sont des epics de ce projet.
    """
    eager = (
        selectinload(Issue.labels),
        joinedload(Issue.assignee),
        joinedload(Issue.reporter),
    )

    epics = list(
        db.execute(
            select(Issue)
            .where(Issue.project_id == project.id, Issue.type == IssueType.EPIC)
            .options(*eager)
            .order_by(Issue.start_date.is_(None), Issue.start_date, Issue.created_at, Issue.id)
        )
        .unique()
        .scalars()
        .all()
    )

    # Tous les enfants du projet en une requête, regroupés par epic_id (pas de N+1).
    children = list(
        db.execute(
            select(Issue)
            .where(Issue.project_id == project.id, Issue.epic_id.is_not(None))
            .options(*eager)
            .order_by(Issue.start_date.is_(None), Issue.start_date, Issue.created_at, Issue.id)
        )
        .unique()
        .scalars()
        .all()
    )
    children_by_epic: dict[int, list[Issue]] = {}
    for child in children:
        children_by_epic.setdefault(child.epic_id, []).append(child)

    epic_data: list[TimelineEpicData] = []
    for epic in epics:
        kids = children_by_epic.get(epic.id, [])
        done = sum(1 for k in kids if k.status == IssueStatus.DONE)
        epic_data.append(TimelineEpicData(epic=epic, children=kids, done=done, total=len(kids)))

    # Dépendances dont les DEUX extrémités sont des epics de ce projet. On mappe
    # les ids déjà chargés vers leurs clés (aucune requête supplémentaire sur les
    # issues) et on ne lit que les couples d'ids des dépendances.
    key_by_id = {epic.id: epic.key for epic in epics}
    dependencies: list[tuple[str, str]] = []
    if key_by_id:
        rows = db.execute(
            select(IssueDependency.from_issue_id, IssueDependency.to_issue_id)
            .where(
                IssueDependency.from_issue_id.in_(key_by_id),
                IssueDependency.to_issue_id.in_(key_by_id),
            )
            .order_by(IssueDependency.id)
        ).all()
        dependencies = [(key_by_id[from_id], key_by_id[to_id]) for from_id, to_id in rows]

    return TimelineData(epics=epic_data, dependencies=dependencies)
