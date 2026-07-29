"""Export / import de la veille R&D sous forme d'archive ZIP (domaine VEILLE).

L'archive est **auto-portée** : elle contient le manifeste ``veille.json``
(l'arbre complet — titres, types, statuts, positions, notes Markdown, liens
externes, commentaires) *et* les fichiers téléversés sous ``media/``. Elle est
donc rejouable sur une autre instance (prod → local, sauvegarde, partage).

::

    veille-2026-07-29.zip
    ├── veille.json
    └── media/
        ├── 3/ab12cd_schema.png
        └── 7/ef34ab_demo.mp4

Aucun identifiant de base n'apparaît dans le manifeste : les nœuds se
référencent par ``ref``/``parent_ref`` (cf. :mod:`app.schemas.watch_transfer`).
À l'import, de nouveaux identifiants sont attribués et les fichiers sont
recopiés sous ``{UPLOAD_DIR}/watch/{node_id}/{uuid}_{nom}`` — les chemins de
l'archive ne sont **jamais** utilisés comme chemins disque (anti-traversal).

L'import est robuste et transactionnel : chaque nœud/média/commentaire invalide
est ignoré et signalé dans ``errors``, le reste du lot est créé ; en cas
d'erreur technique, la transaction est annulée et les fichiers déjà écrits sont
nettoyés.

Garde-fous anti « zip bomb » : nombre de nœuds borné par
``WATCH_MAX_IMPORT_NODES``, taille décompressée totale par
``WATCH_MAX_IMPORT_SIZE``, taille de chaque média par ``WATCH_MAX_UPLOAD_SIZE``.
"""

from __future__ import annotations

import io
import json
import mimetypes
import re
import uuid
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.enums import WatchMediaKind
from app.models.user import User
from app.models.watch import WatchComment, WatchMedia, WatchNode
from app.schemas.watch_transfer import (
    ARCHIVE_VERSION,
    MANIFEST_NAME,
    MEDIA_PREFIX,
    WatchArchive,
    WatchArchiveComment,
    WatchArchiveMedia,
    WatchArchiveNode,
    WatchImportError,
    WatchImportResult,
)
from app.services.watch import (
    WatchServiceError,
    _secure_filename,
    _upload_root,
)

# Taille des blocs lus lors de la copie d'un média depuis l'archive.
_CHUNK_SIZE = 1024 * 1024

# Entrée de média valide dans l'archive : ``media/<sous-dossiers>/<fichier>``,
# sans segment de remontée (``..``) ni chemin absolu.
_MEDIA_ENTRY = re.compile(r"^media/(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._\-/]+$")

# Médias correspondant à un fichier embarqué (par opposition à un lien externe).
_FILE_KINDS = (WatchMediaKind.IMAGE, WatchMediaKind.VIDEO)


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
    métadonnées sont conservées et l'import les signalera comme non restaurables
    plutôt que d'échouer.
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


# --------------------------------------------------------------------------- #
# Import — lecture de l'archive
# --------------------------------------------------------------------------- #
def _read_manifest(zf: zipfile.ZipFile | None, payload: bytes) -> WatchArchive:
    """Extrait et valide le manifeste (ZIP avec ``veille.json``, ou JSON nu).

    Lève ``WatchServiceError("bad_archive")`` (→ 400) si l'archive est illisible,
    dépourvue de manifeste, ou d'une version inconnue.
    """
    if zf is not None:
        try:
            raw = zf.read(MANIFEST_NAME)
        except KeyError as exc:
            raise WatchServiceError(
                "bad_archive", f"Archive invalide : « {MANIFEST_NAME} » est absent."
            ) from exc
    else:
        raw = payload

    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WatchServiceError("bad_archive", "Fichier illisible : JSON invalide.") from exc
    if not isinstance(data, dict):
        raise WatchServiceError("bad_archive", "Fichier illisible : objet JSON attendu.")

    version = data.get("version")
    if version != ARCHIVE_VERSION:
        raise WatchServiceError(
            "bad_archive",
            f"Version d'archive non supportée ({version!r}) ; version {ARCHIVE_VERSION} attendue.",
        )

    try:
        return WatchArchive.model_validate(data)
    except ValidationError as exc:
        raise WatchServiceError(
            "bad_archive", f"Archive invalide : {exc.error_count()} champ(s) incorrect(s)."
        ) from exc


