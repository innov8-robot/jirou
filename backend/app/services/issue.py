"""Logique métier des tickets (EPIC-05, JIR-32 à JIR-35).

Les fonctions lèvent :class:`IssueServiceError` pour les erreurs métier
(introuvable, validation de hiérarchie/labels/assignee). La couche endpoint les
traduit en codes HTTP. Les autorisations (403) et l'existence du *projet* (404)
sont gérées en amont par les dépendances de ``app.api.deps``.

Choix documenté (JIR-35) : l'``assignee`` d'un ticket doit être **membre du
projet** (ou son lead) — sinon 422. Cela garantit la cohérence des affectations
avec la liste des membres exposée par l'UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, case, func, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.enums import IssuePriority, IssueStatus, IssueType, NotificationType
from app.models.issue import Issue, Label
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.issue import IssueCreate, IssueUpdate
from app.services import activity as activity_service
from app.services import notification as notification_service

# Champs dont la modification est tracée dans le journal d'activité (JIR-69).
_TRACKED_FIELDS = ("status", "assignee_id", "priority", "story_points", "summary", "sprint_id")


@dataclass
class IssueServiceError(Exception):
    """Erreur métier des tickets, traduite en HTTP par la couche endpoint.

    ``code`` est une étiquette stable (``not_found``, ``validation``,
    ``conflict``) et ``message`` un texte lisible pour le champ ``detail``.
    """

    code: str
    message: str


# Ordre logique des priorités pour le tri (0 = plus haute).
_PRIORITY_ORDER = {
    IssuePriority.HIGHEST: 0,
    IssuePriority.HIGH: 1,
    IssuePriority.MEDIUM: 2,
    IssuePriority.LOW: 3,
    IssuePriority.LOWEST: 4,
}

# Colonnes autorisées pour le tri (clé publique -> colonne ORM).
_SORTABLE = {
    "created_at": Issue.created_at,
    "updated_at": Issue.updated_at,
    "position": Issue.position,
    "key": Issue.key,
    "story_points": Issue.story_points,
    "summary": Issue.summary,
    "status": Issue.status,
    "priority": None,  # traité spécialement (ordre logique)
}


# --------------------------------------------------------------------------- #
# Validation interne
# --------------------------------------------------------------------------- #
def _validate_assignee(db: Session, project: Project, assignee_id: int | None) -> None:
    """Vérifie que ``assignee_id`` désigne un membre du projet (ou le lead)."""
    if assignee_id is None:
        return
    user = db.get(User, assignee_id)
    if user is None:
        raise IssueServiceError("validation", "L'assigné n'existe pas.")
    if assignee_id == project.lead_id:
        return
    membership = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == assignee_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise IssueServiceError("validation", "L'assigné doit être membre du projet.")


def _validate_epic_parent(
    db: Session, project: Project, issue_type: IssueType, epic_id: int | None
) -> None:
    """Valide le rattachement à un epic parent (JIR-35).

    - un epic ne peut pas avoir de parent ;
    - le parent doit être un epic du même projet.
    """
    if issue_type == IssueType.EPIC and epic_id is not None:
        raise IssueServiceError("validation", "Un epic ne peut pas être rattaché à un autre epic.")
    if epic_id is None:
        return
    parent = db.get(Issue, epic_id)
    if parent is None or parent.project_id != project.id:
        raise IssueServiceError("validation", "L'epic parent doit appartenir au même projet.")
    if parent.type != IssueType.EPIC:
        raise IssueServiceError("validation", "Le parent doit être une issue de type epic.")


def _resolve_labels(db: Session, project: Project, label_ids: list[int]) -> list[Label]:
    """Charge les labels demandés en vérifiant qu'ils appartiennent au projet."""
    if not label_ids:
        return []
    unique_ids = set(label_ids)
    labels = list(db.execute(select(Label).where(Label.id.in_(unique_ids))).scalars().all())
    found = {label.id for label in labels}
    missing = unique_ids - found
    if missing or any(label.project_id != project.id for label in labels):
        raise IssueServiceError(
            "validation", "Un ou plusieurs labels n'appartiennent pas au projet."
        )
    return labels


