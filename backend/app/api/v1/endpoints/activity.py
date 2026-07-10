"""Endpoint du journal d'activité d'un ticket (EPIC-10, JIR-69).

``GET /api/v1/issues/{key}/activity`` renvoie les entrées d'audit d'un ticket,
les plus récentes d'abord. Réservé aux membres du projet (réutilise la
dépendance d'issue de ``endpoints.issues``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.endpoints.issues import IssueContext, get_issue_context
from app.core.database import get_db
from app.schemas.activity import ActivityRead
from app.services import activity as activity_service

issue_router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@issue_router.get(
    "/{key}/activity",
    response_model=list[ActivityRead],
    summary="Journal d'activité d'un ticket",
)
def list_issue_activity(
    db: DbSession,
    ctx: Annotated[IssueContext, Depends(get_issue_context)],
) -> list[ActivityRead]:
    """Entrées d'activité du ticket (récentes d'abord). Réservé aux membres."""
    entries = activity_service.list_activity(db, ctx.issue)
    return [ActivityRead.model_validate(entry) for entry in entries]
