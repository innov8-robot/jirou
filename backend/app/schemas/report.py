"""Schémas Pydantic v2 pour la génération de rapports (admin global).

Contrat de ``POST /api/v1/reports/generate`` : un rapport en Markdown, construit
à partir des statistiques (projet ciblé ou vue globale) et éventuellement enrichi
d'une synthèse exécutive rédigée par le LLM (Mistral).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ReportRequest(BaseModel):
    """Payload de génération d'un rapport.

    - ``project_id`` fourni → rapport d'un projet.
    - ``project_id`` absent/``null`` → rapport global (tous les projets).
    """

    model_config = ConfigDict(extra="forbid")

    project_id: int | None = None


class ReportResult(BaseModel):
    """Rapport généré.

    - ``project_id`` : identifiant du projet ciblé, ou ``null`` (rapport global).
    - ``generated_at`` : horodatage ISO 8601 de génération.
    - ``llm_used`` : ``true`` si une synthèse IA a été produite et préfixée.
    - ``markdown`` : le rapport complet au format Markdown.
    """

    project_id: int | None = None
    generated_at: str
    llm_used: bool
    markdown: str
