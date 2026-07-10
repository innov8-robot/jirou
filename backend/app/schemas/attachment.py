"""Schémas Pydantic v2 pour les pièces jointes (EPIC-09, JIR-65).

Contrat de sortie de l'API ``/issues/{key}/attachments`` et
``/attachments/{id}``. L'upload se fait en ``multipart/form-data`` (champ
``file``), il n'a donc pas de schéma de corps JSON.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.issue import MiniUser


class AttachmentRead(BaseModel):
    """Représentation d'une pièce jointe renvoyée par l'API.

    ``download_url`` pointe vers l'endpoint de téléchargement sécurisé.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    filename: str
    content_type: str
    size: int
    uploaded_by: MiniUser
    created_at: datetime
    download_url: str
