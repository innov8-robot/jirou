"""Schémas Pydantic v2 pour les vues sauvegardées (EPIC-10, JIR-70).

Contrat d'entrée/sortie de ``/projects/{id}/views`` et ``/views/{id}``. Les
filtres sont un objet JSON libre transmis tel quel (le front en est maître).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SavedViewCreate(BaseModel):
    """Payload de création d'une vue sauvegardée (POST /projects/{id}/views)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    filters: dict[str, Any] = Field(default_factory=dict)


class SavedViewRead(BaseModel):
    """Représentation d'une vue sauvegardée renvoyée par l'API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    filters: dict[str, Any]
    project_id: int | None = None
