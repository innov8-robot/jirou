"""Logique métier des sprints, du backlog et de la vélocité (EPIC-07).

Les fonctions lèvent :class:`SprintServiceError` pour les erreurs métier ; la
couche endpoint les traduit en codes HTTP. Les autorisations (403) et
l'existence du *projet* (404) sont gérées en amont par ``app.api.deps``.

Règles clefs :

- **Un seul sprint ``active`` par projet** : :func:`start_sprint` renvoie une
  erreur ``conflict`` (409) s'il en existe déjà un.
- **Clôture** : :func:`complete_sprint` fige ``committed_points`` /
  ``completed_points`` (snapshots pour la vélocité), garde les issues ``done``
  rattachées et déplace les autres (backlog ou sprint suivant).
- **backlog-move** : place une issue dans un bucket (sprint ou backlog) à un
  index donné et renormalise les positions du/des bucket(s) touché(s), dans le
  même esprit que ``issue.move_issue``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.enums import IssueStatus, IssueType, SprintStatus
from app.models.issue import Issue, Label
from app.models.project import Project
from app.models.sprint import Sprint
from app.schemas.sprint import SprintCreate, SprintUpdate


@dataclass
class SprintServiceError(Exception):
    """Erreur métier des sprints, traduite en HTTP par la couche endpoint.

    ``code`` est une étiquette stable (``not_found``, ``conflict``,
    ``validation``, ``bad_request``) et ``message`` un texte lisible pour le
    champ ``detail``.
    """

    code: str
    message: str


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #
def get_sprint_by_id(db: Session, sprint_id: int) -> Sprint | None:
    """Retourne le sprint portant cet identifiant, ou ``None``."""
    return db.get(Sprint, sprint_id)


def count_sprint_issues(db: Session, sprint_id: int) -> int:
    """Nombre d'issues actuellement rattachées à un sprint."""
    return int(
        db.execute(
            select(func.count()).select_from(Issue).where(Issue.sprint_id == sprint_id)
        ).scalar_one()
    )


def list_sprints(db: Session, project: Project, *, include_completed: bool = False) -> list[Sprint]:
    """Sprints d'un projet, triés par ``order`` puis ``id``.

    Exclut les sprints ``completed`` sauf si ``include_completed`` est vrai.
    """
    stmt = select(Sprint).where(Sprint.project_id == project.id)
    if not include_completed:
        stmt = stmt.where(Sprint.status != SprintStatus.COMPLETED)
    stmt = stmt.order_by(Sprint.order, Sprint.id)
    return list(db.execute(stmt).scalars().all())


def get_active_sprint(db: Session, project_id: int) -> Sprint | None:
    """Retourne le sprint ``active`` du projet, ou ``None``."""
    stmt = select(Sprint).where(
        Sprint.project_id == project_id, Sprint.status == SprintStatus.ACTIVE
    )
    return db.execute(stmt).scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Écriture — sprint
# --------------------------------------------------------------------------- #
def create_sprint(db: Session, project: Project, data: SprintCreate) -> Sprint:
    """Crée un sprint ``future`` en fin de liste (``order`` = max + 1)."""
    max_order = db.execute(
        select(func.max(Sprint.order)).where(Sprint.project_id == project.id)
    ).scalar_one_or_none()
    next_order = 0.0 if max_order is None else float(max_order) + 1.0

    sprint = Sprint(
        project_id=project.id,
        name=data.name,
        goal=data.goal,
        status=SprintStatus.FUTURE,
        order=next_order,
    )
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return sprint


def update_sprint(db: Session, sprint: Sprint, data: SprintUpdate) -> Sprint:
    """Applique une mise à jour partielle (champs explicitement fournis)."""
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(sprint, field, value)
    db.commit()
    db.refresh(sprint)
    return sprint


def start_sprint(
    db: Session,
    sprint: Sprint,
    *,
    start_date: object = ...,
    end_date: object = ...,
) -> Sprint:
    """Démarre un sprint (→ ``active``).

    Lève ``conflict`` (409) s'il existe déjà un sprint ``active`` dans le projet
    (autre que celui-ci). Les dates fournies écrasent les valeurs existantes.
    """
    existing = get_active_sprint(db, sprint.project_id)
    if existing is not None and existing.id != sprint.id:
        raise SprintServiceError(
            "conflict", "Un sprint est déjà actif dans ce projet ; clôturez-le d'abord."
        )

    sprint.status = SprintStatus.ACTIVE
    if start_date is not ...:
        sprint.start_date = start_date  # type: ignore[assignment]
    if end_date is not ...:
        sprint.end_date = end_date  # type: ignore[assignment]
    db.commit()
    db.refresh(sprint)
    return sprint


