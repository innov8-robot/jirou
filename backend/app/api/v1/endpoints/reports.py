"""Endpoint de génération de rapports, réservé à l'admin global.

``POST /api/v1/reports/generate`` produit un rapport Markdown à partir des
statistiques (un projet si ``project_id`` est fourni, sinon une vue globale de
tous les projets), enrichi si possible d'une synthèse exécutive rédigée par le
LLM. L'accès est restreint à l'admin *global* (``require_role(ADMIN)``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.report import ReportRequest, ReportResult
from app.services import project as project_service
from app.services import report as report_service

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.post(
    "/generate",
    response_model=ReportResult,
    summary="Générer un rapport (admin global)",
)
def generate_report(
    data: ReportRequest,
    db: DbSession,
    current_user: AdminUser,
) -> ReportResult:
    """Génère un rapport de projet (``project_id`` fourni) ou global (absent).

    - 403 si l'appelant n'est pas admin global.
    - 404 si ``project_id`` désigne un projet inexistant.
    """
    project = None
    if data.project_id is not None:
        project = project_service.get_project(db, data.project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable.")
    return report_service.generate_report(db, project)
