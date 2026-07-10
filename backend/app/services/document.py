"""Logique métier de la documentation de projet (pages Markdown).

CRUD de pages de documentation rattachées à un projet. Le ``content`` est
stocké tel quel (Markdown brut) : aucun rendu côté serveur. Les autorisations
(403) et l'existence du projet (404) sont gérées en amont par la couche
endpoint / les dépendances de ``app.api.deps``.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.document import DocumentCreate, DocumentUpdate


def get_document(db: Session, document_id: int) -> Document | None:
    """Retourne le document portant cet identifiant, ou ``None``."""
    return db.get(Document, document_id)


def list_documents(db: Session, project_id: int) -> list[Document]:
    """Documents d'un projet, triés par date de mise à jour décroissante."""
    stmt = (
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.updated_at.desc(), Document.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def list_all_for_user(db: Session, user: User) -> list[Document]:
    """Documents visibles par ``user``, triés par mise à jour décroissante.

    Inclut : les documents **généraux** (``project_id`` NULL) et ceux des projets
    dont ``user`` est membre. Exclut les documents des projets où il n'est pas
    membre.
    """
    member_projects = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    stmt = (
        select(Document)
        .where(
            or_(
                Document.project_id.is_(None),
                Document.project_id.in_(member_projects),
            )
        )
        .order_by(Document.updated_at.desc(), Document.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def create_document(db: Session, project: Project, author: User, data: DocumentCreate) -> Document:
    """Crée une page de documentation attribuée à ``author``."""
    document = Document(
        project_id=project.id,
        author_id=author.id,
        title=data.title,
        content=data.content,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def create_general(db: Session, author: User, data: DocumentCreate) -> Document:
    """Crée un document **général** (non rattaché à un projet), attribué à ``author``."""
    document = Document(
        project_id=None,
        author_id=author.id,
        title=data.title,
        content=data.content,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def update_document(db: Session, document: Document, data: DocumentUpdate) -> Document:
    """Applique une mise à jour partielle (champs explicitement fournis)."""
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(document, field, value)
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document: Document) -> None:
    """Supprime définitivement un document."""
    db.delete(document)
    db.commit()
