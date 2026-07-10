"""Hooks d'indexation RAG incrémentale (best-effort, en tâche de fond).

Ces fonctions sont destinées à être planifiées via ``BackgroundTasks`` : elles
s'exécutent **après** la réponse HTTP, ouvrent leur **propre** session DB (celle
de la requête est déjà fermée), n'ont **aucun effet** si le chatbot n'est pas
configuré (``MISTRAL_API_KEY`` absente), et **n'échouent jamais** vers l'appelant
— toute erreur (Qdrant/Mistral injoignable…) est journalisée puis avalée, car
l'opération métier est déjà committée et ne doit pas être impactée.

Convention : les hooks d'indexation reçoivent des **identifiants** (pas des objets
ORM liés à la session de requête) et rechargent l'objet ; les hooks de
désindexation n'ont besoin que de l'identifiant (le point Qdrant est déterministe).
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.comment import Comment
from app.models.document import Document
from app.models.issue import Issue
from app.services import rag as rag_service

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    """Vrai si l'indexation RAG est active (clé Mistral configurée)."""
    return bool(settings.MISTRAL_API_KEY)


# --------------------------------------------------------------------------- #
# Indexation (upsert incrémental)
# --------------------------------------------------------------------------- #
def index_issue(issue_id: int) -> None:
    """(Ré)indexe un ticket. Sans effet s'il n'existe plus ou si RAG est désactivé."""
    if not _enabled():
        return
    try:
        with SessionLocal() as db:
            issue = db.get(Issue, issue_id)
            if issue is None:
                return
            rag_service.index_chunks([rag_service.build_issue_chunk(issue)])
    except Exception:  # noqa: BLE001 - best-effort : ne jamais casser l'opération métier
        logger.exception("RAG: échec d'indexation du ticket %s", issue_id)


def index_issues_bulk(issue_ids: list[int]) -> None:
    """(Ré)indexe un lot de tickets en un seul batch d'embeddings (import CSV)."""
    if not _enabled() or not issue_ids:
        return
    try:
        with SessionLocal() as db:
            issues = list(db.execute(select(Issue).where(Issue.id.in_(issue_ids))).scalars().all())
            if issues:
                rag_service.index_chunks([rag_service.build_issue_chunk(i) for i in issues])
    except Exception:  # noqa: BLE001
        logger.exception("RAG: échec d'indexation en lot (%d tickets)", len(issue_ids))


def index_comment(comment_id: int) -> None:
    """(Ré)indexe un commentaire. Sans effet s'il n'existe plus."""
    if not _enabled():
        return
    try:
        with SessionLocal() as db:
            comment = db.get(Comment, comment_id)
            if comment is None:
                return
            issue = db.get(Issue, comment.issue_id)
            if issue is None:
                return
            rag_service.index_chunks([rag_service.build_comment_chunk(issue, comment)])
    except Exception:  # noqa: BLE001
        logger.exception("RAG: échec d'indexation du commentaire %s", comment_id)


def index_document(document_id: int) -> None:
    """(Ré)indexe un document (de projet ou général). Sans effet s'il n'existe plus."""
    if not _enabled():
        return
    try:
        with SessionLocal() as db:
            document = db.get(Document, document_id)
            if document is None:
                return
            rag_service.index_chunks([rag_service.build_document_chunk(document)])
    except Exception:  # noqa: BLE001
        logger.exception("RAG: échec d'indexation du document %s", document_id)


# --------------------------------------------------------------------------- #
# Désindexation (suppression de points)
# --------------------------------------------------------------------------- #
def unindex_issue(issue_id: int, comment_ids: list[int] | None = None) -> None:
    """Retire de l'index un ticket **et ses commentaires** (dont les points sont orphelins).

    ``comment_ids`` doit être capturé **avant** la suppression en base (cascade),
    car les lignes n'existent plus au moment où le hook s'exécute.
    """
    if not _enabled():
        return
    try:
        ids = [rag_service.point_id("issue", issue_id)]
        ids += [rag_service.point_id("comment", cid) for cid in comment_ids or []]
        rag_service.delete_points(ids)
    except Exception:  # noqa: BLE001
        logger.exception("RAG: échec de désindexation du ticket %s", issue_id)


def unindex_comment(comment_id: int) -> None:
    """Retire un commentaire de l'index."""
    if not _enabled():
        return
    try:
        rag_service.delete_points([rag_service.point_id("comment", comment_id)])
    except Exception:  # noqa: BLE001
        logger.exception("RAG: échec de désindexation du commentaire %s", comment_id)


def unindex_document(document_id: int) -> None:
    """Retire un document de l'index."""
    if not _enabled():
        return
    try:
        rag_service.delete_points([rag_service.point_id("document", document_id)])
    except Exception:  # noqa: BLE001
        logger.exception("RAG: échec de désindexation du document %s", document_id)
