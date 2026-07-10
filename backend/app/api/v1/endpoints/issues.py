"""Endpoints de gestion des tickets (EPIC-05, JIR-32 à JIR-35).

Deux familles de routes :

- sous ``/api/v1/projects/{project_id}/issues`` (création, liste) — réutilisent
  les dépendances projet de ``app.api.deps`` ;
- sous ``/api/v1/issues/{key}`` (détail, mise à jour, suppression) — résolvent
  l'issue par sa clé puis vérifient l'appartenance au projet via des
  dépendances locales.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    CurrentUser,
    ProjectContext,
    get_project_membership,
    require_project_role,
)
from app.core.database import get_db
from app.models.enums import IssueStatus, IssueType, ProjectRole, UserRole
from app.models.issue import Issue
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.import_csv import ImportResult
from app.schemas.issue import (
    BoardColumn,
    BoardRead,
    DependencyLink,
    IssueCreate,
    IssueDetail,
    IssueMove,
    IssueProgress,
    IssueRead,
    IssueUpdate,
    MiniIssue,
)
from app.schemas.sprint import BacklogMove
from app.schemas.timeline import (
    DependencyCreate,
    DependencyRead,
    TimelineDependency,
    TimelineEpic,
    TimelineRead,
)
from app.services import comment as comment_service
from app.services import dependency as dependency_service
from app.services import issue as issue_service
from app.services import issue_import as issue_import_service
from app.services import rag_hooks
from app.services import sprint as sprint_service
from app.services import timeline as timeline_service
from app.services.dependency import DependencyServiceError
from app.services.issue import IssueServiceError
from app.services.project import get_membership
from app.services.sprint import SprintServiceError

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

# Erreurs métier -> codes HTTP.
_ERROR_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "conflict": status.HTTP_409_CONFLICT,
    "validation": status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _raise_service_error(exc: IssueServiceError) -> None:
    raise HTTPException(
        status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=exc.message,
    )


_ISSUE_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Ticket introuvable."
)
_ISSUE_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Accès refusé : vous n'êtes pas membre de ce projet.",
)
_VIEWER_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Un viewer ne peut pas modifier les tickets.",
)


# --------------------------------------------------------------------------- #
# Dépendances locales : résolution d'une issue par clé
# --------------------------------------------------------------------------- #
@dataclass
class IssueContext:
    """Contexte d'accès à une issue résolue par clé."""

    issue: Issue
    project: Project
    membership: ProjectMember | None
    current_user: User


def get_issue_context(key: str, current_user: CurrentUser, db: DbSession) -> IssueContext:
    """Résout l'issue par clé et exige que l'appelant soit membre du projet.

    - 404 si la clé est inconnue.
    - 403 si l'appelant n'est ni membre du projet ni admin global.
    """
    issue = issue_service.get_issue_by_key(db, key)
    if issue is None:
        raise _ISSUE_NOT_FOUND
    project = db.get(Project, issue.project_id)
    membership = get_membership(db, project.id, current_user.id)
    if membership is None and current_user.role != UserRole.ADMIN:
        raise _ISSUE_FORBIDDEN
    return IssueContext(
        issue=issue, project=project, membership=membership, current_user=current_user
    )


def require_issue_writer(
    ctx: Annotated[IssueContext, Depends(get_issue_context)],
) -> IssueContext:
    """Comme :func:`get_issue_context` mais interdit les viewers (403)."""
    if ctx.membership is not None and ctx.membership.role == ProjectRole.VIEWER:
        raise _VIEWER_FORBIDDEN
    return ctx


def _serialize_dependency(dependency) -> DependencyRead:  # noqa: ANN001
    """Sérialise une dépendance ORM en ``DependencyRead`` (``from`` bloque ``to``)."""
    return DependencyRead(
        id=dependency.id,
        type=dependency.type,
        from_=MiniIssue.model_validate(dependency.from_issue),
        to=MiniIssue.model_validate(dependency.to_issue),
    )


def _dependency_links(db: Session, issue: Issue) -> list[DependencyLink]:
    """Construit les liens de dépendance vus depuis ``issue`` (outward/inward)."""
    links: list[DependencyLink] = []
    for dep in dependency_service.list_links_for_issue(db, issue):
        if dep.from_issue_id == issue.id:
            links.append(
                DependencyLink(
                    id=dep.id,
                    type=dep.type,
                    direction="outward",
                    issue=MiniIssue.model_validate(dep.to_issue),
                )
            )
        else:
            links.append(
                DependencyLink(
                    id=dep.id,
                    type=dep.type,
                    direction="inward",
                    issue=MiniIssue.model_validate(dep.from_issue),
                )
            )
    return links


