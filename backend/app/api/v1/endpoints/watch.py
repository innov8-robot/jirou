"""Endpoints du domaine VEILLE (base de connaissances R&D en arbre/graphe).

Fonctionnalité **globale** (non rattachée à un projet) : tout utilisateur
connecté peut lister, créer, éditer et commenter. La suppression d'un nœud, d'un
média ou d'un commentaire est réservée à son **créateur** ou à un **admin global**.

Familles de routes (préfixe ``/api/v1/watch``) :

- ``/watch/nodes`` : arbre à plat (graphe), CRUD d'un nœud (cascade du sous-arbre
  à la suppression, détection de cycle au changement de parent) ;
- ``/watch/nodes/{id}/media`` et ``/watch/media/{id}`` : médias (upload image/vidéo,
  lien externe, téléchargement sécurisé anti-traversal, suppression) ;
- ``/watch/nodes/{id}/comments`` et ``/watch/comments/{id}`` : fil de commentaires ;
- ``/watch/export`` : archive ZIP complète (arbre + fichiers), pour sauvegarde ;
- ``/watch/nodes/{id}/import`` : greffe une branche sous un nœud depuis un CSV.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.models.watch import WatchComment, WatchMedia, WatchNode
from app.schemas.issue import MiniUser
from app.schemas.watch import (
    MediaPreview,
    WatchCommentCreate,
    WatchCommentRead,
    WatchCommentUpdate,
    WatchMediaLinkCreate,
    WatchMediaRead,
    WatchNodeCreate,
    WatchNodeRead,
    WatchNodeSummary,
    WatchNodeUpdate,
)
from app.schemas.watch_csv import WatchCsvImportResult
from app.services import watch as watch_service
from app.services import watch_csv as watch_csv_service
from app.services import watch_transfer as transfer_service
from app.services.watch import WatchServiceError

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

_NODE_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nœud introuvable.")
_MEDIA_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Média introuvable.")
_COMMENT_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Commentaire introuvable."
)

# Erreurs métier -> codes HTTP.
_ERROR_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "too_large": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    "unsupported_media_type": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    "cycle": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "bad_archive": status.HTTP_400_BAD_REQUEST,
}


def _http_error(exc: WatchServiceError) -> HTTPException:
    """Traduit une erreur métier en :class:`HTTPException`."""
    return HTTPException(
        status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=exc.message,
    )


def _media_download_url(media: WatchMedia) -> str | None:
    """URL de téléchargement pour un upload (image/vidéo), ``None`` pour un lien."""
    if media.stored_path is None:
        return None
    return f"{settings.API_V1_PREFIX}/watch/media/{media.id}/download"


def _serialize_media(media: WatchMedia) -> WatchMediaRead:
    """Sérialise un média (``download_url`` seulement pour un upload)."""
    download_url = _media_download_url(media)
    return WatchMediaRead(
        id=media.id,
        node_id=media.node_id,
        kind=media.kind,
        filename=media.filename,
        content_type=media.content_type,
        size=media.size,
        url=media.url,
        title=media.title,
        download_url=download_url,
        created_at=media.created_at,
    )


def _serialize_preview(node: WatchNode) -> MediaPreview | None:
    """Aperçu du premier média du nœud (par ``created_at`` croissant), ou ``None``.

    Repose sur ``WatchNode.media`` (ordonné par ``created_at, id``) chargé en amont.
    """
    if not node.media:
        return None
    media = node.media[0]
    return MediaPreview(
        media_id=media.id,
        kind=media.kind,
        url=media.url,
        download_url=_media_download_url(media),
        content_type=media.content_type,
    )


def _serialize_node(node: WatchNode) -> WatchNodeRead:
    """Sérialise un nœud avec ses médias."""
    return WatchNodeRead(
        id=node.id,
        parent_id=node.parent_id,
        title=node.title,
        type=node.type,
        note=node.note,
        status=node.status,
        pos_x=node.pos_x,
        pos_y=node.pos_y,
        created_by=MiniUser.model_validate(node.created_by) if node.created_by else None,
        created_at=node.created_at,
        updated_at=node.updated_at,
        media=[_serialize_media(m) for m in node.media],
    )


# --------------------------------------------------------------------------- #
# Dépendances locales : résolution par identifiant
# --------------------------------------------------------------------------- #
def get_node_or_404(node_id: int, current_user: CurrentUser, db: DbSession) -> WatchNode:
    """Résout un nœud par identifiant (404 sinon), **après** authentification.

    Dépendre de ``CurrentUser`` ici n'est pas décoratif : sans cela, la
    résolution du nœud précède le contrôle du jeton et un appelant anonyme
    distingue un 404 (nœud absent) d'un 401 (nœud existant) — de quoi énumérer
    les identifiants de la veille. L'ordre est ainsi garanti pour **toutes** les
    routes qui utilisent ``NodeDep``.
    """
    node = watch_service.get_node(db, node_id)
    if node is None:
        raise _NODE_NOT_FOUND
    return node


NodeDep = Annotated[WatchNode, Depends(get_node_or_404)]


def _require_owner_or_admin(owner_id: int | None, user: User, action: str) -> None:
    """Autorise le créateur/auteur (``owner_id``) ou un admin global, 403 sinon."""
    if owner_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{action} réservée au créateur ou à un admin global.",
        )


# --------------------------------------------------------------------------- #
# Nœuds
# --------------------------------------------------------------------------- #
@router.get("/nodes", response_model=list[WatchNodeSummary], summary="Lister tous les nœuds")
def list_nodes(current_user: CurrentUser, db: DbSession) -> list[WatchNodeSummary]:
    """Tous les nœuds (arbre à plat) pour construire le graphe côté frontend."""
    nodes = watch_service.list_nodes(db)
    media_counts = watch_service.media_counts(db)
    comment_counts = watch_service.comment_counts(db)
    return [
        WatchNodeSummary(
            id=node.id,
            parent_id=node.parent_id,
            title=node.title,
            type=node.type,
            status=node.status,
            pos_x=node.pos_x,
            pos_y=node.pos_y,
            media_count=media_counts.get(node.id, 0),
            comment_count=comment_counts.get(node.id, 0),
            preview=_serialize_preview(node),
        )
        for node in nodes
    ]


@router.post(
    "/nodes",
    response_model=WatchNodeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un nœud",
)
def create_node(data: WatchNodeCreate, current_user: CurrentUser, db: DbSession) -> WatchNodeRead:
    """Crée un nœud (racine si ``parent_id`` absent). 404 si le parent est inconnu."""
    try:
        node = watch_service.create_node(db, data, current_user)
    except WatchServiceError as exc:
        raise _http_error(exc) from exc
    return _serialize_node(node)


@router.get("/nodes/{node_id}", response_model=WatchNodeRead, summary="Détail d'un nœud")
def get_node(node: NodeDep, current_user: CurrentUser) -> WatchNodeRead:
    """Détail d'un nœud avec ses médias. 404 si le nœud est inconnu."""
    return _serialize_node(node)


