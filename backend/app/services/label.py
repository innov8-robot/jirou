"""Logique métier des labels (EPIC-05, JIR-31).

Les labels sont propres à un projet ; le nom est unique par projet (409 en cas
de conflit). Les erreurs métier passent par :class:`IssueServiceError`
(réutilisée depuis ``app.services.issue``).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.issue import Label
from app.models.project import Project
from app.schemas.issue import LabelCreate, LabelUpdate
from app.services.issue import IssueServiceError


def get_label(db: Session, label_id: int) -> Label | None:
    """Retourne le label portant cet identifiant, ou ``None``."""
    return db.get(Label, label_id)


def list_labels(db: Session, project: Project) -> list[Label]:
    """Liste les labels d'un projet, triés par nom."""
    stmt = select(Label).where(Label.project_id == project.id).order_by(Label.name, Label.id)
    return list(db.execute(stmt).scalars().all())


def _name_taken(db: Session, project_id: int, name: str, exclude_id: int | None = None) -> bool:
    stmt = select(Label.id).where(Label.project_id == project_id, Label.name == name)
    if exclude_id is not None:
        stmt = stmt.where(Label.id != exclude_id)
    return db.execute(stmt).first() is not None


def create_label(db: Session, project: Project, data: LabelCreate) -> Label:
    """Crée un label. Lève ``conflict`` si le nom est déjà pris dans le projet."""
    if _name_taken(db, project.id, data.name):
        raise IssueServiceError("conflict", "Ce nom de label est déjà utilisé dans le projet.")
    label = Label(project_id=project.id, name=data.name, color=data.color)
    db.add(label)
    db.commit()
    db.refresh(label)
    return label


def update_label(db: Session, label: Label, data: LabelUpdate) -> Label:
    """Met à jour un label (partiel). Lève ``conflict`` si le nouveau nom existe."""
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and _name_taken(db, label.project_id, changes["name"], label.id):
        raise IssueServiceError("conflict", "Ce nom de label est déjà utilisé dans le projet.")
    for field, value in changes.items():
        setattr(label, field, value)
    db.commit()
    db.refresh(label)
    return label


def delete_label(db: Session, label: Label) -> None:
    """Supprime un label (retire aussi ses liaisons issue-label via CASCADE)."""
    db.delete(label)
    db.commit()
