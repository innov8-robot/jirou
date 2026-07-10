"""Endpoints des pièces jointes (EPIC-09, JIR-65).

Deux familles de routes :

- sous ``/api/v1/issues/{key}/attachments`` (liste, upload multipart) —
  réutilisent les dépendances d'issue de ``endpoints.issues`` ;
- sous ``/api/v1/attachments/{attachment_id}`` (téléchargement, suppression) —
  résolvent la pièce jointe par identifiant puis vérifient l'appartenance au
  projet et les droits.

Le fichier n'est jamais servi hors du dossier ``uploads`` : le chemin est
résolu et validé (anti-traversal) par le service avant tout accès disque.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.api.v1.endpoints.issues import (
    IssueContext,
    get_issue_context,
    require_issue_writer,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.attachment import Attachment
from app.models.enums import ProjectRole, UserRole
from app.models.issue import Issue
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.attachment import AttachmentRead
from app.schemas.issue import MiniUser
from app.services import attachment as attachment_service
from app.services.attachment import AttachmentServiceError
from app.services.project import get_membership

router = APIRouter()
issue_router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

_ATTACHMENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Pièce jointe introuvable."
)
_ATTACHMENT_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Accès refusé : vous n'êtes pas membre de ce projet.",
)

# Erreurs métier -> codes HTTP.
_ERROR_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "too_large": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    "unsupported_media_type": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
}


def _serialize(attachment: Attachment) -> AttachmentRead:
    """Sérialise une pièce jointe en ``AttachmentRead`` (avec ``download_url``)."""
    return AttachmentRead(
        id=attachment.id,
        issue_id=attachment.issue_id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size=attachment.size,
        uploaded_by=MiniUser.model_validate(attachment.uploaded_by),
        created_at=attachment.created_at,
        download_url=f"{settings.API_V1_PREFIX}/attachments/{attachment.id}/download",
    )


# --------------------------------------------------------------------------- #
# Dépendance locale : résolution d'une pièce jointe par identifiant
# --------------------------------------------------------------------------- #
@dataclass
class AttachmentContext:
    """Contexte d'accès à une pièce jointe résolue par identifiant."""

    attachment: Attachment
    project: Project
    membership: ProjectMember | None
    current_user: User


def get_attachment_context(
    attachment_id: int, current_user: CurrentUser, db: DbSession
) -> AttachmentContext:
    """Résout la pièce jointe et exige que l'appelant soit membre du projet.

    - 404 si la pièce jointe est inconnue.
    - 403 si l'appelant n'est ni membre du projet ni admin global.
    """
    attachment = attachment_service.get_attachment(db, attachment_id)
    if attachment is None:
        raise _ATTACHMENT_NOT_FOUND
    issue = db.get(Issue, attachment.issue_id)
    project = db.get(Project, issue.project_id)
    membership = get_membership(db, project.id, current_user.id)
    if membership is None and current_user.role != UserRole.ADMIN:
        raise _ATTACHMENT_FORBIDDEN
    return AttachmentContext(
        attachment=attachment,
        project=project,
        membership=membership,
        current_user=current_user,
    )


# --------------------------------------------------------------------------- #
# Routes rattachées à l'issue
# --------------------------------------------------------------------------- #
@issue_router.get(
    "/{key}/attachments",
    response_model=list[AttachmentRead],
    summary="Lister les pièces jointes d'un ticket",
)
def list_attachments(
    db: DbSession,
    ctx: Annotated[IssueContext, Depends(get_issue_context)],
) -> list[AttachmentRead]:
    """Pièces jointes d'un ticket (plus récentes d'abord). Réservé aux membres."""
    attachments = attachment_service.list_attachments(db, ctx.issue)
    return [_serialize(attachment) for attachment in attachments]


@issue_router.post(
    "/{key}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Téléverser une pièce jointe",
)
def upload_attachment(
    db: DbSession,
    ctx: Annotated[IssueContext, Depends(require_issue_writer)],
    file: Annotated[UploadFile, File()],
) -> AttachmentRead:
    """Téléverse un fichier (multipart ``file``). Interdit aux viewers (403).

    - 413 si le fichier dépasse la taille maximale configurée.
    """
    try:
        attachment = attachment_service.save_upload(
            db,
            ctx.issue,
            source=file.file,
            filename=file.filename,
            content_type=file.content_type,
            uploader=ctx.current_user,
        )
    except AttachmentServiceError as exc:
        raise HTTPException(
            status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=exc.message,
        ) from exc
    return _serialize(attachment)


# --------------------------------------------------------------------------- #
# Routes rattachées à la pièce jointe
# --------------------------------------------------------------------------- #
@router.get(
    "/{attachment_id}/download",
    summary="Télécharger une pièce jointe",
)
def download_attachment(
    ctx: Annotated[AttachmentContext, Depends(get_attachment_context)],
) -> FileResponse:
    """Renvoie le contenu binaire (Content-Disposition attachment). Réservé aux membres.

    - 404 si le fichier est absent du disque ou sort du dossier ``uploads``.
    """
    attachment = ctx.attachment
    try:
        path = attachment_service.resolve_path(attachment)
    except AttachmentServiceError as exc:
        raise HTTPException(
            status_code=_ERROR_STATUS.get(exc.code, status.HTTP_404_NOT_FOUND),
            detail=exc.message,
        ) from exc
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.filename,
    )


@router.delete(
    "/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une pièce jointe",
)
def delete_attachment(
    db: DbSession,
    ctx: Annotated[AttachmentContext, Depends(get_attachment_context)],
) -> None:
    """Supprime une pièce jointe.

    Réservé à l'uploader, au lead/admin projet ou à un admin global (403 sinon).
    """
    user = ctx.current_user
    is_uploader = ctx.attachment.uploaded_by_id == user.id
    is_global_admin = user.role == UserRole.ADMIN
    is_lead = ctx.project.lead_id == user.id
    is_project_admin = ctx.membership is not None and ctx.membership.role == ProjectRole.ADMIN
    if not (is_uploader or is_global_admin or is_lead or is_project_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Suppression réservée à l'uploader, au lead/admin projet ou à un admin global.",
        )
    attachment_service.delete_attachment(db, ctx.attachment)