@router.patch("/nodes/{node_id}", response_model=WatchNodeRead, summary="Modifier un nœud")
def update_node(
    data: WatchNodeUpdate, node: NodeDep, current_user: CurrentUser, db: DbSession
) -> WatchNodeRead:
    """Mise à jour partielle. 422 si ``parent_id`` crée un cycle ; 404 si parent inconnu."""
    try:
        node = watch_service.update_node(db, node, data)
    except WatchServiceError as exc:
        raise _http_error(exc) from exc
    return _serialize_node(node)


@router.delete(
    "/nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un nœud (cascade du sous-arbre)",
)
def delete_node(node: NodeDep, current_user: CurrentUser, db: DbSession) -> None:
    """Supprime un nœud et son sous-arbre. Réservé au créateur ou à un admin global."""
    _require_owner_or_admin(node.created_by_id, current_user, "Suppression")
    watch_service.delete_node(db, node)


# --------------------------------------------------------------------------- #
# Export (archive ZIP) & import CSV ancré
# --------------------------------------------------------------------------- #
def _read_bounded(file: UploadFile, max_size: int, label: str) -> bytes:
    """Lit un fichier téléversé en bornant sa taille (413 au-delà)."""
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{label} trop volumineux (maximum {max_size} octets).",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/export", summary="Exporter toute la veille (archive ZIP)")
def export_watch(current_user: CurrentUser, db: DbSession) -> Response:
    """Renvoie une archive ZIP contenant ``veille.json`` et les fichiers ``media/``.

    L'archive porte l'arbre complet (titres, types, statuts, positions, notes,
    liens externes, commentaires) et les images/vidéos téléversées ; elle est
    réimportable telle quelle via ``POST /watch/import``.
    """
    content = transfer_service.export_archive(db, source=settings.PROJECT_NAME)
    filename = transfer_service.export_filename()
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/nodes/{node_id}/import",
    response_model=WatchCsvImportResult,
    summary="Importer des sous-nœuds sous un nœud (CSV)",
)
def import_children(
    node: NodeDep,
    current_user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
) -> WatchCsvImportResult:
    """Greffe une branche sous ``node`` depuis un CSV (multipart ``file``).

    En-tête : ``title,parent,type,status,note,links``. Seul ``title`` est
    obligatoire ; ``parent`` référence le titre d'une autre ligne du fichier
    (vide = enfant direct du nœud choisi), ce qui permet de décrire un sous-arbre
    sans connaître les identifiants de la base.

    L'import est robuste : une ligne invalide est ignorée et signalée dans
    ``errors``, un parent introuvable ou cyclique est rattaché au nœud choisi
    avec un avertissement, et le reste du lot est créé.

    - 400 si le CSV est illisible, vide, d'en-tête invalide ou trop long ;
    - 404 si le nœud est inconnu ; 413 si le fichier est trop volumineux.
    """
    csv_bytes = _read_bounded(file, settings.WATCH_MAX_CSV_SIZE, "Fichier")
    try:
        return watch_csv_service.import_children_from_csv(db, node, csv_bytes, current_user)
    except WatchServiceError as exc:
        raise _http_error(exc) from exc