def _check_zip_budget(zf: zipfile.ZipFile) -> None:
    """Refuse une archive dont la taille décompressée annoncée est excessive."""
    total = sum(info.file_size for info in zf.infolist())
    if total > settings.WATCH_MAX_IMPORT_SIZE:
        raise WatchServiceError(
            "bad_archive",
            f"Archive trop volumineuse une fois décompressée ({total} octets, "
            f"maximum {settings.WATCH_MAX_IMPORT_SIZE}).",
        )


def _order_refs(
    nodes: list[WatchArchiveNode], errors: list[WatchImportError]
) -> list[tuple[WatchArchiveNode, str | None]]:
    """Ordonne les nœuds parents-avant-enfants et normalise les parents douteux.

    Retourne une liste de ``(nœud, parent_ref effectif)``. Un ``parent_ref``
    inconnu, ou impliqué dans un cycle, est ramené à ``None`` (le nœud devient
    une racine) avec un avertissement — l'arbre importé reste ainsi exploitable.
    """
    by_ref = {node.ref: node for node in nodes}
    children: dict[str | None, list[WatchArchiveNode]] = defaultdict(list)

    for node in nodes:
        parent = node.parent_ref
        if parent is not None and parent not in by_ref:
            errors.append(
                WatchImportError(
                    ref=node.ref,
                    message=(
                        f"parent_ref « {parent} » introuvable dans l'archive : "
                        "nœud importé comme racine."
                    ),
                )
            )
            parent = None
        elif parent == node.ref:
            errors.append(
                WatchImportError(
                    ref=node.ref,
                    message="parent_ref pointe sur le nœud lui-même : nœud importé comme racine.",
                )
            )
            parent = None
        children[parent].append(node)

    # Parcours en largeur depuis les racines : garantit parents avant enfants.
    ordered: list[tuple[WatchArchiveNode, str | None]] = []
    frontier = list(children[None])
    ordered.extend((node, None) for node in frontier)
    seen = {node.ref for node in frontier}
    while frontier:
        next_frontier: list[WatchArchiveNode] = []
        for parent in frontier:
            for child in children[parent.ref]:
                if child.ref in seen:
                    continue
                seen.add(child.ref)
                ordered.append((child, parent.ref))
                next_frontier.append(child)
        frontier = next_frontier

    # Non atteints depuis une racine : cycle de parents → rattachés à la racine.
    for node in nodes:
        if node.ref not in seen:
            seen.add(node.ref)
            errors.append(
                WatchImportError(
                    ref=node.ref,
                    message="cycle de parents détecté : nœud importé comme racine.",
                )
            )
            ordered.append((node, None))
    return ordered


# --------------------------------------------------------------------------- #
# Import — écriture
# --------------------------------------------------------------------------- #
def _users_by_email(db: Session, emails: set[str]) -> dict[str, int]:
    """Map ``e-mail (minuscule) -> user_id`` pour les e-mails cités par l'archive."""
    if not emails:
        return {}
    stmt = select(User).where(func.lower(User.email).in_({e.lower() for e in emails}))
    return {user.email.lower(): user.id for user in db.execute(stmt).scalars()}


class _MediaWriter:
    """Copie les médias de l'archive sur disque en bornant la volumétrie.

    Suit les fichiers écrits pour pouvoir les effacer si la transaction échoue,
    et refuse de dépasser ``WATCH_MAX_IMPORT_SIZE`` cumulés.
    """

    def __init__(self, zf: zipfile.ZipFile | None) -> None:
        self._zf = zf
        self._names = set(zf.namelist()) if zf is not None else set()
        self._root = _upload_root()
        self._budget = settings.WATCH_MAX_IMPORT_SIZE
        self.written: list[Path] = []

    def entry_is_usable(self, path: str | None) -> bool:
        """Vrai si ``path`` désigne une entrée de média exploitable de l'archive."""
        return (
            self._zf is not None
            and path is not None
            and bool(_MEDIA_ENTRY.match(path))
            and path in self._names
        )

    def copy(self, node_id: int, entry: str, filename: str | None) -> tuple[str, int]:
        """Copie l'entrée ``entry`` sous ``watch/{node_id}/{uuid}_{nom}``.

        Retourne ``(chemin relatif, taille)``. Lève ``WatchServiceError`` avec le
        code ``too_large`` si le média ou le cumul dépasse les bornes.
        """
        assert self._zf is not None
        safe_name = _secure_filename(filename or Path(entry).name)
        relative = f"{node_id}/{uuid.uuid4().hex}_{safe_name}"
        target = self._root / relative
        target.parent.mkdir(parents=True, exist_ok=True)

        max_size = min(settings.WATCH_MAX_UPLOAD_SIZE, self._budget)
        size = 0
        try:
            with self._zf.open(entry) as src, target.open("wb") as out:
                while True:
                    chunk = src.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_size:
                        raise WatchServiceError(
                            "too_large",
                            f"média « {safe_name} » trop volumineux (maximum {max_size} octets)",
                        )
                    out.write(chunk)
        except WatchServiceError:
            target.unlink(missing_ok=True)
            raise
        except (OSError, zipfile.BadZipFile) as exc:
            target.unlink(missing_ok=True)
            raise WatchServiceError(
                "bad_archive", f"média « {safe_name} » illisible dans l'archive"
            ) from exc

        self._budget -= size
        self.written.append(target)
        return relative, size

    def cleanup(self) -> None:
        """Efface les fichiers écrits (appelé si la transaction est annulée)."""
        for path in self.written:
            path.unlink(missing_ok=True)
        self.written.clear()


