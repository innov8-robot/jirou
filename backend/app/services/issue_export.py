"""Export CSV des tickets d'un projet (pendant de :mod:`app.services.issue_import`).

Expose :func:`export_issues_to_csv`, réutilisable hors du contexte HTTP. Le
fichier produit est **réimportable** : ses colonnes reprennent l'en-tête attendu
par l'import CSV (``type,summary,description,priority,story_points,status,
labels,assignee_email,epic_key``), enrichi de colonnes de contexte que l'import
ignore silencieusement (``key``, ``sprint``, ``reporter_email``, dates).

::

    key,type,summary,description,priority,story_points,status,labels,...
    JIR-1,epic,Authentification,Gérer les comptes,high,,todo,auth,,...
    JIR-2,story,Écran de connexion,,high,5,todo,auth;frontend,alice@ex.fr,JIR-1,...

Conventions du format, alignées sur l'import :

- séparateur virgule, une ligne d'en-tête, encodage UTF-8 **avec BOM** (Excel
  affiche alors correctement les accents ; l'import décode ``utf-8-sig``) ;
- labels multiples séparés par ``;`` ;
- ``epic_key`` porte la clé de l'epic parent — réimportée dans le *même* projet
  elle retrouve son epic ; dans un autre projet, l'import signalera la clé
  introuvable et créera le ticket sans parent ;
- dates au format ISO (``AAAA-MM-JJ`` pour les dates, ISO 8601 pour les
  horodatages), cellules vides pour les valeurs absentes.

Les filtres acceptés sont ceux de la liste des tickets (type, statut, assigné,
label, epic, sprint, recherche, tri) : l'export porte donc exactement le
sous-ensemble affiché à l'écran, sans pagination.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import IssueStatus, IssueType
from app.models.issue import Issue
from app.models.project import Project
from app.models.sprint import Sprint
from app.services import issue as issue_service

# En-tête du CSV produit. Les neuf colonnes reconnues par l'import figurent
# telles quelles ; les autres sont du contexte en lecture seule.
EXPORT_HEADER = [
    "key",
    "type",
    "summary",
    "description",
    "priority",
    "story_points",
    "status",
    "labels",
    "assignee_email",
    "epic_key",
    "sprint",
    "start_date",
    "due_date",
    "reporter_email",
    "created_at",
    "updated_at",
]


def export_filename(project: Project, now: datetime | None = None) -> str:
    """Nom de fichier proposé au téléchargement (``JIR-tickets-AAAA-MM-JJ.csv``)."""
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%d")
    return f"{project.key}-tickets-{stamp}.csv"


def _iso(value: date | datetime | None) -> str:
    """Formate une date/un horodatage en ISO, chaîne vide si absent."""
    return value.isoformat() if value is not None else ""


def _epic_keys(db: Session, project: Project) -> dict[int, str]:
    """Map ``issue_id -> clé`` des epics du projet (pour la colonne ``epic_key``)."""
    stmt = select(Issue.id, Issue.key).where(
        Issue.project_id == project.id, Issue.type == IssueType.EPIC
    )
    return dict(db.execute(stmt).all())


def _sprint_names(db: Session, project: Project) -> dict[int, str]:
    """Map ``sprint_id -> nom`` des sprints du projet (pour la colonne ``sprint``)."""
    stmt = select(Sprint.id, Sprint.name).where(Sprint.project_id == project.id)
    return dict(db.execute(stmt).all())


def _row(issue: Issue, epic_keys: dict[int, str], sprint_names: dict[int, str]) -> list[str]:
    """Sérialise un ticket en une ligne de CSV (ordre de :data:`EXPORT_HEADER`)."""
    return [
        issue.key,
        issue.type.value,
        issue.summary,
        issue.description or "",
        issue.priority.value,
        "" if issue.story_points is None else str(issue.story_points),
        issue.status.value,
        ";".join(label.name for label in issue.labels),
        issue.assignee.email if issue.assignee else "",
        epic_keys.get(issue.epic_id or 0, ""),
        sprint_names.get(issue.sprint_id or 0, ""),
        _iso(issue.start_date),
        _iso(issue.due_date),
        issue.reporter.email if issue.reporter else "",
        _iso(issue.created_at),
        _iso(issue.updated_at),
    ]


def export_issues_to_csv(
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
) -> bytes:
    """Exporte les tickets de ``project`` en CSV (octets UTF-8 avec BOM).

    Les filtres sont ceux de :func:`app.services.issue.list_issues` et l'export
    n'est **pas** paginé : tous les tickets correspondants sont écrits. Un CSV
    sans ticket ne contient que sa ligne d'en-tête (fichier valide, pas d'erreur).

    :raises IssueServiceError: ``validation`` (→ 422) si ``sort`` est inconnu.
    """
    issues = issue_service.list_issues(
        db,
        project,
        type=type,
        status=status,
        assignee_id=assignee_id,
        label_id=label_id,
        epic_id=epic_id,
        sprint_id=sprint_id,
        search=search,
        sort=sort,
        limit=None,
    )
    epic_keys = _epic_keys(db, project)
    sprint_names = _sprint_names(db, project)

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(EXPORT_HEADER)
    for issue in issues:
        writer.writerow(_row(issue, epic_keys, sprint_names))
    # BOM : Excel reconnaît alors l'UTF-8 ; l'import décode ``utf-8-sig``.
    return buffer.getvalue().encode("utf-8-sig")
