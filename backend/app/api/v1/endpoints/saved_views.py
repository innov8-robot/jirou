"""Endpoints des vues sauvegardées (EPIC-10, JIR-70).

Deux familles de routes :

- sous ``/api/v1/projects/{project_id}/views`` (liste, création) — réservées aux
  membres du projet ; chacun ne voit que **ses** vues ;
- sous ``/api/v1/views/{view_id}`` (suppression) — réservée au propriétaire.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, ProjectContext, get_project_membership
from app.core.database import get_db
from app.schemas.saved_view import SavedViewCreate, SavedViewRead
from app.services import saved_view as saved_view_service
from app.services.saved_view import SavedViewServiceError

router = APIRouter()
project_router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


# --------------------------------------------------------------------------- #
# Routes rattachées au projet
# --------------------------------------------------------------------------- #
@project_router.get(
    "/{project_id}/views",
    response_model=list[SavedViewRead],
    summary="Lister mes vues sauvegardées d'un projet",
)
def list_views(
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
) -> list[SavedViewRead]:
    """Vues sauvegardées de l'appelant pour ce projet. Réservé aux membres."""
    views = saved_view_service.list_views(db, ctx.current_user.id, ctx.project.id)
    return [SavedViewRead.model_validate(view) for view in views]


@project_router.post(
    "/{project_id}/views",
    response_model=SavedViewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une vue sauvegardée",
)
def create_view(
    data: SavedViewCreate,
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
) -> SavedViewRead:
    """Crée une vue pour l'appelant. 409 si le nom est déjà pris. Réservé aux membres."""
    try:
        view = saved_view_service.create_view(
            db,
            user_id=ctx.current_user.id,
            project_id=ctx.project.id,
            name=data.name,
            filters=data.filters,
        )
    except SavedViewServiceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    return SavedViewRead.model_validate(view)


# --------------------------------------------------------------------------- #
# Routes rattachées à la vue
# --------------------------------------------------------------------------- #
@router.delete(
    "/{view_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une vue sauvegardée",
)
def delete_view(
    view_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Supprime une vue. 404 si inconnue, 403 si elle appartient à un autre utilisateur."""
    view = saved_view_service.get_view(db, view_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vue introuvable.")
    if view.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Suppression réservée au propriétaire de la vue.",
        )
    saved_view_service.delete_view(db, view)
