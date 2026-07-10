"""Endpoints de la documentation (pages Markdown), de projet ou générales.

Trois familles de routes :

- sous ``/api/v1/projects/{project_id}/documents`` (liste, création) —
  réutilisent les dépendances projet de ``app.api.deps`` (membre / membre≠viewer) ;
- sous ``/api/v1/documents`` (liste globale, création d'un document général) —
  réservées à tout utilisateur connecté ;
- sous ``/api/v1/documents/{document_id}`` (détail, édition, suppression) —
  résolvent le document par identifiant puis vérifient les droits selon qu'il
  soit rattaché à un projet ou général.

Règles d'autorisation — documents de **projet** :

- ``GET`` (liste et détail) : tout **membre** du projet (ou admin global).
- ``POST`` : membre ``member``/``admin`` du projet (viewer interdit) ; le lead
  et l'admin global sont autorisés.
- ``PATCH`` : l'**auteur** du document, ou un membre ``member``/``admin`` (viewer
  interdit sauf s'il en est l'auteur), le lead ou l'admin global.
- ``DELETE`` : l'**auteur**, le **lead**, un **admin projet** ou un **admin global**.

Règles d'autorisation — documents **généraux** (``project_id`` NULL) :

- ``GET`` (détail) : tout utilisateur connecté.
- ``PATCH`` / ``DELETE`` : l'**auteur** ou un **admin global**.

La liste globale ``GET /documents`` renvoie les documents généraux plus ceux des
projets dont l'appelant est membre.

Le ``content`` est stocké tel quel (Markdown brut) : aucun rendu côté serveur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    CurrentUser,
    ProjectContext,
    get_project_membership,
    require_project_role,
)
from app.core.database import get_db
from app.models.document import Document
from app.models.enums import ProjectRole, UserRole
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.document import (
    DocumentCreate,
    DocumentRead,
    DocumentSummary,
    DocumentUpdate,
    GlobalDocumentSummary,
)
from app.services import document as document_service
from app.services import rag_hooks
from app.services.project import get_membership

router = APIRouter()
project_router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

_DOCUMENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable."
)
_DOCUMENT_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Accès refusé : vous n'êtes pas membre de ce projet.",
)


# --------------------------------------------------------------------------- #
# Dépendance locale : résolution d'un document par identifiant
# --------------------------------------------------------------------------- #
@dataclass
class DocumentContext:
    """Contexte d'accès à un document résolu par identifiant.

    ``project`` et ``membership`` valent ``None`` pour un document général.
    """

    document: Document
    project: Project | None
    membership: ProjectMember | None
    current_user: User

    @property
    def is_general(self) -> bool:
        """Vrai si le document n'est rattaché à aucun projet."""
        return self.document.project_id is None


def get_document_context(
    document_id: int, current_user: CurrentUser, db: DbSession
) -> DocumentContext:
    """Résout le document et vérifie le droit de **lecture** de l'appelant.

    - 404 si le document est inconnu.
    - Document **général** : lisible par tout utilisateur connecté.
    - Document de **projet** : 403 si l'appelant n'est ni membre ni admin global.
    """
    document = document_service.get_document(db, document_id)
    if document is None:
        raise _DOCUMENT_NOT_FOUND
    if document.project_id is None:
        return DocumentContext(
            document=document, project=None, membership=None, current_user=current_user
        )
    project = db.get(Project, document.project_id)
    membership = get_membership(db, project.id, current_user.id)
    if membership is None and current_user.role != UserRole.ADMIN:
        raise _DOCUMENT_FORBIDDEN
    return DocumentContext(
        document=document, project=project, membership=membership, current_user=current_user
    )


def _is_project_writer(ctx: DocumentContext) -> bool:
    """Vrai si l'appelant peut écrire dans le projet (membre≠viewer, lead, admin global)."""
    user = ctx.current_user
    if user.role == UserRole.ADMIN or (ctx.project is not None and ctx.project.lead_id == user.id):
        return True
    return ctx.membership is not None and ctx.membership.role in {
        ProjectRole.MEMBER,
        ProjectRole.ADMIN,
    }


# --------------------------------------------------------------------------- #
# Routes rattachées au projet
# --------------------------------------------------------------------------- #
@project_router.get(
    "/{project_id}/documents",
    response_model=list[DocumentSummary],
    summary="Lister les documents d'un projet",
)
def list_documents(
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
    db: DbSession,
) -> list[DocumentSummary]:
    """Résumés des documents (sans contenu), triés par mise à jour décroissante.

    Réservé aux membres du projet (403) ; 404 si le projet est inconnu.
    """
    documents = document_service.list_documents(db, ctx.project.id)
    return [DocumentSummary.model_validate(doc) for doc in documents]


