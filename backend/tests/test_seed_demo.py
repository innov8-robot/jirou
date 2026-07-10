"""Tests du SEED DE DÉMO (EPIC-10, JIR-74).

Vérifie que la fonction principale crée le projet de démo peuplé, et qu'une
seconde exécution est idempotente (aucun doublon).
"""

from __future__ import annotations

from scripts.seed_demo import DEMO_PROJECT_KEY, seed_demo
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import SprintStatus
from app.models.issue import Issue
from app.models.project import Project
from app.models.sprint import Sprint


def _count_demo_projects(db: Session) -> int:
    return int(
        db.execute(
            select(func.count()).select_from(Project).where(Project.key == DEMO_PROJECT_KEY)
        ).scalar_one()
    )


def test_seed_demo_creates_populated_project(db_session: Session) -> None:
    project, action = seed_demo(db_session)

    assert action == "created"
    assert project.key == DEMO_PROJECT_KEY

    issue_count = int(
        db_session.execute(
            select(func.count()).select_from(Issue).where(Issue.project_id == project.id)
        ).scalar_one()
    )
    assert issue_count > 0

    # Au moins un sprint actif peuplé (pour board/sprint/dashboard).
    active = db_session.execute(
        select(Sprint).where(Sprint.project_id == project.id, Sprint.status == SprintStatus.ACTIVE)
    ).scalar_one_or_none()
    assert active is not None
    in_sprint = int(
        db_session.execute(
            select(func.count()).select_from(Issue).where(Issue.sprint_id == active.id)
        ).scalar_one()
    )
    assert in_sprint > 0


def test_seed_demo_is_idempotent(db_session: Session) -> None:
    seed_demo(db_session)
    project, action = seed_demo(db_session)

    assert action == "skipped"
    assert project.key == DEMO_PROJECT_KEY
    assert _count_demo_projects(db_session) == 1
