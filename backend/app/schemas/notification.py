"""Schémas Pydantic v2 pour les notifications in-app (EPIC-09, JIR-67).

Contrat de sortie de l'API ``/notifications``. Rappel conventions : payloads en
``snake_case``, erreurs ``{"detail": ...}``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationType
from app.schemas.issue import MiniUser


class NotificationRead(BaseModel):
    """Représentation d'une notification renvoyée par l'API.

    ``issue_key`` et ``project_id`` sont dérivés de l'issue liée (``null`` si la
    notification n'est rattachée à aucune issue).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    message: str
    is_read: bool
    created_at: datetime
    actor: MiniUser | None = None
    issue_key: str | None = None
    project_id: int | None = None


class UnreadCount(BaseModel):
    """Nombre de notifications non lues de l'utilisateur courant."""

    count: int


class ReadAllResult(BaseModel):
    """Résultat de l'action « tout marquer comme lu »."""

    updated: int
