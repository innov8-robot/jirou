"""Endpoints de gestion des utilisateurs (JIR-15).

Profil personnel (``/users/me``) et administration des comptes
(``/users`` et ``/users/{user_id}``, réservés aux administrateurs).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_role
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import UserRead
from app.schemas.issue import IssueRead
from app.schemas.user import PasswordChange, UserAdminUpdate, UserProfileUpdate
from app.services import issue as issue_service
from app.services.user import (
    admin_update_user,
    change_password,
    get_user_by_id,
    list_users,
    update_profile,
)

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


# --------------------------------------------------------------------------- #
# Profil personnel
# --------------------------------------------------------------------------- #
@router.patch(
    "/me",
    response_model=UserRead,
    summary="Mettre à jour son profil",
)
def update_me(data: UserProfileUpdate, current_user: CurrentUser, db: DbSession) -> User:
    """Met à jour partiellement le profil de l'utilisateur courant (nom, avatar)."""
    return update_profile(db, current_user, data)


@router.get(
    "/me/issues",
    response_model=list[IssueRead],
    summary="Mes tickets (tous projets confondus)",
)
def list_my_issues(current_user: CurrentUser, db: DbSession) -> list[IssueRead]:
    """Tickets assignés à l'utilisateur courant, triés par mise à jour décroissante.

    Couvre tous les projets où l'utilisateur est membre (JIR-72).
    """
    issues = issue_service.list_assigned_to_user(db, current_user)
    return [IssueRead.model_validate(issue) for issue in issues]


@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Changer son mot de passe",
)
def change_my_password(data: PasswordChange, current_user: CurrentUser, db: DbSession) -> None:
    """Change le mot de passe courant. 400 si ``current_password`` est incorrect."""
    if not change_password(db, current_user, data.current_password, data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect.",
        )


# --------------------------------------------------------------------------- #
# Administration des utilisateurs (admin uniquement)
# --------------------------------------------------------------------------- #
@router.get(
    "",
    response_model=list[UserRead],
    summary="Lister les utilisateurs (admin)",
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def list_all_users(
    db: DbSession,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[User]:
    """Liste paginée de tous les utilisateurs. Réservé aux administrateurs (403 sinon)."""
    return list_users(db, skip=skip, limit=limit)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Modifier un utilisateur (admin)",
)
def admin_update(
    user_id: int,
    data: UserAdminUpdate,
    db: DbSession,
    admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> User:
    """Modifie le rôle et/ou l'état d'activation d'un utilisateur (admin uniquement).

    - 404 si l'utilisateur est introuvable.
    - 400 (garde-fou) si l'admin tente de se retirer son propre rôle admin ou
      de se désactiver lui-même.
    """
    target = get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    if target.id == admin.id:
        if data.role is not None and data.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous ne pouvez pas retirer votre propre rôle administrateur.",
            )
        if data.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous ne pouvez pas désactiver votre propre compte.",
            )

    return admin_update_user(db, target, data)