# --------------------------------------------------------------------------- #
# Génération de clé (JIR-32) — atomique
# --------------------------------------------------------------------------- #
def _next_key(db: Session, project: Project) -> str:
    """Incrémente ``issue_counter`` de façon atomique et renvoie la clé.

    ``UPDATE ... RETURNING`` verrouille la ligne du projet le temps de
    l'incrément : deux créations concurrentes obtiennent des compteurs distincts
    (pas de collision de clé).
    """
    counter = db.execute(
        update(Project)
        .where(Project.id == project.id)
        .values(issue_counter=Project.issue_counter + 1)
        .returning(Project.issue_counter)
    ).scalar_one()
    return f"{project.key}-{counter}"


# --------------------------------------------------------------------------- #
# Lecture
# --------------------------------------------------------------------------- #
def get_issue_by_key(db: Session, key: str) -> Issue | None:
    """Retourne le ticket portant cette clé, ou ``None``."""
    return db.execute(select(Issue).where(Issue.key == key)).scalar_one_or_none()


def get_children(db: Session, epic: Issue) -> list[Issue]:
    """Retourne les issues rattachées à cet epic (triées par position puis clé)."""
    stmt = (
        select(Issue)
        .where(Issue.epic_id == epic.id)
        .options(
            selectinload(Issue.labels),
            joinedload(Issue.assignee),
            joinedload(Issue.reporter),
        )
        .order_by(Issue.position, Issue.id)
    )
    return list(db.execute(stmt).scalars().all())


def get_progress(db: Session, epic: Issue) -> tuple[int, int]:
    """Retourne ``(done, total)`` des enfants d'un epic."""
    total = int(
        db.execute(
            select(func.count()).select_from(Issue).where(Issue.epic_id == epic.id)
        ).scalar_one()
    )
    done = int(
        db.execute(
            select(func.count())
            .select_from(Issue)
            .where(Issue.epic_id == epic.id, Issue.status == IssueStatus.DONE)
        ).scalar_one()
    )
    return done, total


def _apply_sort(stmt: Select, sort: str | None) -> Select:
    """Applique un tri ``sort`` (ex. ``-created_at``, ``position``, ``priority``)."""
    if not sort:
        return stmt.order_by(Issue.position, Issue.id)
    descending = sort.startswith("-")
    field = sort[1:] if descending else sort
    if field not in _SORTABLE:
        raise IssueServiceError("validation", f"Tri non supporté : {field!r}.")
    if field == "priority":
        column = case(_PRIORITY_ORDER, value=Issue.priority)
    else:
        column = _SORTABLE[field]
    return stmt.order_by(column.desc() if descending else column.asc(), Issue.id)


def list_issues(
    db: Session,
    project: Project,
    *,
    type: IssueType | None = None,
    status: IssueStatus | None = None,
    assignee_id: int | None = None,
    label_id: int | None = None,
    epic_id: int | None = None,
    sprint_id: int | None = None,
    search: str | None = None,
    sort: str | None = None,
    skip: int = 0,
    limit: int | None = 50,
) -> list[Issue]:
    """Liste filtrée/triée/paginée des tickets d'un projet (JIR-33).

    ``limit=None`` retire la pagination et renvoie tous les tickets filtrés —
    utilisé par l'export CSV, qui doit porter le lot complet et non une page.

    Requête optimisée : labels préchargés (``selectinload``), assigné et
    rapporteur joints (``joinedload``) — pas de N+1.
    """
    stmt = (
        select(Issue)
        .where(Issue.project_id == project.id)
        .options(
            selectinload(Issue.labels),
            joinedload(Issue.assignee),
            joinedload(Issue.reporter),
        )
    )
    if type is not None:
        stmt = stmt.where(Issue.type == type)
    if status is not None:
        stmt = stmt.where(Issue.status == status)
    if assignee_id is not None:
        stmt = stmt.where(Issue.assignee_id == assignee_id)
    if epic_id is not None:
        stmt = stmt.where(Issue.epic_id == epic_id)
    if sprint_id is not None:
        stmt = stmt.where(Issue.sprint_id == sprint_id)
    if label_id is not None:
        stmt = stmt.where(Issue.labels.any(Label.id == label_id))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Issue.key.ilike(pattern)
            | Issue.summary.ilike(pattern)
            | Issue.description.ilike(pattern)
        )

    stmt = _apply_sort(stmt, sort)
    stmt = stmt.offset(skip)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).unique().scalars().all())