def _content_type_for(media: WatchArchiveMedia, filename: str | None) -> str:
    """Content-type d'un média importé : celui de l'archive s'il est cohérent.

    Sinon déduit de l'extension, avec repli sur ``application/octet-stream`` —
    le ``kind`` (image/vidéo) reste celui déclaré par l'archive.
    """
    expected_prefix = f"{media.kind.value}/"
    declared = (media.content_type or "").lower()
    if declared.startswith(expected_prefix):
        return media.content_type or "application/octet-stream"
    guessed, _ = mimetypes.guess_type(filename or "")
    if guessed and guessed.lower().startswith(expected_prefix):
        return guessed
    return "application/octet-stream"


def _purge_existing(db: Session) -> list[Path]:
    """Supprime tous les nœuds de veille et retourne les fichiers à effacer.

    Les lignes sont supprimées dans la transaction courante (cascade sur les
    médias et commentaires) ; les fichiers ne sont effacés qu'après le commit,
    par l'appelant, pour ne rien perdre si l'import échoue.
    """
    root = _upload_root()
    stale: list[Path] = []
    for stored_path in (
        db.execute(select(WatchMedia.stored_path).where(WatchMedia.stored_path.is_not(None)))
        .scalars()
        .all()
    ):
        path = (root / stored_path).resolve()
        if path.is_relative_to(root):
            stale.append(path)
    for node in db.execute(select(WatchNode)).scalars().all():
        db.delete(node)
    db.flush()
    return stale


def import_archive(
    db: Session,
    payload: bytes,
    actor: User,
    *,
    replace: bool = False,
) -> WatchImportResult:
    """Importe une archive de veille (ZIP, ou manifeste JSON nu).

    :param replace: si ``True``, la veille existante (nœuds, médias, commentaires)
        est supprimée avant l'import. L'autorisation (admin global) est vérifiée
        en amont par la couche endpoint.
    :raises WatchServiceError: ``bad_archive`` (→ 400) si l'archive est illisible,
        d'une version inconnue, trop volumineuse ou dépasse le nombre de nœuds.

    Les nœuds sont créés parents-avant-enfants ; les médias fichiers sont
    recopiés sous ``uploads/watch/{node_id}/``, les liens externes réinsérés
    tels quels. Un nœud est attribué à l'utilisateur de ``created_by_email`` s'il
    existe sur l'instance, sinon à l'importateur ; un commentaire dont l'auteur
    est inconnu est conservé sans auteur.
    """
    zf: zipfile.ZipFile | None = None
    if zipfile.is_zipfile(io.BytesIO(payload)):
        try:
            zf = zipfile.ZipFile(io.BytesIO(payload))
        except zipfile.BadZipFile as exc:
            raise WatchServiceError("bad_archive", "Archive ZIP illisible.") from exc
        _check_zip_budget(zf)

    try:
        manifest = _read_manifest(zf, payload)

        if len(manifest.nodes) > settings.WATCH_MAX_IMPORT_NODES:
            raise WatchServiceError(
                "bad_archive",
                f"Trop de nœuds ({len(manifest.nodes)}), "
                f"maximum {settings.WATCH_MAX_IMPORT_NODES}.",
            )

        errors: list[WatchImportError] = []
        # Refs dupliquées : la première gagne, les suivantes sont ignorées.
        unique_nodes: list[WatchArchiveNode] = []
        seen_refs: set[str] = set()
        for node in manifest.nodes:
            if node.ref in seen_refs:
                errors.append(
                    WatchImportError(ref=node.ref, message="ref dupliquée : nœud ignoré.")
                )
                continue
            seen_refs.add(node.ref)
            unique_nodes.append(node)

        emails = {n.created_by_email for n in unique_nodes if n.created_by_email}
        emails |= {c.author_email for n in unique_nodes for c in n.comments if c.author_email}
        user_ids = _users_by_email(db, emails)

        stale_files: list[Path] = _purge_existing(db) if replace else []
        writer = _MediaWriter(zf)
        ref_to_id: dict[str, int] = {}
        media_created = 0
        comments_created = 0

        try:
            for archive_node, parent_ref in _order_refs(unique_nodes, errors):
                node = WatchNode(
                    parent_id=ref_to_id.get(parent_ref) if parent_ref is not None else None,
                    title=archive_node.title,
                    type=archive_node.type,
                    note=archive_node.note,
                    status=archive_node.status,
                    pos_x=archive_node.pos_x,
                    pos_y=archive_node.pos_y,
                    created_by_id=(
                        user_ids.get((archive_node.created_by_email or "").lower()) or actor.id
                    ),
                )
                db.add(node)
                db.flush()
                ref_to_id[archive_node.ref] = node.id

                media_created += _import_media(
                    db, node, archive_node, writer=writer, actor=actor, errors=errors
                )
                comments_created += _import_comments(db, node, archive_node, user_ids=user_ids)

            db.commit()
        except Exception:
            db.rollback()
            writer.cleanup()
            raise

        # Commit acquis : les fichiers de l'ancienne veille peuvent partir.
        for path in stale_files:
            path.unlink(missing_ok=True)

        return WatchImportResult(
            nodes_created=len(ref_to_id),
            media_created=media_created,
            comments_created=comments_created,
            replaced=replace,
            error_count=len(errors),
            errors=errors,
        )
    finally:
        if zf is not None:
            zf.close()


