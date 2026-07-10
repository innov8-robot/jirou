"""Logique métier des commentaires (EPIC-09, JIR-62/64).

CRUD d'un fil de commentaires chronologique attaché à une issue. À la création,
les ``mention_user_ids`` déclenchent une notification ``mention`` pour chaque
utilisateur **membre du projet** (l'auteur lui-même et les non-membres sont
ignorés). Les autorisations (403) sont gérées en amont par la couche endpoint.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.comment import Comment
from app.models.enums import NotificationType
from app.models.issue import Issue
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.services import activity as activity_service
from app.services import notification as notification_service


def _is_project_member(db: Session, project: Project, user_id: int) -> bool:
    """Vrai si ``user_id`` est le lead ou un membre du projet."""
    if project.lead_id == user_id:
        return True
    membership = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    return membership is not None


def get_comment(db: Session, comment_id: int) -> Comment | None:
    """Retourne le commentaire portant cet identifiant, ou ``None``."""
    return db.get(Comment, comment_id)


def list_comments(db: Session, issue: Issue) -> list[Comment]:
    """Commentaires d'une issue, dans l'ordre chronologique (plus ancien d'abord)."""
    stmt = (
        select(Comment).where(Comment.issue_id == issue.id).order_by(Comment.created_at, Comment.id)
    )
    return list(db.execute(stmt).scalars().all())


def create_comment(
    db: Session,
    issue: Issue,
    project: Project,
    author: User,
    body: str,
    mention_user_ids: list[int],
) -> Comment:
    """Crée un commentaire et notifie les utilisateurs mentionnés (membres uniquement).

    Un seul commit englobe le commentaire et les notifications de mention.
    """
    comment = Comment(issue_id=issue.id, author_id=author.id, body=body)
    db.add(comment)

    # Journal d'activité (JIR-69) : trace la prise de parole sur l'issue.
    activity_service.log(
        db,
        issue_id=issue.id,
        project_id=project.id,
        action="commented",
        actor_id=author.id,
    )

    # Notifications de mention : dédoublonnées, hors auteur, membres du projet.
    for user_id in dict.fromkeys(mention_user_ids):
        if user_id == author.id:
            continue
        if not _is_project_member(db, project, user_id):
            continue
        notification_service.notify(
            db,
            user_id=user_id,
            type=NotificationType.MENTION,
            actor_id=author.id,
            issue_id=issue.id,
            message=f"{author.full_name} vous a mentionné sur {issue.key}",
        )

    db.commit()
    db.refresh(comment)
    return comment


def update_comment(db: Session, comment: Comment, body: str) -> Comment:
    """Met à jour le corps d'un commentaire."""
    comment.body = body
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, comment: Comment) -> None:
    """Supprime définitivement un commentaire."""
    db.delete(comment)
    db.commit()