def list_assigned_to_user(db: Session, user: User) -> list[Issue]:
    """Issues assignées à ``user`` dans tous les projets où il est membre (JIR-72).

    Triées par ``updated_at`` décroissant. Requête eager-loadée (pas de N+1).
    """
    member_project_ids = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    stmt = (
        select(Issue)
        .where(
            Issue.assignee_id == user.id,
            Issue.project_id.in_(member_project_ids),
        )
        .options(
            selectinload(Issue.labels),
            joinedload(Issue.assignee),
            joinedload(Issue.reporter),
        )
        .order_by(Issue.updated_at.desc(), Issue.id.desc())
    )
    return list(db.execute(stmt).unique().scalars().all())


# --------------------------------------------------------------------------- #
# Board Kanban (EPIC-06, JIR-40)
# --------------------------------------------------------------------------- #
# Ordre figé des colonnes du board (contrat front/back).
BOARD_STATUS_ORDER: tuple[IssueStatus, ...] = (
    IssueStatus.TODO,
    IssueStatus.IN_PROGRESS,
    IssueStatus.IN_REVIEW,
    IssueStatus.DONE,
)


def get_board(
    db: Session,
    project: Project,
    *,
    assignee_id: int | None = None,
    type: IssueType | None = None,
    label_id: int | None = None,
    epic_id: int | None = None,
    sprint_id: int | None = None,
    search: str | None = None,
) -> dict[IssueStatus, list[Issue]]:
    """Tickets d'un projet groupés par statut, triés par ``position`` puis ``created_at``.

    Renvoie un dict dont les 4 clés de statut sont toujours présentes (listes
    éventuellement vides). Filtres optionnels cumulables. Requête eager-loadée
    (labels/assigné/rapporteur) pour éviter les N+1.
    """
    stmt = (
        select(Issue)
        .where(Issue.project_id == project.id)
        .options(
            selectinload(Issue.labels),
            joinedload(Issue.assignee),
            joinedload(Issue.reporter),
        )
        .order_by(Issue.position, Issue.created_at, Issue.id)
    )
    if assignee_id is not None:
        stmt = stmt.where(Issue.assignee_id == assignee_id)
    if type is not None:
        stmt = stmt.where(Issue.type == type)
    if epic_id is not None:
        stmt = stmt.where(Issue.epic_id == epic_id)
    if sprint_id is not None:
        stmt = stmt.where(Issue.sprint_id == sprint_id)
    if label_id is not None:
        stmt = stmt.where(Issue.labels.any(Label.id == label_id))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Issue.key.ilike(pattern)
            | Issue.summary.ilike(pattern)
            | Issue.description.ilike(pattern)
        )

    grouped: dict[IssueStatus, list[Issue]] = {s: [] for s in BOARD_STATUS_ORDER}
    for issue in db.execute(stmt).unique().scalars().all():
        grouped[issue.status].append(issue)
    return grouped


def _column_issues(
    db: Session, project_id: int, status: IssueStatus, exclude_id: int
) -> list[Issue]:
    """Issues d'une colonne (projet + statut), triées, en excluant ``exclude_id``."""
    stmt = (
        select(Issue)
        .where(
            Issue.project_id == project_id,
            Issue.status == status,
            Issue.id != exclude_id,
        )
        .order_by(Issue.position, Issue.created_at, Issue.id)
    )
    return list(db.execute(stmt).scalars().all())


def move_issue(db: Session, issue: Issue, *, status: IssueStatus, position: int) -> Issue:
    """Déplace/réordonne une issue dans le board (JIR-40), de façon transactionnelle.

    Place ``issue`` au statut ``status`` et à l'index ``position`` (0-based,
    clampé dans ``[0, len(colonne)]``) parmi les issues de ce statut dans le même
    projet, puis **renormalise** les positions de la colonne de destination (et
    de l'ancienne colonne si le statut change) en entiers séquentiels ``0,1,2,…``
    afin d'éviter la dérive de précision. Un seul commit.
    """
    old_status = issue.status

    destination = _column_issues(db, issue.project_id, status, issue.id)
    index = max(0, min(position, len(destination)))

    issue.status = status
    destination.insert(index, issue)
    for rank, item in enumerate(destination):
        item.position = float(rank)

    if old_status != status:
        for rank, item in enumerate(_column_issues(db, issue.project_id, old_status, issue.id)):
            item.position = float(rank)

    db.commit()
    db.refresh(issue)
    return issue


