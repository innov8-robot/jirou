"""Endpoints de gestion des sprints, du backlog et de la vélocité (EPIC-07).

Deux familles de routes :

- sous ``/api/v1/projects/{project_id}/...`` (liste/création de sprints,
  backlog, vélocité) — réutilisent les dépendances projet de ``app.api.deps`` ;
- sous ``/api/v1/sprints/{sprint_id}/...`` (édition, démarrage, clôture,
  suppression) — résolvent le sprint par id puis vérifient l'appartenance au
  projet via des dépendances locales.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    CurrentUser,
    ProjectContext,
    get_project_membership,
    require_project_role,
)
from app.core.database import get_db
from app.models.enums import IssueType, ProjectRole, UserRole
from app.models.project import Project, ProjectMember
from app.models.sprint import Sprint
from app.models.user import User
from app.schemas.issue import IssueRead
from app.schemas.sprint import (
    BacklogBucket,
    BacklogList,
    BacklogRead,
    SprintComplete,
    SprintCompleteResult,
    SprintCreate,
    SprintRead,
    SprintStart,
    SprintUpdate,
    VelocityPoint,
)
from app.services import sprint as sprint_service
from app.services.project import get_membership
from app.services.sprint import SprintServiceError

router = APIRouter()
project_router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

# Erreurs métier -> codes HTTP.
_ERROR_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "conflict": status.HTTP_409_CONFLICT,
    "validation": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "bad_request": status.HTTP_400_BAD_REQUEST,
}


def _raise_service_error(exc: SprintServiceError) -> None:
    raise HTTPException(
        status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=exc.message,
    )


_SPRINT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Sprint introuvable."
)
_SPRINT_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Accès refusé : vous n'êtes pas membre de ce projet.",
)
_VIEWER_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Un viewer ne peut pas modifier les sprints.",
)


# --------------------------------------------------------------------------- #
# Sérialisation
# --------------------------------------------------------------------------- #
def _serialize_sprint(db: Session, sprint: Sprint) -> SprintRead:
    """Sérialise un sprint en ``SprintRead`` en calculant ``issue_count``."""
    data = SprintRead.model_validate(sprint)
    data.issue_count = sprint_service.count_sprint_issues(db, sprint.id)
    return data


# --------------------------------------------------------------------------- #
# Dépendances locales : résolution d'un sprint par id
# --------------------------------------------------------------------------- #
@dataclass
class SprintContext:
    """Contexte d'accès à un sprint résolu par id."""

    sprint: Sprint
    project: Project
    membership: ProjectMember | None
    current_user: User


def get_sprint_context(sprint_id: int, current_user: CurrentUser, db: DbSession) -> SprintContext:
    """Résout le sprint par id et exige que l'appelant soit membre du projet.

    - 404 si le sprint est inconnu.
    - 403 si l'appelant n'est ni membre du projet ni admin global.
    """
    sprint = sprint_service.get_sprint_by_id(db, sprint_id)
    if sprint is None:
        raise _SPRINT_NOT_FOUND
    project = db.get(Project, sprint.project_id)
    membership = get_membership(db, project.id, current_user.id)
    if membership is None and current_user.role != UserRole.ADMIN:
        raise _SPRINT_FORBIDDEN
    return SprintContext(
        sprint=sprint, project=project, membership=membership, current_user=current_user
    )


def require_sprint_writer(
    ctx: Annotated[SprintContext, Depends(get_sprint_context)],
) -> SprintContext:
    """Comme :func:`get_sprint_context` mais interdit les viewers (403)."""
    if ctx.membership is not None and ctx.membership.role == ProjectRole.VIEWER:
        raise _VIEWER_FORBIDDEN
    return ctx


# --------------------------------------------------------------------------- #
# Routes rattachées au projet
# --------------------------------------------------------------------------- #
@project_router.get(
    "/{project_id}/sprints",
    response_model=list[SprintRead],
    summary="Lister les sprints d'un projet",
)
def list_sprints(
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
    include_completed: Annotated[bool, Query()] = False,
) -> list[SprintRead]:
    """Liste des sprints (triés par ordre). Réservé aux membres.

    Par défaut, exclut les sprints ``completed`` (``?include_completed=true``
    pour les inclure).
    """
    sprints = sprint_service.list_sprints(db, ctx.project, include_completed=include_completed)
    return [_serialize_sprint(db, sprint) for sprint in sprints]


@project_router.post(
    "/{project_id}/sprints",
    response_model=SprintRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un sprint",
)
def create_sprint(
    data: SprintCreate,
    db: DbSession,
    ctx: Annotated[
        ProjectContext,
        Depends(require_project_role(ProjectRole.ADMIN, ProjectRole.MEMBER)),
    ],
) -> SprintRead:
    """Crée un sprint (statut ``future``). Interdit aux viewers (403), 404 si projet inconnu."""
    sprint = sprint_service.create_sprint(db, ctx.project, data)
    return _serialize_sprint(db, sprint)


