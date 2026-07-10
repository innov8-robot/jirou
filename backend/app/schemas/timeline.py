"""Schémas Pydantic v2 pour la timeline et les dépendances (EPIC-08, JIR-56/61).

Contrat d'entrée/sortie des endpoints ``/projects/{id}/timeline`` et
``/issues/{key}/dependencies``. Rappel conventions : payloads en ``snake_case``,
erreurs ``{"detail": ...}``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DependencyType
from app.schemas.issue import IssueProgress, IssueRead, MiniIssue


# --------------------------------------------------------------------------- #
# Timeline (JIR-56)
# --------------------------------------------------------------------------- #
class TimelineDependency(BaseModel):
    """Lien de dépendance epic↔epic, tracé sur la timeline. ``from`` bloque ``to``."""

    from_key: str
    to_key: str


class TimelineEpic(BaseModel):
    """Un epic de la timeline avec ses enfants et sa progression."""

    epic: IssueRead
    children: list[IssueRead] = Field(default_factory=list)
    progress: IssueProgress


class TimelineRead(BaseModel):
    """Données de timeline d'un projet (JIR-56)."""

    epics: list[TimelineEpic] = Field(default_factory=list)
    dependencies: list[TimelineDependency] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Dépendances (JIR-61)
# --------------------------------------------------------------------------- #
class DependencyCreate(BaseModel):
    """Payload de création d'une dépendance (POST /issues/{key}/dependencies).

    L'issue de l'URL est le ``from`` (elle **bloque** ``target_key``).
    """

    model_config = ConfigDict(extra="forbid")

    target_key: str = Field(min_length=1)
    type: DependencyType = DependencyType.BLOCKS


class DependencyRead(BaseModel):
    """Dépendance renvoyée par l'API : ``from`` bloque ``to``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: DependencyType
    from_: MiniIssue = Field(serialization_alias="from")
    to: MiniIssue