@project_router.post(
    "/{project_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un document",
)
def create_document(
    data: DocumentCreate,
    db: DbSession,
    background: BackgroundTasks,
    ctx: Annotated[
        ProjectContext,
        Depends(require_project_role(ProjectRole.MEMBER, ProjectRole.ADMIN)),
    ],
) -> DocumentRead:
    """Crée une page de documentation. Interdit aux viewers (403).

    Le lead et l'admin global sont autorisés. 404 si le projet est inconnu.
    Indexe le document dans le RAG en tâche de fond (best-effort).
    """
    document = document_service.create_document(db, ctx.project, ctx.current_user, data)
    background.add_task(rag_hooks.index_document, document.id)
    return DocumentRead.model_validate(document)


# --------------------------------------------------------------------------- #
# Routes globales (documents généraux + liste transverse)
# --------------------------------------------------------------------------- #
@router.get(
    "",
    response_model=list[GlobalDocumentSummary],
    summary="Lister tous les documents visibles",
)
def list_all_documents(
    current_user: CurrentUser,
    db: DbSession,
) -> list[GlobalDocumentSummary]:
    """Documents visibles par l'appelant, triés par mise à jour décroissante.

    Renvoie les documents **généraux** (sans projet) et ceux des projets dont
    l'appelant est membre ; exclut les documents des autres projets.
    """
    documents = document_service.list_all_for_user(db, current_user)
    return [GlobalDocumentSummary.model_validate(doc) for doc in documents]


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un document général",
)
def create_general_document(
    data: DocumentCreate,
    current_user: CurrentUser,
    db: DbSession,
    background: BackgroundTasks,
) -> DocumentRead:
    """Crée un document **général** (non rattaché à un projet), attribué à l'appelant.

    Indexe le document dans le RAG en tâche de fond (best-effort).
    """
    document = document_service.create_general(db, current_user, data)
    background.add_task(rag_hooks.index_document, document.id)
    return DocumentRead.model_validate(document)


# --------------------------------------------------------------------------- #
# Routes rattachées au document
# --------------------------------------------------------------------------- #
@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Détail d'un document",
)
def get_document(
    ctx: Annotated[DocumentContext, Depends(get_document_context)],
) -> DocumentRead:
    """Détail d'un document (avec contenu).

    Document général : lisible par tout utilisateur connecté. Document de projet :
    réservé aux membres (403) ; 404 si le document est inconnu.
    """
    return DocumentRead.model_validate(ctx.document)


@router.patch(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Modifier un document",
)
def update_document(
    data: DocumentUpdate,
    db: DbSession,
    background: BackgroundTasks,
    ctx: Annotated[DocumentContext, Depends(get_document_context)],
) -> DocumentRead:
    """Modifie un document.

    - Document général : réservé à l'auteur ou à un admin global.
    - Document de projet : auteur, membre ``member``/``admin``, lead ou admin
      global (un viewer non-auteur ne peut pas éditer).

    Réindexe le document dans le RAG en tâche de fond (ignoré si texte inchangé).
    """
    user = ctx.current_user
    is_author = ctx.document.author_id == user.id
    if ctx.is_general:
        allowed = is_author or user.role == UserRole.ADMIN
    else:
        allowed = is_author or _is_project_writer(ctx)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Édition réservée à l'auteur ou à un membre non-viewer du projet.",
        )
    document = document_service.update_document(db, ctx.document, data)
    background.add_task(rag_hooks.index_document, document.id)
    return DocumentRead.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un document",
)
def delete_document(
    db: DbSession,
    background: BackgroundTasks,
    ctx: Annotated[DocumentContext, Depends(get_document_context)],
) -> None:
    """Supprime un document.

    - Document général : réservé à l'auteur ou à un admin global.
    - Document de projet : auteur, lead, admin projet ou admin global.

    Retire le document de l'index RAG en tâche de fond.
    """
    user = ctx.current_user
    is_author = ctx.document.author_id == user.id
    is_global_admin = user.role == UserRole.ADMIN
    if ctx.is_general:
        allowed = is_author or is_global_admin
    else:
        is_lead = ctx.project is not None and ctx.project.lead_id == user.id
        is_project_admin = ctx.membership is not None and ctx.membership.role == ProjectRole.ADMIN
        allowed = is_author or is_global_admin or is_lead or is_project_admin
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Suppression réservée à l'auteur, au lead/admin projet ou à un admin global.",
        )
    document_id = ctx.document.id
    document_service.delete_document(db, ctx.document)
    background.add_task(rag_hooks.unindex_document, document_id)
