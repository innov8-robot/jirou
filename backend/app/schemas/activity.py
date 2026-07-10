"""Schémas Pydantic v2 pour le journal d'activité (EPIC-10, JIR-69).

Contrat de sortie de ``GET /issues/{key}/activity`` : la liste chronologique
inverse (récentes d'abord) des entrées d'audit d'un ticket.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.issue import MiniUser


class ActivityRead(BaseModel):
    """Une entrée du journal d'activité d'un ticket."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    actor: MiniUser | None = None
    created_at: datetime
