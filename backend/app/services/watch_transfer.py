"""Export de la veille R&D sous forme d'archive ZIP (domaine VEILLE).

L'archive est **auto-portée** : elle contient le manifeste ``veille.json``
(l'arbre complet — titres, types, statuts, positions, notes Markdown, liens
externes, commentaires) *et* les fichiers téléversés sous ``media/``.

::

    veille-2026-07-29.zip
    ├── veille.json
    └── media/
        ├── 3/ab12cd_schema.png
        └── 7/ef34ab_demo.mp4

Aucun identifiant de base n'apparaît dans le manifeste : les nœuds se
référencent par ``ref``/``parent_ref`` (cf. :mod:`app.schemas.watch_transfer`).

C'est une **sauvegarde**, pas un format d'échange réimportable : l'ajout de
contenu se fait par l'import CSV ancré sous un nœud
(:mod:`app.services.watch_csv`), plus sûr qu'un remplacement global de l'arbre.
"""

from __future__ import annotations

import io
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.watch import WatchComment, WatchNode
from app.schemas.watch_transfer import (
    ARCHIVE_VERSION,
    MANIFEST_NAME,
    MEDIA_PREFIX,
    WatchArchive,
    WatchArchiveComment,
    WatchArchiveMedia,
    WatchArchiveNode,
)
from app.services.watch import _upload_root


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def export_filename(now: datetime | None = None) -> str:
    """Nom de fichier proposé au téléchargement (``veille-AAAA-MM-JJ.zip``)."""
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%d")
    return f"veille-{stamp}.zip"


def _archive_media_path(node_id: int, stored_path: str) -> str:
    """Chemin d'une entrée de média dans l'archive, dérivé du nom stocké."""
    return f"{MEDIA_PREFIX}{node_id}/{Path(stored_path).name}"


def _serialize_comment(comment: WatchComment) -> WatchArchiveComment:
    """Sérialise un commentaire pour le manifeste."""
    return WatchArchiveComment(
        body=comment.body,
        author_email=comment.author.email if comment.author else None,
        author_name=comment.author.full_name if comment.author else None,
        created_at=comment.created_at,
    )


def export_archive(db: Session, *, source: str | None = None) -> bytes:
    """Construit l'archive ZIP de toute la veille et retourne ses octets.

    Les fichiers absents du disque sont exportés sans leur ``path`` : leurs
    métadonnées sont conservées plutôt que de faire échouer l'export.
    """
    nodes = list(
        db.execute(select(WatchNode).options(selectinload(WatchNode.media)).order_by(WatchNode.id))
        .scalars()
        .all()
    )
    comments_by_node: dict[int, list[WatchComment]] = defaultdict(list)
    for comment in (
        db.execute(select(WatchComment).order_by(WatchComment.created_at, WatchComment.id))
        .scalars()
        .all()
    ):
        comments_by_node[comment.node_id].append(comment)

    root = _upload_root()
    # (chemin dans l'archive, chemin disque) des fichiers à embarquer.
    files: list[tuple[str, Path]] = []
    archive_nodes: list[WatchArchiveNode] = []

    for node in nodes:
        media_entries: list[WatchArchiveMedia] = []
        for media in node.media:
            entry = WatchArchiveMedia(
                kind=media.kind,
                filename=media.filename,
                content_type=media.content_type,
                size=media.size,
                url=media.url,
                title=media.title,
                created_at=media.created_at,
            )
            if media.stored_path is not None:
                path = (root / media.stored_path).resolve()
                if path.is_relative_to(root) and path.is_file():
                    entry.path = _archive_media_path(node.id, media.stored_path)
                    files.append((entry.path, path))
            media_entries.append(entry)

        archive_nodes.append(
            WatchArchiveNode(
                ref=str(node.id),
                parent_ref=str(node.parent_id) if node.parent_id is not None else None,
                title=node.title,
                type=node.type,
                note=node.note,
                status=node.status,
                pos_x=node.pos_x,
                pos_y=node.pos_y,
                created_by_email=node.created_by.email if node.created_by else None,
                created_at=node.created_at,
                media=media_entries,
                comments=[_serialize_comment(c) for c in comments_by_node.get(node.id, [])],
            )
        )

    manifest = WatchArchive(
        version=ARCHIVE_VERSION,
        exported_at=datetime.now(UTC),
        source=source,
        nodes=archive_nodes,
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, manifest.model_dump_json(indent=2))
        # Images/vidéos : déjà compressées, stockées telles quelles.
        for arc_name, disk_path in files:
            zf.write(disk_path, arc_name, compress_type=zipfile.ZIP_STORED)
    return buffer.getvalue()
