"""Logique métier du journal d'activité (EPIC-10, JIR-69).

Fournit un helper de journalisation réutilisable (:func:`log`) branché par les
services issue (création/mise à jour) et commentaire, ainsi que la lecture
chronologique. Comme :mod:`app.services.notification`, le helper **n'émet pas de
commit** : il ajoute l'entrée à la session pour que le commit du service
appelant l'englobe (effet de bord cohérent avec la transaction en cours).
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity import ActivityLog
from app.models.issue import Issue


def stringify(value: object) -> str | None:
    """Convertit une valeur de champ en texte pour ``old_value``/``new_value``.

    ``None`` reste ``None`` ; les énumérations sont réduites à leur valeur.
    """
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def log(
    db: Session,
    *,
    issue_id: int,
    project_id: int,
    action: str,
    actor_id: int | None = None,
    field: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> ActivityLog:
    """Crée une entrée d'activité et l'ajoute à la session (sans commit).

    Le commit est laissé au service appelant afin de conserver une transaction
    cohérente (l'entrée est un effet de bord de l'action déclenchante).
    """
    entry = ActivityLog(
        issue_id=issue_id,
        project_id=project_id,
        actor_id=actor_id,
        action=action,
        field=field,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(entry)
    return entry


def list_activity(db: Session, issue: Issue) -> list[ActivityLog]:
    """Entrées d'activité d'une issue, les plus récentes d'abord."""
    stmt = (
        select(ActivityLog)
        .where(ActivityLog.issue_id == issue.id)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
    )
    return list(db.execute(stmt).scalars().all())
