"""Endpoints de gestion des projets et de leurs membres (EPIC-04, JIR-24/25).

Toutes les routes sont montées sous ``/api/v1/projects`` (tag ``projects``).
Les autorisations projet sont centralisées dans ``app.api.deps``
(:func:`get_project_membership`, :func:`require_project_role`).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    CurrentUser,
    ProjectContext,
    get_project_membership,
    require_project_role,
    require_role,
)
from app.core.database import get_db
from app.models.enums import ProjectRole, UserRole
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectDetail,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectMemberUpdate,
    ProjectRead,
    ProjectUpdate,
)
from app.services import project as project_service
from app.services.project import ProjectServiceError

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

# Erreurs métier -> codes HTTP.
_ERROR_STATUS = {
    "conflict": status.HTTP_409_CONFLICT,
    "not_found": status.HTTP_404_NOT_FOUND,
    "last_admin": status.HTTP_400_BAD_REQUEST,
}


def _raise_service_error(exc: ProjectServiceError) -> None:
    raise HTTPException(
        status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=exc.message,
    )


# --------------------------------------------------------------------------- #
# Sérialisation
# --------------------------------------------------------------------------- #
def _to_read(project: Project, my_role: ProjectRole | None, member_count: int) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        key=project.key,
        description=project.description,
        color=project.color,
        lead_id=project.lead_id,
        is_archived=project.is_archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
        member_count=member_count,
        my_role=my_role,
    )


# --------------------------------------------------------------------------- #
# CRUD projets (JIR-24)
# --------------------------------------------------------------------------- #
@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un projet",
)
def create_project(
    data: ProjectCreate,
    db: DbSession,
    # admin ou member global autorisés ; viewer global interdit (403).
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.MEMBER))],
) -> ProjectRead:
    """Crée un projet. Le créateur devient lead et membre ``admin`` du projet.

    - 409 si la clé est déjà prise, 422 si la clé est invalide.
    """
    try:
        project = project_service.create_project(db, data, current_user)
    except ProjectServiceError as exc:
        _raise_service_error(exc)
    return _to_read(project, ProjectRole.ADMIN, member_count=1)


@router.get(
    "",
    response_model=list[ProjectRead],
    summary="Lister mes projets",
)
def list_projects(
    current_user: CurrentUser,
    db: DbSession,
    include_archived: Annotated[bool, Query()] = False,
) -> list[ProjectRead]:
    """Liste les projets dont l'appelant est membre (archivés exclus par défaut)."""
    projects = project_service.list_projects_for_user(
        db, current_user, include_archived=include_archived
    )
    result: list[ProjectRead] = []
    for project in projects:
        my_role = next((m.role for m in project.members if m.user_id == current_user.id), None)
        result.append(_to_read(project, my_role, member_count=len(project.members)))
    return result


@router.get(
    "/{project_id}",
    response_model=ProjectDetail,
    summary="Détail d'un projet",
)
def get_project_detail(
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
    db: DbSession,
) -> ProjectDetail:
    """Détail d'un projet (avec ses membres). Réservé aux membres (403) ; 404 sinon."""
    members = project_service.list_members(db, ctx.project.id)
    base = _to_read(ctx.project, ctx.my_role, member_count=len(members))
    return ProjectDetail(
        **base.model_dump(),
        members=[ProjectMemberRead.model_validate(m) for m in members],
    )


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    summary="Modifier un projet",
)
def update_project(
    data: ProjectUpdate,
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(require_project_role(ProjectRole.ADMIN))],
) -> ProjectRead:
    """Modifie un projet. Réservé au lead, à un admin projet ou à un admin global."""
    project = project_service.update_project(db, ctx.project, data)
    member_count = project_service.count_members(db, project.id)
    return _to_read(project, ctx.my_role, member_count=member_count)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver un projet (soft delete)",
)
def delete_project(
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(require_project_role(ProjectRole.ADMIN))],
) -> None:
    """Archivage logique : positionne ``is_archived = True``. Mêmes droits que PATCH."""
    project_service.archive_project(db, ctx.project)


# --------------------------------------------------------------------------- #
# Membres (JIR-25)
# --------------------------------------------------------------------------- #
@router.get(
    "/{project_id}/members",
    response_model=list[ProjectMemberRead],
    summary="Lister les membres d'un projet",
)
def list_members(
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
    db: DbSession,
) -> list[ProjectMember]:
    """Membres d'un projet. Réservé aux membres (403) ; 404 si projet inconnu."""
    return project_service.list_members(db, ctx.project.id)


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un membre par email",
)
def add_member(
    data: ProjectMemberCreate,
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(require_project_role(ProjectRole.ADMIN))],
) -> ProjectMember:
    """Ajoute un membre (par email). Réservé au lead/admin projet.

    - 404 si l'email est inconnu, 409 si déjà membre.
    """
    try:
        return project_service.add_member(db, ctx.project, data.email, data.role)
    except ProjectServiceError as exc:
        _raise_service_error(exc)


@router.patch(
    "/{project_id}/members/{user_id}",
    response_model=ProjectMemberRead,
    summary="Changer le rôle d'un membre",
)
def update_member(
    user_id: int,
    data: ProjectMemberUpdate,
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(require_project_role(ProjectRole.ADMIN))],
) -> ProjectMember:
    """Change le rôle projet d'un membre. Réservé au lead/admin projet.

    - 404 si le membre est introuvable.
    - 400 (garde-fou) si l'on rétrograde le lead ou le dernier admin projet.
    """
    try:
        return project_service.update_member_role(db, ctx.project, user_id, data.role)
    except ProjectServiceError as exc:
        _raise_service_error(exc)


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un membre",
)
def remove_member(
    user_id: int,
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(require_project_role(ProjectRole.ADMIN))],
) -> None:
    """Retire un membre du projet. Réservé au lead/admin projet.

    - 404 si le membre est introuvable.
    - 400 (garde-fou) si l'on retire le lead ou le dernier admin projet.
    """
    try:
        project_service.remove_member(db, ctx.project, user_id)
    except ProjectServiceError as exc:
        _raise_service_error(exc)
