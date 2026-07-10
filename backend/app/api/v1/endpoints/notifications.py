"""Endpoints des notifications in-app (EPIC-09, JIR-67).

Toutes les routes sont relatives à l'utilisateur courant : chacun ne voit et ne
manipule que **ses** notifications. ``issue_key`` et ``project_id`` sont dérivés
de l'issue liée à la notification.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.notification import Notification
from app.schemas.issue import MiniUser
from app.schemas.notification import NotificationRead, ReadAllResult, UnreadCount
from app.services import notification as notification_service

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


def _serialize(notification: Notification) -> NotificationRead:
    """Sérialise une notification en ``NotificationRead`` (issue_key/project_id dérivés)."""
    issue = notification.issue
    return NotificationRead(
        id=notification.id,
        type=notification.type,
        message=notification.message,
        is_read=notification.is_read,
        created_at=notification.created_at,
        actor=MiniUser.model_validate(notification.actor) if notification.actor else None,
        issue_key=issue.key if issue is not None else None,
        project_id=issue.project_id if issue is not None else None,
    )


@router.get(
    "",
    response_model=list[NotificationRead],
    summary="Lister mes notifications",
)
def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[NotificationRead]:
    """Notifications de l'utilisateur courant, les plus récentes d'abord."""
    notifications = notification_service.list_notifications(
        db, current_user.id, unread_only=unread_only, limit=limit
    )
    return [_serialize(notification) for notification in notifications]


@router.get(
    "/unread-count",
    response_model=UnreadCount,
    summary="Compteur de notifications non lues",
)
def get_unread_count(db: DbSession, current_user: CurrentUser) -> UnreadCount:
    """Nombre de notifications non lues de l'utilisateur courant."""
    return UnreadCount(count=notification_service.unread_count(db, current_user.id))


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationRead,
    summary="Marquer une notification comme lue",
)
def mark_read(
    notification_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> NotificationRead:
    """Marque une notification comme lue. Réservé à son destinataire (404 sinon)."""
    notification = notification_service.get_notification(db, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification introuvable."
        )
    notification = notification_service.mark_read(db, notification)
    return _serialize(notification)


@router.post(
    "/read-all",
    response_model=ReadAllResult,
    summary="Tout marquer comme lu",
)
def mark_all_read(db: DbSession, current_user: CurrentUser) -> ReadAllResult:
    """Marque toutes les notifications non lues de l'utilisateur comme lues."""
    updated = notification_service.mark_all_read(db, current_user.id)
    return ReadAllResult(updated=updated)
