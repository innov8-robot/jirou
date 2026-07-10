"""Schémas Pydantic v2 pour la recherche globale (EPIC-10, JIR-68).

Contrat de sortie de ``GET /search`` : des résultats groupés (tickets + projets)
limités aux projets dont l'appelant est membre. Rappel conventions : payloads en
``snake_case``, erreurs ``{"detail": ...}``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IssueStatus, IssueType


class SearchIssue(BaseModel):
    """Ticket allégé dans les résultats de recherche."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    summary: str
    type: IssueType
    status: IssueStatus
    project_id: int


class SearchProject(BaseModel):
    """Projet allégé dans les résultats de recherche."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key: str
    color: str | None = None


class SearchResults(BaseModel):
    """Résultats groupés d'une recherche globale."""

    issues: list[SearchIssue] = Field(default_factory=list)
    projects: list[SearchProject] = Field(default_factory=list)
