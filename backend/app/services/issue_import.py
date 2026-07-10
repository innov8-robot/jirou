"""Import CSV de tickets dans un projet (EPIC-05).

Expose :func:`import_issues_from_csv`, réutilisable hors du contexte HTTP. La
logique est *robuste* : chaque ligne est validée indépendamment ; une ligne
invalide est ignorée et signalée dans ``errors`` sans faire échouer l'import,
les autres lignes sont créées. L'ensemble est persisté dans **une seule
transaction** (commit final) : soit tout le lot valide est créé, soit rien (en
cas d'erreur technique avant le commit).

Format attendu (en-tête obligatoire, séparateur virgule, UTF-8, noms de
colonnes insensibles à la casse) ::

    type,summary,description,priority,story_points,status,labels,assignee_email,epic_key

Rattachement à une epic (lignes non-epic), dans l'ordre :

1. ``epic_key`` correspond à une epic **existante** du projet (match sur la clé,
   insensible à la casse) ;
2. sinon ``epic_key`` correspond (insensible à la casse) au ``summary`` d'une
   ligne ``type=epic`` **plus haut** dans le même CSV (créée pendant l'import) ;
3. sinon, si ``epic_key`` est absent et que ``target_epic_id`` (choisi dans
   l'UI) est fourni → cette epic.

Une ligne ``type=epic`` ignore tout rattachement. Un ``epic_key`` fourni mais
introuvable produit un avertissement (ticket créé sans parent).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.enums import IssuePriority, IssueStatus, IssueType
from app.models.issue import Issue, Label
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.import_csv import ImportError, ImportResult
from app.schemas.issue import IssueRead
from app.services.issue import IssueServiceError, _next_key

# Nombre maximal de lignes de données acceptées (au-delà → 400).
MAX_ROWS = 1000

# Couleur par défaut des labels créés à la volée pendant l'import.
_DEFAULT_LABEL_COLOR = "#94A3B8"

# Colonnes reconnues de l'en-tête (les autres sont ignorées).
_REQUIRED_HEADER = "summary"


@dataclass
class _ParsedRow:
    """Ligne de données validée, prête à être transformée en :class:`Issue`."""

    row: int
    type: IssueType
    summary: str
    description: str | None
    priority: IssuePriority
    story_points: int | None
    status: IssueStatus
    labels: list[str]
    assignee_email: str | None
    epic_key: str | None
    warnings: list[str] = field(default_factory=list)


def _clean(value: str | None) -> str:
    """Normalise une cellule : ``None``/espaces → chaîne vide nettoyée."""
    return (value or "").strip()


def _parse_row(raw: dict[str, str], row_number: int) -> tuple[_ParsedRow | None, list[str]]:
    """Valide une ligne brute.

    Retourne ``(parsed, errors)`` : si ``errors`` est non vide, la ligne est
    rejetée (``parsed`` vaut ``None``). Les avertissements non bloquants sont
    portés par ``parsed.warnings``.
    """
    summary = _clean(raw.get("summary"))
    if not summary:
        return None, ["Ligne ignorée : le champ « summary » est obligatoire."]

    warnings: list[str] = []

    type_raw = _clean(raw.get("type")).lower()
    try:
        issue_type = IssueType(type_raw) if type_raw else IssueType.TASK
    except ValueError:
        return None, [f"Ligne ignorée : type inconnu « {type_raw} »."]

    priority_raw = _clean(raw.get("priority")).lower()
    try:
        priority = IssuePriority(priority_raw) if priority_raw else IssuePriority.MEDIUM
    except ValueError:
        return None, [f"Ligne ignorée : priorité inconnue « {priority_raw} »."]

    status_raw = _clean(raw.get("status")).lower()
    try:
        issue_status = IssueStatus(status_raw) if status_raw else IssueStatus.TODO
    except ValueError:
        return None, [f"Ligne ignorée : statut inconnu « {status_raw} »."]

    story_points: int | None = None
    points_raw = _clean(raw.get("story_points"))
    if points_raw:
        try:
            story_points = int(points_raw)
        except ValueError:
            warnings.append(
                f"story_points « {points_raw} » n'est pas un entier : valeur ignorée (null)."
            )

    labels = [part.strip() for part in _clean(raw.get("labels")).split(";") if part.strip()]
    assignee_email = _clean(raw.get("assignee_email")) or None
    epic_key = _clean(raw.get("epic_key")) or None
    description = _clean(raw.get("description")) or None

    parsed = _ParsedRow(
        row=row_number,
        type=issue_type,
        summary=summary,
        description=description,
        priority=priority,
        story_points=story_points,
        status=issue_status,
        labels=labels,
        assignee_email=assignee_email,
        epic_key=epic_key,
        warnings=warnings,
    )
    return parsed, []


def _decode_and_read(csv_bytes: bytes) -> list[list[str]]:
    """Décode les octets UTF-8 et renvoie les lignes CSV. Lève 400 si illisible."""
    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IssueServiceError("bad_csv", "Le fichier n'est pas encodé en UTF-8.") from exc
    try:
        return list(csv.reader(io.StringIO(text)))
    except csv.Error as exc:
        raise IssueServiceError("bad_csv", "CSV illisible.") from exc


def _build_member_emails(db: Session, project: Project) -> dict[str, int]:
    """Map ``email (minuscule) -> user_id`` des membres du projet (lead inclus)."""
    emails: dict[str, int] = {}
    rows = db.execute(
        select(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project.id)
    ).scalars()
    for user in rows:
        emails[user.email.lower()] = user.id
    lead = db.get(User, project.lead_id)
    if lead is not None:
        emails[lead.email.lower()] = lead.id
    return emails


def _existing_epics_by_key(db: Session, project: Project) -> dict[str, int]:
    """Map ``clé (minuscule) -> issue_id`` des epics existantes du projet."""
    rows = db.execute(
        select(Issue).where(Issue.project_id == project.id, Issue.type == IssueType.EPIC)
    ).scalars()
    return {issue.key.lower(): issue.id for issue in rows}


def _resolve_labels(
    db: Session, project: Project, names: list[str], cache: dict[str, Label]
) -> list[Label]:
    """Récupère (ou crée) les labels par nom, insensible à la casse, sans doublon."""
    resolved: list[Label] = []
    seen: set[str] = set()
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        label = cache.get(key)
        if label is None:
            label = Label(project_id=project.id, name=name, color=_DEFAULT_LABEL_COLOR)
            db.add(label)
            db.flush()
            cache[key] = label
        resolved.append(label)
    return resolved


def import_issues_from_csv(
    db: Session,
    project: Project,
    csv_bytes: bytes,
    actor: User,
    target_epic_id: int | None = None,
) -> ImportResult:
    """Importe des tickets depuis un CSV dans ``project``.

    :param target_epic_id: epic (du projet) sélectionnée dans l'UI pour rattacher
        les lignes qui ne fournissent pas leur propre ``epic_key``. Doit désigner
        une epic du projet, sinon ``IssueServiceError("validation")`` (→ 422).
    :raises IssueServiceError: ``bad_csv`` (→ 400) si le fichier est illisible,
        vide ou d'en-tête invalide, ou dépasse la limite de lignes ;
        ``validation`` (→ 422) si ``target_epic_id`` n'est pas une epic du projet.
    """
    # Validation de la cible de rattachement fournie par le formulaire.
    if target_epic_id is not None:
        target = db.get(Issue, target_epic_id)
        if target is None or target.project_id != project.id or target.type != IssueType.EPIC:
            raise IssueServiceError("validation", "epic_id doit désigner une epic de ce projet.")

    rows = _decode_and_read(csv_bytes)
    if not rows:
        raise IssueServiceError("bad_csv", "Le fichier CSV est vide.")

    header = [cell.strip().lower() for cell in rows[0]]
    if _REQUIRED_HEADER not in header:
        raise IssueServiceError(
            "bad_csv", "En-tête invalide : la colonne « summary » est obligatoire."
        )

    data_rows = rows[1:]
    if len(data_rows) > MAX_ROWS:
        raise IssueServiceError(
            "bad_csv", f"Trop de lignes ({len(data_rows)}), maximum {MAX_ROWS}."
        )

    # Validation ligne à ligne (numérotation : 1 = première ligne de données).
    parsed_rows: list[_ParsedRow] = []
    errors: list[ImportError] = []
    for offset, cells in enumerate(data_rows, start=1):
        if not any(cell.strip() for cell in cells):
            continue  # ligne entièrement vide : ignorée silencieusement
        raw = dict(zip(header, cells, strict=False))
        parsed, row_errors = _parse_row(raw, offset)
        if row_errors:
            errors.extend(ImportError(row=offset, message=msg) for msg in row_errors)
            continue
        assert parsed is not None
        parsed_rows.append(parsed)

    member_emails = _build_member_emails(db, project)
    existing_epics = _existing_epics_by_key(db, project)
    label_cache: dict[str, Label] = {
        label.name.lower(): label
        for label in db.execute(select(Label).where(Label.project_id == project.id)).scalars()
    }

    # (summary minuscule, row, issue_id) des epics créées pendant cet import.
    csv_epics: list[tuple[str, int, int]] = []
    created: list[tuple[int, int]] = []  # (row, issue_id) pour l'ordre de sortie

    def _persist(parsed: _ParsedRow, epic_id: int | None) -> Issue:
        for message in parsed.warnings:
            errors.append(ImportError(row=parsed.row, message=message))
        assignee_id: int | None = None
        if parsed.assignee_email is not None:
            assignee_id = member_emails.get(parsed.assignee_email.lower())
            if assignee_id is None:
                errors.append(
                    ImportError(
                        row=parsed.row,
                        message=(
                            f"assignee_email « {parsed.assignee_email} » n'est pas membre "
                            "du projet : ticket créé sans assigné."
                        ),
                    )
                )
        issue = Issue(
            project_id=project.id,
            key=_next_key(db, project),
            type=parsed.type,
            summary=parsed.summary,
            description=parsed.description,
            status=parsed.status,
            priority=parsed.priority,
            story_points=parsed.story_points,
            assignee_id=assignee_id,
            reporter_id=actor.id,
            epic_id=epic_id,
        )
        issue.labels = _resolve_labels(db, project, parsed.labels, label_cache)
        db.add(issue)
        db.flush()
        created.append((parsed.row, issue.id))
        return issue

    # Passe 1 : créer les epics du CSV (pour connaître leurs id/summary).
    for parsed in parsed_rows:
        if parsed.type != IssueType.EPIC:
            continue
        issue = _persist(parsed, epic_id=None)
        csv_epics.append((parsed.summary.lower(), parsed.row, issue.id))

    # Passe 2 : créer les autres lignes en résolvant leur epic parent.
    for parsed in parsed_rows:
        if parsed.type == IssueType.EPIC:
            continue
        epic_id: int | None = None
        if parsed.epic_key is not None:
            key = parsed.epic_key.lower()
            if key in existing_epics:
                epic_id = existing_epics[key]
            else:
                candidates = [
                    (epic_row, issue_id)
                    for (summary, epic_row, issue_id) in csv_epics
                    if summary == key and epic_row < parsed.row
                ]
                if candidates:
                    epic_id = max(candidates, key=lambda item: item[0])[1]
                else:
                    errors.append(
                        ImportError(
                            row=parsed.row,
                            message=(
                                f"epic_key « {parsed.epic_key} » introuvable : "
                                "ticket créé sans parent."
                            ),
                        )
                    )
        elif target_epic_id is not None:
            epic_id = target_epic_id
        _persist(parsed, epic_id=epic_id)

    db.commit()

    # Recharge les tickets créés (eager) pour la sérialisation, dans l'ordre du fichier.
    created.sort(key=lambda item: item[0])
    created_ids = [issue_id for (_row, issue_id) in created]
    issues_by_id: dict[int, Issue] = {}
    if created_ids:
        loaded = (
            db.execute(
                select(Issue)
                .where(Issue.id.in_(created_ids))
                .options(
                    selectinload(Issue.labels),
                    joinedload(Issue.assignee),
                    joinedload(Issue.reporter),
                )
            )
            .unique()
            .scalars()
        )
        issues_by_id = {issue.id: issue for issue in loaded}

    issues = [IssueRead.model_validate(issues_by_id[i]) for i in created_ids if i in issues_by_id]
    return ImportResult(
        created=len(issues),
        error_count=len(errors),
        errors=errors,
        issues=issues,
    )
