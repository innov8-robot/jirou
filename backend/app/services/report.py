"""Génération de rapports (statistiques + synthèse LLM), réservée à l'admin global.

Deux modes :

- **Projet** (:func:`build_project_report`) : réutilise
  :func:`app.services.stats.get_project_stats` (statuts / types / assignés,
  sprint actif, tickets récents) et la vélocité
  (:func:`app.services.sprint.get_velocity`).
- **Global** (:func:`build_global_report`) : agrège sur TOUS les projets (nombre
  de projets, total de tickets, répartition globale par statut / type, top des
  projets par volume).

Chaque *builder* renvoie ``(markdown, payload)`` où ``markdown`` est un rapport
autonome (indépendant du LLM) et ``payload`` un dictionnaire sérialisable
soumis au modèle pour la synthèse.

:func:`generate_report` assemble le tout : si ``settings.MISTRAL_API_KEY`` est
renseignée, il tente une synthèse exécutive via
:func:`app.services.rag.chat_completion` et la préfixe en section ``## Synthèse``.
En l'absence de clé **ou** en cas d'échec de l'appel, aucune erreur n'est levée :
le rapport de statistiques est renvoyé avec une note et ``llm_used=false``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import IssueStatus, IssueType
from app.models.issue import Issue
from app.models.project import Project
from app.schemas.report import ReportResult
from app.services import rag as rag_service
from app.services import sprint as sprint_service
from app.services import stats as stats_service

_SYNTHESIS_SYSTEM_PROMPT = (
    "Tu es un chef de projet. Rédige une synthèse exécutive concise en français "
    "à partir de ces statistiques : points saillants, avancement, risques, "
    "recommandations. Markdown."
)

_LLM_UNAVAILABLE_NOTE = "_Synthèse IA indisponible (MISTRAL_API_KEY non configurée)._"


# --------------------------------------------------------------------------- #
# Helpers de rendu Markdown
# --------------------------------------------------------------------------- #
def _counts_table(header: str, rows: list[tuple[str, int]]) -> str:
    """Construit un tableau Markdown ``| Libellé | Nombre |``."""
    lines = [f"| {header} | Nombre |", "|---|---|"]
    lines.extend(f"| {label} | {count} |" for label, count in rows)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Rapport d'un projet
# --------------------------------------------------------------------------- #
def build_project_report(db: Session, project: Project) -> tuple[str, dict]:
    """Construit le Markdown et le payload d'un rapport de projet."""
    data = stats_service.get_project_stats(db, project)
    velocity = sprint_service.get_velocity(db, project)

    by_status = {status.value: count for status, count in data.by_status.items()}
    by_type = {type_.value: count for type_, count in data.by_type.items()}
    by_assignee = [
        {"assignee": (user.full_name if user is not None else "Non assigné"), "count": count}
        for user, count in data.by_assignee
    ]

    active_sprint: dict | None = None
    if data.active_sprint is not None:
        s = data.active_sprint
        active_sprint = {
            "name": s.sprint.name,
            "done": s.done,
            "total": s.total,
            "points_done": s.points_done,
            "points_total": s.points_total,
        }

    velocity_payload = [
        {
            "sprint": sprint.name,
            "committed_points": sprint.committed_points,
            "completed_points": sprint.completed_points,
        }
        for sprint in velocity
    ]

    payload = {
        "type": "projet",
        "project": {"name": project.name, "key": project.key},
        "total": data.total,
        "by_status": by_status,
        "by_type": by_type,
        "by_assignee": by_assignee,
        "active_sprint": active_sprint,
        "velocity": velocity_payload,
    }

    parts = [
        f"# Rapport de projet — {project.name} ({project.key})",
        f"_Nombre total de tickets : **{data.total}**_",
        "## Répartition par statut",
        _counts_table("Statut", list(by_status.items())),
        "## Répartition par type",
        _counts_table("Type", list(by_type.items())),
        "## Répartition par assigné",
        _counts_table("Assigné", [(row["assignee"], row["count"]) for row in by_assignee])
        if by_assignee
        else "_Aucun ticket._",
    ]

    if active_sprint is not None:
        parts.append("## Sprint actif")
        parts.append(
            f"**{active_sprint['name']}** — "
            f"{active_sprint['done']}/{active_sprint['total']} tickets terminés, "
            f"{active_sprint['points_done']}/{active_sprint['points_total']} points."
        )
    else:
        parts.append("## Sprint actif")
        parts.append("_Aucun sprint actif._")

    if velocity_payload:
        parts.append("## Vélocité (sprints clôturés)")
        parts.append(
            "\n".join(
                ["| Sprint | Engagé | Terminé |", "|---|---|---|"]
                + [
                    f"| {v['sprint']} | {v['committed_points']} | {v['completed_points']} |"
                    for v in velocity_payload
                ]
            )
        )

    if data.recent:
        parts.append("## Tickets récents")
        parts.append(
            "\n".join(
                f"- `{issue.key}` — {issue.summary} (_{issue.status.value}_)"
                for issue in data.recent
            )
        )

    return "\n\n".join(parts), payload


