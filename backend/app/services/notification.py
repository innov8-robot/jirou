"""Logique métier des notifications in-app (EPIC-09, JIR-67).

Fournit un helper de création réutilisable (:func:`notify`) branché par les
services commentaire (mention) et issue (assignation), ainsi que les requêtes de
lecture et de marquage. Le helper **n'émet pas de commit** : il ajoute la
notification à la session pour que le commit du service appelant l'englobe
(effet de bord cohérent avec la transaction en cours).
"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.enums import NotificationType
from app.models.notification import Notification


def notify(
    db: Session,
    *,
    user_id: int,
    type: NotificationType,
    message: str,
    actor_id: int | None = None,
    issue_id: int | None = None,
) -> Notification:
    """Crée une notification et l'ajoute à la session (sans commit).

    Le commit est laissé au service appelant afin de conserver une transaction
    cohérente (la notification est un effet de bord de l'action déclenchante).
    """
    notification = Notification(
        user_id=user_id,
        type=type,
        message=message,
        actor_id=actor_id,
        issue_id=issue_id,
    )
    db.add(notification)
    return notification


def list_notifications(
    db: Session,
    user_id: int,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> list[Notification]:
    """Notifications de l'utilisateur, les plus récentes d'abord."""
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def unread_count(db: Session, user_id: int) -> int:
    """Nombre de notifications non lues de l'utilisateur."""
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
    )
    return int(db.execute(stmt).scalar_one())


def get_notification(db: Session, notification_id: int) -> Notification | None:
    """Retourne la notification portant cet identifiant, ou ``None``."""
    return db.get(Notification, notification_id)


def mark_read(db: Session, notification: Notification) -> Notification:
    """Marque une notification comme lue."""
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_read(db: Session, user_id: int) -> int:
    """Marque toutes les notifications non lues de l'utilisateur comme lues.

    Retourne le nombre de lignes mises à jour.
    """
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return int(result.rowcount or 0)
