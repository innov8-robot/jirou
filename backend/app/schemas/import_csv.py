"""Schémas Pydantic v2 pour l'import CSV de tickets (EPIC-05).

Contrat de sortie de l'endpoint ``POST /projects/{id}/issues/import``. L'import
est *robuste* : chaque ligne du CSV est validée indépendamment. ``errors``
agrège à la fois les lignes rejetées (ex. ``summary`` vide, ``type`` inconnu) et
les avertissements non bloquants (ex. ``assignee_email`` non membre) — les deux
sont distingués par le contenu de ``message``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.issue import IssueRead


class ImportError(BaseModel):
    """Une anomalie rencontrée sur une ligne du CSV (erreur OU avertissement).

    ``row`` est le numéro de la ligne **de données** (1 = première ligne après
    l'en-tête). ``message`` décrit l'anomalie ; il permet de distinguer une
    ligne rejetée (« ignorée ») d'un simple avertissement (« ticket créé »).
    """

    row: int
    message: str


class ImportResult(BaseModel):
    """Résultat d'un import CSV.

    - ``created`` : nombre de tickets effectivement créés ;
    - ``error_count`` : nombre d'entrées dans ``errors`` (erreurs + warnings) ;
    - ``errors`` : détail des anomalies par ligne ;
    - ``issues`` : les tickets créés (mêmes objets que ``IssueRead``).
    """

    created: int
    error_count: int
    errors: list[ImportError] = Field(default_factory=list)
    issues: list[IssueRead] = Field(default_factory=list)
