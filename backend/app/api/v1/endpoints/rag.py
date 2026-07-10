"""Endpoints du chatbot RAG (EPIC-10).

Trois routes sous ``/api/v1/rag`` réservées à tout utilisateur connecté :

- ``GET  /rag/status``  : indique si le chatbot est configuré (clé Mistral).
- ``POST /rag/reindex`` : (ré)indexe dans Qdrant les projets dont l'appelant est
  membre — ou **tous** les projets si l'appelant est admin global.
- ``POST /rag/chat``    : répond à une question en s'appuyant uniquement sur le
  contenu accessible à l'appelant (ses projets + documents généraux).

Le service ne joint jamais Mistral/Qdrant à l'import ; si la clé Mistral est
absente, les routes ``reindex``/``chat`` renvoient **503** avec un message clair.
Les erreurs réseau (Qdrant/Mistral injoignables) sont également traduites en 503.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.project import Project
from app.schemas.rag import RagAnswer, RagChatRequest, RagStatus
from app.services import rag as rag_service
from app.services.rag import RagNotConfigured, RagUnavailable

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

_NOT_CONFIGURED_DETAIL = "Chatbot non configuré : renseignez MISTRAL_API_KEY."


def _target_project_ids(db: Session, user: CurrentUser) -> list[int]:
    """Projets à (ré)indexer : tous si admin global, sinon ceux de l'appelant."""
    if user.role == UserRole.ADMIN:
        return sorted(db.execute(select(Project.id)).scalars())
    return rag_service.member_project_ids(db, user)


@router.get("/status", response_model=RagStatus, summary="Statut du chatbot")
def rag_status(current_user: CurrentUser) -> RagStatus:
    """Indique si le chatbot est activé (clé API Mistral configurée)."""
    return RagStatus(enabled=bool(settings.MISTRAL_API_KEY))


@router.post("/reindex", summary="Réindexer le contenu accessible")
def rag_reindex(current_user: CurrentUser, db: DbSession) -> dict[str, int]:
    """Réindexe les projets de l'appelant (ou tous, si admin global).

    503 si le chatbot n'est pas configuré ou si Qdrant/Mistral est injoignable.
    """
    if not settings.MISTRAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_NOT_CONFIGURED_DETAIL
        )
    project_ids = _target_project_ids(db, current_user)
    try:
        indexed = rag_service.reindex(db, project_ids)
    except RagNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_NOT_CONFIGURED_DETAIL
        ) from exc
    except RagUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return {"indexed": indexed}


@router.post("/chat", response_model=RagAnswer, summary="Poser une question au chatbot")
def rag_chat(data: RagChatRequest, current_user: CurrentUser, db: DbSession) -> RagAnswer:
    """Répond à une question en respectant les droits d'accès de l'appelant.

    503 si la clé Mistral est absente ou si Qdrant/Mistral est injoignable.
    """
    if not settings.MISTRAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_NOT_CONFIGURED_DETAIL
        )
    try:
        result = rag_service.answer(db, current_user, data.question)
    except RagNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_NOT_CONFIGURED_DETAIL
        ) from exc
    except RagUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return RagAnswer.model_validate(result)