def _serialize_detail(db: Session, issue: Issue) -> IssueDetail:
    """Sérialise une issue en ``IssueDetail`` (enfants, progression epic, dépendances)."""
    detail = IssueDetail.model_validate(issue)
    if issue.type == IssueType.EPIC:
        children = issue_service.get_children(db, issue)
        detail.children = [IssueRead.model_validate(child) for child in children]
        done, total = issue_service.get_progress(db, issue)
        detail.progress = IssueProgress(done=done, total=total)
    detail.dependencies = _dependency_links(db, issue)
    return detail


# --------------------------------------------------------------------------- #
# Routes rattachées au projet
# --------------------------------------------------------------------------- #
project_router = APIRouter()


@project_router.post(
    "/{project_id}/issues",
    response_model=IssueRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un ticket",
)
def create_issue(
    data: IssueCreate,
    db: DbSession,
    background: BackgroundTasks,
    # membre du projet mais PAS viewer.
    ctx: Annotated[
        ProjectContext,
        Depends(require_project_role(ProjectRole.ADMIN, ProjectRole.MEMBER)),
    ],
) -> IssueRead:
    """Crée un ticket. Clé auto-générée, reporter = utilisateur courant.

    - 403 si viewer projet, 404 si projet inconnu, 422 si validation échoue.

    Indexe le ticket dans le RAG en tâche de fond (best-effort).
    """
    try:
        issue = issue_service.create_issue(db, ctx.project, data, ctx.current_user)
    except IssueServiceError as exc:
        _raise_service_error(exc)
    background.add_task(rag_hooks.index_issue, issue.id)
    return IssueRead.model_validate(issue)


@project_router.post(
    "/{project_id}/issues/import",
    response_model=ImportResult,
    summary="Importer des tickets depuis un CSV",
)
def import_issues(
    db: DbSession,
    background: BackgroundTasks,
    # membre du projet mais PAS viewer.
    ctx: Annotated[
        ProjectContext,
        Depends(require_project_role(ProjectRole.ADMIN, ProjectRole.MEMBER)),
    ],
    file: Annotated[UploadFile, File()],
    epic_id: Annotated[int | None, Form()] = None,
) -> ImportResult:
    """Importe des tickets depuis un fichier CSV (multipart ``file``).

    Chaque ligne est validée indépendamment : une ligne invalide est ignorée et
    signalée dans ``errors`` (avec avertissements non bloquants), les autres sont
    créées. Le champ de formulaire optionnel ``epic_id`` rattache les lignes qui
    ne fournissent pas leur propre ``epic_key`` à une epic du projet.

    - 400 si le CSV est illisible/vide, d'en-tête invalide ou trop volumineux ;
    - 403 si viewer projet, 404 si projet inconnu ;
    - 422 si ``epic_id`` ne désigne pas une epic du projet.
    """
    csv_bytes = file.file.read()
    try:
        result = issue_import_service.import_issues_from_csv(
            db, ctx.project, csv_bytes, ctx.current_user, target_epic_id=epic_id
        )
    except IssueServiceError as exc:
        _raise_service_error(exc)
    background.add_task(rag_hooks.index_issues_bulk, [issue.id for issue in result.issues])
    return result


