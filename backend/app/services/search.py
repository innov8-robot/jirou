"""Logique métier de la recherche globale (EPIC-10, JIR-68).

La recherche est strictement limitée aux projets dont l'appelant est membre
(sous-requête sur ``project_members``). Les tickets matchent sur leur clé
(préfixe, insensible à la casse) ou leur résumé/description ; les projets sur
leur nom ou leur clé. Chaque type de résultat est limité indépendamment.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.issue import Issue
from app.models.project import Project, ProjectMember
from app.models.user import User


@dataclass
class SearchData:
    """Résultats bruts d'une recherche, sérialisés par la couche endpoint."""

    issues: list[Issue]
    projects: list[Project]


def search(db: Session, user: User, q: str, *, limit: int = 20) -> SearchData:
    """Recherche tickets + projets dans le périmètre des projets de ``user``.

    ``q`` vide (après nettoyage) renvoie des listes vides sans requête.
    """
    query = q.strip()
    if not query:
        return SearchData(issues=[], projects=[])

    member_project_ids = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    contains = f"%{query}%"
    prefix = f"{query}%"

    issue_stmt = (
        select(Issue)
        .where(
            Issue.project_id.in_(member_project_ids),
            Issue.key.ilike(prefix)
            | Issue.summary.ilike(contains)
            | Issue.description.ilike(contains),
        )
        .order_by(Issue.updated_at.desc(), Issue.id.desc())
        .limit(limit)
    )
    issues = list(db.execute(issue_stmt).scalars().all())

    project_stmt = (
        select(Project)
        .where(
            Project.id.in_(member_project_ids),
            Project.name.ilike(contains) | Project.key.ilike(contains),
        )
        .order_by(Project.name, Project.id)
        .limit(limit)
    )
    projects = list(db.execute(project_stmt).scalars().all())

    return SearchData(issues=issues, projects=projects)
