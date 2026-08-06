"""Schémas Pydantic v2 de l'archive d'export de la veille (domaine VEILLE).

Décrit le contenu de ``veille.json`` à l'intérieur du ZIP produit par
``GET /watch/export``. Le manifeste est *auto-porté* — aucun identifiant de base
n'y figure : les nœuds se référencent entre eux par ``ref``/``parent_ref``, et
les fichiers par un chemin relatif dans l'archive (``media/...``).

Le champ ``version`` fige la structure : un lecteur peut refuser une version
qu'il ne sait pas interpréter.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import WatchMediaKind, WatchNodeType, WatchStatus

# Version du format d'archive écrite à l'export et acceptée à l'import.
ARCHIVE_VERSION = 1

# Nom du manifeste JSON à la racine de l'archive ZIP.
MANIFEST_NAME = "veille.json"

# Préfixe du dossier des fichiers téléversés dans l'archive.
MEDIA_PREFIX = "media/"


# --------------------------------------------------------------------------- #
# Format d'archive
# --------------------------------------------------------------------------- #
class WatchArchiveMedia(BaseModel):
    """Un média dans l'archive : fichier embarqué ou lien externe.

    - ``kind=link`` : seul ``url`` (et éventuellement ``title``) est significatif ;
    - ``kind=image``/``video`` : ``path`` pointe vers l'entrée du ZIP contenant
      les octets du fichier (``media/...``). Un média ``image``/``video`` sans
      ``path`` (ou dont l'entrée est absente de l'archive) est ignoré à l'import
      et signalé.
    """

    model_config = ConfigDict(extra="ignore")

    kind: WatchMediaKind
    filename: str | None = Field(default=None, max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    size: int | None = None
    url: str | None = Field(default=None, max_length=2048)
    title: str | None = Field(default=None, max_length=255)
    # Chemin de l'entrée dans le ZIP (``media/...``), ``None`` pour un lien.
    path: str | None = Field(default=None, max_length=1024)
    created_at: datetime | None = None


class WatchArchiveComment(BaseModel):
    """Un commentaire dans l'archive.

    L'auteur est décrit par son e-mail (rattaché à l'import s'il existe sur
    l'instance cible, sinon le commentaire est conservé sans auteur) ; le nom
    complet n'est là que pour la lisibilité du JSON.
    """

    model_config = ConfigDict(extra="ignore")

    body: str = Field(min_length=1)
    author_email: str | None = None
    author_name: str | None = None
    created_at: datetime | None = None


class WatchArchiveNode(BaseModel):
    """Un nœud de veille dans l'archive.

    ``ref`` est un identifiant *local à l'archive* (unique) ; ``parent_ref``
    désigne le parent par sa ``ref`` (``None`` pour une racine). Un
    ``parent_ref`` inconnu ou cyclique fait basculer le nœud en racine, avec un
    avertissement.
    """

    model_config = ConfigDict(extra="ignore")

    ref: str = Field(min_length=1, max_length=64)
    parent_ref: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    type: WatchNodeType = WatchNodeType.THEME
    note: str = ""
    status: WatchStatus | None = None
    pos_x: float = 0
    pos_y: float = 0
    created_by_email: str | None = None
    created_at: datetime | None = None
    media: list[WatchArchiveMedia] = Field(default_factory=list)
    comments: list[WatchArchiveComment] = Field(default_factory=list)


class WatchArchive(BaseModel):
    """Manifeste ``veille.json`` : l'arbre de veille complet, à plat."""

    model_config = ConfigDict(extra="ignore")

    version: int = ARCHIVE_VERSION
    exported_at: datetime | None = None
    # Instance d'origine (indicatif, aide au diagnostic).
    source: str | None = None
    nodes: list[WatchArchiveNode] = Field(default_factory=list)
