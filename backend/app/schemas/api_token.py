"""Schémas Pydantic v2 des jetons d'API personnels.

Contrat de ``/users/me/tokens``. Deux formes de sortie, volontairement
distinctes :

- :class:`ApiTokenRead` — métadonnées seules, renvoyées par la liste. Le secret
  n'y figure **jamais** ; ``prefix`` sert uniquement à reconnaître le jeton.
- :class:`ApiTokenCreated` — renvoyée **une seule fois**, à la création, et
  porte le champ ``token`` en clair.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiTokenCreate(BaseModel):
    """Payload de création d'un jeton (POST /users/me/tokens)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    # Durée de vie en jours ; absent = jeton sans expiration.
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class ApiTokenRead(BaseModel):
    """Métadonnées d'un jeton (sans le secret).

    ``revoked_at`` non nul signifie que le jeton est inutilisable ; la ligne est
    conservée pour garder la trace de son existence.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prefix: str
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiTokenCreated(ApiTokenRead):
    """Jeton fraîchement créé : seule réponse à porter le secret en clair."""

    token: str
