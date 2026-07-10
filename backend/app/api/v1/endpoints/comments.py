"""Endpoints des commentaires (EPIC-09, JIR-62/64).

Deux familles de routes :

- sous ``/api/v1/issues/{key}/comments`` (liste, création) — réutilisent les
  dépendances d'issue de ``endpoints.issues`` (membre / membre≠viewer) ;
- sous ``/api/v1/comments/{comment_id}`` (édition, suppression) — résolvent le
  commentaire par identifiant puis vérifient l'appartenance au projet et les
  droits (auteur / lead-admin projet / admin global).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.api.v1.endpoints.issues import (
    IssueContext,
    get_issue_context,
    require_issue_writer,
)
from app.core.database import get_db
from app.models.comment import Comment
from app.models.enums import ProjectRole, UserRole
from app.models.issue import Issue
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentRead, CommentUpdate
from app.services import comment as comment_service
from app.services.project import get_membership

router = APIRouter()
issue_router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

_COMMENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Commentaire introuvable."
)
_COMMENT_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Accès refusé : vous n'êtes pas membre de ce projet.",
)


# --------------------------------------------------------------------------- #
# Dépendance locale : résolution d'un commentaire par identifiant
# --------------------------------------------------------------------------- #
@dataclass
class CommentContext:
    """Contexte d'accès à un commentaire résolu par identifiant."""

    comment: Comment
    project: Project
    membership: ProjectMember | None
    current_user: User


def get_comment_context(
    comment_id: int, current_user: CurrentUser, db: DbSession
) -> CommentContext:
    """Résout le commentaire et exige que l'appelant soit membre du projet.

    - 404 si le commentaire est inconnu.
    - 403 si l'appelant n'est ni membre du projet ni admin global.
    """
    comment = comment_service.get_comment(db, comment_id)
    if comment is None:
        raise _COMMENT_NOT_FOUND
    issue = db.get(Issue, comment.issue_id)
    project = db.get(Project, issue.project_id)
    membership = get_membership(db, project.id, current_user.id)
    if membership is None and current_user.role != UserRole.ADMIN:
        raise _COMMENT_FORBIDDEN
    return CommentContext(
        comment=comment, project=project, membership=membership, current_user=current_user
    )


# --------------------------------------------------------------------------- #
# Routes rattachées à l'issue
# --------------------------------------------------------------------------- #
@issue_router.get(
    "/{key}/comments",
    response_model=list[CommentRead],
    summary="Lister les commentaires d'un ticket",
)
def list_comments(
    db: DbSession,
    ctx: Annotated[IssueContext, Depends(get_issue_context)],
) -> list[CommentRead]:
    """Fil chronologique des commentaires (plus ancien d'abord). Réservé aux membres."""
    comments = comment_service.list_comments(db, ctx.issue)
    return [CommentRead.model_validate(comment) for comment in comments]


@issue_router.post(
    "/{key}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un commentaire",
)
def create_comment(
    data: CommentCreate,
    db: DbSession,
    ctx: Annotated[IssueContext, Depends(require_issue_writer)],
) -> CommentRead:
    """Crée un commentaire. Interdit aux viewers (403).

    ``mention_user_ids`` déclenche une notification ``mention`` pour chaque
    utilisateur membre du projet (l'auteur et les non-membres sont ignorés).
    """
    comment = comment_service.create_comment(
        db,
        ctx.issue,
        ctx.project,
        ctx.current_user,
        data.body,
        data.mention_user_ids,
    )
    return CommentRead.model_validate(comment)


# --------------------------------------------------------------------------- #
# Routes rattachées au commentaire
# --------------------------------------------------------------------------- #
@router.patch(
    "/{comment_id}",
    response_model=CommentRead,
    summary="Modifier un commentaire",
)
def update_comment(
    data: CommentUpdate,
    db: DbSession,
    ctx: Annotated[CommentContext, Depends(get_comment_context)],
) -> CommentRead:
    """Modifie un commentaire. Réservé à son auteur ou à un admin global (403 sinon)."""
    user = ctx.current_user
    is_author = ctx.comment.author_id == user.id
    is_global_admin = user.role == UserRole.ADMIN
    if not (is_author or is_global_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Édition réservée à l'auteur ou à un admin global.",
        )
    comment = comment_service.update_comment(db, ctx.comment, data.body)
    return CommentRead.model_validate(comment)


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un commentaire",
)
def delete_comment(
    db: DbSession,
    ctx: Annotated[CommentContext, Depends(get_comment_context)],
) -> None:
    """Supprime un commentaire.

    Réservé à l'auteur, au lead/admin projet ou à un admin global (403 sinon).
    """
    user = ctx.current_user
    is_author = ctx.comment.author_id == user.id
    is_global_admin = user.role == UserRole.ADMIN
    is_lead = ctx.project.lead_id == user.id
    is_project_admin = ctx.membership is not None and ctx.membership.role == ProjectRole.ADMIN
    if not (is_author or is_global_admin or is_lead or is_project_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Suppression réservée à l'auteur, au lead/admin projet ou à un admin global.",
        )
    comment_service.delete_comment(db, ctx.comment)