# --------------------------------------------------------------------------- #
# Médias
# --------------------------------------------------------------------------- #
@router.get(
    "/nodes/{node_id}/media",
    response_model=list[WatchMediaRead],
    summary="Lister les médias d'un nœud",
)
def list_media(node: NodeDep, current_user: CurrentUser, db: DbSession) -> list[WatchMediaRead]:
    """Médias d'un nœud (plus ancien d'abord)."""
    return [_serialize_media(m) for m in watch_service.list_media(db, node)]


@router.post(
    "/nodes/{node_id}/media",
    response_model=WatchMediaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Téléverser un média (image/vidéo)",
)
def upload_media(
    node: NodeDep,
    current_user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
) -> WatchMediaRead:
    """Téléverse un fichier (multipart ``file``). ``kind`` déduit du content-type.

    - 415 si le type n'est ni ``image/*`` ni ``video/*`` ;
    - 413 si le fichier dépasse ``WATCH_MAX_UPLOAD_SIZE``.
    """
    try:
        media = watch_service.save_upload(
            db,
            node,
            source=file.file,
            filename=file.filename,
            content_type=file.content_type,
            uploader=current_user,
        )
    except WatchServiceError as exc:
        raise _http_error(exc) from exc
    return _serialize_media(media)


@router.post(
    "/nodes/{node_id}/media/link",
    response_model=WatchMediaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un lien externe",
)
def create_media_link(
    data: WatchMediaLinkCreate, node: NodeDep, current_user: CurrentUser, db: DbSession
) -> WatchMediaRead:
    """Ajoute un lien externe (kind=``link``), ex. une vidéo YouTube."""
    media = watch_service.create_link(
        db, node, url=data.url, title=data.title, creator=current_user
    )
    return _serialize_media(media)


@router.get("/media/{media_id}/download", summary="Télécharger un média")
def download_media(media_id: int, current_user: CurrentUser, db: DbSession) -> FileResponse:
    """Renvoie le contenu binaire d'un média téléversé (anti-traversal).

    - 404 si le média est inconnu, si c'est un lien, ou si le fichier est absent.
    """
    media = watch_service.get_media(db, media_id)
    if media is None:
        raise _MEDIA_NOT_FOUND
    try:
        path = watch_service.resolve_path(media)
    except WatchServiceError as exc:
        raise _http_error(exc) from exc
    return FileResponse(
        path,
        media_type=media.content_type or "application/octet-stream",
        filename=media.filename or "file",
    )


@router.delete(
    "/media/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un média",
)
def delete_media(media_id: int, current_user: CurrentUser, db: DbSession) -> None:
    """Supprime un média. Réservé au créateur ou à un admin global."""
    media = watch_service.get_media(db, media_id)
    if media is None:
        raise _MEDIA_NOT_FOUND
    _require_owner_or_admin(media.created_by_id, current_user, "Suppression")
    watch_service.delete_media(db, media)


# --------------------------------------------------------------------------- #
# Commentaires
# --------------------------------------------------------------------------- #
@router.get(
    "/nodes/{node_id}/comments",
    response_model=list[WatchCommentRead],
    summary="Lister les commentaires d'un nœud",
)
def list_comments(
    node: NodeDep, current_user: CurrentUser, db: DbSession
) -> list[WatchCommentRead]:
    """Fil chronologique des commentaires (plus ancien d'abord)."""
    return [WatchCommentRead.model_validate(c) for c in watch_service.list_comments(db, node)]


@router.post(
    "/nodes/{node_id}/comments",
    response_model=WatchCommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un commentaire",
)
def create_comment(
    data: WatchCommentCreate, node: NodeDep, current_user: CurrentUser, db: DbSession
) -> WatchCommentRead:
    """Crée un commentaire sur un nœud."""
    comment = watch_service.create_comment(db, node, current_user, data.body)
    return WatchCommentRead.model_validate(comment)


def _get_comment_or_404(comment_id: int, db: Session) -> WatchComment:
    comment = watch_service.get_comment(db, comment_id)
    if comment is None:
        raise _COMMENT_NOT_FOUND
    return comment


@router.patch(
    "/comments/{comment_id}",
    response_model=WatchCommentRead,
    summary="Modifier un commentaire",
)
def update_comment(
    comment_id: int, data: WatchCommentUpdate, current_user: CurrentUser, db: DbSession
) -> WatchCommentRead:
    """Modifie un commentaire. Réservé à l'auteur ou à un admin global (403 sinon)."""
    comment = _get_comment_or_404(comment_id, db)
    _require_owner_or_admin(comment.author_id, current_user, "Édition")
    comment = watch_service.update_comment(db, comment, data.body)
    return WatchCommentRead.model_validate(comment)


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un commentaire",
)
def delete_comment(comment_id: int, current_user: CurrentUser, db: DbSession) -> None:
    """Supprime un commentaire. Réservé à l'auteur ou à un admin global (403 sinon)."""
    comment = _get_comment_or_404(comment_id, db)
    _require_owner_or_admin(comment.author_id, current_user, "Suppression")
    watch_service.delete_comment(db, comment)