def _next_future_sprint(db: Session, project_id: int, exclude_id: int) -> Sprint | None:
    """Prochain sprint ``future`` du projet (par ``order``), hors ``exclude_id``."""
    stmt = (
        select(Sprint)
        .where(
            Sprint.project_id == project_id,
            Sprint.status == SprintStatus.FUTURE,
            Sprint.id != exclude_id,
        )
        .order_by(Sprint.order, Sprint.id)
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


@dataclass
class CompleteResult:
    """Résultat interne de :func:`complete_sprint`."""

    sprint: Sprint
    committed_points: int
    completed_points: int
    done_count: int
    not_done_count: int
    moved_to: str


def complete_sprint(
    db: Session, sprint: Sprint, *, move_incomplete_to: str = "backlog"
) -> CompleteResult:
    """Clôture un sprint (→ ``completed``) et fige les snapshots de vélocité.

    - Lève ``bad_request`` (400) si le sprint n'est pas ``active``.
    - ``committed_points`` = somme des story points de toutes les issues du
      sprint ; ``completed_points`` = somme des points des issues ``done``.
    - Les issues ``done`` restent rattachées (vélocité historique) ; les autres
      partent au backlog (``move_incomplete_to="backlog"``) ou vers le prochain
      sprint ``future`` s'il existe, sinon le backlog (``"next"``).
    """
    if sprint.status != SprintStatus.ACTIVE:
        raise SprintServiceError("bad_request", "Seul un sprint actif peut être clôturé.")

    issues = list(db.execute(select(Issue).where(Issue.sprint_id == sprint.id)).scalars().all())
    done = [i for i in issues if i.status == IssueStatus.DONE]
    not_done = [i for i in issues if i.status != IssueStatus.DONE]

    committed = sum(i.story_points or 0 for i in issues)
    completed = sum(i.story_points or 0 for i in done)

    if move_incomplete_to == "next":
        target = _next_future_sprint(db, sprint.project_id, sprint.id)
        if target is not None:
            target_id: int | None = target.id
            moved_to = f"sprint:{target.id}"
        else:
            target_id = None
            moved_to = "backlog"
    else:
        target_id = None
        moved_to = "backlog"

    for issue in not_done:
        issue.sprint_id = target_id

    sprint.status = SprintStatus.COMPLETED
    sprint.completed_at = datetime.now(UTC)
    sprint.committed_points = committed
    sprint.completed_points = completed

    db.commit()
    db.refresh(sprint)
    return CompleteResult(
        sprint=sprint,
        committed_points=committed,
        completed_points=completed,
        done_count=len(done),
        not_done_count=len(not_done),
        moved_to=moved_to,
    )


def delete_sprint(db: Session, sprint: Sprint) -> None:
    """Supprime un sprint ; ses issues repassent au backlog (``sprint_id=null``).

    Le ``ON DELETE SET NULL`` de la FK gère le détachement, mais on le fait
    explicitement pour rester indépendant du dialecte et du passive_deletes.
    """
    for issue in db.execute(select(Issue).where(Issue.sprint_id == sprint.id)).scalars().all():
        issue.sprint_id = None
    db.delete(sprint)
    db.commit()


# --------------------------------------------------------------------------- #
# Backlog (JIR-49)
# --------------------------------------------------------------------------- #
def _issue_query_options(stmt: Select) -> Select:
    """Ajoute l'eager-loading standard (labels/assigné/rapporteur)."""
    return stmt.options(
        selectinload(Issue.labels),
        joinedload(Issue.assignee),
        joinedload(Issue.reporter),
    )


def _apply_issue_filters(
    stmt: Select,
    *,
    assignee_id: int | None,
    type: IssueType | None,
    label_id: int | None,
    search: str | None,
) -> Select:
    """Applique les filtres optionnels du backlog à une requête d'issues."""
    if assignee_id is not None:
        stmt = stmt.where(Issue.assignee_id == assignee_id)
    if type is not None:
        stmt = stmt.where(Issue.type == type)
    if label_id is not None:
        stmt = stmt.where(Issue.labels.any(Label.id == label_id))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Issue.key.ilike(pattern)
            | Issue.summary.ilike(pattern)
            | Issue.description.ilike(pattern)
        )
    return stmt


def _points(issues: list[Issue]) -> int:
    """Somme des story points d'une liste d'issues (null → 0)."""
    return sum(i.story_points or 0 for i in issues)


