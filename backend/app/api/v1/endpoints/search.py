"""Endpoint de recherche globale (EPIC-10, JIR-68).

``GET /api/v1/search`` renvoie tickets + projets pertinents, strictement limités
aux projets dont l'appelant est membre.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.schemas.search import SearchIssue, SearchProject, SearchResults
from app.services import search as search_service

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/search",
    response_model=SearchResults,
    summary="Recherche globale (tickets + projets)",
)
def global_search(
    db: DbSession,
    current_user: CurrentUser,
    q: Annotated[str, Query()] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchResults:
    """Recherche tickets (clé/résumé/description) et projets (nom/clé).

    Limitée aux projets dont l'appelant est membre. ``q`` vide → listes vides.
    """
    data = search_service.search(db, current_user, q, limit=limit)
    return SearchResults(
        issues=[SearchIssue.model_validate(issue) for issue in data.issues],
        projects=[SearchProject.model_validate(project) for project in data.projects],
    )