def _import_media(
    db: Session,
    node: WatchNode,
    archive_node: WatchArchiveNode,
    *,
    writer: _MediaWriter,
    actor: User,
    errors: list[WatchImportError],
) -> int:
    """Recrée les médias d'un nœud. Retourne le nombre de médias créés.

    Un média invalide (lien sans URL, fichier absent de l'archive, fichier trop
    volumineux) est ignoré et signalé — les autres sont créés.
    """
    created = 0
    for media in archive_node.media:
        if media.kind == WatchMediaKind.LINK:
            if not media.url:
                errors.append(
                    WatchImportError(ref=archive_node.ref, message="lien sans URL : média ignoré.")
                )
                continue
            db.add(
                WatchMedia(
                    node_id=node.id,
                    kind=WatchMediaKind.LINK,
                    url=media.url,
                    title=media.title,
                    created_by_id=actor.id,
                )
            )
            created += 1
            continue

        if media.kind not in _FILE_KINDS:
            errors.append(
                WatchImportError(
                    ref=archive_node.ref,
                    message=f"type de média inconnu « {media.kind} » : média ignoré.",
                )
            )
            continue

        if not writer.entry_is_usable(media.path):
            errors.append(
                WatchImportError(
                    ref=archive_node.ref,
                    message=(
                        f"fichier « {media.filename or media.path or '?'} » absent de "
                        "l'archive : média ignoré."
                    ),
                )
            )
            continue

        assert media.path is not None
        try:
            relative, size = writer.copy(node.id, media.path, media.filename)
        except WatchServiceError as exc:
            errors.append(
                WatchImportError(ref=archive_node.ref, message=f"{exc.message} : média ignoré.")
            )
            continue

        db.add(
            WatchMedia(
                node_id=node.id,
                kind=media.kind,
                filename=_secure_filename(media.filename or Path(media.path).name),
                stored_path=relative,
                content_type=_content_type_for(media, media.filename),
                size=size,
                title=media.title,
                created_by_id=actor.id,
            )
        )
        created += 1
    return created


def _import_comments(
    db: Session,
    node: WatchNode,
    archive_node: WatchArchiveNode,
    *,
    user_ids: dict[str, int],
) -> int:
    """Recrée les commentaires d'un nœud (auteur conservé si l'e-mail existe)."""
    created = 0
    for comment in archive_node.comments:
        db.add(
            WatchComment(
                node_id=node.id,
                author_id=user_ids.get((comment.author_email or "").lower()),
                body=comment.body,
            )
        )
        created += 1
    return created
