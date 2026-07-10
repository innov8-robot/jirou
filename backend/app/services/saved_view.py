"""Logique métier des vues sauvegardées (EPIC-10, JIR-70).

CRUD des vues de filtres nommées, propres à un utilisateur et à un projet. Les
fonctions lèvent :class:`SavedViewServiceError` pour les erreurs métier (nom déjà
pris) ; la couche endpoint les traduit en codes HTTP. Les autorisations et
l'existence du projet sont gérées en amont.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.saved_view import SavedView


@dataclass
class SavedViewServiceError(Exception):
    """Erreur métier des vues sauvegardées, traduite en HTTP par l'endpoint.

    ``code`` est une étiquette stable (``conflict``) et ``message`` un texte
    lisible pour le champ ``detail``.
    """

    code: str
    message: str


def get_view(db: Session, view_id: int) -> SavedView | None:
    """Retourne la vue portant cet identifiant, ou ``None``."""
    return db.get(SavedView, view_id)


def list_views(db: Session, user_id: int, project_id: int) -> list[SavedView]:
    """Vues d'un utilisateur pour un projet donné, triées par création puis id."""
    stmt = (
        select(SavedView)
        .where(SavedView.user_id == user_id, SavedView.project_id == project_id)
        .order_by(SavedView.created_at, SavedView.id)
    )
    return list(db.execute(stmt).scalars().all())


def create_view(
    db: Session,
    *,
    user_id: int,
    project_id: int,
    name: str,
    filters: dict[str, Any],
) -> SavedView:
    """Crée une vue pour l'utilisateur. Lève ``conflict`` si le nom est déjà pris."""
    existing = db.execute(
        select(SavedView).where(
            SavedView.user_id == user_id,
            SavedView.project_id == project_id,
            SavedView.name == name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise SavedViewServiceError("conflict", "Une vue portant ce nom existe déjà.")

    view = SavedView(user_id=user_id, project_id=project_id, name=name, filters=filters)
    db.add(view)
    db.commit()
    db.refresh(view)
    return view


def delete_view(db: Session, view: SavedView) -> None:
    """Supprime définitivement une vue sauvegardée."""
    db.delete(view)
    db.commit()
