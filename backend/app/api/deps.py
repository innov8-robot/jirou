"""Dépendances FastAPI de sécurité : utilisateur courant & guard de rôles."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import TOKEN_TYPE_ACCESS, JWTError, decode_token
from app.models.enums import ProjectRole, UserRole
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.services.project import get_membership, get_project
from app.services.user import get_user_by_id

# tokenUrl : chemin (relatif à la racine) de l'endpoint de login, pour Swagger.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Identifiants invalides ou jeton expiré.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Décode le Bearer access token et renvoie l'utilisateur actif correspondant.

    401 si le jeton est absent, invalide, expiré ou du mauvais type ;
    401 également si l'utilisateur est inconnu ou désactivé.
    """
    try:
        payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
        subject = payload.get("sub")
        if subject is None:
            raise _CREDENTIALS_EXC
        user_id = int(subject)
    except (JWTError, ValueError) as exc:
        raise _CREDENTIALS_EXC from exc

    user = get_user_by_id(db, user_id)
    if user is None:
        raise _CREDENTIALS_EXC
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte désactivé.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(
    *roles: UserRole,
) -> Callable[[User], Coroutine[Any, Any, User] | User]:
    """Fabrique une dépendance qui exige que l'utilisateur ait l'un des ``roles``.

    Renvoie 403 si le rôle est insuffisant. Réutilisable sur n'importe quelle
    route ::

        @router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
        def admin_only() -> ...

    ou pour récupérer l'utilisateur ::

        def admin_only(user: User = Depends(require_role(UserRole.ADMIN))): ...
    """
    allowed = set(roles)

    def _checker(current_user: CurrentUser) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rôle insuffisant pour accéder à cette ressource.",
            )
        return current_user

    return _checker


# --------------------------------------------------------------------------- #
# Autorisations au niveau projet (EPIC-04)
# --------------------------------------------------------------------------- #
@dataclass
class ProjectContext:
    """Contexte d'accès à un projet résolu par les dépendances ci-dessous.

    - ``project``    : le projet demandé (toujours présent, sinon 404 en amont).
    - ``membership`` : l'appartenance de l'appelant au projet, ou ``None`` si
      l'accès est accordé via le rôle *global* ``admin`` sans être membre.
    - ``current_user`` : l'utilisateur authentifié.

    ``my_role`` expose le rôle projet de l'appelant (``None`` si non membre),
    utilisé pour sérialiser ``ProjectRead.my_role``.
    """

    project: Project
    membership: ProjectMember | None
    current_user: User

    @property
    def my_role(self) -> ProjectRole | None:
        return self.membership.role if self.membership is not None else None


_PROJECT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable."
)
_PROJECT_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Accès refusé : vous n'êtes pas membre de ce projet.",
)


def get_project_membership(
    project_id: int,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ProjectContext:
    """Exige que l'appelant soit **membre** du projet (n'importe quel rôle).

    L'admin *global* peut consulter n'importe quel projet même sans en être
    membre (``membership`` vaudra alors ``None``).

    - 404 si le projet n'existe pas.
    - 403 si l'appelant n'est ni membre ni admin global.
    """
    project = get_project(db, project_id)
    if project is None:
        raise _PROJECT_NOT_FOUND

    membership = get_membership(db, project_id, current_user.id)
    if membership is None and current_user.role != UserRole.ADMIN:
        raise _PROJECT_FORBIDDEN
    return ProjectContext(project=project, membership=membership, current_user=current_user)


def require_project_role(
    *roles: ProjectRole,
) -> Callable[..., ProjectContext]:
    """Fabrique une dépendance exigeant un rôle projet parmi ``roles``.

    Sont toujours autorisés, indépendamment de ``roles`` :

    - l'admin *global* (``UserRole.ADMIN``), même non membre ;
    - le *lead* du projet.

    - 404 si le projet est introuvable.
    - 403 si l'appelant n'a pas un rôle suffisant.
    """
    allowed = set(roles)

    def _checker(
        project_id: int,
        current_user: CurrentUser,
        db: Annotated[Session, Depends(get_db)],
    ) -> ProjectContext:
        project = get_project(db, project_id)
        if project is None:
            raise _PROJECT_NOT_FOUND

        membership = get_membership(db, project_id, current_user.id)

        allowed_access = (
            current_user.role == UserRole.ADMIN
            or project.lead_id == current_user.id
            or (membership is not None and membership.role in allowed)
        )
        if not allowed_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rôle projet insuffisant pour cette action.",
            )
        return ProjectContext(project=project, membership=membership, current_user=current_user)

    return _checker