@dataclass
class BacklogData:
    """Données brutes du backlog, sérialisées par la couche endpoint."""

    backlog_issues: list[Issue]
    backlog_points: int
    sprints: list[tuple[Sprint, list[Issue], int]]


def get_backlog(
    db: Session,
    project: Project,
    *,
    assignee_id: int | None = None,
    type: IssueType | None = None,
    label_id: int | None = None,
    search: str | None = None,
) -> BacklogData:
    """Construit la vue backlog : issues sans sprint + sprints future/active.

    Filtres appliqués aux issues (backlog ET sprints). Issues triées par
    ``position`` puis ``created_at`` ; sprints triés par ``order``.
    """
    # Backlog produit : issues du projet sans sprint.
    backlog_stmt = _issue_query_options(
        select(Issue).where(Issue.project_id == project.id, Issue.sprint_id.is_(None))
    )
    backlog_stmt = _apply_issue_filters(
        backlog_stmt, assignee_id=assignee_id, type=type, label_id=label_id, search=search
    ).order_by(Issue.position, Issue.created_at, Issue.id)
    backlog_issues = list(db.execute(backlog_stmt).unique().scalars().all())

    # Sprints future + active du projet, triés par order.
    sprints = list(
        db.execute(
            select(Sprint)
            .where(
                Sprint.project_id == project.id,
                Sprint.status != SprintStatus.COMPLETED,
            )
            .order_by(Sprint.order, Sprint.id)
        )
        .scalars()
        .all()
    )

    buckets: list[tuple[Sprint, list[Issue], int]] = []
    for sprint in sprints:
        stmt = _issue_query_options(select(Issue).where(Issue.sprint_id == sprint.id))
        stmt = _apply_issue_filters(
            stmt, assignee_id=assignee_id, type=type, label_id=label_id, search=search
        ).order_by(Issue.position, Issue.created_at, Issue.id)
        issues = list(db.execute(stmt).unique().scalars().all())
        buckets.append((sprint, issues, _points(issues)))

    return BacklogData(
        backlog_issues=backlog_issues,
        backlog_points=_points(backlog_issues),
        sprints=buckets,
    )


def _bucket_issues(
    db: Session, project_id: int, sprint_id: int | None, exclude_id: int
) -> list[Issue]:
    """Issues d'un bucket (projet + sprint ou backlog), triées, hors ``exclude_id``."""
    stmt = select(Issue).where(
        Issue.project_id == project_id,
        Issue.id != exclude_id,
    )
    if sprint_id is None:
        stmt = stmt.where(Issue.sprint_id.is_(None))
    else:
        stmt = stmt.where(Issue.sprint_id == sprint_id)
    stmt = stmt.order_by(Issue.position, Issue.created_at, Issue.id)
    return list(db.execute(stmt).scalars().all())


def backlog_move(db: Session, issue: Issue, *, sprint_id: int | None, position: int) -> Issue:
    """Déplace une issue vers un sprint ou le backlog à l'index ``position``.

    Renormalise les positions (entiers ``0..n``) du bucket cible et, si le
    bucket change, de l'ancien bucket. Lève ``validation`` (422) si
    ``sprint_id`` pointe un sprint d'un autre projet ou inexistant.
    """
    if sprint_id is not None:
        target = db.get(Sprint, sprint_id)
        if target is None or target.project_id != issue.project_id:
            raise SprintServiceError(
                "validation", "Le sprint cible doit appartenir au même projet."
            )

    old_sprint_id = issue.sprint_id

    destination = _bucket_issues(db, issue.project_id, sprint_id, issue.id)
    index = max(0, min(position, len(destination)))

    issue.sprint_id = sprint_id
    destination.insert(index, issue)
    for rank, item in enumerate(destination):
        item.position = float(rank)

    if old_sprint_id != sprint_id:
        for rank, item in enumerate(_bucket_issues(db, issue.project_id, old_sprint_id, issue.id)):
            item.position = float(rank)

    db.commit()
    db.refresh(issue)
    return issue


# --------------------------------------------------------------------------- #
# Vélocité / reporting (JIR-53, JIR-54)
# --------------------------------------------------------------------------- #
def get_velocity(db: Session, project: Project) -> list[Sprint]:
    """Sprints ``completed`` du projet, triés par ``completed_at`` puis ``id``."""
    stmt = (
        select(Sprint)
        .where(Sprint.project_id == project.id, Sprint.status == SprintStatus.COMPLETED)
        .order_by(Sprint.completed_at, Sprint.id)
    )
    return list(db.execute(stmt).scalars().all())