@project_router.get(
    "/{project_id}/issues",
    response_model=list[IssueRead],
    summary="Lister les tickets d'un projet",
)
def list_issues(
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
    type: Annotated[IssueType | None, Query()] = None,
    status: Annotated[IssueStatus | None, Query()] = None,
    assignee_id: Annotated[int | None, Query()] = None,
    label_id: Annotated[int | None, Query()] = None,
    epic_id: Annotated[int | None, Query()] = None,
    sprint_id: Annotated[int | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    sort: Annotated[str | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[IssueRead]:
    """Liste filtrable/triable/paginée des tickets. Réservé aux membres."""
    try:
        issues = issue_service.list_issues(
            db,
            ctx.project,
            type=type,
            status=status,
            assignee_id=assignee_id,
            label_id=label_id,
            epic_id=epic_id,
            sprint_id=sprint_id,
            search=search,
            sort=sort,
            skip=skip,
            limit=limit,
        )
    except IssueServiceError as exc:
        _raise_service_error(exc)
    return [IssueRead.model_validate(issue) for issue in issues]


@project_router.get(
    "/{project_id}/board",
    response_model=BoardRead,
    summary="Board Kanban d'un projet",
)
def get_project_board(
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
    assignee_id: Annotated[int | None, Query()] = None,
    type: Annotated[IssueType | None, Query()] = None,
    label_id: Annotated[int | None, Query()] = None,
    epic_id: Annotated[int | None, Query()] = None,
    sprint_id: Annotated[int | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> BoardRead:
    """Tickets groupés par statut pour un board Kanban. Réservé aux membres.

    Renvoie toujours les 4 colonnes (``todo``, ``in_progress``, ``in_review``,
    ``done``) dans cet ordre, même vides. Filtres optionnels cumulables. Le
    filtre ``sprint_id`` sert au board Scrum du sprint actif (EPIC-07).
    """
    grouped = issue_service.get_board(
        db,
        ctx.project,
        assignee_id=assignee_id,
        type=type,
        label_id=label_id,
        epic_id=epic_id,
        sprint_id=sprint_id,
        search=search,
    )
    columns = [
        BoardColumn(
            status=status_,
            issues=[IssueRead.model_validate(issue) for issue in grouped[status_]],
        )
        for status_ in issue_service.BOARD_STATUS_ORDER
    ]
    return BoardRead(columns=columns)


@project_router.get(
    "/{project_id}/timeline",
    response_model=TimelineRead,
    summary="Données de timeline / roadmap d'un projet (EPIC-08, JIR-56)",
)
def get_project_timeline(
    db: DbSession,
    ctx: Annotated[ProjectContext, Depends(get_project_membership)],
) -> TimelineRead:
    """Epics du projet (dates, enfants, progression) + dépendances epic↔epic.

    Réservé aux membres du projet (403 non-membre, 404 projet inconnu). Les epics
    sans dates sont renvoyés (le front gère l'absence de dates). Requêtes
    eager-loadées (pas de N+1).
    """
    data = timeline_service.build_timeline(db, ctx.project)
    return TimelineRead(
        epics=[
            TimelineEpic(
                epic=IssueRead.model_validate(item.epic),
                children=[IssueRead.model_validate(child) for child in item.children],
                progress=IssueProgress(done=item.done, total=item.total),
            )
            for item in data.epics
        ],
        dependencies=[
            TimelineDependency(from_key=from_key, to_key=to_key)
            for from_key, to_key in data.dependencies
        ],
    )


# --------------------------------------------------------------------------- #
# Routes rattachées à la clé de l'issue
# --------------------------------------------------------------------------- #
@router.get(
    "/{key}",
    response_model=IssueDetail,
    summary="Détail d'un ticket par clé",
)
def get_issue(
    db: DbSession,
    ctx: Annotated[IssueContext, Depends(get_issue_context)],
) -> IssueDetail:
    """Détail d'un ticket (avec enfants + progression si epic). Réservé aux membres."""
    return _serialize_detail(db, ctx.issue)


@router.patch(
    "/{key}",
    response_model=IssueDetail,
    summary="Mettre à jour un ticket",
)
def update_issue(
    data: IssueUpdate,
    db: DbSession,
    background: BackgroundTasks,
    ctx: Annotated[IssueContext, Depends(require_issue_writer)],
) -> IssueDetail:
    """Mise à jour partielle d'un ticket. Interdit aux viewers (403), 422 si invalide.

    Réindexe le ticket dans le RAG en tâche de fond (best-effort ; ignoré si le
    texte n'a pas changé grâce au hash).
    """
    try:
        issue = issue_service.update_issue(db, ctx.issue, data, actor=ctx.current_user)
    except IssueServiceError as exc:
        _raise_service_error(exc)
    background.add_task(rag_hooks.index_issue, issue.id)
    return _serialize_detail(db, issue)


@router.patch(
    "/{key}/move",
    response_model=IssueRead,
    summary="Déplacer/réordonner une issue (drag & drop)",
)
def move_issue(
    data: IssueMove,
    db: DbSession,
    background: BackgroundTasks,
    ctx: Annotated[IssueContext, Depends(require_issue_writer)],
) -> IssueRead:
    """Place l'issue au statut/rang cibles et renormalise les colonnes touchées.

    - 403 pour un viewer projet, 404 si la clé est inconnue, 422 si le statut est
      invalide. ``position`` hors bornes est clampé (pas d'erreur).

    Le statut fait partie du texte indexé : on réindexe en tâche de fond (le hash
    évite tout embed inutile si le contenu n'a pas réellement changé).
    """
    issue = issue_service.move_issue(db, ctx.issue, status=data.status, position=data.position)
    background.add_task(rag_hooks.index_issue, issue.id)
    return IssueRead.model_validate(issue)


@router.patch(
    "/{key}/backlog-move",
    response_model=IssueRead,
    summary="Déplacer une issue entre backlog et sprints (EPIC-07)",
)
def backlog_move(
    data: BacklogMove,
    db: DbSession,
    background: BackgroundTasks,
    ctx: Annotated[IssueContext, Depends(require_issue_writer)],
) -> IssueRead:
    """Place l'issue dans un sprint (``sprint_id``) ou le backlog (``null``) au rang cible.

    Renormalise les positions du bucket cible et de l'ancien bucket.

    - 403 pour un viewer projet, 404 si la clé est inconnue, 422 si ``sprint_id``
      pointe un sprint d'un autre projet. ``position`` hors bornes est clampé.
    """
    try:
        issue = sprint_service.backlog_move(
            db, ctx.issue, sprint_id=data.sprint_id, position=data.position
        )
    except SprintServiceError as exc:
        raise HTTPException(
            status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=exc.message,
        ) from exc
    background.add_task(rag_hooks.index_issue, issue.id)
    return IssueRead.model_validate(issue)


@router.delete(
    "/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un ticket",
)
def delete_issue(
    db: DbSession,
    background: BackgroundTasks,
    ctx: Annotated[IssueContext, Depends(get_issue_context)],
) -> None:
    """Supprime un ticket. Réservé au reporter, au lead/admin projet ou admin global.

    Retire de l'index RAG le ticket **et ses commentaires** (points orphelins après
    la cascade) en tâche de fond ; les ids sont capturés avant la suppression.
    """
    user = ctx.current_user
    is_global_admin = user.role == UserRole.ADMIN
    is_lead = ctx.project.lead_id == user.id
    is_project_admin = ctx.membership is not None and ctx.membership.role == ProjectRole.ADMIN
    is_reporter = ctx.issue.reporter_id == user.id
    if not (is_global_admin or is_lead or is_project_admin or is_reporter):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Suppression réservée au reporter, au lead/admin projet ou à un admin global.",
        )
    issue_id = ctx.issue.id
    comment_ids = [comment.id for comment in comment_service.list_comments(db, ctx.issue)]
    issue_service.delete_issue(db, ctx.issue)
    background.add_task(rag_hooks.unindex_issue, issue_id, comment_ids)


# --------------------------------------------------------------------------- #
# Dépendances entre tickets (EPIC-08, JIR-61)
# --------------------------------------------------------------------------- #
@router.post(
    "/{key}/dependencies",
    response_model=DependencyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une dépendance depuis un ticket (EPIC-08, JIR-61)",
)
def create_dependency(
    data: DependencyCreate,
    db: DbSession,
    ctx: Annotated[IssueContext, Depends(require_issue_writer)],
) -> DependencyRead:
    """L'issue de l'URL **bloque** ``target_key``. Interdit aux viewers (403).

    - 404 si l'issue source ou la cible est inconnue ;
    - 409 en cas de doublon (ou de dépendance inverse déjà existante) ;
    - 422 pour une auto-dépendance ou une cible d'un autre projet.
    """
    try:
        dependency = dependency_service.create_dependency(db, ctx.issue, data.target_key, data.type)
    except DependencyServiceError as exc:
        raise HTTPException(
            status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=exc.message,
        ) from exc
    loaded = dependency_service.load_with_issues(db, dependency.id)
    return _serialize_dependency(loaded)


@router.delete(
    "/{key}/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une dépendance d'un ticket (EPIC-08, JIR-61)",
)
def delete_dependency(
    dependency_id: int,
    db: DbSession,
    ctx: Annotated[IssueContext, Depends(require_issue_writer)],
) -> None:
    """Supprime une dépendance rattachée à l'issue de l'URL. Interdit aux viewers (403).

    - 404 si la dépendance est inconnue ou ne touche pas cette issue.
    """
    dependency = dependency_service.get_dependency_by_id(db, dependency_id)
    if dependency is None or ctx.issue.id not in (
        dependency.from_issue_id,
        dependency.to_issue_id,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dépendance introuvable.")
    dependency_service.delete_dependency(db, dependency)
