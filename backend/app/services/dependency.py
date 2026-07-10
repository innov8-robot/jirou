"""Logique métier des dépendances entre tickets (EPIC-08, JIR-61).

Une dépendance oriente un blocage : l'issue ``from`` **bloque** l'issue ``to``.
Les fonctions lèvent :class:`DependencyServiceError` pour les erreurs métier ; la
couche endpoint les traduit en codes HTTP. Les autorisations (403) et
l'existence de l'issue source (404) sont gérées en amont par ``app.api.deps``.

Règles :

- ``target_key`` doit exister (sinon ``not_found``/404) et appartenir au **même
  projet** que la source (sinon ``validation``/422) ;
- pas d'auto-dépendance : ``from == to`` → ``validation``/422 ;
- pas de doublon ``(from, to, type)`` → ``conflict``/409 ;
- détection de cycle directe : si la dépendance inverse existe déjà (``to``
  bloque déjà ``from`` pour ce type), on refuse (``conflict``/409).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.dependency import IssueDependency
from app.models.enums import DependencyType
from app.models.issue import Issue


@dataclass
class DependencyServiceError(Exception):
    """Erreur métier des dépendances, traduite en HTTP par la couche endpoint.

    ``code`` est une étiquette stable (``not_found``, ``conflict``,
    ``validation``) et ``message`` un texte lisible pour le champ ``detail``.
    """

    code: str
    message: str


def get_dependency_by_id(db: Session, dependency_id: int) -> IssueDependency | None:
    """Retourne la dépendance portant cet identifiant, ou ``None``."""
    return db.get(IssueDependency, dependency_id)


def create_dependency(
    db: Session,
    from_issue: Issue,
    target_key: str,
    dep_type: DependencyType,
) -> IssueDependency:
    """Crée une dépendance ``from_issue`` bloque ``target_key`` (JIR-61)."""
    target = db.execute(select(Issue).where(Issue.key == target_key)).scalar_one_or_none()
    if target is None:
        raise DependencyServiceError("not_found", "Le ticket cible est introuvable.")
    if target.id == from_issue.id:
        raise DependencyServiceError("validation", "Un ticket ne peut pas dépendre de lui-même.")
    if target.project_id != from_issue.project_id:
        raise DependencyServiceError(
            "validation", "Le ticket cible doit appartenir au même projet."
        )

    existing = db.execute(
        select(IssueDependency).where(
            IssueDependency.from_issue_id == from_issue.id,
            IssueDependency.to_issue_id == target.id,
            IssueDependency.type == dep_type,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise DependencyServiceError("conflict", "Cette dépendance existe déjà.")

    # Détection de cycle directe (A↔B) : refuser la dépendance inverse.
    inverse = db.execute(
        select(IssueDependency).where(
            IssueDependency.from_issue_id == target.id,
            IssueDependency.to_issue_id == from_issue.id,
            IssueDependency.type == dep_type,
        )
    ).scalar_one_or_none()
    if inverse is not None:
        raise DependencyServiceError("conflict", "La dépendance inverse existe déjà (cycle).")

    dependency = IssueDependency(
        from_issue_id=from_issue.id,
        to_issue_id=target.id,
        type=dep_type,
    )
    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return dependency


def delete_dependency(db: Session, dependency: IssueDependency) -> None:
    """Supprime définitivement une dépendance."""
    db.delete(dependency)
    db.commit()


def load_with_issues(db: Session, dependency_id: int) -> IssueDependency | None:
    """Charge une dépendance avec ses deux issues (pour la sérialisation)."""
    return db.execute(
        select(IssueDependency)
        .where(IssueDependency.id == dependency_id)
        .options(
            joinedload(IssueDependency.from_issue),
            joinedload(IssueDependency.to_issue),
        )
    ).scalar_one_or_none()


def list_links_for_issue(db: Session, issue: Issue) -> list[IssueDependency]:
    """Toutes les dépendances touchant ``issue`` (source ou cible), issues chargées.

    Le sens (``outward``/``inward``) est déterminé à la sérialisation selon que
    ``issue`` est la source ou la cible de chaque dépendance.
    """
    stmt = (
        select(IssueDependency)
        .where(
            or_(
                IssueDependency.from_issue_id == issue.id,
                IssueDependency.to_issue_id == issue.id,
            )
        )
        .options(
            joinedload(IssueDependency.from_issue),
            joinedload(IssueDependency.to_issue),
        )
        .order_by(IssueDependency.id)
    )
    return list(db.execute(stmt).scalars().all())