@project_router.get(
    "/{project_id}/backlog",
    response_model=BacklogRead,
    summary="Vue backlog d'un projet",
)
def get_backlog(
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
    assignee_id: Annotated[int | None, Query()] = None,
    type: Annotated[IssueType | None, Query()] = None,
    label_id: Annotated[int | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> BacklogRead:
    """Backlog produit (issues sans sprint) + sprints future/active avec leurs issues.

    Réservé aux membres. Filtres optionnels appliqués aux issues.
    """
    data = sprint_service.get_backlog(
        db,
        ctx.project,
        assignee_id=assignee_id,
        type=type,
        label_id=label_id,
        search=search,
    )
    return BacklogRead(
        backlog=BacklogList(
            issues=[IssueRead.model_validate(i) for i in data.backlog_issues],
            points=data.backlog_points,
        ),
        sprints=[
            BacklogBucket(
                sprint=_serialize_sprint(db, sprint),
                issues=[IssueRead.model_validate(i) for i in issues],
                points=points,
            )
            for sprint, issues, points in data.sprints
        ],
    )


@project_router.get(
    "/{project_id}/velocity",
    response_model=list[VelocityPoint],
    summary="Vélocité d'un projet",
)
def get_velocity(
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
) -> list[VelocityPoint]:
    """Points engagés vs complétés pour chaque sprint clôturé (par ``completed_at``)."""
    sprints = sprint_service.get_velocity(db, ctx.project)
    return [
        VelocityPoint(
            sprint_id=sprint.id,
            name=sprint.name,
            committed_points=sprint.committed_points,
            completed_points=sprint.completed_points,
        )
        for sprint in sprints
    ]


# --------------------------------------------------------------------------- #
# Routes rattachées à l'identifiant du sprint
# --------------------------------------------------------------------------- #
@router.patch(
    "/{sprint_id}",
    response_model=SprintRead,
    summary="Mettre à jour un sprint",
)
def update_sprint(
    data: SprintUpdate,
    db: DbSession,
    ctx: Annotated[SprintContext, Depends(require_sprint_writer)],
) -> SprintRead:
    """Mise à jour partielle d'un sprint (nom, objectif, dates). Interdit aux viewers."""
    sprint = sprint_service.update_sprint(db, ctx.sprint, data)
    return _serialize_sprint(db, sprint)


@router.post(
    "/{sprint_id}/start",
    response_model=SprintRead,
    summary="Démarrer un sprint",
)
def start_sprint(
    data: SprintStart,
    db: DbSession,
    ctx: Annotated[SprintContext, Depends(require_sprint_writer)],
) -> SprintRead:
    """Passe le sprint à ``active``. 409 si un sprint est déjà actif dans le projet."""
    changes = data.model_dump(exclude_unset=True)
    kwargs: dict[str, object] = {}
    if "start_date" in changes:
        kwargs["start_date"] = changes["start_date"]
    if "end_date" in changes:
        kwargs["end_date"] = changes["end_date"]
    try:
        sprint = sprint_service.start_sprint(db, ctx.sprint, **kwargs)
    except SprintServiceError as exc:
        _raise_service_error(exc)
    return _serialize_sprint(db, sprint)


@router.post(
    "/{sprint_id}/complete",
    response_model=SprintCompleteResult,
    summary="Clôturer un sprint",
)
def complete_sprint(
    data: SprintComplete,
    db: DbSession,
    ctx: Annotated[SprintContext, Depends(require_sprint_writer)],
) -> SprintCompleteResult:
    """Passe le sprint à ``completed`` et fige les snapshots de vélocité.

    400 si le sprint n'est pas actif. Les issues non ``done`` partent au backlog
    ou vers le prochain sprint selon ``move_incomplete_to``.
    """
    try:
        result = sprint_service.complete_sprint(
            db, ctx.sprint, move_incomplete_to=data.move_incomplete_to
        )
    except SprintServiceError as exc:
        _raise_service_error(exc)
    return SprintCompleteResult(
        sprint=_serialize_sprint(db, result.sprint),
        completed_points=result.completed_points,
        committed_points=result.committed_points,
        done_count=result.done_count,
        not_done_count=result.not_done_count,
        moved_to=result.moved_to,
    )


@router.delete(
    "/{sprint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un sprint",
)
def delete_sprint(
    db: DbSession,
    ctx: Annotated[SprintContext, Depends(require_sprint_writer)],
) -> None:
    """Supprime un sprint ; ses issues repassent au backlog (``sprint_id=null``)."""
    sprint_service.delete_sprint(db, ctx.sprint)
