"""Peuple une base de démonstration cohérente pour Jirou (EPIC-10, JIR-74).

Usage ::

    python -m scripts.seed_demo
    # ou
    python scripts/seed_demo.py

Crée un jeu de données de démo : quelques utilisateurs, un projet ``DEMO`` avec
ses labels, un backlog varié (epics + enfants, statuts/priorités/assignations
diverses, quelques dates), deux sprints (dont un **actif** peuplé) — de quoi
illustrer board, backlog, sprint, timeline et tableaux de bord.

Le script est **idempotent** : si le projet ``DEMO`` existe déjà, il ne recrée
rien (les utilisateurs manquants sont toutefois recréés au besoin). Il s'appuie
sur les services applicatifs existants pour rester cohérent avec l'API.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.enums import (
    IssuePriority,
    IssueStatus,
    IssueType,
    ProjectRole,
    UserRole,
)
from app.models.project import Project
from app.models.user import User
from app.schemas.issue import IssueCreate, IssueUpdate, LabelCreate
from app.schemas.project import ProjectCreate
from app.schemas.sprint import SprintCreate
from app.services import issue as issue_service
from app.services import label as label_service
from app.services import project as project_service
from app.services import sprint as sprint_service
from app.services.user import get_user_by_email

DEMO_PROJECT_KEY = "DEMO"
DEMO_PASSWORD = "demo_password123"  # noqa: S105 - valeur de dev par défaut

# Utilisateurs de démo : (email, nom complet). Le premier devient lead/admin.
DEMO_USERS: list[tuple[str, str]] = [
    ("demo.lead@jirou.app", "Alice Martin"),
    ("demo.dev@jirou.app", "Bob Dupont"),
    ("demo.qa@jirou.app", "Carol Nguyen"),
]

# Labels de démo : (nom, couleur).
DEMO_LABELS: list[tuple[str, str]] = [
    ("backend", "#0ea5e9"),
    ("frontend", "#f59e0b"),
    ("urgent", "#ef4444"),
    ("tech-debt", "#8b5cf6"),
]


def _get_or_create_user(db: Session, email: str, full_name: str) -> User:
    """Retourne l'utilisateur de démo, en le créant (rôle ``member``) au besoin."""
    user = get_user_by_email(db, email)
    if user is not None:
        return user
    user = User(
        email=email,
        hashed_password=hash_password(DEMO_PASSWORD),
        full_name=full_name,
        role=UserRole.MEMBER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_demo_project(db: Session) -> Project | None:
    """Retourne le projet ``DEMO`` s'il existe déjà, sinon ``None``."""
    return db.execute(select(Project).where(Project.key == DEMO_PROJECT_KEY)).scalar_one_or_none()


def seed_demo(db: Session) -> tuple[Project, str]:
    """Crée (ou retrouve) le jeu de démo. Retourne ``(project, action)``.

    ``action`` vaut ``"created"`` lors du premier seed, ``"skipped"`` si le
    projet ``DEMO`` existait déjà (idempotence).
    """
    users = [_get_or_create_user(db, email, name) for email, name in DEMO_USERS]
    lead, dev, qa = users

    existing = _get_demo_project(db)
    if existing is not None:
        return existing, "skipped"

    # --- projet + membres -------------------------------------------------- #
    project = project_service.create_project(
        db,
        ProjectCreate(
            name="Projet Démo Jirou",
            key=DEMO_PROJECT_KEY,
            description="Projet de démonstration peuplé automatiquement.",
            color="#6366f1",
        ),
        lead,
    )
    project_service.add_member(db, project, dev.email, ProjectRole.MEMBER)
    project_service.add_member(db, project, qa.email, ProjectRole.VIEWER)

    # --- labels ------------------------------------------------------------ #
    labels = {
        name: label_service.create_label(db, project, LabelCreate(name=name, color=color))
        for name, color in DEMO_LABELS
    }

    # --- sprints ----------------------------------------------------------- #
    sprint_active = sprint_service.create_sprint(
        db, project, SprintCreate(name="Sprint 1", goal="Fondations de l'authentification")
    )
    sprint_future = sprint_service.create_sprint(
        db, project, SprintCreate(name="Sprint 2", goal="Board & filtres avancés")
    )
    today = date.today()
    sprint_service.start_sprint(
        db,
        sprint_active,
        start_date=today - timedelta(days=3),
        end_date=today + timedelta(days=11),
    )

    # --- epics ------------------------------------------------------------- #
    def _create(
        *,
        type_: IssueType,
        summary: str,
        priority: IssuePriority = IssuePriority.MEDIUM,
        assignee: User | None = None,
        points: int | None = None,
        epic_id: int | None = None,
        label_names: list[str] | None = None,
        start: date | None = None,
        due: date | None = None,
    ):
        data = IssueCreate(
            type=type_,
            summary=summary,
            priority=priority,
            story_points=points,
            assignee_id=assignee.id if assignee is not None else None,
            epic_id=epic_id,
            start_date=start,
            due_date=due,
            label_ids=[labels[name].id for name in (label_names or [])],
        )
        return issue_service.create_issue(db, project, data, lead)

    epic_auth = _create(
        type_=IssueType.EPIC,
        summary="Authentification & comptes",
        priority=IssuePriority.HIGH,
        start=today - timedelta(days=5),
        due=today + timedelta(days=20),
    )
    epic_board = _create(
        type_=IssueType.EPIC,
        summary="Tableau Kanban",
        start=today,
        due=today + timedelta(days=40),
    )

    # --- enfants + statuts + affectation aux sprints ----------------------- #
    # (type, résumé, priorité, assigné, points, epic, labels, statut cible, sprint cible)
    plan = [
        (
            IssueType.STORY,
            "Écran de connexion",
            IssuePriority.HIGH,
            dev,
            5,
            epic_auth,
            ["frontend"],
            IssueStatus.DONE,
            sprint_active,
        ),
        (
            IssueType.TASK,
            "Endpoint refresh token",
            IssuePriority.MEDIUM,
            dev,
            3,
            epic_auth,
            ["backend"],
            IssueStatus.IN_PROGRESS,
            sprint_active,
        ),
        (
            IssueType.BUG,
            "Fuite de session après logout",
            IssuePriority.HIGHEST,
            qa,
            2,
            epic_auth,
            ["backend", "urgent"],
            IssueStatus.IN_REVIEW,
            sprint_active,
        ),
        (
            IssueType.STORY,
            "Drag & drop des cartes",
            IssuePriority.HIGH,
            dev,
            8,
            epic_board,
            ["frontend"],
            IssueStatus.TODO,
            sprint_active,
        ),
        (
            IssueType.TASK,
            "Filtre par assigné",
            IssuePriority.LOW,
            qa,
            3,
            epic_board,
            ["frontend"],
            IssueStatus.TODO,
            sprint_future,
        ),
        (
            IssueType.STORY,
            "Colonnes configurables",
            IssuePriority.MEDIUM,
            None,
            5,
            epic_board,
            ["frontend", "tech-debt"],
            IssueStatus.TODO,
            None,
        ),
        (
            IssueType.BUG,
            "Crash au chargement du board",
            IssuePriority.HIGHEST,
            dev,
            1,
            None,
            ["urgent"],
            IssueStatus.IN_PROGRESS,
            sprint_active,
        ),
    ]

    for (
        type_,
        summary,
        priority,
        assignee,
        points,
        epic,
        label_names,
        target_status,
        sprint,
    ) in plan:
        issue = _create(
            type_=type_,
            summary=summary,
            priority=priority,
            assignee=assignee,
            points=points,
            epic_id=epic.id if epic is not None else None,
            label_names=label_names,
        )
        if sprint is not None:
            sprint_service.backlog_move(db, issue, sprint_id=sprint.id, position=0)
        if target_status != IssueStatus.TODO:
            issue_service.update_issue(db, issue, IssueUpdate(status=target_status), actor=lead)

    return project, "created"


def main() -> None:
    """Point d'entrée CLI : applique le seed de démo sur ``DATABASE_URL``."""
    db = SessionLocal()
    try:
        project, action = seed_demo(db)
    finally:
        db.close()

    if action == "created":
        print(
            f"[seed_demo] Projet de démo créé : {project.key} (id={project.id}). "
            f"Comptes de démo : {', '.join(email for email, _ in DEMO_USERS)} "
            f"(mot de passe : {DEMO_PASSWORD})."
        )
    else:
        print(
            f"[seed_demo] Le projet {project.key} (id={project.id}) existe déjà : "
            f"aucun changement (seed idempotent)."
        )


if __name__ == "__main__":
    main()
