"""Logique métier des pièces jointes (EPIC-09, JIR-65).

Le contenu binaire est stocké sur disque sous ``settings.UPLOAD_DIR`` dans un
sous-dossier par issue : ``{UPLOAD_DIR}/{issue_id}/{uuid}_{nom_sécurisé}``. Seules
les métadonnées sont persistées en base. Le nom de fichier d'origine est
assaini et préfixé d'un UUID pour éviter les collisions et les traversées de
chemin. La taille est bornée par ``settings.MAX_UPLOAD_SIZE`` (413 au-delà).

Les autorisations (403) sont gérées en amont par la couche endpoint ; ce module
lève :class:`AttachmentServiceError` pour les erreurs métier (fichier trop gros,
introuvable).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment
from app.models.issue import Issue
from app.models.user import User

# Taille des blocs lus lors de la copie du flux entrant.
_CHUNK_SIZE = 1024 * 1024

# Caractères autorisés dans le nom stocké ; tout le reste est remplacé par « _ ».
_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class AttachmentServiceError(Exception):
    """Erreur métier des pièces jointes, traduite en HTTP par la couche endpoint.

    ``code`` est une étiquette stable (``too_large``, ``not_found``) et
    ``message`` un texte lisible pour le champ ``detail``.
    """

    code: str
    message: str


def _upload_root() -> Path:
    """Racine absolue du stockage des pièces jointes (créée si absente)."""
    root = Path(settings.UPLOAD_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _secure_filename(filename: str | None) -> str:
    """Assainit un nom de fichier : basename, caractères sûrs, non vide."""
    name = Path(filename or "").name  # retire tout composant de chemin
    name = _FILENAME_SAFE.sub("_", name).strip("._")
    return name or "file"


def get_attachment(db: Session, attachment_id: int) -> Attachment | None:
    """Retourne la pièce jointe portant cet identifiant, ou ``None``."""
    return db.get(Attachment, attachment_id)


def list_attachments(db: Session, issue: Issue) -> list[Attachment]:
    """Pièces jointes d'une issue, les plus récentes d'abord."""
    stmt = (
        select(Attachment)
        .where(Attachment.issue_id == issue.id)
        .order_by(Attachment.created_at.desc(), Attachment.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def save_upload(
    db: Session,
    issue: Issue,
    *,
    source: BinaryIO,
    filename: str | None,
    content_type: str | None,
    uploader: User,
) -> Attachment:
    """Copie le flux entrant sur disque (bornage taille) et persiste les métadonnées.

    Lève ``AttachmentServiceError("too_large")`` si le fichier dépasse
    ``settings.MAX_UPLOAD_SIZE`` (le fichier partiel est nettoyé).
    """
    max_size = settings.MAX_UPLOAD_SIZE
    safe_name = _secure_filename(filename)
    relative = f"{issue.id}/{uuid.uuid4().hex}_{safe_name}"
    target = _upload_root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)

    size = 0
    source.seek(0)
    try:
        with target.open("wb") as out:
            while True:
                chunk = source.read(_CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_size:
                    raise AttachmentServiceError(
                        "too_large",
                        f"Fichier trop volumineux (maximum {max_size} octets).",
                    )
                out.write(chunk)
    except AttachmentServiceError:
        target.unlink(missing_ok=True)
        raise

    attachment = Attachment(
        issue_id=issue.id,
        uploaded_by_id=uploader.id,
        filename=safe_name,
        stored_path=relative,
        content_type=content_type or "application/octet-stream",
        size=size,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def resolve_path(attachment: Attachment) -> Path:
    """Chemin absolu du fichier, garanti sous la racine ``uploads`` (anti-traversal).

    Lève ``AttachmentServiceError("not_found")`` si le chemin sort du dossier ou
    si le fichier est absent du disque.
    """
    root = _upload_root()
    path = (root / attachment.stored_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise AttachmentServiceError("not_found", "Fichier introuvable.")
    return path


def delete_attachment(db: Session, attachment: Attachment) -> None:
    """Supprime la ligne en base puis le fichier sur disque (best-effort)."""
    root = _upload_root()
    path = (root / attachment.stored_path).resolve()
    db.delete(attachment)
    db.commit()
    if path.is_relative_to(root):
        path.unlink(missing_ok=True)