# --------------------------------------------------------------------------- #
# Rapport global (tous les projets)
# --------------------------------------------------------------------------- #
def build_global_report(db: Session) -> tuple[str, dict]:
    """Construit le Markdown et le payload d'un rapport global (tous les projets)."""
    projects = list(db.execute(select(Project).order_by(Project.id)).scalars().all())
    project_count = len(projects)

    total = int(db.execute(select(func.count()).select_from(Issue)).scalar_one())

    by_status = dict.fromkeys((s.value for s in IssueStatus), 0)
    for status, count in db.execute(
        select(Issue.status, func.count()).group_by(Issue.status)
    ).all():
        by_status[status.value] = int(count)

    by_type = dict.fromkeys((t.value for t in IssueType), 0)
    for type_, count in db.execute(select(Issue.type, func.count()).group_by(Issue.type)).all():
        by_type[type_.value] = int(count)

    # Volume de tickets par projet (top décroissant).
    volume_rows = db.execute(
        select(Issue.project_id, func.count()).group_by(Issue.project_id)
    ).all()
    volume_by_project = {pid: int(count) for pid, count in volume_rows}
    top_projects = sorted(
        (
            {
                "name": project.name,
                "key": project.key,
                "total": volume_by_project.get(project.id, 0),
            }
            for project in projects
        ),
        key=lambda item: (-item["total"], item["key"]),
    )[:15]

    payload = {
        "type": "global",
        "project_count": project_count,
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "top_projects": top_projects,
    }

    parts = [
        "# Rapport global",
        (f"_Projets : **{project_count}** — Tickets (tous projets) : **{total}**_"),
        "## Répartition globale par statut",
        _counts_table("Statut", list(by_status.items())),
        "## Répartition globale par type",
        _counts_table("Type", list(by_type.items())),
        "## Top projets par volume de tickets",
    ]
    if top_projects:
        parts.append(
            "\n".join(
                ["| Projet | Clé | Tickets |", "|---|---|---|"]
                + [f"| {p['name']} | {p['key']} | {p['total']} |" for p in top_projects]
            )
        )
    else:
        parts.append("_Aucun projet._")

    return "\n\n".join(parts), payload


# --------------------------------------------------------------------------- #
# Assemblage + synthèse LLM
# --------------------------------------------------------------------------- #
def _synthesize(payload: dict) -> str | None:
    """Tente une synthèse LLM ; renvoie ``None`` si clé absente ou appel en échec."""
    if not settings.MISTRAL_API_KEY:
        return None
    messages = [
        {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]
    try:
        return rag_service.chat_completion(messages)
    except Exception:  # noqa: BLE001 - toute défaillance LLM => rapport sans synthèse
        return None


def generate_report(db: Session, project: Project | None) -> ReportResult:
    """Génère le rapport (projet si ``project`` fourni, sinon global).

    N'échoue jamais à cause du LLM : en l'absence de clé ou sur erreur d'appel,
    le rapport de statistiques est renvoyé avec une note et ``llm_used=false``.
    """
    if project is not None:
        base_markdown, payload = build_project_report(db, project)
        project_id: int | None = project.id
    else:
        base_markdown, payload = build_global_report(db)
        project_id = None

    synthesis = _synthesize(payload)
    if synthesis is not None:
        markdown = f"## Synthèse\n\n{synthesis}\n\n---\n\n{base_markdown}"
        llm_used = True
    else:
        markdown = f"{_LLM_UNAVAILABLE_NOTE}\n\n{base_markdown}"
        llm_used = False

    return ReportResult(
        project_id=project_id,
        generated_at=datetime.now(UTC).isoformat(),
        llm_used=llm_used,
        markdown=markdown,
    )
