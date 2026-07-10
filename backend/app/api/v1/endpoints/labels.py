"""Endpoints de gestion des labels (EPIC-05, JIR-31).

Deux familles de routes :

- sous ``/api/v1/projects/{project_id}/labels`` (liste, création) ;
- sous ``/api/v1/labels/{label_id}`` (mise à jour, suppression).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    CurrentUser,
    ProjectContext,
    get_project_membership,
    require_project_role,
)
from app.core.database import get_db
from app.models.enums import ProjectRole, UserRole
from app.models.issue import Label
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.issue import LabelCreate, LabelRead, LabelUpdate
from app.services import label as label_service
from app.services.issue import IssueServiceError
from app.services.project import get_membership

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

_ERROR_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "conflict": status.HTTP_409_CONFLICT,
    "validation": status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _raise_service_error(exc: IssueServiceError) -> None:
    raise HTTPException(
        status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=exc.message,
    )


_LABEL_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label introuvable.")
_LABEL_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Accès refusé : vous n'êtes pas membre de ce projet.",
)
_VIEWER_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Un viewer ne peut pas modifier les labels.",
)


@dataclass
class LabelContext:
    """Contexte d'accès à un label résolu par identifiant."""

    label: Label
    project: Project
    membership: ProjectMember | None
    current_user: User


def require_label_writer(label_id: int, current_user: CurrentUser, db: DbSession) -> LabelContext:
    """Résout un label par id et exige un membre non-viewer du projet.

    - 404 si le label est inconnu ; 403 si non membre ou viewer.
    """
    label = label_service.get_label(db, label_id)
    if label is None:
        raise _LABEL_NOT_FOUND
    project = db.get(Project, label.project_id)
    membership = get_membership(db, project.id, current_user.id)
    if membership is None and current_user.role != UserRole.ADMIN:
        raise _LABEL_FORBIDDEN
    if membership is not None and membership.role == ProjectRole.VIEWER:
        raise _VIEWER_FORBIDDEN
    return LabelContext(
        label=label, project=project, membership=membership, current_user=current_user
    )


# --------------------------------------------------------------------------- #
# Routes rattachées au projet
# --------------------------------------------------------------------------- #
project_router = APIRouter()


@project_router.get(
    "/{project_id}/labels",
    response_model=list[LabelRead],
    summary="Lister les labels d'un projet",
)
def list_labels(
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
) -> list[Label]:
    """Labels d'un projet. Réservé aux membres (403) ; 404 si projet inconnu."""
    return label_service.list_labels(db, ctx.project)


@project_router.post(
    "/{project_id}/labels",
    response_model=LabelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un label",
)
def create_label(
    data: LabelCreate,
    db: DbSession,
    ctx: Annotated[
        ProjectContext,
        Depends(require_project_role(ProjectRole.ADMIN, ProjectRole.MEMBER)),
    ],
) -> Label:
    """Crée un label. Interdit aux viewers (403), 409 si le nom est déjà pris."""
    try:
        return label_service.create_label(db, ctx.project, data)
    except IssueServiceError as exc:
        _raise_service_error(exc)


# --------------------------------------------------------------------------- #
# Routes rattachées au label
# --------------------------------------------------------------------------- #
@router.patch(
    "/{label_id}",
    response_model=LabelRead,
    summary="Modifier un label",
)
def update_label(
    data: LabelUpdate,
    db: DbSession,
    ctx: Annotated[LabelContext, Depends(require_label_writer)],
) -> Label:
    """Modifie un label (nom/couleur). Interdit aux viewers, 409 si nom déjà pris."""
    try:
        return label_service.update_label(db, ctx.label, data)
    except IssueServiceError as exc:
        _raise_service_error(exc)


@router.delete(
    "/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un label",
)
def delete_label(
    db: DbSession,
    ctx: Annotated[LabelContext, Depends(require_label_writer)],
) -> None:
    """Supprime un label. Interdit aux viewers (403), 404 si inconnu."""
    label_service.delete_label(db, ctx.label)