# --------------------------------------------------------------------------- #
# Écriture
# --------------------------------------------------------------------------- #
def create_issue(db: Session, project: Project, data: IssueCreate, reporter: User) -> Issue:
    """Crée un ticket : clé auto-générée, reporter = utilisateur courant.

    Valide l'assigné, l'epic parent et les labels avant persistance.
    """
    _validate_assignee(db, project, data.assignee_id)
    _validate_epic_parent(db, project, data.type, data.epic_id)
    labels = _resolve_labels(db, project, data.label_ids)

    key = _next_key(db, project)
    issue = Issue(
        project_id=project.id,
        key=key,
        type=data.type,
        summary=data.summary,
        description=data.description,
        priority=data.priority,
        story_points=data.story_points,
        assignee_id=data.assignee_id,
        reporter_id=reporter.id,
        epic_id=data.epic_id,
        start_date=data.start_date,
        due_date=data.due_date,
    )
    issue.labels = labels
    db.add(issue)
    db.flush()  # attribue issue.id avant de journaliser l'activité
    activity_service.log(
        db,
        issue_id=issue.id,
        project_id=issue.project_id,
        action="created",
        actor_id=reporter.id,
    )
    db.commit()
    db.refresh(issue)
    return issue


def update_issue(db: Session, issue: Issue, data: IssueUpdate, actor: User | None = None) -> Issue:
    """Applique une mise à jour partielle (champs explicitement fournis).

    Effet de bord (EPIC-09, JIR-67) : si ``assignee_id`` change vers un
    utilisateur non nul distinct de ``actor``, une notification ``assignment``
    est créée pour le nouvel assigné, dans le même commit que la mise à jour.
    """
    changes = data.model_dump(exclude_unset=True)
    project = db.get(Project, issue.project_id)
    old_assignee_id = issue.assignee_id
    # Snapshot des champs tracés avant application (pour le journal d'activité).
    old_tracked = {field: getattr(issue, field) for field in _TRACKED_FIELDS}

    # Type et epic_id peuvent changer ensemble : on valide sur les valeurs cibles.
    new_type = changes.get("type", issue.type)
    if "epic_id" in changes or "type" in changes:
        new_epic_id = changes.get("epic_id", issue.epic_id)
        _validate_epic_parent(db, project, new_type, new_epic_id)
    if "assignee_id" in changes:
        _validate_assignee(db, project, changes["assignee_id"])
    if "label_ids" in changes:
        issue.labels = _resolve_labels(db, project, changes.pop("label_ids") or [])

    for field, value in changes.items():
        setattr(issue, field, value)

    # Journal d'activité (JIR-69) : une entrée par champ tracé réellement modifié.
    actor_id = actor.id if actor is not None else None
    for field in _TRACKED_FIELDS:
        if field not in changes:
            continue
        new_val = getattr(issue, field)
        if new_val == old_tracked[field]:
            continue
        activity_service.log(
            db,
            issue_id=issue.id,
            project_id=issue.project_id,
            action="updated",
            actor_id=actor_id,
            field=field,
            old_value=activity_service.stringify(old_tracked[field]),
            new_value=activity_service.stringify(new_val),
        )

    # Notification d'assignation : nouvel assigné réel, différent de l'acteur.
    new_assignee_id = issue.assignee_id
    if (
        "assignee_id" in changes
        and new_assignee_id is not None
        and new_assignee_id != old_assignee_id
        and (actor is None or new_assignee_id != actor.id)
    ):
        actor_name = actor.full_name if actor is not None else "Quelqu'un"
        notification_service.notify(
            db,
            user_id=new_assignee_id,
            type=NotificationType.ASSIGNMENT,
            actor_id=actor.id if actor is not None else None,
            issue_id=issue.id,
            message=f"{actor_name} vous a assigné {issue.key}",
        )

    db.commit()
    db.refresh(issue)
    return issue


def delete_issue(db: Session, issue: Issue) -> None:
    """Supprime définitivement un ticket."""
    db.delete(issue)
    db.commit()
