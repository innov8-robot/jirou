"""Logique métier du domaine VEILLE (base de connaissances R&D en arbre/graphe).

Regroupe la gestion des nœuds (arbre + détection de cycle), des médias (fichiers
téléversés sur disque sous ``{UPLOAD_DIR}/watch/{node_id}/...`` ou liens externes)
et des commentaires. Le stockage disque réutilise les mêmes garanties que les
pièces jointes : nom assaini, préfixe UUID, bornage de taille et anti-traversal.

Les autorisations (403) sont gérées en amont par la couche endpoint ; ce module
lève :class:`WatchServiceError` pour les erreurs métier (fichier trop gros,
introuvable, cycle).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.enums import WatchMediaKind
from app.models.user import User
from app.models.watch import WatchComment, WatchMedia, WatchNode
from app.schemas.watch import WatchNodeCreate, WatchNodeUpdate

# Taille des blocs lus lors de la copie du flux entrant.
_CHUNK_SIZE = 1024 * 1024

# Caractères autorisés dans le nom stocké ; tout le reste est remplacé par « _ ».
_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class WatchServiceError(Exception):
    """Erreur métier de la veille, traduite en HTTP par la couche endpoint.

    ``code`` est une étiquette stable (``too_large``, ``not_found``, ``cycle``,
    ``unsupported_media_type``) et ``message`` un texte lisible pour ``detail``.
    """

    code: str
    message: str


# --------------------------------------------------------------------------- #
# Stockage disque (médias téléversés)
# --------------------------------------------------------------------------- #
def _upload_root() -> Path:
    """Racine absolue du stockage des médias de veille (créée si absente)."""
    root = (Path(settings.UPLOAD_DIR) / "watch").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _secure_filename(filename: str | None) -> str:
    """Assainit un nom de fichier : basename, caractères sûrs, non vide."""
    name = Path(filename or "").name
    name = _FILENAME_SAFE.sub("_", name).strip("._")
    return name or "file"


# --------------------------------------------------------------------------- #
# Nœuds
# --------------------------------------------------------------------------- #
def get_node(db: Session, node_id: int) -> WatchNode | None:
    """Retourne le nœud portant cet identifiant, ou ``None``."""
    return db.get(WatchNode, node_id)


def list_nodes(db: Session) -> list[WatchNode]:
    """Tous les nœuds (arbre à plat), pour construire le graphe côté frontend.

    Charge les médias en une seule requête (``selectinload``) pour l'aperçu de
    carte (premier média), sans N+1.
    """
    stmt = select(WatchNode).options(selectinload(WatchNode.media)).order_by(WatchNode.id)
    return list(db.execute(stmt).scalars().all())


def media_counts(db: Session) -> dict[int, int]:
    """Nombre de médias par ``node_id`` (pour les résumés)."""
    stmt = select(WatchMedia.node_id, func.count(WatchMedia.id)).group_by(WatchMedia.node_id)
    return dict(db.execute(stmt).all())


def comment_counts(db: Session) -> dict[int, int]:
    """Nombre de commentaires par ``node_id`` (pour les résumés)."""
    stmt = select(WatchComment.node_id, func.count(WatchComment.id)).group_by(WatchComment.node_id)
    return dict(db.execute(stmt).all())


def create_node(db: Session, data: WatchNodeCreate, creator: User) -> WatchNode:
    """Crée un nœud. Lève ``WatchServiceError("not_found")`` si le parent est inconnu."""
    if data.parent_id is not None and db.get(WatchNode, data.parent_id) is None:
        raise WatchServiceError("not_found", "Nœud parent introuvable.")
    node = WatchNode(
        parent_id=data.parent_id,
        title=data.title,
        type=data.type,
        note=data.note,
        status=data.status,
        pos_x=data.pos_x,
        pos_y=data.pos_y,
        created_by_id=creator.id,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def _descendant_ids(db: Session, node_id: int) -> set[int]:
    """Ensemble des identifiants des descendants de ``node_id`` (parcours en largeur)."""
    descendants: set[int] = set()
    frontier = [node_id]
    while frontier:
        stmt = select(WatchNode.id).where(WatchNode.parent_id.in_(frontier))
        children = [row for (row,) in db.execute(stmt).all()]
        new = [c for c in children if c not in descendants]
        descendants.update(new)
        frontier = new
    return descendants


def update_node(db: Session, node: WatchNode, data: WatchNodeUpdate) -> WatchNode:
    """Applique une mise à jour partielle. Valide le nouveau parent (existence + cycle).

    Lève ``WatchServiceError("cycle")`` (422) si ``parent_id`` est le nœud lui-même
    ou l'un de ses descendants ; ``WatchServiceError("not_found")`` si le parent
    est inconnu.
    """
    fields = data.model_dump(exclude_unset=True)

    if "parent_id" in fields:
        new_parent = fields["parent_id"]
        if new_parent is not None:
            if new_parent == node.id:
                raise WatchServiceError("cycle", "Un nœud ne peut pas être son propre parent.")
            if db.get(WatchNode, new_parent) is None:
                raise WatchServiceError("not_found", "Nœud parent introuvable.")
            if new_parent in _descendant_ids(db, node.id):
                raise WatchServiceError(
                    "cycle", "Le parent ne peut pas être un descendant du nœud."
                )

    for key, value in fields.items():
        setattr(node, key, value)
    db.commit()
    db.refresh(node)
    return node


def delete_node(db: Session, node: WatchNode) -> None:
    """Supprime un nœud et tout son sous-arbre (cascade), avec les médias sur disque.

    La suppression physique des fichiers du sous-arbre est faite au préalable
    (best-effort), la cascade en base retirant ensuite nœuds/médias/commentaires.
    """
    subtree = {node.id} | _descendant_ids(db, node.id)
    root = _upload_root()
    stmt = select(WatchMedia).where(
        WatchMedia.node_id.in_(subtree), WatchMedia.stored_path.is_not(None)
    )
    for media in db.execute(stmt).scalars().all():
        path = (root / media.stored_path).resolve()
        if path.is_relative_to(root):
            path.unlink(missing_ok=True)
    db.delete(node)
    db.commit()


# --------------------------------------------------------------------------- #
# Médias
# --------------------------------------------------------------------------- #
def get_media(db: Session, media_id: int) -> WatchMedia | None:
    """Retourne le média portant cet identifiant, ou ``None``."""
    return db.get(WatchMedia, media_id)


def list_media(db: Session, node: WatchNode) -> list[WatchMedia]:
    """Médias d'un nœud, dans l'ordre chronologique (plus ancien d'abord)."""
    stmt = (
        select(WatchMedia)
        .where(WatchMedia.node_id == node.id)
        .order_by(WatchMedia.created_at, WatchMedia.id)
    )
    return list(db.execute(stmt).scalars().all())


def _kind_from_content_type(content_type: str | None) -> WatchMediaKind:
    """Déduit ``image``/``video`` du content-type. Lève une erreur sinon (415)."""
    ct = (content_type or "").lower()
    if ct.startswith("image/"):
        return WatchMediaKind.IMAGE
    if ct.startswith("video/"):
        return WatchMediaKind.VIDEO
    raise WatchServiceError(
        "unsupported_media_type",
        "Type de fichier non supporté (image/* ou video/* attendu).",
    )


def save_upload(
    db: Session,
    node: WatchNode,
    *,
    source: BinaryIO,
    filename: str | None,
    content_type: str | None,
    uploader: User,
) -> WatchMedia:
    """Copie le flux entrant sur disque (bornage taille) et persiste les métadonnées.

    Le ``kind`` est déduit du content-type (image/vidéo). Lève
    ``WatchServiceError("unsupported_media_type")`` (415) pour un autre type, et
    ``WatchServiceError("too_large")`` (413) au-delà de ``WATCH_MAX_UPLOAD_SIZE``
    (le fichier partiel est nettoyé).
    """
    kind = _kind_from_content_type(content_type)
    max_size = settings.WATCH_MAX_UPLOAD_SIZE
    safe_name = _secure_filename(filename)
    relative = f"{node.id}/{uuid.uuid4().hex}_{safe_name}"
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
                    raise WatchServiceError(
                        "too_large",
                        f"Fichier trop volumineux (maximum {max_size} octets).",
                    )
                out.write(chunk)
    except WatchServiceError:
        target.unlink(missing_ok=True)
        raise

    media = WatchMedia(
        node_id=node.id,
        kind=kind,
        filename=safe_name,
        stored_path=relative,
        content_type=content_type or "application/octet-stream",
        size=size,
        created_by_id=uploader.id,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


def create_link(
    db: Session, node: WatchNode, *, url: str, title: str | None, creator: User
) -> WatchMedia:
    """Ajoute un lien externe (kind=``link``) au nœud."""
    media = WatchMedia(
        node_id=node.id,
        kind=WatchMediaKind.LINK,
        url=url,
        title=title,
        created_by_id=creator.id,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


def resolve_path(media: WatchMedia) -> Path:
    """Chemin absolu du fichier, garanti sous la racine ``uploads/watch`` (anti-traversal).

    Lève ``WatchServiceError("not_found")`` pour un lien externe, si le chemin sort
    du dossier ou si le fichier est absent du disque.
    """
    if media.stored_path is None:
        raise WatchServiceError("not_found", "Ce média n'est pas un fichier téléchargeable.")
    root = _upload_root()
    path = (root / media.stored_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise WatchServiceError("not_found", "Fichier introuvable.")
    return path


def delete_media(db: Session, media: WatchMedia) -> None:
    """Supprime la ligne en base puis le fichier sur disque (best-effort)."""
    stored_path = media.stored_path
    db.delete(media)
    db.commit()
    if stored_path is not None:
        root = _upload_root()
        path = (root / stored_path).resolve()
        if path.is_relative_to(root):
            path.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Commentaires
# --------------------------------------------------------------------------- #
def get_comment(db: Session, comment_id: int) -> WatchComment | None:
    """Retourne le commentaire portant cet identifiant, ou ``None``."""
    return db.get(WatchComment, comment_id)


def list_comments(db: Session, node: WatchNode) -> list[WatchComment]:
    """Commentaires d'un nœud, dans l'ordre chronologique (plus ancien d'abord)."""
    stmt = (
        select(WatchComment)
        .where(WatchComment.node_id == node.id)
        .order_by(WatchComment.created_at, WatchComment.id)
    )
    return list(db.execute(stmt).scalars().all())


def create_comment(db: Session, node: WatchNode, author: User, body: str) -> WatchComment:
    """Crée un commentaire sur un nœud."""
    comment = WatchComment(node_id=node.id, author_id=author.id, body=body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def update_comment(db: Session, comment: WatchComment, body: str) -> WatchComment:
    """Met à jour le corps d'un commentaire."""
    comment.body = body
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, comment: WatchComment) -> None:
    """Supprime définitivement un commentaire."""
    db.delete(comment)
    db.commit()
