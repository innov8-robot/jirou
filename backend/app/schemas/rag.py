"""Schémas Pydantic du chatbot RAG (EPIC-10).

Contrats d'entrée/sortie des endpoints ``/rag`` : question posée par
l'utilisateur, réponse générée et sources (chunks) mobilisées, ainsi que le
statut de configuration du service.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RagStatus(BaseModel):
    """Statut de disponibilité du chatbot."""

    # ``True`` si la clé API Mistral est configurée côté serveur.
    enabled: bool


class RagChatRequest(BaseModel):
    """Corps d'une requête de conversation."""

    question: str = Field(..., min_length=1, description="Question en langage naturel.")


class RagSource(BaseModel):
    """Une source (chunk) ayant servi à construire la réponse."""

    kind: str
    project_id: int | None = None
    issue_key: str | None = None
    title: str | None = None


class RagAnswer(BaseModel):
    """Réponse du chatbot : texte généré + sources citées."""

    answer: str
    sources: list[RagSource]
